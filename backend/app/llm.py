"""Model access. The rest of the backend talks to one tiny interface, `client.messages.create(...)`, in the shape of the Anthropic
Messages API (system prompt, tools, forced tool choice, image blocks, tool results). Behind it:

  anthropic  - the official SDK (Claude). Set REFORM3D_LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY.
  openai     - any server that speaks the OpenAI chat-completions protocol with tool calling: Google Gemini's compatibility endpoint,
               OpenRouter, Groq, Cerebras, Together, Mistral, or a model you host yourself with vLLM, llama.cpp or Ollama.
               Set REFORM3D_LLM_PROVIDER=openai, REFORM3D_LLM_BASE_URL, REFORM3D_LLM_MODEL and (if the server needs one) REFORM3D_LLM_API_KEY.
  pool       - REFORM3D_LLM_POOL lists several models. Calls go to the first one that is healthy; when it runs out of quota or fails, the call
               moves to the next, and the failed one rests for a while. The designer can also run several of them at once (app/designer.py).

Swapping models, including a model you fine-tuned, never touches the planner or the designer."""
from __future__ import annotations
import json
import logging
import re
import threading
import time
from types import SimpleNamespace
from typing import Any

from .config import PoolMember, Settings

log = logging.getLogger("reform3d.llm")


class LLMError(RuntimeError):
    """The model call failed in a way the caller should treat as 'the model is unavailable'.
    `status` is the HTTP status when there was one; `retry_after` is the provider's own suggestion in seconds."""

    def __init__(self, message: str, status: int | None = None, retry_after: float | None = None):
        super().__init__(message)
        self.status, self.retry_after = status, retry_after


def _build_client(m: PoolMember, timeout: float, pooled: bool) -> Any:
    if m.kind == "openai":
        # In a pool, overload (503) or a long Retry-After means "try another model now": fail fast instead of sleeping and retrying here.
        return OpenAICompatClient(m.base_url, m.api_key, timeout, retries=1 if pooled else 3, max_wait=5.0 if pooled else 20.0)
    import anthropic
    return anthropic.Anthropic(api_key=m.api_key, timeout=timeout, max_retries=0 if pooled else 2)


def make_client(settings: Settings) -> Any | None:
    """Return a client for the configured model(s), or None when nothing is configured."""
    if not settings.enable_llm or not settings.llm_configured:
        return None
    if settings.uses_pool:
        return PoolClient(settings.models(), timeout=settings.timeout_for_llm)
    if settings.llm_provider == "openai":
        return OpenAICompatClient(settings.llm_base_url, settings.llm_api_key, settings.timeout_for_llm)
    import anthropic
    return anthropic.Anthropic(api_key=settings.llm_api_key, timeout=settings.timeout_for_llm, max_retries=2)


def candidate_clients(settings: Settings, count: int) -> list["PoolClient"]:
    """Up to `count` clients, each pinned to a different ready model, for running one design on several models at once."""
    if not settings.enable_llm or not settings.uses_pool:
        return []
    members = settings.models()
    ready = [m for m in members if BOOK.ready(m.label)] or members
    return [PoolClient([m], timeout=settings.timeout_for_llm) for m in ready[:max(1, count)]]


def pool_status(settings: Settings) -> dict:
    """What /health shows: which models are in play and how many seconds each still rests. Never includes a key."""
    return {"models": [m.label for m in settings.models()], "resting": BOOK.snapshot()}


def model_label(client: Any, settings: Settings) -> list[str]:
    used = getattr(client, "used", None)
    return list(used) if used else [settings.llm_model or "model"]


# ------------------------------------------------------------------------------------ OpenAI-compatible adapter
def _get(obj: Any, key: str, default=None):
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


def _simplify_schema(node: Any) -> Any:
    """Strip JSON-Schema features several providers reject (type unions, additionalProperties, numeric bounds)."""
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k in ("additionalProperties", "minimum", "maximum", "default", "examples"):
                continue
            if k == "type" and isinstance(v, list):
                v = next((t for t in v if t != "null"), "string")
            out[k] = _simplify_schema(v)
        return out
    if isinstance(node, list):
        return [_simplify_schema(x) for x in node]
    return node


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(_get(b, "text", "") for b in content if _get(b, "type") == "text")


def _user_parts(blocks: list) -> list[dict]:
    parts: list[dict] = []
    for b in blocks:
        t = _get(b, "type")
        if t == "text":
            parts.append({"type": "text", "text": _get(b, "text", "")})
        elif t == "image":
            src = _get(b, "source", {})
            parts.append({"type": "image_url", "image_url": {"url": f"data:{_get(src, 'media_type')};base64,{_get(src, 'data')}"}})
    return parts


def to_openai_messages(system: str, messages: list[dict]) -> list[dict]:
    out: list[dict] = [{"role": "system", "content": system}] if system else []
    for m in messages:
        role, content = m["role"], m["content"]
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue
        if role == "assistant":
            text = "\n".join(_get(b, "text", "") for b in content if _get(b, "type") == "text").strip()
            calls = []
            for b in content:
                if _get(b, "type") != "tool_use":
                    continue
                call = {"id": _get(b, "id"), "type": "function", "function": {"name": _get(b, "name"), "arguments": json.dumps(_get(b, "input", {}))}}
                if _get(b, "extra_content"):                    # Gemini's thought signature: must be sent back unchanged with the call
                    call["extra_content"] = _get(b, "extra_content")
                calls.append(call)
            msg: dict = {"role": "assistant", "content": text or None}
            if calls:
                msg["tool_calls"] = calls
            out.append(msg)
            continue
        results = [b for b in content if _get(b, "type") == "tool_result"]
        extra_images: list[dict] = []
        for b in results:                                       # tool results carry text; any pictures follow as a user message
            inner = _get(b, "content", "")
            if not isinstance(inner, str):
                extra_images += _user_parts([x for x in inner if _get(x, "type") == "image"])
            prefix = "ERROR: " if _get(b, "is_error") else ""
            out.append({"role": "tool", "tool_call_id": _get(b, "tool_use_id"), "content": prefix + (_text_of(inner) or "(no text)")})
        rest = _user_parts([b for b in content if _get(b, "type") != "tool_result"]) + extra_images
        if rest:
            out.append({"role": "user", "content": rest})
    return out


def _json_in_text(text: str) -> dict | None:
    """Weaker models sometimes answer with the tool arguments as plain JSON text instead of a tool call."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, dict) else None
    except ValueError:
        return None


class _Messages:
    def __init__(self, outer: "OpenAICompatClient"):
        self.outer = outer

    def create(self, *, model: str, max_tokens: int, system: str = "", messages: list, tools: list | None = None, tool_choice: dict | None = None, **_: Any):
        o = self.outer
        body: dict = {"model": model, "max_tokens": max_tokens, "messages": to_openai_messages(system, messages)}
        if tools:
            body["tools"] = [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""),
                                                               "parameters": _simplify_schema(t["input_schema"])}} for t in tools]
            tc = (tool_choice or {}).get("type", "auto")
            if tc == "tool":
                body["tool_choice"] = {"type": "function", "function": {"name": tool_choice["name"]}}
            elif tc == "any":
                body["tool_choice"] = "required"
            else:
                body["tool_choice"] = "auto"
        try:
            try:
                data = o._post(body)
            except LLMError as e:
                # Groq counts the requested max_tokens against a tokens-per-minute cap: shrink the answer budget to fit and ask once more
                m = re.search(r"Limit (\d+), Requested (\d+)", str(e))
                if e.status != 413 or not m:
                    raise
                smaller = body["max_tokens"] - (int(m.group(2)) - int(m.group(1))) - 200
                if smaller < 3500:                                  # too little room left for CAD code plus the model's own thinking: let the pool try another model
                    raise
                body = {**body, "max_tokens": smaller}
                data = o._post(body)
        except LLMError as e:
            # Some servers (Gemma on Google's endpoint) fail with a 500 on forced tool calls with nested schemas but work with "auto";
            # the design loop already asks again if the model answers without a tool call.
            if e.status != 500 or body.get("tool_choice") in (None, "auto"):
                raise
            data = o._post({**body, "tool_choice": "auto"})
        try:
            msg = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError):
            raise LLMError(f"unexpected reply from the model server: {str(data)[:300]}")
        blocks: list = []
        if msg.get("content"):
            blocks.append(SimpleNamespace(type="text", text=msg["content"]))
        for i, call in enumerate(msg.get("tool_calls") or []):
            fn = call.get("function", {})
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                args = _json_in_text(fn.get("arguments") or "") or {}
                if not args and data["choices"][0].get("finish_reason") == "length":
                    args = {"_truncated": True}                      # the answer hit the token limit in the middle of the code
            block = SimpleNamespace(type="tool_use", id=call.get("id") or f"call_{i}", name=fn.get("name", ""), input=args)
            if call.get("extra_content"):
                block.extra_content = call["extra_content"]
            blocks.append(block)
        if tools and not any(b.type == "tool_use" for b in blocks) and msg.get("content"):
            args = _json_in_text(msg["content"])
            if args:
                names = [t["name"] for t in tools]
                name = (tool_choice or {}).get("name") or (names[0] if len(names) == 1 else None)
                if name:
                    blocks.append(SimpleNamespace(type="tool_use", id="call_text", name=name, input=args))
        return SimpleNamespace(content=blocks, stop_reason=data["choices"][0].get("finish_reason"))


class OpenAICompatClient:
    """Minimal OpenAI chat-completions client that answers in Anthropic-Messages shape. Uses httpx directly, no extra SDK."""

    def __init__(self, base_url: str, api_key: str = "", timeout: float = 120.0, retries: int = 3, max_wait: float = 20.0):
        self.base_url, self.api_key, self.timeout, self.retries, self.max_wait = base_url.rstrip("/"), api_key, timeout, retries, max_wait
        self.messages = _Messages(self)

    def _post(self, body: dict) -> dict:
        import httpx
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        last, status, hint = "no attempt", None, None
        for attempt in range(self.retries):
            try:
                r = self._send(body, headers)
            except _TooSlow:
                last, status, hint = f"the model took longer than {self.timeout:.0f} seconds", None, None
                break                                           # a slow model will be slow again: let the caller move on
            except httpx.HTTPError as e:
                last, status, hint = f"could not reach the model server ({e.__class__.__name__})", None, None
                time.sleep(1.5 * (attempt + 1))
                continue
            if r.status_code == 200:
                try:
                    return r.json()
                except ValueError:
                    raise LLMError("the model server returned something that is not JSON")
            detail = r.text[:300].replace("\n", " ")
            last, status, hint = f"model server error {r.status_code}: {detail}", r.status_code, _retry_after(r.headers, r.text)
            if r.status_code in (429, 500, 502, 503, 504):
                wait = hint if hint is not None else 2.0 * (attempt + 1)
                if wait > self.max_wait:                        # a long wait means the quota is used up: report it instead of sleeping through it
                    break
                time.sleep(wait)
                continue
            break                                               # 400/401/403/404: retrying will not help
        raise LLMError(last, status=status, retry_after=hint)


    def _send(self, body: dict, headers: dict):
        """POST with a hard wall-clock limit. Some gateways keep a slow request alive by sending blank keep-alive bytes, so a plain read
        timeout never fires; reading the body as a stream lets us stop at the deadline."""
        import httpx
        deadline = time.monotonic() + self.timeout
        with httpx.stream("POST", self.base_url + "/chat/completions", json=body, headers=headers,
                          timeout=httpx.Timeout(self.timeout, connect=min(20.0, self.timeout))) as r:
            chunks = []
            for chunk in r.iter_bytes():
                chunks.append(chunk)
                if time.monotonic() > deadline:
                    raise _TooSlow()
            # iter_bytes() already undid any gzip, so drop the encoding headers or httpx would try to decode the body again
            plain = {k: v for k, v in r.headers.items() if k.lower() not in ("content-encoding", "content-length", "transfer-encoding")}
            return httpx.Response(r.status_code, headers=plain, content=b"".join(chunks))


class _TooSlow(Exception):
    pass


def _retry_after(headers: Any, text: str = "") -> float | None:
    """Seconds to wait: the Retry-After header, or Google's "retryDelay": "17s" in the error body. The HTTP-date form is ignored."""
    try:
        return max(0.0, float(headers.get("retry-after")))
    except (TypeError, ValueError):
        m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', text or "")
        return float(m.group(1)) if m else None


# ------------------------------------------------------------------------------------ a pool of models
class CooldownBook:
    """Remembers which models are resting after a failure, shared by every job in this process. Each failure in a row rests the model longer
    (a quota that is used up for the day should not be retried every minute); one success clears the record."""

    def __init__(self, clock=time.monotonic):
        self._clock, self._until, self._strikes, self._lock = clock, {}, {}, threading.Lock()

    def ready(self, label: str) -> bool:
        return self.remaining(label) <= 0

    def remaining(self, label: str) -> float:
        with self._lock:
            return max(0.0, self._until.get(label, 0.0) - self._clock())

    def penalise(self, label: str, base: float, retry_after: float | None = None) -> float:
        with self._lock:
            strikes = self._strikes.get(label, 0) + 1
            self._strikes[label] = strikes
            # the provider's own hint is the best guide (a per-minute limit says "17s"); otherwise rest longer after each failure in a row
            # (a daily quota says "48000s", which is trusted up to a day)
            rest = min(86400.0, max(1.0, retry_after)) if retry_after is not None else min(3600.0, base * (3 ** (strikes - 1)))
            self._until[label] = self._clock() + rest
            return rest

    def success(self, label: str) -> None:
        with self._lock:
            self._strikes.pop(label, None)
            self._until.pop(label, None)

    def snapshot(self) -> dict[str, int]:
        now = self._clock()
        with self._lock:
            return {k: round(v - now) for k, v in self._until.items() if v - now > 0}

    def reset(self) -> None:
        with self._lock:
            self._until.clear()
            self._strikes.clear()


BOOK = CooldownBook()


def _rest_for(status: int | None) -> float:
    """First rest in seconds, by the kind of failure: quota or rate limit, bad key or model name, a rejected request, or a server hiccup."""
    if status == 429:
        return 60.0
    if status in (401, 403, 404):
        return 600.0
    if status is not None and 400 <= status < 500:
        return 30.0
    return 20.0


def _error_facts(e: Exception) -> tuple[int | None, float | None]:
    """HTTP status and Retry-After from our own errors or from the Anthropic SDK's."""
    status = getattr(e, "status", None) or getattr(e, "status_code", None)
    hint = getattr(e, "retry_after", None)
    if hint is None:
        hint = _retry_after(getattr(getattr(e, "response", None), "headers", None) or {})
    return (status if isinstance(status, int) else None), hint


_NO_PICTURE = "[a picture was attached here, but this model cannot see pictures]"


def _has_image(messages: list[dict]) -> bool:
    def walk(c: Any) -> bool:
        if isinstance(c, list):
            return any(walk(b) for b in c)
        return _get(c, "type") == "image" or (_get(c, "type") == "tool_result" and walk(_get(c, "content")))
    return any(walk(m["content"]) for m in messages if not isinstance(m["content"], str))


def _needs_flat(member: PoolMember, messages: list[dict]) -> bool:
    """Gemini's thinking models refuse tool calls in the history that carry no thought signature, which happens when another model made
    them. For those, the earlier calls and results are re-sent as plain text instead."""
    if member.provider.split(":")[0] != "gemini":
        return False
    for m in messages:
        if m["role"] == "assistant" and isinstance(m["content"], list):
            for b in m["content"]:
                if _get(b, "type") == "tool_use" and not _get(b, "extra_content"):
                    return True
    return False


def flatten_tools(messages: list[dict]) -> list[dict]:
    """The conversation with every tool call and tool result written out as ordinary text."""
    out: list[dict] = []
    for m in messages:
        c = m["content"]
        if isinstance(c, str):
            out.append(m)
            continue
        if m["role"] == "assistant":
            parts = []
            for b in c:
                if _get(b, "type") == "text" and _get(b, "text"):
                    parts.append(_get(b, "text"))
                elif _get(b, "type") == "tool_use":
                    parts.append(f"[I called {_get(b, 'name')} with: {json.dumps(_get(b, 'input', {}))[:15000]}]")
            out.append({"role": "assistant", "content": "\n".join(parts) or "(no answer)"})
            continue
        blocks = []
        for b in c:
            if _get(b, "type") == "tool_result":
                inner = _get(b, "content", "")
                prefix = "Result of that call" + (" (an error)" if _get(b, "is_error") else "") + ": "
                if isinstance(inner, str):
                    blocks.append({"type": "text", "text": prefix + inner})
                else:
                    blocks.append({"type": "text", "text": prefix})
                    blocks += [x if isinstance(x, dict) else {"type": _get(x, "type"), "text": _get(x, "text", "")} for x in inner]
            else:
                blocks.append(b)
        out.append({"role": m["role"], "content": blocks})
    return out



def strip_images(messages: list[dict]) -> list[dict]:
    """A copy of the conversation with every image replaced by a short note, for models that cannot see pictures."""
    def fix(block: Any) -> Any:
        if isinstance(block, dict):
            if block.get("type") == "image":
                return {"type": "text", "text": _NO_PICTURE}
            if block.get("type") == "tool_result" and isinstance(block.get("content"), list):
                return {**block, "content": [fix(b) for b in block["content"]]}
        return block
    out = []
    for m in messages:
        c = m["content"]
        out.append({**m, "content": [fix(b) for b in c] if isinstance(c, list) else c})
    return out


class _PoolMessages:
    def __init__(self, pool: "PoolClient"):
        self.pool = pool

    def create(self, *, model: str | None = None, messages: list, **kw: Any):
        """Try the pool once; if every model is only briefly resting (a per-minute limit), wait for the first to come back and try again,
        rather than failing a design that is half done. At most pool.patience seconds of waiting in total."""
        waited = 0.0
        while True:
            try:
                return self._once(messages, kw)
            except LLMError as e:
                if not getattr(e, "rate_limited", False):
                    raise
                soonest = min(self.pool.book.remaining(m.label) for m in self.pool.members)
                if soonest <= 0 or waited + soonest > self.pool.patience:
                    raise
                log.warning("every model is briefly rate limited; waiting %.0fs", soonest)
                self.pool.sleep(soonest + 0.5)
                waited += soonest + 0.5

    def _once(self, messages: list, kw: dict):
        pool, errors, statuses = self.pool, [], []
        ready = [m for m in pool.members if pool.book.ready(m.label)]
        if _has_image(messages):                                               # pictures go to a model that can see them first
            ready = [m for m in ready if m.vision] + [m for m in ready if not m.vision]
        order = ready or sorted(pool.members, key=lambda m: pool.book.remaining(m.label))[:1]    # everyone is resting: try the one that rests least
        for m in order:
            try:
                msgs = messages if m.vision else strip_images(messages)
                if _needs_flat(m, msgs):
                    msgs = flatten_tools(msgs)
                resp = pool.client_for(m).messages.create(model=m.model, messages=msgs, **kw)
            except Exception as e:                                              # any failure of one member moves the call to the next
                status, hint = _error_facts(e)
                statuses.append(status)
                rest = pool.book.penalise(m.label, _rest_for(status), hint)
                log.warning("model %s failed (%s); resting %.0fs", m.label, e.__class__.__name__, rest)
                errors.append(f"{m.label}: {str(e)[:160]}")
                continue
            pool.book.success(m.label)
            with pool._lock:
                if m.label not in pool.used:
                    pool.used.append(m.label)
            return resp
        err = LLMError("no model could answer. " + " | ".join(errors)[:600])
        err.rate_limited = bool(statuses) and all(x == 429 for x in statuses)     # only a rate limit is worth waiting out
        raise err


class PoolClient:
    """Several models behind the one `messages.create` interface. Each call goes to the first model that is not resting, in the order given;
    on failure the model rests (see CooldownBook) and the same call moves to the next. The conversation is re-sent in full on every call, so
    a design can switch models part-way through. Models that cannot see pictures get the conversation with the pictures replaced by a note."""

    def __init__(self, members: list[PoolMember], book: CooldownBook | None = None, timeout: float = 120.0, clients: dict | None = None,
                 patience: float = 75.0, sleep=time.sleep):
        if not members:
            raise ValueError("a pool needs at least one model")
        self.members, self.book, self.timeout, self.patience, self.sleep = list(members), book or BOOK, timeout, patience, sleep
        self.vision = any(m.vision for m in self.members)                      # the designer sends pictures when at least one member can see them
        self.used: list[str] = []                                              # labels of the models that answered, in order of first use
        self._clients = dict(clients or {})
        self._lock = threading.Lock()
        self.messages = _PoolMessages(self)

    def client_for(self, m: PoolMember) -> Any:
        with self._lock:
            if m.label not in self._clients:
                self._clients[m.label] = _build_client(m, self.timeout, pooled=len(self.members) > 1)
            return self._clients[m.label]
