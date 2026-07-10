"""TUI robustness tests: the god must never fail silently in the chat log."""
import pytest
from unittest.mock import MagicMock
from textual.widgets import RichLog
from illuvutar.tui.app import GodChatApp


@pytest.fixture
def capture_writes(monkeypatch):
    """Record everything written to any RichLog (the chat log)."""
    writes: list[str] = []
    orig = RichLog.write

    def spy(self, content, *args, **kwargs):
        writes.append(str(content))
        return orig(self, content, *args, **kwargs)

    monkeypatch.setattr(RichLog, "write", spy)
    return writes


def _make_app(chat_return=None, chat_error=None):
    god = MagicMock()
    god.messages = []
    god.is_done.return_value = False
    if chat_error is not None:
        god.chat.side_effect = chat_error
    else:
        god.chat.return_value = chat_return
    writer = MagicMock()
    writer.status.return_value = {}
    return GodChatApp(god_agent=god, writer=writer)


async def _submit(app, text):
    inp = app.query_one("#input")
    app.set_focus(inp)
    inp.value = text
    await app.workers.wait_for_complete()  # drain any startup workers
    from textual.widgets import Input
    app.post_message(Input.Submitted(inp, text))
    await app.workers.wait_for_complete()


@pytest.mark.asyncio
async def test_god_error_is_shown_not_silent(capture_writes):
    app = _make_app(chat_error=RuntimeError("connection refused"))
    async with app.run_test() as pilot:
        await _submit(app, "hello")
        await pilot.pause()

    joined = "\n".join(capture_writes)
    assert any("connection refused" in w for w in capture_writes), (
        f"god error was swallowed; log was:\n{joined}"
    )


@pytest.mark.asyncio
async def test_god_shows_thinking_indicator_then_response(capture_writes):
    app = _make_app(chat_return="Behold, the forest stirs.")
    async with app.run_test() as pilot:
        await _submit(app, "make a world")
        await pilot.pause()

    joined = "\n".join(capture_writes)
    assert any("contempl" in w.lower() or "thinking" in w.lower() for w in capture_writes), (
        f"no thinking indicator; log was:\n{joined}"
    )
    assert any("Behold, the forest stirs." in w for w in capture_writes), (
        f"response not rendered; log was:\n{joined}"
    )
