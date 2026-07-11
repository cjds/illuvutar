import json
from unittest.mock import MagicMock, patch
from illuvutar.llm.client import LLMClient, parse_json


def _fake_openai(content=None, tool_calls=None):
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    resp = MagicMock()
    resp.choices = [MagicMock(message=msg)]
    inst = MagicMock()
    inst.chat.completions.create.return_value = resp
    return inst


def test_chat_returns_plain_text():
    with patch("illuvutar.llm.client.OpenAI", return_value=_fake_openai(content="hello")):
        c = LLMClient(endpoint="http://x/v1", model="m", api_key="k")
        m = c.chat([{"role": "user", "content": "hi"}])
    assert m.content == "hello"
    assert m.tool_calls == []
    assert m.raw == {"role": "assistant", "content": "hello"}


def test_chat_normalizes_tool_calls_to_dict_args():
    tc = MagicMock()
    tc.id = "call_1"; tc.function.name = "run_wfc"
    tc.function.arguments = json.dumps({"width": 24, "height": 20})
    with patch("illuvutar.llm.client.OpenAI", return_value=_fake_openai(content="", tool_calls=[tc])):
        m = LLMClient().chat([{"role": "user", "content": "go"}], tools=[{"type": "function"}])
    assert m.tool_calls[0].id == "call_1"
    assert m.tool_calls[0].name == "run_wfc"
    assert m.tool_calls[0].arguments == {"width": 24, "height": 20}
    assert m.raw["tool_calls"][0]["id"] == "call_1"           # OpenAI-shaped for history


def test_config_precedence_env_then_default(monkeypatch):
    monkeypatch.delenv("ILLUVUTAR_LLM_ENDPOINT", raising=False)
    with patch("illuvutar.llm.client.OpenAI") as O:
        LLMClient()
        assert O.call_args.kwargs["base_url"] == "http://localhost:11434/v1"
    monkeypatch.setenv("ILLUVUTAR_LLM_ENDPOINT", "http://env/v1")
    with patch("illuvutar.llm.client.OpenAI") as O:
        LLMClient()
        assert O.call_args.kwargs["base_url"] == "http://env/v1"
    with patch("illuvutar.llm.client.OpenAI") as O:
        LLMClient(endpoint="http://cli/v1")                    # CLI arg wins
        assert O.call_args.kwargs["base_url"] == "http://cli/v1"


def test_parse_json_strips_fences_and_finds_array():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('here you go: [{"name": "x"}] cheers') == [{"name": "x"}]
    assert parse_json("not json at all") is None


def test_parse_json_single_line_fence():
    assert parse_json('```json {"a": 1}```') == {"a": 1}


def test_complete_returns_plain_text():
    with patch("illuvutar.llm.client.OpenAI", return_value=_fake_openai(content="hi there")):
        assert LLMClient().complete("say hi") == "hi there"


def test_chat_tolerates_malformed_tool_arguments():
    from unittest.mock import MagicMock
    tc = MagicMock(); tc.id = "c"; tc.function.name = "f"; tc.function.arguments = "{not json"
    with patch("illuvutar.llm.client.OpenAI", return_value=_fake_openai(content="", tool_calls=[tc])):
        m = LLMClient().chat([{"role": "user", "content": "x"}])
    assert m.tool_calls[0].arguments == {}
