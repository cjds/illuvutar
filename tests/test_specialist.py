import pytest
import yaml
from unittest.mock import patch, MagicMock
from illuvutar.agents.specialist import SpecialistAgent

@pytest.fixture
def mandate_file(tmp_path):
    mandate = {
        "role": "faction-agent",
        "task": "Create 2 rival factions for the northern forest region.",
        "constraints": ["Factions must reference only region id 0", "Tone: hostile"],
        "output_file": "factions",
        "read_files": ["constitution", "regions"],
    }
    path = tmp_path / "faction-agent-mandate.yaml"
    path.write_text(yaml.dump(mandate))
    return path

def test_specialist_runs_and_returns_text(mandate_file, tmp_path):
    tools = MagicMock()
    tools.read_file.return_value = "world_name: Test"
    tools.write_world_state.return_value = "Written factions successfully."
    tools.query_palette.return_value = ""

    with patch("illuvutar.agents.specialist.ollama") as mock_ollama:
        msg = MagicMock()
        msg.content = "I have created two rival factions."
        msg.tool_calls = []
        mock_ollama.chat.return_value = MagicMock(message=msg)

        agent = SpecialistAgent(model="llama3.2", mandate_path=mandate_file, tools=tools)
        result = agent.run()
        assert isinstance(result, str)
        assert len(result) > 0
