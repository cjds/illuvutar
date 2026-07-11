import pytest
from unittest.mock import MagicMock
from illuvutar.agents.god import GodAgent
from illuvutar.agents.tools import AgentTools
from illuvutar.llm.client import LLMMessage, ToolCall


@pytest.fixture
def mock_tools(monkeypatch):
    tools = MagicMock(spec=AgentTools)
    tools.query_palette.return_value = "- grass_plain"
    monkeypatch.setattr(AgentTools, "definitions", staticmethod(lambda: []))
    return tools


def _client(*messages):
    c = MagicMock()
    c.chat.side_effect = list(messages)
    return c


def test_god_returns_text_response(mock_tools):
    c = _client(LLMMessage(content="I shall build a forest.", tool_calls=[],
                           raw={"role": "assistant", "content": "I shall build a forest."}))
    agent = GodAgent(client=c, tools=mock_tools)
    assert "forest" in agent.chat("make a world")


def test_god_dispatches_tool_then_answers(mock_tools):
    tc = ToolCall(id="c1", name="query_palette", arguments={"description": "grass"})
    first = LLMMessage(content="", tool_calls=[tc],
                       raw={"role": "assistant", "content": "", "tool_calls": [
                           {"id": "c1", "type": "function",
                            "function": {"name": "query_palette", "arguments": "{}"}}]})
    second = LLMMessage(content="Found grass.", tool_calls=[],
                        raw={"role": "assistant", "content": "Found grass."})
    agent = GodAgent(client=_client(first, second), tools=mock_tools)
    out = agent.chat("what tiles?")
    mock_tools.query_palette.assert_called_once_with(description="grass")
    assert "grass" in out
    # the tool result was appended with a tool_call_id
    tool_msgs = [m for m in agent.messages if m.get("role") == "tool"]
    assert tool_msgs and tool_msgs[-1]["tool_call_id"] == "c1"


def test_god_detects_completion(mock_tools):
    c = _client(LLMMessage(content="The world is complete.", tool_calls=[],
                           raw={"role": "assistant", "content": "The world is complete."}))
    agent = GodAgent(client=c, tools=mock_tools)
    agent.chat("finish")
    assert agent.is_done()


def test_god_sanitizes_legacy_memory():
    # old ollama-shaped history (tool_calls without ids, tool msg without tool_call_id)
    legacy = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "x", "arguments": {}}}]},
        {"role": "tool", "content": "result"},
    ]
    mem = MagicMock(); mem.load.return_value = legacy
    agent = GodAgent(client=MagicMock(), tools=MagicMock(), memory=mem)
    # no tool-role messages and no assistant tool_calls survive → all remaining are OpenAI-valid
    assert all(m["role"] != "tool" for m in agent.messages)
    assert all("tool_calls" not in m for m in agent.messages)
    assert [m["content"] for m in agent.messages if m["role"] == "user"] == ["hi"]
