import asyncio
import pytest
from unittest.mock import MagicMock
from illuvutar.studio.god_session import GodSession


@pytest.mark.asyncio
async def test_run_turn_streams_events_then_rejects_concurrent():
    god = MagicMock()
    god.chat_stream.return_value = iter([
        {"type": "tool_call", "name": "run_wfc", "args": {}},
        {"type": "message", "text": "done"},
        {"type": "done", "complete": True},
    ])
    s = GodSession(god=god, writer=MagicMock())
    q = s.subscribe()
    assert await s.run_turn("build") is True
    assert await s.run_turn("again") is False          # one turn at a time
    seen = []
    while True:
        e = await asyncio.wait_for(q.get(), timeout=2)
        seen.append(e)
        if e.get("type") == "turn_end":
            break
    kinds = [e["type"] for e in seen]
    assert "tool_call" in kinds and "message" in kinds and kinds[-1] == "turn_end"
    assert await s.run_turn("now free") is True         # freed after turn_end
