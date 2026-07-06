import pytest
from unittest.mock import MagicMock, patch
from illuvutar.agents.god import GodAgent
from illuvutar.agents.tools import AgentTools

@pytest.fixture
def mock_tools():
    tools = MagicMock(spec=AgentTools)
    tools.read_file.return_value = "world_name: Test"
    tools.query_palette.return_value = "- grass_plain (layer=ground)"
    AgentTools.definitions = staticmethod(lambda: [])
    return tools

def _make_ollama_response(content, tool_calls=None):
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    resp = MagicMock()
    resp.message = msg
    return resp

def test_god_returns_text_response(mock_tools):
    with patch("illuvutar.agents.god.ollama") as mock_ollama:
        mock_ollama.chat.return_value = _make_ollama_response("I shall build a world of ancient forest.")
        agent = GodAgent(model="llama3.2", tools=mock_tools)
        response = agent.chat("What kind of world shall we make?")
        assert "forest" in response

def test_god_calls_tool_when_requested(mock_tools):
    tool_call = MagicMock()
    tool_call.function.name = "query_palette"
    tool_call.function.arguments = {"description": "forest tiles"}

    with patch("illuvutar.agents.god.ollama") as mock_ollama:
        # First response has a tool call, second is final text
        mock_ollama.chat.side_effect = [
            _make_ollama_response("", tool_calls=[tool_call]),
            _make_ollama_response("I found these forest tiles."),
        ]
        agent = GodAgent(model="llama3.2", tools=mock_tools)
        response = agent.chat("What forest tiles do we have?")
        mock_tools.query_palette.assert_called_once_with(description="forest tiles")
        assert "forest" in response

def test_god_tracks_message_history(mock_tools):
    with patch("illuvutar.agents.god.ollama") as mock_ollama:
        mock_ollama.chat.return_value = _make_ollama_response("A dark and misty world.")
        agent = GodAgent(model="llama3.2", tools=mock_tools)
        agent.chat("Make it dark.")
        agent.chat("Add mist.")
        # Both turns should be in history
        assert len(agent.messages) >= 4  # 2 user + 2 assistant
