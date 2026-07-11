"""Owns the god agent and streams a turn's events to SSE subscribers."""
import asyncio


class GodSession:
    def __init__(self, god, writer):
        self.god = god
        self.writer = writer
        self._subscribers: list[asyncio.Queue] = []
        self._running = False

    def status(self) -> dict:
        return self.writer.status()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    def _emit(self, event: dict) -> None:
        for q in list(self._subscribers):
            q.put_nowait(event)

    async def run_turn(self, text: str) -> bool:
        if self._running:
            return False
        self._running = True
        loop = asyncio.get_running_loop()

        def work():
            try:
                for event in self.god.chat_stream(text):
                    loop.call_soon_threadsafe(self._emit, event)
            except Exception as ex:
                loop.call_soon_threadsafe(self._emit, {"type": "error", "message": str(ex)})
            finally:
                loop.call_soon_threadsafe(self._finish)

        loop.run_in_executor(None, work)
        return True

    def _finish(self) -> None:
        self._running = False
        self._emit({"type": "turn_end"})
