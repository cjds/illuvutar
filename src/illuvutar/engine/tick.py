import asyncio
from illuvutar.engine.entities.store import EntityStore
from illuvutar.engine.physics.passability import PassabilityMap
from illuvutar.engine.systems.input import InputSystem, Command
from illuvutar.engine.systems.physics_system import PhysicsSystem
from illuvutar.engine.systems.health import HealthSystem
from illuvutar.engine.systems.environment import EnvironmentSystem
from illuvutar.engine.systems.interaction import InteractionSystem
from illuvutar.engine.systems.inventory import InventorySystem
from illuvutar.engine.systems.ai_decision import AIDecisionSystem
from illuvutar.engine.systems.ollama_ai import OllamaAISystem
from illuvutar.engine.systems.render_output import RenderOutputSystem
from illuvutar.engine.wrl.schema import WRLFrame, WRLThought
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
        ai_model: str = "llama3.2",
        world_dir=None,
    ):
        self._store = store
        self._tick_interval = tick_interval
        self._frame_callback = frame_callback
        self._running = False
        self._paused = False
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
        self._ollama_ai = OllamaAISystem(store, passability, model=ai_model,
                                         think_interval=50, world_dir=world_dir)
        self._pending_thoughts: list[WRLThought] = []
        self._whispers: dict[str, list[str]] = {}
        self._thought_log: list[dict] = []

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def tick(self) -> int:
        return self._tick

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def enqueue_command(self, command: Command) -> None:
        self._command_queue.append(command)

    def inject_whisper(self, entity_id: str, text: str) -> None:
        self._whispers.setdefault(entity_id, []).append(text)

    def recent_thoughts(self) -> list[dict]:
        return list(self._thought_log[-50:])

    def stop(self) -> None:
        self._running = False
        self._ollama_ai.flush_all()

    async def start(self) -> None:
        self._running = True
        while self._running:
            if not self._paused:
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

        # Drain pending whispers into OllamaAISystem before scheduling thinks
        for eid, msgs in list(self._whispers.items()):
            for msg in msgs:
                self._ollama_ai.inject_whisper(eid, msg)
        self._whispers.clear()

        # Schedule entity AI thinks (non-blocking, runs in background)
        await self._ollama_ai.schedule_thinks(t)
        # Drain completed thoughts/commands
        ai_results = await self._ollama_ai.drain_results()
        for item in ai_results:
            if isinstance(item, WRLThought):
                self._pending_thoughts.append(item)
                self._thought_log.append({"entity_id": item.entity_id, "text": item.text, "tick": item.tick})
                if len(self._thought_log) > 200:
                    self._thought_log = self._thought_log[-100:]
            else:
                # It's a Command — inject into input system
                self._command_queue.append(item)

        frame = self._render.run(t)
        # Attach pending thoughts to frame
        frame.thoughts = list(self._pending_thoughts)
        self._pending_thoughts.clear()
        await self._frame_callback(frame)
        self._tick += 1
