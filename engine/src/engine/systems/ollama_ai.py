"""OllamaAISystem: async LLM-driven entity thinking every N simulation ticks."""
import asyncio
import json
import ollama
from engine.entities.store import EntityStore
from engine.entities.components import Position, Label, AIComponent, Tags, Mind
from engine.entities.persistence import save_entity_state
from engine.physics.passability import PassabilityMap
from engine.physics.adjacency import get_adjacent_entities
from engine.systems.input import Command
from engine.wrl.schema import WRLThought

_THINK_PROMPT = """\
You are {name}, a {kind} in a living 2D world.
Who you are (you cannot change these): name={name}, kind={kind}.
What you believe about yourself (your identity, keep within {facts_words} words):
{facts}
Your goal: {goal}
Your position: ({x}, {y})
Nearby entities: {nearby}
World context: {context}
What you remember (keep within {memory_words} words, in your own words):
{memory}

Decide what to do next. Respond with ONLY valid JSON (no markdown):
{{"action": "move|say|rest|think", "direction": "north|south|east|west", "text": "...", "thought": "...", "memory": "...", "facts": "...", "set_goal": "..."}}

Rules:
- "action" is required. Choose one of: move, say, rest, think
- "direction" only for move
- "text" only for say (what you speak aloud)
- "thought" always required — your inner monologue (1-2 sentences, vivid)
- "memory" (optional) — REWRITE your full memory, keeping only what matters within {memory_words} words
- "facts" (optional) — REWRITE your identity beliefs within {facts_words} words
- "set_goal" (optional) — a new goal, only if yours has changed
- Stay in character. Be brief."""


class OllamaAISystem:
    def __init__(
        self,
        store: EntityStore,
        passability: PassabilityMap,
        model: str = "llama3.2",
        think_interval: int = 50,
        world_dir=None,
    ):
        self._store = store
        self._passability = passability
        self._model = model
        self._think_interval = think_interval
        self._world_dir = world_dir
        self._last_think: dict[str, int] = {}
        self._pending: list[asyncio.Task] = []
        self._results: list[WRLThought | Command] = []
        self._lock = asyncio.Lock()
        self._whispers: dict[str, list[str]] = {}

    def inject_whisper(self, entity_id: str, text: str) -> None:
        """Queue a whisper to be included in entity's next think context."""
        self._whispers.setdefault(entity_id, []).append(text)

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

        # Pull pending whispers for this entity
        pending_whispers = self._whispers.pop(entity_id, [])
        whisper_ctx = ("\nSomeone whispers to you: " + " | ".join(pending_whispers)) if pending_whispers else ""

        mind = self._store.get_component(entity_id, Mind)
        facts_text = (mind.facts if mind and mind.facts else "nothing yet")
        memory_text = (mind.memory if mind and mind.memory else "nothing yet")
        facts_words = mind.facts_word_limit if mind else 30
        memory_words = mind.memory_word_limit if mind else 60

        prompt = _THINK_PROMPT.format(
            name=name, kind=kind, goal=goal,
            x=x, y=y, nearby=nearby_str,
            context="A 2D world of forest, ruins, and open plain.",
            facts=facts_text, memory=memory_text,
            facts_words=facts_words, memory_words=memory_words,
        ) + whisper_ctx

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

        # Apply entity-authored memory / identity edits
        changed = False
        if mind is not None:
            if "facts" in decision and decision["facts"] is not None:
                changed |= mind.set_facts(str(decision["facts"]))
            if "memory" in decision and decision["memory"] is not None:
                changed |= mind.set_memory(str(decision["memory"]))
        new_goal = decision.get("set_goal")
        if isinstance(new_goal, str) and new_goal.strip() and ai is not None:
            if ai.goal != new_goal.strip():
                ai.goal = new_goal.strip()
                changed = True
        if changed and self._world_dir is not None and mind is not None and ai is not None:
            save_entity_state(self._world_dir, entity_id, ai.goal, mind)

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

    def flush_all(self) -> None:
        """Persist every AI entity's current state (shutdown safety net)."""
        if self._world_dir is None:
            return
        for eid in self._store.all_ids():
            mind = self._store.get_component(eid, Mind)
            ai = self._store.get_component(eid, AIComponent)
            if mind is not None and ai is not None:
                save_entity_state(self._world_dir, eid, ai.goal, mind)
