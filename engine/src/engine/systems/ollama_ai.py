"""OllamaAISystem: async LLM-driven entity thinking every N simulation ticks."""
import asyncio
import json
import ollama
from engine.entities.store import EntityStore
from engine.entities.components import Position, Label, AIComponent, Tags
from engine.physics.passability import PassabilityMap
from engine.physics.adjacency import get_adjacent_entities
from engine.systems.input import Command
from engine.wrl.schema import WRLThought

_THINK_PROMPT = """\
You are {name}, a {kind} in a living 2D world.
Your current goal: {goal}
Your position: ({x}, {y})
Nearby entities: {nearby}
World context: {context}

Decide what to do next. Respond with ONLY valid JSON (no markdown):
{{"action": "move|say|rest|think", "direction": "north|south|east|west", "text": "...", "thought": "..."}}

Rules:
- "action" is required. Choose one of: move, say, rest, think
- "direction" only for move
- "text" only for say (what you speak aloud)
- "thought" always required — your inner monologue (1-2 sentences, vivid)
- Stay in character. Be brief."""


class OllamaAISystem:
    def __init__(
        self,
        store: EntityStore,
        passability: PassabilityMap,
        model: str = "llama3.2",
        think_interval: int = 50,
    ):
        self._store = store
        self._passability = passability
        self._model = model
        self._think_interval = think_interval
        self._last_think: dict[str, int] = {}
        self._pending: list[asyncio.Task] = []
        self._results: list[WRLThought | Command] = []
        self._lock = asyncio.Lock()

    async def schedule_thinks(self, tick: int) -> None:
        """Schedule a background think for each entity due for their next cycle."""
        for entity_id in self._store.all_ids():
            ai = self._store.get_component(entity_id, AIComponent)
            if ai is None:
                continue
            last = self._last_think.get(entity_id, -self._think_interval)
            if tick - last < self._think_interval:
                continue
            self._last_think[entity_id] = tick
            task = asyncio.create_task(self._think(entity_id, tick))
            self._pending.append(task)

    async def drain_results(self) -> list[WRLThought | Command]:
        """Collect completed think results. Non-blocking."""
        still_running = []
        for task in self._pending:
            if task.done():
                try:
                    items = task.result()
                    async with self._lock:
                        self._results.extend(items)
                except Exception:
                    pass
            else:
                still_running.append(task)
        self._pending = still_running

        async with self._lock:
            out = list(self._results)
            self._results.clear()
        return out

    async def _think(self, entity_id: str, tick: int) -> list[WRLThought | Command]:
        pos = self._store.get_component(entity_id, Position)
        label = self._store.get_component(entity_id, Label)
        ai = self._store.get_component(entity_id, AIComponent)
        tags = self._store.get_component(entity_id, Tags)

        name = label.name if label else entity_id
        kind = (tags.values[1] if tags and len(tags.values) > 1 else "being")
        goal = ai.goal if ai else "exist"
        x, y = (pos.x, pos.y) if pos else (0, 0)

        nearby_ids = get_adjacent_entities(entity_id, self._store, radius=3)
        nearby_names = []
        for nid in nearby_ids[:4]:
            nlabel = self._store.get_component(nid, Label)
            nearby_names.append(nlabel.name if nlabel else nid)
        nearby_str = ", ".join(nearby_names) if nearby_names else "nobody"

        prompt = _THINK_PROMPT.format(
            name=name, kind=kind, goal=goal,
            x=x, y=y, nearby=nearby_str,
            context="A 2D world of forest, ruins, and open plain.",
        )

        try:
            client = ollama.AsyncClient()
            response = await client.chat(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = (response.message.content or "").strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:])
            if raw.endswith("```"):
                raw = raw[: raw.rfind("```")]
            decision = json.loads(raw.strip())
        except Exception:
            # Fallback: idle thought on parse/network failure
            return [WRLThought(entity_id=entity_id, text=f"[{name} is lost in thought...]", tick=tick)]

        results: list[WRLThought | Command] = []
        thought_text = decision.get("thought", "")
        action = decision.get("action", "rest")

        if thought_text:
            results.append(WRLThought(entity_id=entity_id, text=thought_text, tick=tick))

        if action == "move" and pos:
            direction = decision.get("direction", "south")
            results.append(Command(entity_id=entity_id, action="move", params={"direction": direction}))
        elif action == "say":
            say_text = decision.get("text", "")
            if say_text:
                results.append(WRLThought(
                    entity_id=entity_id,
                    text=f'"{say_text}"',
                    tick=tick,
                ))

        return results
