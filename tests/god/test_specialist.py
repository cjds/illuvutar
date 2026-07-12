import pytest
import yaml
from unittest.mock import MagicMock
from illuvutar.god.agents.specialist import SpecialistAgent
from illuvutar.god.llm.client import LLMMessage

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

    client = MagicMock()
    client.chat.return_value = LLMMessage(
        content="I have created two rival factions.",
        tool_calls=[],
        raw={"role": "assistant", "content": "I have created two rival factions."},
    )

    agent = SpecialistAgent(client=client, mandate_path=mandate_file, tools=tools)
    result = agent.run()
    assert isinstance(result, str)
    assert len(result) > 0
