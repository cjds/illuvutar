import asyncio
import pytest
from engine.entities.store import EntityStore
from engine.physics.passability import PassabilityMap
from engine.tick import TickLoop


@pytest.mark.asyncio
async def test_tick_loop_calls_callback():
    store = EntityStore()
    passability = PassabilityMap(tilemap=[["grass"]], rules={"grass": "open"})
    frames_received = []

    async def on_frame(frame):
        frames_received.append(frame)

    loop = TickLoop(
        store=store,
        passability=passability,
        palette={0: "void"},
        tilemap_data=[],
        world_id="test",
        width=1, height=1,
        frame_callback=on_frame,
        tick_interval=0.05,  # 50ms for test speed
    )

    task = asyncio.create_task(loop.start())
    await asyncio.sleep(0.18)  # ~3 ticks at 50ms
    loop.stop()
    await task

    assert len(frames_received) >= 2
