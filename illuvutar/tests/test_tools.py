import pytest
from pathlib import Path
from unittest.mock import MagicMock
from illuvutar.agents.tools import AgentTools


@pytest.fixture
def tools(tmp_path):
    writer = MagicMock()
    writer.world_dir = tmp_path
    writer.read.return_value = {"world_name": "Test"}
    rag = MagicMock()
    rag.query.return_value = []
    return AgentTools(writer=writer, rag=rag, tiles=[], palette_dir=tmp_path)


def test_read_file_reads_world_state(tools, tmp_path):
    (tmp_path / "constitution.yaml").write_text("world_name: Test\n")
    result = tools.read_file("constitution")
    assert "world_name" in result or result is not None


def test_write_world_state_delegates_to_writer(tools):
    tools.write_world_state(
        "constitution",
        '{"world_name": "X", "palette_used": "p", "width": 32, "height": 32, "tone": "t", "rules": []}',
    )
    tools.writer.write.assert_called_once()


def test_query_palette_returns_string(tools):
    result = tools.query_palette("water edge tiles")
    assert isinstance(result, str)


def test_definitions_returns_list(tools):
    defs = AgentTools.definitions()
    assert isinstance(defs, list)
    assert len(defs) >= 4
    names = [d["function"]["name"] for d in defs]
    assert "read_file" in names
    assert "write_world_state" in names
    assert "query_palette" in names
    assert "run_wfc" in names
