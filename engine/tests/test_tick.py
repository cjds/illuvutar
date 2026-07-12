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


import json
from engine.entities.store import EntityStore
from engine.entities.components import (
    Position, Label, AIComponent, Tags, PhysicsComponent, Mind
)
from engine.physics.passability import PassabilityMap
from engine.tick import TickLoop


def test_stop_flushes_entity_state_to_disk(tmp_path):
    store = EntityStore()
    store.create("guardian", "guardian", [
        Position(1, 1), Label("Sentinel"),
        AIComponent(agent_id="guardian", goal="guard"),
        Tags(["agent"]), PhysicsComponent(),
        Mind(memory="I saw a stranger", facts="I distrust strangers"),
    ])
    passability = PassabilityMap(tilemap=[["g"] * 4 for _ in range(4)],
                                 rules={"g": "open"})

    async def noop_frame(_frame):
        return None

    loop = TickLoop(
        store=store, passability=passability, palette={0: "g"},
        tilemap_data=[], world_id="w", width=4, height=4,
        frame_callback=noop_frame, world_dir=tmp_path,
    )
    # Simulate that this entity's state changed during a think cycle (it is
    # marked dirty). flush_all now only persists changed entities, so an
    # entity that never thought should not have its seed state shadowed.
    loop._ollama_ai._dirty.add("guardian")
    loop.stop()

    saved = json.loads((tmp_path / ".entities" / "guardian.json").read_text())
    assert saved["memory"] == "I saw a stranger"
    assert saved["facts"] == "I distrust strangers"
    assert saved["goal"] == "guard"


def _loop(tmp_path=None):
    from engine.entities.store import EntityStore
    from engine.physics.passability import PassabilityMap
    store = EntityStore()
    pass_ = PassabilityMap(tilemap=[["g"] * 3 for _ in range(3)], rules={"g": "open"})
    async def noop(_f): return None
    return TickLoop(store=store, passability=pass_, palette={0: "g"}, tilemap_data=[],
                    world_id="w", width=3, height=3, frame_callback=noop, tick_interval=0.01)


def test_pause_resume_toggles_flag():
    lp = _loop()
    assert lp.paused is False
    lp.pause(); assert lp.paused is True
    lp.resume(); assert lp.paused is False


@pytest.mark.asyncio
async def test_paused_loop_does_not_tick():
    lp = _loop()
    calls = {"n": 0}
    async def counting_tick():
        calls["n"] += 1
    lp._tick_once = counting_tick
    lp.pause()
    task = asyncio.create_task(lp.start())
    await asyncio.sleep(0.05)          # several intervals
    paused_count = calls["n"]
    lp.resume()
    await asyncio.sleep(0.05)
    lp.stop()
    await asyncio.sleep(0.02)
    assert paused_count == 0           # no ticks while paused
    assert calls["n"] > 0              # ticked after resume
