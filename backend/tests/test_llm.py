"""The provider adapter: Anthropic-shaped calls in, OpenAI chat-completions on the wire, Anthropic-shaped answers out."""
import contextlib
import json
import types
import httpx
import pytest
from app.config import Settings
from app.designer import SUBMIT_TOOL
from app.llm import LLMError, OpenAICompatClient, make_client, to_openai_messages, _simplify_schema


def reply(message, status=200, headers=None):
    return httpx.Response(status, json={"choices": [{"message": message, "finish_reason": "stop"}]} if status == 200 else {"error": "x"}, headers=headers)


def tool_reply(name="submit_design", args='{"title": "t"}'):
    return reply({"content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": name, "arguments": args}}]})


@pytest.fixture
def wire(monkeypatch):
    sent, queue = [], []

    def fake_post(url, json=None, headers=None, timeout=None):
        sent.append({"url": url, "body": json, "headers": headers})
        r = queue.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(httpx, "post", fake_post)

    @contextlib.contextmanager
    def fake_stream(method, url, json=None, headers=None, timeout=None):
        yield fake_post(url, json=json, headers=headers, timeout=timeout)
    monkeypatch.setattr(httpx, "stream", fake_stream)
    monkeypatch.setattr("time.sleep", lambda s: None)
    return types.SimpleNamespace(sent=sent, queue=queue)


def call(client, **kw):
    args = dict(model="m", max_tokens=100, system="sys", messages=[{"role": "user", "content": "hi"}], tools=[SUBMIT_TOOL],
                tool_choice={"type": "tool", "name": "submit_design"})
    args.update(kw)
    return client.messages.create(**args)


def test_request_shape_and_auth(wire):
    wire.queue.append(tool_reply())
    r = call(OpenAICompatClient("https://host/v1/", "KEY"))
    sent = wire.sent[0]
    assert sent["url"] == "https://host/v1/chat/completions" and sent["headers"]["Authorization"] == "Bearer KEY"
    assert sent["body"]["tool_choice"] == {"type": "function", "function": {"name": "submit_design"}}
    assert sent["body"]["tools"][0]["function"]["name"] == "submit_design"
    assert r.content[0].type == "tool_use" and r.content[0].input == {"title": "t"} and r.content[0].id == "c1"


def test_no_auth_header_for_local_servers(wire):
    wire.queue.append(tool_reply())
    call(OpenAICompatClient("http://localhost:11434/v1"))
    assert "Authorization" not in wire.sent[0]["headers"]


def test_tool_choice_any_becomes_required(wire):
    wire.queue.append(tool_reply())
    call(OpenAICompatClient("http://x/v1"), tool_choice={"type": "any"})
    assert wire.sent[0]["body"]["tool_choice"] == "required"


def test_messages_with_images_tool_calls_and_results():
    msgs = [{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "AAA"}}, {"type": "text", "text": "Problem"}]},
            {"role": "assistant", "content": [types.SimpleNamespace(type="text", text="ok"), types.SimpleNamespace(type="tool_use", id="t1", name="submit_design", input={"code": "x"})]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "is_error": True, "content": "NameError"}]},
            {"role": "assistant", "content": [types.SimpleNamespace(type="tool_use", id="t2", name="submit_design", input={})]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t2", "content": [{"type": "text", "text": "render"}, {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "BBB"}}]}]}]
    out = to_openai_messages("SYS", msgs)
    assert out[0] == {"role": "system", "content": "SYS"}
    assert out[1]["content"][0]["image_url"]["url"] == "data:image/jpeg;base64,AAA"
    assert out[2]["tool_calls"][0]["function"]["arguments"] == json.dumps({"code": "x"}) and out[2]["content"] == "ok"
    assert out[3] == {"role": "tool", "tool_call_id": "t1", "content": "ERROR: NameError"}
    assert out[5]["role"] == "tool" and out[5]["content"] == "render"
    assert out[6]["role"] == "user" and out[6]["content"][0]["image_url"]["url"] == "data:image/png;base64,BBB"


def test_schema_is_simplified_for_picky_providers():
    s = _simplify_schema({"type": "object", "additionalProperties": {"type": ["number", "string"]}, "properties": {"c": {"type": ["number", "null"], "minimum": 0, "maximum": 1}}})
    assert "additionalProperties" not in s and s["properties"]["c"] == {"type": "number"}


def test_plain_json_answers_are_recovered(wire):
    wire.queue.append(reply({"content": 'Sure! {"title": "t", "code": "x"}'}))
    r = call(OpenAICompatClient("http://x/v1"))
    assert [b.type for b in r.content] == ["text", "tool_use"] and r.content[1].name == "submit_design" and r.content[1].input["code"] == "x"


def test_retries_rate_limits_then_succeeds(wire):
    wire.queue += [reply({}, status=429, headers={"retry-after": "1"}), tool_reply()]
    assert call(OpenAICompatClient("http://x/v1")).content[0].type == "tool_use" and len(wire.sent) == 2


def test_auth_errors_are_not_retried(wire):
    wire.queue.append(httpx.Response(401, text="bad key"))
    with pytest.raises(LLMError) as e:
        call(OpenAICompatClient("http://x/v1"))
    assert "401" in str(e.value) and len(wire.sent) == 1


def test_network_errors_become_llm_errors(wire):
    wire.queue += [httpx.ConnectError("down")] * 3
    with pytest.raises(LLMError):
        call(OpenAICompatClient("http://x/v1"))


def test_provider_presets(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gk")
    s = Settings(llm_provider="gemini", llm_model="some-model", llm_base_url="", llm_api_key="")
    assert s.llm_provider == "openai" and s.llm_api_key == "gk" and "generativelanguage.googleapis.com" in s.llm_base_url and s.llm_configured
    assert isinstance(make_client(s), OpenAICompatClient)
    for preset, host in (("deepseek", "api.deepseek.com"), ("zai", "api.z.ai"), ("openrouter", "openrouter.ai")):
        s2 = Settings(llm_provider=preset, llm_model="m", llm_base_url="", llm_api_key="k")
        assert s2.llm_provider == "openai" and host in s2.llm_base_url and s2.llm_configured
    assert not Settings(llm_provider="ollama", llm_model="", llm_base_url="", llm_api_key="").llm_configured
    assert Settings(llm_provider="ollama", llm_model="qwen", llm_base_url="", llm_api_key="").llm_configured
    assert not Settings(llm_provider="anthropic", llm_api_key="", llm_model="").llm_configured
    assert make_client(Settings(llm_provider="anthropic", llm_api_key="", llm_model="")) is None
    assert make_client(Settings(llm_provider="anthropic", llm_api_key="k", llm_model="", enable_llm=False)) is None


def test_a_cut_off_tool_call_is_reported_as_cut_off_not_as_missing_code():
    from app.llm import OpenAICompatClient
    c = OpenAICompatClient("http://x")
    c._post = lambda body: {"choices": [{"finish_reason": "length", "message": {"content": None, "tool_calls": [
        {"id": "1", "function": {"name": "submit_design", "arguments": '{"title": "x", "code": "def build(:'}}]}}]}
    r = c.messages.create(model="m", max_tokens=100, messages=[{"role": "user", "content": "hi"}], tools=[{"name": "submit_design", "input_schema": {"type": "object", "properties": {}}}])
    assert [b.input for b in r.content if b.type == "tool_use"] == [{"_truncated": True}]


def test_a_second_key_for_the_same_provider_is_its_own_pool_member():
    from app.config import parse_pool
    env = {"GEMINI_API_KEY": "k1", "GEMINI_API_KEY_2": "k2"}
    members, skipped = parse_pool("gemini=gemini-2.5-flash, gemini:2=gemini-2.5-flash, gemini:3=gemini-2.5-flash", env)
    assert [m.label for m in members] == ["gemini/gemini-2.5-flash", "gemini:2/gemini-2.5-flash"]
    assert [m.api_key for m in members] == ["k1", "k2"]
    assert skipped and "GEMINI_API_KEY_3" in skipped[0] and "k2" not in " ".join(skipped)
