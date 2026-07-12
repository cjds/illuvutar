import asyncio


class SSEBroadcaster:
    def __init__(self):
        self._queues: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=10)
        self._queues.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._queues:
            self._queues.remove(q)

    async def broadcast(self, frame_toml: str) -> None:
        dead = []
        for q in self._queues:
            try:
                q.put_nowait(frame_toml)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            if q in self._queues:
                self._queues.remove(q)
