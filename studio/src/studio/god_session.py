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
