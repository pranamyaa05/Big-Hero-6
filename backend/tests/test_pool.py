"""Several models behind one interface: pool parsing, failover and rest periods, text-only members, and running models side by side."""
import contextlib
import time
import types

import httpx
import pytest

from app.config import PoolMember, Settings, parse_pool
from app.designer import DesignDeclined, DesignError, design_part
from app.llm import BOOK, CooldownBook, LLMError, OpenAICompatClient, PoolClient, candidate_clients, make_client, strip_images
from app.planner import Request
from conftest import make_settings
from fakes import FakeClient, accept, submit, tool_use

GOOD = "def build():\n    return {'plate': extrude(rrect(40, 20, 4), 6) - cyl(3, 8, -1)}"
BAD = "def build():\n    return nothing_here"
KEYS = {"GROQ_API_KEY": "SECRET-GROQ", "CEREBRAS_API_KEY": "SECRET-CEREBRAS", "GEMINI_API_KEY": "SECRET-GEMINI"}


def member(provider="a", model="m1", vision=True):
    return PoolMember("openai", provider, model, "http://x/v1", "k", vision)


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture(autouse=True)
def fresh_book():
    BOOK.reset()
    yield
    BOOK.reset()


def pool_of(*pairs, clock=None):
    """PoolClient over scripted members: pairs of (PoolMember, FakeClient)."""
    book = CooldownBook(clock or time.monotonic)
    return PoolClient([m for m, _ in pairs], book=book, clients={m.label: c for m, c in pairs}, sleep=lambda s: None), book


def ask(pool, text="hi", **kw):
    return pool.messages.create(model="ignored", max_tokens=10, system="s", messages=[{"role": "user", "content": text}], tools=[], **kw)


# ------------------------------------------------------------------ parsing
def test_parse_pool_entries_flags_and_skips():
    members, skipped = parse_pool("cerebras=gpt-oss-120b, groq=openai/gpt-oss-120b+text; gemini=gemini-x+vision\nnvidia=foo, bogus=m, mistral, ollama=qwen:7b, cerebras=gpt-oss-120b", KEYS)
    assert [m.label for m in members] == ["cerebras/gpt-oss-120b", "groq/openai/gpt-oss-120b", "gemini/gemini-x", "ollama/qwen:7b"]
    assert [m.vision for m in members] == [False, False, True, False]        # providers default to text-only unless known to see pictures
    assert members[0].base_url == "https://api.cerebras.ai/v1" and members[0].api_key == "SECRET-CEREBRAS"
    why = " | ".join(skipped)
    assert "NVIDIA_API_KEY is not set" in why and "unknown provider" in why and "provider=model" in why
    assert "SECRET" not in why and "SECRET" not in repr(members)              # keys never reach messages or reprs


def test_parse_pool_survives_quotes_left_by_env_files():
    members, skipped = parse_pool('"cerebras=a, groq=b+text"', KEYS)
    assert [m.label for m in members] == ["cerebras/a", "groq/b"] and not skipped


def test_parse_pool_vision_defaults_and_global_switch():
    members, _ = parse_pool("gemini=g, gemini=h+text, groq=q+vision", KEYS | {"GROQ_API_KEY": "k"})
    assert [m.vision for m in members] == [True, False, True]
    members, _ = parse_pool("gemini=g, groq=q+vision", KEYS, default_vision=False)
    assert [m.vision for m in members] == [False, False]                      # REFORM3D_LLM_VISION=false wins over everything


def test_parse_pool_url_placeholder_and_anthropic():
    members, skipped = parse_pool("cloudflare=@cf/openai/gpt-oss-120b", {"CLOUDFLARE_API_TOKEN": "t"})
    assert not members and "CLOUDFLARE_ACCOUNT_ID is not set" in skipped[0]
    members, _ = parse_pool("cloudflare=@cf/openai/gpt-oss-120b, anthropic=claude-x", {"CLOUDFLARE_API_TOKEN": "t", "CLOUDFLARE_ACCOUNT_ID": "acct1", "ANTHROPIC_API_KEY": "a"})
    assert members[0].base_url == "https://api.cloudflare.com/client/v4/accounts/acct1/ai/v1" and members[0].model == "@cf/openai/gpt-oss-120b"
    assert members[1].kind == "anthropic" and members[1].vision


def test_settings_with_a_pool(monkeypatch):
    for k, v in KEYS.items():
        monkeypatch.setenv(k, v)
    s = Settings(llm_pool="cerebras=a, groq=b", llm_provider="anthropic", llm_api_key="", llm_model="")
    assert s.llm_configured and s.uses_pool and [m.label for m in s.models()] == ["cerebras/a", "groq/b"]
    # the single-model settings, when complete, come first
    s = Settings(llm_pool="cerebras=a", llm_provider="gemini", llm_model="g1", llm_base_url="", llm_api_key="")
    assert [m.label for m in s.models()] == ["gemini/g1", "cerebras/a"]
    # nothing usable: not configured, even though a pool string was given
    monkeypatch.delenv("GROQ_API_KEY")
    s = Settings(llm_pool="groq=b", llm_provider="anthropic", llm_api_key="", llm_model="")
    assert not s.llm_configured and s.pool_skipped and make_client(s) is None


def test_make_client_uses_the_pool_only_when_one_is_set(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    assert isinstance(make_client(Settings(llm_pool="groq=m", llm_provider="anthropic", llm_api_key="", llm_model="")), PoolClient)
    assert isinstance(make_client(Settings(llm_pool="", llm_provider="groq", llm_model="m", llm_api_key="k", llm_base_url="")), OpenAICompatClient)


# ------------------------------------------------------------------ failover and rest periods
def test_a_failing_model_hands_the_call_to_the_next_and_rests():
    clock = Clock()
    a, b = member("a", "m1"), member("b", "m2")
    fa, fb = FakeClient(LLMError("quota", status=429), tool_use("x", {})), FakeClient(tool_use("x", {}), tool_use("x", {}))
    pool, book = pool_of((a, fa), (b, fb), clock=clock)
    r = ask(pool)
    assert r.content[0].name == "x" and len(fa.calls) == 1 and len(fb.calls) == 1
    assert fb.calls[0]["model"] == "m2" and fa.calls[0]["model"] == "m1"       # each member is called with its own model name
    assert pool.used == ["b/m2"] and not book.ready("a/m1") and book.ready("b/m2")
    ask(pool)                                                                  # a is resting: the call goes straight to b
    assert len(fa.calls) == 1 and len(fb.calls) == 2
    clock.t += 61                                                              # the rest is over: a is tried first again
    ask(pool)
    assert len(fa.calls) == 2 and pool.used == ["b/m2", "a/m1"]


def test_rests_grow_with_repeated_failures_and_clear_on_success():
    clock = Clock()
    book = CooldownBook(clock)
    assert book.penalise("m", 60) == 60 and book.penalise("m", 60) == 180 and book.penalise("m", 60) == 540
    assert book.penalise("m", 60) == 1620 and book.penalise("m", 60) == 3600     # capped at an hour
    assert book.snapshot() == {"m": 3600}
    book.success("m")
    assert book.ready("m") and book.penalise("m", 60) == 60
    assert book.penalise("n", 60, retry_after=900) == 900                      # the provider's own Retry-After is honoured


def test_error_kinds_rest_for_different_times():
    clock = Clock()
    a, b = member("a"), member("b")
    for status, expect in ((429, 60), (401, 600), (400, 30), (503, 20), (None, 20)):
        pool, book = pool_of((a, FakeClient(LLMError("x", status=status))), (b, FakeClient(tool_use("x", {}))), clock=clock)
        ask(pool)
        assert round(book.remaining("a/m1")) == expect, status


def test_sdk_style_errors_are_understood():
    class RateLimited(Exception):
        status_code = 429
        response = types.SimpleNamespace(headers={"retry-after": "300"})
    a, b = member("a"), member("b")
    pool, book = pool_of((a, FakeClient(RateLimited("slow down"))), (b, FakeClient(tool_use("x", {}))), clock=Clock())
    ask(pool)
    assert round(book.remaining("a/m1")) == 300


def test_every_model_failing_raises_one_llm_error_naming_them():
    a, b = member("a"), member("b")
    pool, _ = pool_of((a, FakeClient(LLMError("quota used up", status=429))), (b, FakeClient(LLMError("bad key", status=401))))
    with pytest.raises(LLMError) as e:
        ask(pool)
    assert "a/m1" in str(e.value) and "b/m1" in str(e.value) and "quota used up" in str(e.value)


def test_when_everyone_is_resting_the_one_that_rests_least_is_tried():
    clock = Clock()
    a, b = member("a"), member("b")
    pool, book = pool_of((a, FakeClient(tool_use("x", {}))), (b, FakeClient(tool_use("x", {}))), clock=clock)
    book.penalise("a/m1", 600)
    book.penalise("b/m1", 60)
    ask(pool)
    assert pool.used == ["b/m1"]


def test_a_pool_needs_members():
    with pytest.raises(ValueError):
        PoolClient([])


# ------------------------------------------------------------------ pictures
def image_block():
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "AAAA"}}


def test_strip_images_replaces_pictures_and_leaves_the_original_alone():
    msgs = [{"role": "user", "content": [{"type": "text", "text": "look"}, image_block()]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t", "content": [{"type": "text", "text": "ok"}, image_block()]}]},
            {"role": "assistant", "content": "plain"}]
    out = strip_images(msgs)
    assert "image" not in str(out) and out[0]["content"][1]["type"] == "text" and out[1]["content"][0]["content"][1]["type"] == "text"
    assert out[2] == msgs[2] and msgs[0]["content"][1]["type"] == "image" and msgs[1]["content"][0]["content"][1]["type"] == "image"


def test_text_only_members_never_receive_pictures():
    blind, seeing = member("a", "m1", vision=False), member("b", "m2", vision=True)
    fa, fb = FakeClient(tool_use("x", {}), tool_use("x", {})), FakeClient(tool_use("x", {}))
    pool, _ = pool_of((blind, fa), (seeing, fb))
    msgs = [{"role": "user", "content": [{"type": "text", "text": "look"}, image_block()]}]
    pool.book.penalise("b/m2", 600)                       # the seeing model is resting, so the blind one must take the picture request
    pool.messages.create(model="", max_tokens=1, system="", messages=msgs, tools=[])
    assert "image" not in str(fa.calls[0]["messages"])
    assert pool.vision
    pool.book.success("b/m2")
    pool.messages.create(model="", max_tokens=1, system="", messages=msgs, tools=[])
    assert "image" in str(fb.calls[0]["messages"])
    assert not PoolClient([blind], book=CooldownBook()).vision


# ------------------------------------------------------------------ the quota-aware HTTP client
@pytest.fixture
def wire(monkeypatch):
    sent, queue, slept = [], [], []

    def fake_post(url, json=None, headers=None, timeout=None):
        sent.append({"url": url, "body": json})
        return queue.pop(0)
    monkeypatch.setattr(httpx, "post", fake_post)

    @contextlib.contextmanager
    def fake_stream(method, url, json=None, headers=None, timeout=None):
        yield fake_post(url, json=json, headers=headers, timeout=timeout)
    monkeypatch.setattr(httpx, "stream", fake_stream)
    monkeypatch.setattr("time.sleep", lambda s: slept.append(s))
    return types.SimpleNamespace(sent=sent, queue=queue, slept=slept)


def http(status, headers=None):
    return httpx.Response(status, json={"error": "x"}, headers=headers)


def test_a_long_retry_after_fails_fast_so_the_next_model_can_take_over(wire):
    wire.queue.append(http(429, {"retry-after": "3600"}))
    c = OpenAICompatClient("http://x/v1", "k", retries=2, max_wait=5.0)
    with pytest.raises(LLMError) as e:
        c.messages.create(model="m", max_tokens=1, messages=[{"role": "user", "content": "hi"}])
    assert e.value.status == 429 and e.value.retry_after == 3600 and len(wire.sent) == 1 and not wire.slept


def test_a_short_retry_after_is_waited_out(wire):
    wire.queue += [http(429, {"retry-after": "2"}), httpx.Response(200, json={"choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}]})]
    c = OpenAICompatClient("http://x/v1", "k", retries=2, max_wait=5.0)
    r = c.messages.create(model="m", max_tokens=1, messages=[{"role": "user", "content": "hi"}])
    assert r.content[0].text == "hi" and wire.slept == [2.0]


def test_pool_members_are_built_to_fail_fast(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("CEREBRAS_API_KEY", "k")
    c = PoolClient(Settings(llm_pool="groq=m, cerebras=n", llm_provider="anthropic", llm_api_key="", llm_model="").models())
    inner = c.client_for(c.members[0])
    assert isinstance(inner, OpenAICompatClient) and inner.max_wait == 5.0 and inner.retries == 1     # the next model is the retry
    solo = PoolClient(Settings(llm_pool="groq=m", llm_provider="anthropic", llm_api_key="", llm_model="").models())
    assert solo.client_for(solo.members[0]).retries == 3


# ------------------------------------------------------------------ the design loop on a pool
def test_a_design_can_continue_on_another_model_when_one_runs_out_mid_way(tmp_path):
    a, b = member("a", "m1"), member("b", "m2")
    fa = FakeClient(submit(GOOD), LLMError("daily quota", status=429))          # answers the first call, then its quota runs out
    fb = FakeClient(accept())
    pool, _ = pool_of((a, fa), (b, fb))
    d = design_part(Request(description="a request"), make_settings(tmp_path), tmp_path / "work", pool)
    assert d["reviewed"] and d["attempts"] == 1 and d["models"] == ["a/m1", "b/m2"]
    assert len(fb.calls[0]["messages"]) == 3, "the second model receives the whole conversation so far"


def test_review_reaches_a_text_only_member_as_measurements(tmp_path):
    blind, seeing = member("a", "m1", vision=False), member("b", "m2", vision=True)
    fa = FakeClient(submit(GOOD), accept())
    pool, _ = pool_of((blind, fa), (seeing, FakeClient()))
    design_part(Request(description="a request"), make_settings(tmp_path), tmp_path / "work", pool)
    review = fa.calls[1]["messages"][-1]["content"][0]["content"]
    assert all(b["type"] == "text" for b in review)
    assert "40.0 x 20.0 x 6.0 mm" in str(review) and "cannot see pictures" in str(review)


def test_the_pool_reports_vision_to_the_designer(tmp_path):
    blind = member("a", "m1", vision=False)
    fa = FakeClient(submit(GOOD), accept())
    pool, _ = pool_of((blind, fa))
    req = Request(description="a request", photos=[("image/jpeg", b"\xff\xd8x")])
    design_part(req, make_settings(tmp_path), tmp_path / "work", pool)
    assert all(b["type"] == "text" for b in fa.calls[0]["messages"][0]["content"])
    assert "cannot see images" in fa.calls[0]["messages"][0]["content"][-1]["text"]


# ------------------------------------------------------------------ several models at once
class Slow:
    """A scripted model that answers after a delay, shaped like a one-model PoolClient so the race can label it."""

    def __init__(self, member_, *responses, delay=0.0):
        self.members, self.fc, self.delay, self.messages = [member_], FakeClient(*responses), delay, self

    def create(self, **kw):
        time.sleep(self.delay)
        return self.fc.messages.create(**kw)


def race(tmp_path, *clients, **over):
    s = make_settings(tmp_path, design_candidates=len(clients), **over)
    return design_part(Request(description="a request"), s, tmp_path / "work", candidates=list(clients)), tmp_path / "work"


def test_race_first_takes_the_first_valid_design(tmp_path):
    slow = Slow(member("a", "slow"), submit(GOOD, title="slow one"), accept(), delay=1.5)
    fast = Slow(member("b", "fast"), submit(GOOD, title="fast one"), accept())
    t0 = time.monotonic()
    d, work = race(tmp_path, slow, fast)
    assert d["title"] == "fast one" and d["models"] == ["b/fast"] and d["race"] == "first"
    assert time.monotonic() - t0 < 1.4, "the result must not wait for the slower model"
    assert [(c["model"], c["outcome"]) for c in d["candidates"]] == [("a/slow", "stopped early"), ("b/fast", "won")]
    assert (work / "freeform_pieces.npz").exists() and not list(work.glob("cand*"))


def test_race_best_ranks_valid_designs(tmp_path):
    # the first model needs two attempts but finishes first; the second is clean on the first try and arrives within the grace period
    quick_but_clumsy = Slow(member("a", "clumsy"), submit(BAD), submit(GOOD, title="clumsy"), accept())
    clean = Slow(member("b", "clean"), submit(GOOD, title="clean"), accept(), delay=0.6)
    d, _ = race(tmp_path, quick_but_clumsy, clean, design_race="best", design_race_grace_s=20)
    assert d["title"] == "clean" and d["models"] == ["b/clean"]
    assert [c["outcome"] for c in d["candidates"]] == ["valid, not chosen", "won"]


def test_race_best_stops_waiting_when_the_grace_period_ends(tmp_path):
    fast = Slow(member("a", "fast"), submit(GOOD, title="fast"), accept())
    never = Slow(member("b", "never"), submit(GOOD, title="never"), accept(), delay=3.0)
    t0 = time.monotonic()
    d, _ = race(tmp_path, fast, never, design_race="best", design_race_grace_s=0.3)
    assert d["title"] == "fast" and time.monotonic() - t0 < 2.5


def test_one_refusal_declines_the_whole_request(tmp_path):
    refuses = Slow(member("a", "careful"), tool_use("decline_request", {"reason": "that is a climbing part"}))
    complies = Slow(member("b", "eager"), submit(GOOD), accept(), delay=1.0)
    with pytest.raises(DesignDeclined) as e:
        race(tmp_path, refuses, complies)
    assert "climbing part" in str(e.value)


def test_candidates_that_fail_only_drop_out(tmp_path):
    broken = Slow(member("a", "down"), LLMError("server error 500", status=500))
    working = Slow(member("b", "up"), submit(GOOD), accept(), delay=0.2)
    d, _ = race(tmp_path, broken, working)
    assert d["models"] == ["b/up"] and d["candidates"][0]["outcome"].startswith("failed: The AI model could not be reached")


def test_race_where_everything_fails_reports_the_first_error(tmp_path):
    with pytest.raises(DesignError) as e:
        race(tmp_path, Slow(member("a"), LLMError("quota", status=429)), Slow(member("b"), LLMError("quota", status=429)))
    assert "could not be reached" in str(e.value)


def test_candidate_clients_pick_different_ready_models(monkeypatch):
    for k, v in KEYS.items():
        monkeypatch.setenv(k, v)
    s = Settings(llm_pool="cerebras=a, groq=b, gemini=c", llm_provider="anthropic", llm_api_key="", llm_model="", enable_llm=True)
    assert [c.members[0].label for c in candidate_clients(s, 2)] == ["cerebras/a", "groq/b"]
    BOOK.penalise("cerebras/a", 600)                                              # a resting model is skipped
    assert [c.members[0].label for c in candidate_clients(s, 2)] == ["groq/b", "gemini/c"]
    assert len(candidate_clients(s, 9)) == 2
    assert candidate_clients(Settings(llm_pool="", llm_provider="anthropic", llm_api_key="", llm_model=""), 3) == []


def test_race_settings_are_normalised():
    assert Settings(design_race="BEST", llm_provider="anthropic", llm_api_key="", llm_model="").design_race == "best"
    assert Settings(design_race="whatever", llm_provider="anthropic", llm_api_key="", llm_model="").design_race == "first"


# ------------------------------------------------------------------ what the operator sees
def test_health_lists_models_but_never_keys(make_client, monkeypatch):
    for k, v in KEYS.items():
        monkeypatch.setenv(k, v)
    c = make_client(enable_llm=True, llm_pool="cerebras=a, groq=b, nvidia=c", design_candidates=2)
    h = c.get("/health")
    body = h.json()
    assert body["design"] and body["provider"] == "pool" and body["pool"]["models"] == ["cerebras/a", "groq/b"] and body["candidates"] == 2
    assert "SECRET" not in h.text and "NVIDIA_API_KEY" not in h.text


def test_health_for_a_single_model_names_the_provider(make_client):
    c = make_client(enable_llm=True, llm_provider="groq", llm_model="m", llm_api_key="k", llm_base_url="")
    body = c.get("/health").json()
    assert body["provider"] == "groq" and body["pool"] is None


def test_cli_models_lists_what_will_be_called_and_what_was_left_out(monkeypatch, capsys):
    from app.cli import main
    for k, v in KEYS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("REFORM3D_LLM_POOL", "cerebras=a, gemini=g, nvidia=n")
    monkeypatch.setenv("REFORM3D_DESIGN_CANDIDATES", "2")
    assert main(["models"]) == 0
    out = capsys.readouterr().out
    assert "1. cerebras/a  (text only)" in out and "2. gemini/g  (sees pictures)" in out
    assert "left out: nvidia/n: NVIDIA_API_KEY is not set" in out and "design candidates: 2 (first)" in out and "SECRET" not in out


def test_google_retry_delay_in_the_body_is_used(wire):
    body = '[{"error": {"code": 429, "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "17s"}]}}]'
    wire.queue.append(httpx.Response(429, text=body))
    c = OpenAICompatClient("http://x/v1", "k", retries=1, max_wait=5.0)
    with pytest.raises(LLMError) as e:
        c.messages.create(model="m", max_tokens=1, messages=[{"role": "user", "content": "hi"}])
    assert e.value.retry_after == 17.0
    book = CooldownBook(Clock())
    assert book.penalise("g", 60, 17.0) == 17.0 and book.penalise("g", 60, 17.0) == 17.0      # a provider hint is not escalated


def test_a_model_that_never_finishes_is_cut_off(monkeypatch):
    @contextlib.contextmanager
    def slow_stream(method, url, **kw):
        class R:
            status_code, headers = 200, {}
            def iter_bytes(self):
                while True:                      # keep-alive bytes forever, like a gateway holding a slow request open
                    time.sleep(0.05)
                    yield b" "
        yield R()
    monkeypatch.setattr(httpx, "stream", slow_stream)
    c = OpenAICompatClient("http://x/v1", "k", timeout=0.3, retries=3)
    t0 = time.monotonic()
    with pytest.raises(LLMError, match="longer than"):
        c.messages.create(model="m", max_tokens=1, messages=[{"role": "user", "content": "hi"}])
    assert time.monotonic() - t0 < 1.5


def test_gemini_thought_signatures_go_back_with_the_tool_calls(wire):
    sig = {"google": {"thought_signature": "SIG123"}}
    wire.queue.append(httpx.Response(200, json={"choices": [{"message": {"tool_calls": [{"id": "c1", "type": "function", "extra_content": sig,
                                                                                       "function": {"name": "submit_design", "arguments": "{}"}}]}, "finish_reason": "tool_calls"}]}))
    wire.queue.append(httpx.Response(200, json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}))
    c = OpenAICompatClient("http://x/v1", "k")
    r = c.messages.create(model="m", max_tokens=1, messages=[{"role": "user", "content": "hi"}])
    assert r.content[0].extra_content == sig
    c.messages.create(model="m", max_tokens=1, messages=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": r.content},
                                                          {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "fine"}]}])
    call = wire.sent[-1]["body"]["messages"][1]["tool_calls"][0]
    assert call["extra_content"] == sig


def test_gemini_members_get_foreign_tool_calls_as_text():
    from app.llm import flatten_tools
    gem, other = PoolMember("openai", "gemini", "g", "http://x", "k", True), member("b", "m2")
    history = [{"role": "user", "content": "make a part"},
               {"role": "assistant", "content": [tool_use("submit_design", {"code": "def build(): ..."}, id="t1")]},
               {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "is_error": True, "content": "NameError"}]}]
    fg = FakeClient(tool_use("x", {}))
    pool, _ = pool_of((gem, fg), (other, FakeClient()))
    pool.messages.create(model="", max_tokens=1, system="", messages=history, tools=[])
    sent = fg.calls[0]["messages"]
    assert "I called submit_design" in sent[1]["content"] and "Result of that call (an error): NameError" in sent[2]["content"][0]["text"]
    assert flatten_tools([{"role": "user", "content": "x"}]) == [{"role": "user", "content": "x"}]


def test_compressed_replies_are_read_once(monkeypatch):
    import gzip
    payload = json_bytes = __import__("json").dumps({"choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}]}).encode()
    @contextlib.contextmanager
    def gz_stream(method, url, **kw):
        class R:
            status_code, headers = 200, httpx.Headers({"content-encoding": "gzip", "content-type": "application/json"})
            def iter_bytes(self):                 # like httpx: the bytes come out already decompressed
                yield payload
        yield R()
    monkeypatch.setattr(httpx, "stream", gz_stream)
    r = OpenAICompatClient("http://x/v1", "k").messages.create(model="m", max_tokens=1, messages=[{"role": "user", "content": "hi"}])
    assert r.content[0].text == "hi"


def test_a_500_on_a_forced_tool_call_is_retried_with_auto(wire):
    wire.queue += [httpx.Response(500, json={"error": "internal"}),
                   httpx.Response(200, json={"choices": [{"message": {"tool_calls": [{"id": "c", "type": "function", "function": {"name": "x", "arguments": "{}"}}]}, "finish_reason": "tool_calls"}]})]
    c = OpenAICompatClient("http://x/v1", "k", retries=1)
    r = c.messages.create(model="m", max_tokens=1, messages=[{"role": "user", "content": "hi"}],
                          tools=[{"name": "x", "description": "", "input_schema": {"type": "object", "properties": {}}}], tool_choice={"type": "any"})
    assert r.content[0].name == "x" and [s["body"]["tool_choice"] for s in wire.sent] == ["required", "auto"]


def test_requests_with_pictures_go_to_a_model_that_can_see_first():
    blind, seeing = member("a", "fast", vision=False), member("b", "eyes", vision=True)
    fa, fb = FakeClient(tool_use("x", {})), FakeClient(tool_use("x", {}))
    pool, _ = pool_of((blind, fa), (seeing, fb))
    pool.messages.create(model="", max_tokens=1, system="", messages=[{"role": "user", "content": [image_block(), {"type": "text", "text": "look"}]}], tools=[])
    assert pool.used == ["b/eyes"] and not fa.calls
    pool.messages.create(model="", max_tokens=1, system="", messages=[{"role": "user", "content": "no picture"}], tools=[])
    assert pool.used == ["b/eyes", "a/fast"]


def test_a_brief_rate_limit_on_every_model_is_waited_out():
    clock = Clock()
    slept = []
    a, b = member("a"), member("b")
    fa = FakeClient(LLMError("per minute", status=429, retry_after=20), tool_use("x", {}))
    fb = FakeClient(LLMError("per minute", status=429, retry_after=40))
    book = CooldownBook(clock)

    def sleep(s):
        slept.append(s)
        clock.t += s
    pool = PoolClient([a, b], book=book, clients={a.label: fa, b.label: fb}, patience=75, sleep=sleep)
    r = pool.messages.create(model="", max_tokens=1, system="", messages=[{"role": "user", "content": "hi"}], tools=[])
    assert r.content[0].name == "x" and slept == [20.5] and pool.used == ["a/m1"]
    # a daily quota is not waited for
    fc = FakeClient(LLMError("daily", status=429, retry_after=48000))
    pool2 = PoolClient([member("c")], book=CooldownBook(clock), clients={"c/m1": fc}, patience=75, sleep=sleep)
    with pytest.raises(LLMError):
        pool2.messages.create(model="", max_tokens=1, system="", messages=[{"role": "user", "content": "hi"}], tools=[])
    assert slept == [20.5]


def test_request_too_large_shrinks_the_answer_budget(wire):
    wire.queue += [httpx.Response(413, text='{"error":{"message":"Request too large for model on tokens per minute (TPM): Limit 8000, Requested 12100"}}'),
                   httpx.Response(200, json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]})]
    c = OpenAICompatClient("http://x/v1", "k", retries=1)
    r = c.messages.create(model="m", max_tokens=9000, messages=[{"role": "user", "content": "hi"}])
    assert r.content[0].text == "ok" and [s["body"]["max_tokens"] for s in wire.sent] == [9000, 4700]
