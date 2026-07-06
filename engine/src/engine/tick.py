import asyncio
from engine.entities.store import EntityStore
from engine.physics.passability import PassabilityMap
from engine.systems.input import InputSystem, Command
from engine.systems.physics_system import PhysicsSystem
from engine.systems.health import HealthSystem
from engine.systems.environment import EnvironmentSystem
from engine.systems.interaction import InteractionSystem
from engine.systems.inventory import InventorySystem
from engine.systems.ai_decision import AIDecisionSystem
from engine.systems.render_output import RenderOutputSystem
from engine.wrl.schema import WRLFrame
from typing import Callable, Awaitable


class TickLoop:
    def __init__(
        self,
        store: EntityStore,
        passability: PassabilityMap,
        palette: dict[int, str],
        tilemap_data: list[dict],
        world_id: str,
        width: int,
        height: int,
        frame_callback: Callable[[WRLFrame], Awaitable[None]],
        tick_interval: float = 0.1,
    ):
        self._store = store
        self._tick_interval = tick_interval
        self._frame_callback = frame_callback
        self._running = False
        self._command_queue: list[Command] = []
        self._tick = 0

        self._input = InputSystem(store, passability)
        self._physics = PhysicsSystem(store, passability)
        self._health = HealthSystem(store)
        self._environment = EnvironmentSystem(store)
        self._interaction = InteractionSystem(store)
        self._inventory = InventorySystem(store)
        self._ai = AIDecisionSystem(store)
        self._render = RenderOutputSystem(store, palette, tilemap_data, world_id, width, height)

    def enqueue_command(self, command: Command) -> None:
        self._command_queue.append(command)

    def stop(self) -> None:
        self._running = False

    async def start(self) -> None:
        self._running = True
        while self._running:
            await self._tick_once()
            await asyncio.sleep(self._tick_interval)

    async def _tick_once(self) -> None:
        t = self._tick
        queue = self._command_queue[:]
        self._command_queue.clear()

        move_intents = self._input.run(t, queue)
        self._physics.run(t, move_intents)
        dead = self._health.run(t)
        for eid in dead:
            self._store.remove(eid)
        self._environment.run(t)

        frame = self._render.run(t)
        await self._frame_callback(frame)
        self._tick += 1
