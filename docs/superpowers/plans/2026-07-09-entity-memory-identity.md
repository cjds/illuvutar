# Entity Memory & Mutable Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every AI entity a word-budgeted, self-authored memory and editable identity (goal + self-facts) that persists across engine restarts.

**Architecture:** A new `Mind` ECS component holds two word-capped text blobs (`memory`, `facts`). The Ollama think loop reads them into the prompt and lets the entity rewrite them via new decision-JSON fields (`memory`, `facts`, `set_goal`); changes are written through to `world_dir/.entities/<id>.json`. The loader seeds `Mind` from `agents.yaml`, overlays any persisted state, and stamps configurable word limits (CLI flag → `constitution.yaml` → default).

**Tech Stack:** Python 3.12, dataclasses, asyncio, ollama AsyncClient, pytest / pytest-asyncio (`asyncio_mode = "auto"`), FastAPI. All work is in the `engine/` project — run tests with `cd engine && uv run pytest`.

## Global Constraints

- Word limits resolve with precedence: **CLI flag `--memory-words`/`--facts-words` → `constitution.yaml` `memory_word_limit`/`facts_word_limit` → built-in defaults (memory 60, facts 30)**.
- Locked identity (id, kind, name) has **no** writable path — entities can only edit `goal`, `memory`, `facts`.
- Persistence is **best-effort**: never let a file error crash the tick loop. Writes are atomic (temp file + `os.replace`).
- Memory/facts are **wholesale replacements** (the entity rewrites the blob), not appends. Over-limit text is truncated to the first N words.
- Follow existing engine patterns: `@app.on_event` (not lifespan), sync file I/O, dataclass components.

## File Structure

**Create:**
- `engine/src/engine/entities/persistence.py` — load/save `.entities/<id>.json`
- `engine/tests/test_mind.py` — `Mind` component unit tests
- `engine/tests/test_entity_persistence.py` — persistence round-trip tests

**Modify:**
- `engine/src/engine/entities/components.py` — add `Mind`; remove dead `AIComponent.memory_ref`
- `engine/src/engine/loader.py` — resolve limits, seed `Mind`, overlay persisted state
- `engine/src/engine/systems/ollama_ai.py` — prompt block, parse/apply updates, write-through, `flush_all`
- `engine/src/engine/tick.py` — thread `world_dir` to `OllamaAISystem`, flush on stop
- `engine/src/engine/server/app.py` — accept + forward `world_dir`
- `engine/src/engine/__main__.py` — `--memory-words`/`--facts-words`, pass `world_dir` + limits
- `engine/tests/test_loader.py` — seeding, overlay, limit precedence
- `engine/tests/test_ollama_ai.py` — prompt + apply + persistence
- `engine/tests/test_tick.py` — flush-on-stop wiring
- `.gitignore` — add `.entities/`

---

### Task 1: `Mind` component

**Files:**
- Modify: `engine/src/engine/entities/components.py`
- Test: `engine/tests/test_mind.py`

**Interfaces:**
- Produces: `Mind` dataclass with fields `memory: str = ""`, `facts: str = ""`, `memory_word_limit: int = 60`, `facts_word_limit: int = 30`; methods `set_memory(text: str) -> bool`, `set_facts(text: str) -> bool` (truncate to word limit, normalize whitespace, return True iff the stored value changed).

- [ ] **Step 1: Write the failing test**

Create `engine/tests/test_mind.py`:

```python
from engine.entities.components import Mind


def test_set_memory_under_limit_kept_verbatim():
    m = Mind(memory_word_limit=5)
    changed = m.set_memory("the ruins feel alive")
    assert changed is True
    assert m.memory == "the ruins feel alive"


def test_set_memory_truncates_to_word_limit():
    m = Mind(memory_word_limit=3)
    m.set_memory("one two three four five")
    assert m.memory == "one two three"


def test_set_memory_normalizes_whitespace():
    m = Mind(memory_word_limit=10)
    m.set_memory("  spaced   out \n words ")
    assert m.memory == "spaced out words"


def test_set_memory_empty_clears():
    m = Mind(memory="something", memory_word_limit=5)
    changed = m.set_memory("   ")
    assert m.memory == ""
    assert changed is True


def test_set_memory_no_change_returns_false():
    m = Mind(memory_word_limit=5)
    m.set_memory("stable text")
    assert m.set_memory("stable text") is False


def test_set_facts_truncates_to_its_own_limit():
    m = Mind(facts_word_limit=2)
    m.set_facts("I distrust every stranger")
    assert m.facts == "I distrust"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd engine && uv run pytest tests/test_mind.py -v`
Expected: FAIL with `ImportError` / `AttributeError` (no `Mind`).

- [ ] **Step 3: Write minimal implementation**

In `engine/src/engine/entities/components.py`, add at the end:

```python
def _truncate_words(text: str, limit: int) -> str:
    return " ".join((text or "").split()[:limit])


@dataclass
class Mind:
    memory: str = ""                 # episodic — "what happened"
    facts: str = ""                  # self-beliefs — "who I am"
    memory_word_limit: int = 60
    facts_word_limit: int = 30

    def set_memory(self, text: str) -> bool:
        new = _truncate_words(text, self.memory_word_limit)
        if new == self.memory:
            return False
        self.memory = new
        return True

    def set_facts(self, text: str) -> bool:
        new = _truncate_words(text, self.facts_word_limit)
        if new == self.facts:
            return False
        self.facts = new
        return True
```

Also remove the dead field from `AIComponent` — change:

```python
@dataclass
class AIComponent:
    agent_id: str
    goal: str = "idle"
    memory_ref: str = ""
```

to:

```python
@dataclass
class AIComponent:
    agent_id: str
    goal: str = "idle"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd engine && uv run pytest tests/test_mind.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Run the full engine suite to catch fallout from removing `memory_ref`**

Run: `cd engine && uv run pytest -q`
Expected: all PASS (no test referenced `memory_ref`).

- [ ] **Step 6: Commit**

```bash
git add engine/src/engine/entities/components.py engine/tests/test_mind.py
git commit -m "feat(engine): add Mind component with word-budgeted memory/facts"
```

---

### Task 2: Entity-state persistence

**Files:**
- Create: `engine/src/engine/entities/persistence.py`
- Test: `engine/tests/test_entity_persistence.py`

**Interfaces:**
- Consumes: `Mind` (Task 1) — reads `.memory` and `.facts`.
- Produces:
  - `load_entity_state(world_dir, entity_id: str) -> dict | None` — returns `{"goal", "memory", "facts"}` dict or `None` (missing/corrupt).
  - `save_entity_state(world_dir, entity_id: str, goal: str, mind: Mind) -> None` — atomic write to `world_dir/.entities/<entity_id>.json`; best-effort (never raises).

- [ ] **Step 1: Write the failing test**

Create `engine/tests/test_entity_persistence.py`:

```python
from engine.entities.components import Mind
from engine.entities.persistence import load_entity_state, save_entity_state


def test_save_then_load_round_trip(tmp_path):
    mind = Mind(memory="met a stranger", facts="I guard the ruins")
    save_entity_state(tmp_path, "guardian", "guard the ruins", mind)
    state = load_entity_state(tmp_path, "guardian")
    assert state == {
        "goal": "guard the ruins",
        "memory": "met a stranger",
        "facts": "I guard the ruins",
    }


def test_load_missing_returns_none(tmp_path):
    assert load_entity_state(tmp_path, "nobody") is None


def test_load_corrupt_returns_none(tmp_path):
    d = tmp_path / ".entities"
    d.mkdir()
    (d / "broken.json").write_text("{ not valid json")
    assert load_entity_state(tmp_path, "broken") is None


def test_load_non_dict_returns_none(tmp_path):
    d = tmp_path / ".entities"
    d.mkdir()
    (d / "list.json").write_text("[1, 2, 3]")
    assert load_entity_state(tmp_path, "list") is None


def test_save_leaves_no_tmp_files(tmp_path):
    save_entity_state(tmp_path, "guardian", "g", Mind(memory="m", facts="f"))
    tmp_leftovers = list((tmp_path / ".entities").glob("*.tmp"))
    assert tmp_leftovers == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd engine && uv run pytest tests/test_entity_persistence.py -v`
Expected: FAIL with `ModuleNotFoundError: engine.entities.persistence`.

- [ ] **Step 3: Write minimal implementation**

Create `engine/src/engine/entities/persistence.py`:

```python
"""Persist evolved entity state (goal, memory, facts) to world_dir/.entities/<id>.json."""
import json
import os
import tempfile
from pathlib import Path

from engine.entities.components import Mind


def _entities_dir(world_dir) -> Path:
    return Path(world_dir) / ".entities"


def load_entity_state(world_dir, entity_id: str) -> dict | None:
    path = _entities_dir(world_dir) / f"{entity_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def save_entity_state(world_dir, entity_id: str, goal: str, mind: Mind) -> None:
    d = _entities_dir(world_dir)
    payload = {"goal": goal, "memory": mind.memory, "facts": mind.facts}
    try:
        d.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(d), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp, d / f"{entity_id}.json")
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    except Exception:
        pass  # best-effort: never crash the tick loop
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd engine && uv run pytest tests/test_entity_persistence.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add engine/src/engine/entities/persistence.py engine/tests/test_entity_persistence.py
git commit -m "feat(engine): atomic best-effort entity-state persistence"
```

---

### Task 3: Loader — seed Mind, overlay persisted state, resolve limits

**Files:**
- Modify: `engine/src/engine/loader.py`
- Test: `engine/tests/test_loader.py`

**Interfaces:**
- Consumes: `Mind` (Task 1), `load_entity_state` (Task 2).
- Produces: `load_world(world_dir, memory_word_limit: int | None = None, facts_word_limit: int | None = None) -> WorldData`. Every AI entity now carries a `Mind` component. Limits resolve CLI arg → `constitution.yaml` → default (60/30).

- [ ] **Step 1: Write the failing tests**

Append to `engine/tests/test_loader.py`:

```python
from engine.entities.components import Mind, AIComponent
from engine.entities.persistence import save_entity_state


def _add_agent(world_dir, agent):
    import yaml
    (world_dir / "agents.yaml").write_text(yaml.dump([agent]))


def test_entity_gets_mind_with_default_limits(world_dir):
    data = load_world(world_dir)
    mind = data.store.get_component("e1", Mind)
    assert mind is not None
    assert mind.memory_word_limit == 60
    assert mind.facts_word_limit == 30


def test_facts_seed_string(world_dir):
    _add_agent(world_dir, {"id": "e1", "kind": "humanoid", "x": 1, "y": 1,
                           "name": "Alice", "behavior": "wander",
                           "facts": "I am cautious"})
    data = load_world(world_dir)
    assert data.store.get_component("e1", Mind).facts == "I am cautious"


def test_facts_seed_list_joined(world_dir):
    _add_agent(world_dir, {"id": "e1", "kind": "humanoid", "x": 1, "y": 1,
                           "name": "Alice", "behavior": "wander",
                           "facts": ["I am cautious", "I distrust strangers"]})
    data = load_world(world_dir)
    facts = data.store.get_component("e1", Mind).facts
    assert "cautious" in facts and "distrust" in facts


def test_persisted_state_overlays_seed(world_dir):
    _add_agent(world_dir, {"id": "e1", "kind": "humanoid", "x": 1, "y": 1,
                           "name": "Alice", "behavior": "wander",
                           "facts": "seed fact"})
    save_entity_state(world_dir, "e1", "evolved goal",
                      Mind(memory="I recall the storm", facts="evolved fact"))
    data = load_world(world_dir)
    mind = data.store.get_component("e1", Mind)
    ai = data.store.get_component("e1", AIComponent)
    assert mind.memory == "I recall the storm"
    assert mind.facts == "evolved fact"
    assert ai.goal == "evolved goal"


def test_cli_limit_overrides_constitution_and_truncates_overlay(world_dir):
    import yaml
    const = yaml.safe_load((world_dir / "constitution.yaml").read_text())
    const["memory_word_limit"] = 40
    (world_dir / "constitution.yaml").write_text(yaml.dump(const))
    save_entity_state(world_dir, "e1", "wander",
                      Mind(memory="alpha beta gamma delta", facts=""))
    data = load_world(world_dir, memory_word_limit=2)  # CLI wins over constitution's 40
    mind = data.store.get_component("e1", Mind)
    assert mind.memory_word_limit == 2
    assert mind.memory == "alpha beta"  # overlay re-truncated to CLI limit


def test_constitution_limit_used_when_no_cli(world_dir):
    import yaml
    const = yaml.safe_load((world_dir / "constitution.yaml").read_text())
    const["facts_word_limit"] = 7
    (world_dir / "constitution.yaml").write_text(yaml.dump(const))
    data = load_world(world_dir)
    assert data.store.get_component("e1", Mind).facts_word_limit == 7
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd engine && uv run pytest tests/test_loader.py -v -k "mind or facts or persisted or limit or constitution"`
Expected: FAIL (`load_world` has no limit args / entities have no `Mind`).

- [ ] **Step 3: Write the implementation**

In `engine/src/engine/loader.py`:

Update imports:

```python
from engine.entities.components import (
    Position, Sprite, Health, PhysicsComponent, Label, Tags, AIComponent, Mind
)
from engine.entities.persistence import load_entity_state
```

Change the signature:

```python
def load_world(world_dir: Path | str, memory_word_limit: int | None = None,
               facts_word_limit: int | None = None) -> WorldData:
```

After the constitution is parsed (right after `palette_used = constitution.get("palette_used", "")`), resolve limits:

```python
    # --- Word-limit resolution: CLI arg > constitution.yaml > default ---
    def _resolve(cli_val, const_key, default):
        if cli_val is not None:
            return int(cli_val)
        const_val = constitution.get(const_key)
        return int(const_val) if const_val is not None else default

    mem_limit = _resolve(memory_word_limit, "memory_word_limit", 60)
    facts_limit = _resolve(facts_word_limit, "facts_word_limit", 30)
```

In the agents loop, replace the `store.create(...)` block with one that builds and overlays a `Mind` and applies persisted goal:

```python
        for agent in (agents_raw or []):
            eid = agent.get("id", f"e_{len(store.all_ids())}")
            kind = agent.get("kind", "humanoid")
            x = int(agent.get("x", 0))
            y = int(agent.get("y", 0))
            name = agent.get("name", eid)
            behavior = agent.get("behavior", "wander_passive")
            sprite_name = _sprite_for_kind(kind)

            # Seed Mind from agents.yaml (facts may be a string or a list)
            facts_seed = agent.get("facts", "")
            if isinstance(facts_seed, list):
                facts_seed = " ".join(str(f) for f in facts_seed)
            mind = Mind(memory_word_limit=mem_limit, facts_word_limit=facts_limit)
            mind.set_facts(str(facts_seed))

            # Overlay persisted evolved state (wins over seed)
            goal = behavior
            state = load_entity_state(world_dir, eid)
            if state:
                goal = state.get("goal", goal)
                mind.set_memory(str(state.get("memory", "")))
                mind.set_facts(str(state.get("facts", mind.facts)))

            store.create(eid, kind, [
                Position(x, y),
                Sprite(sprite_name),
                Health(100.0, 100.0),
                PhysicsComponent(blocking=True),
                Label(name),
                Tags(["agent", kind]),
                AIComponent(agent_id=eid, goal=goal),
                mind,
            ])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd engine && uv run pytest tests/test_loader.py -v`
Expected: PASS (existing + 6 new).

- [ ] **Step 5: Commit**

```bash
git add engine/src/engine/loader.py engine/tests/test_loader.py
git commit -m "feat(engine): seed and overlay entity Mind in loader with configurable limits"
```

---

### Task 4: Ollama think loop — read/write memory, identity, persist

**Files:**
- Modify: `engine/src/engine/systems/ollama_ai.py`
- Test: `engine/tests/test_ollama_ai.py`

**Interfaces:**
- Consumes: `Mind` (Task 1), `save_entity_state` (Task 2).
- Produces: `OllamaAISystem(store, passability, model="llama3.2", think_interval=50, world_dir=None)`. Its prompt includes the entity's facts/memory + word limits; a decision's optional `memory`/`facts`/`set_goal` fields rewrite the components and (if `world_dir` set) write through to disk. New method `flush_all() -> None` saves every AI entity.

- [ ] **Step 1: Write the failing tests**

Append to `engine/tests/test_ollama_ai.py`:

```python
from engine.entities.components import Mind


@pytest.fixture
def store_with_mind():
    s = EntityStore()
    s.create("wanderer", "humanoid", [
        Position(5, 5),
        Label("Elara"),
        AIComponent(agent_id="wanderer", goal="explore"),
        Tags(["agent"]),
        PhysicsComponent(),
        Mind(memory="I passed the old well", facts="I am curious",
             memory_word_limit=60, facts_word_limit=30),
    ])
    return s


def _mock_decision(**fields):
    mock_response = MagicMock()
    mock_response.message.content = json.dumps({"action": "think",
                                                "thought": "hmm", **fields})
    return mock_response


@pytest.mark.asyncio
async def test_prompt_includes_memory_and_facts(store_with_mind, passability, tmp_path):
    sys = OllamaAISystem(store_with_mind, passability, world_dir=tmp_path)
    captured = {}

    async def fake_chat(*, model, messages):
        captured["prompt"] = messages[0]["content"]
        return _mock_decision()

    with patch("engine.systems.ollama_ai.ollama") as mock_ollama:
        mock_ollama.AsyncClient.return_value.chat = AsyncMock(side_effect=fake_chat)
        await sys.schedule_thinks(tick=50)
        await asyncio.sleep(0.1)
        await sys.drain_results()

    assert "I passed the old well" in captured["prompt"]
    assert "I am curious" in captured["prompt"]
    assert "60" in captured["prompt"] and "30" in captured["prompt"]


@pytest.mark.asyncio
async def test_decision_rewrites_memory_facts_goal_and_persists(store_with_mind, passability, tmp_path):
    sys = OllamaAISystem(store_with_mind, passability, world_dir=tmp_path)
    with patch("engine.systems.ollama_ai.ollama") as mock_ollama:
        mock_ollama.AsyncClient.return_value.chat = AsyncMock(
            return_value=_mock_decision(memory="I now recall the storm",
                                        facts="I fear lightning",
                                        set_goal="find shelter"))
        await sys.schedule_thinks(tick=50)
        await asyncio.sleep(0.1)
        await sys.drain_results()

    mind = store_with_mind.get_component("wanderer", Mind)
    ai = store_with_mind.get_component("wanderer", AIComponent)
    assert mind.memory == "I now recall the storm"
    assert mind.facts == "I fear lightning"
    assert ai.goal == "find shelter"
    # persisted to disk
    from engine.entities.persistence import load_entity_state
    assert load_entity_state(tmp_path, "wanderer")["goal"] == "find shelter"


@pytest.mark.asyncio
async def test_overlimit_memory_is_truncated(passability, tmp_path):
    s = EntityStore()
    s.create("w", "humanoid", [
        Position(1, 1), Label("W"), AIComponent(agent_id="w", goal="g"),
        Tags(["agent"]), PhysicsComponent(),
        Mind(memory_word_limit=3, facts_word_limit=3),
    ])
    sys = OllamaAISystem(s, passability, world_dir=tmp_path)
    with patch("engine.systems.ollama_ai.ollama") as mock_ollama:
        mock_ollama.AsyncClient.return_value.chat = AsyncMock(
            return_value=_mock_decision(memory="one two three four five"))
        await sys.schedule_thinks(tick=50)
        await asyncio.sleep(0.1)
        await sys.drain_results()
    assert s.get_component("w", Mind).memory == "one two three"


@pytest.mark.asyncio
async def test_flush_all_writes_every_ai_entity(store_with_mind, passability, tmp_path):
    sys = OllamaAISystem(store_with_mind, passability, world_dir=tmp_path)
    sys.flush_all()
    from engine.entities.persistence import load_entity_state
    state = load_entity_state(tmp_path, "wanderer")
    assert state is not None
    assert state["memory"] == "I passed the old well"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd engine && uv run pytest tests/test_ollama_ai.py -v -k "memory or facts or flush or overlimit"`
Expected: FAIL (`OllamaAISystem` has no `world_dir` param / no `flush_all`; prompt lacks memory).

- [ ] **Step 3: Write the implementation**

In `engine/src/engine/systems/ollama_ai.py`:

Add import near the top:

```python
from engine.entities.components import Position, Label, AIComponent, Tags, Mind
from engine.entities.persistence import save_entity_state
```

(The existing import line already pulls `Position, Label, AIComponent, Tags` — extend it with `Mind` and keep the rest.)

Replace the `_THINK_PROMPT` constant with:

```python
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
```

Update `__init__` to accept and store `world_dir`:

```python
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
```

In `_think`, after computing `nearby_str` and pulling `pending_whispers`, read the `Mind` and fill the new prompt fields. Replace the `prompt = _THINK_PROMPT.format(...)` call with:

```python
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
```

After `decision = json.loads(raw.strip())` succeeds (right before building `results`), apply identity/memory updates and write through:

```python
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
```

Add the `flush_all` method to the class:

```python
    def flush_all(self) -> None:
        """Persist every AI entity's current state (shutdown safety net)."""
        if self._world_dir is None:
            return
        for eid in self._store.all_ids():
            mind = self._store.get_component(eid, Mind)
            ai = self._store.get_component(eid, AIComponent)
            if mind is not None and ai is not None:
                save_entity_state(self._world_dir, eid, ai.goal, mind)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd engine && uv run pytest tests/test_ollama_ai.py -v`
Expected: PASS (existing 3 + 4 new).

- [ ] **Step 5: Commit**

```bash
git add engine/src/engine/systems/ollama_ai.py engine/tests/test_ollama_ai.py
git commit -m "feat(engine): entities read/rewrite memory+identity in think loop, persist changes"
```

---

### Task 5: Wire world_dir through the stack + CLI flags + gitignore

**Files:**
- Modify: `engine/src/engine/tick.py`, `engine/src/engine/server/app.py`, `engine/src/engine/__main__.py`, `.gitignore`
- Test: `engine/tests/test_tick.py`

**Interfaces:**
- Consumes: `OllamaAISystem(..., world_dir=...)` and `flush_all()` (Task 4).
- Produces: `TickLoop(..., world_dir=None)` forwards `world_dir` to `OllamaAISystem` and calls `flush_all()` in `stop()`. `create_app(..., world_dir=None)` forwards it. `__main__` adds `--memory-words`/`--facts-words` and passes `world_dir` end-to-end.

- [ ] **Step 1: Write the failing test**

Append to `engine/tests/test_tick.py`:

```python
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
    loop.stop()

    saved = json.loads((tmp_path / ".entities" / "guardian.json").read_text())
    assert saved["memory"] == "I saw a stranger"
    assert saved["facts"] == "I distrust strangers"
    assert saved["goal"] == "guard"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd engine && uv run pytest tests/test_tick.py::test_stop_flushes_entity_state_to_disk -v`
Expected: FAIL (`TickLoop.__init__` has no `world_dir`).

- [ ] **Step 3: Implement the wiring**

In `engine/src/engine/tick.py`, add `world_dir=None` to `TickLoop.__init__` (after `ai_model`):

```python
        frame_callback: Callable[[WRLFrame], Awaitable[None]],
        tick_interval: float = 0.1,
        ai_model: str = "llama3.2",
        world_dir=None,
    ):
```

Pass it to the AI system (change the `self._ollama_ai = ...` line):

```python
        self._ollama_ai = OllamaAISystem(store, passability, model=ai_model,
                                         think_interval=50, world_dir=world_dir)
```

Flush in `stop()`:

```python
    def stop(self) -> None:
        self._running = False
        self._ollama_ai.flush_all()
```

In `engine/src/engine/server/app.py`, add `world_dir=None` to `create_app`'s signature (after `ai_model`) and forward it to `TickLoop`:

```python
    ai_model: str = "llama3.2",
    world_dir=None,
) -> FastAPI:
```

```python
    tick_loop = TickLoop(
        store=store, passability=passability, palette=palette,
        tilemap_data=tilemap_data, world_id=world_id,
        width=width, height=height, frame_callback=on_frame,
        ai_model=ai_model, world_dir=world_dir,
    )
```

In `engine/src/engine/__main__.py`, add the CLI flags and thread values through. Add after the `--ai-model` argument:

```python
    parser.add_argument("--memory-words", type=int, default=None,
                        help="Override entity memory word limit (else constitution/default)")
    parser.add_argument("--facts-words", type=int, default=None,
                        help="Override entity identity-facts word limit")
```

Change the `load_world` call:

```python
    data = load_world(world_dir, memory_word_limit=args.memory_words,
                      facts_word_limit=args.facts_words)
```

Add `world_dir=world_dir` to the `create_app(...)` call (alongside `ai_model=args.ai_model`):

```python
        ai_model=args.ai_model,
        world_dir=world_dir,
    )
```

In `.gitignore` (repo root), add:

```
.entities/
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd engine && uv run pytest tests/test_tick.py -v`
Expected: PASS (existing + new flush test).

- [ ] **Step 5: Run the full engine suite**

Run: `cd engine && uv run pytest -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add engine/src/engine/tick.py engine/src/engine/server/app.py engine/src/engine/__main__.py engine/tests/test_tick.py .gitignore
git commit -m "feat(engine): thread world_dir + memory-limit flags through engine, flush on shutdown"
```

---

### Task 6: End-to-end verification against demo_world

**Files:** none (manual verification + optional demo seed).

- [ ] **Step 1: Seed a fact on the demo guardian (optional, for a nicer demo)**

Edit `demo_world/agents.yaml` — add a `facts:` line to one agent (e.g. the guardian):

```yaml
  facts: "I am the sentinel of the eastern ruins. I distrust strangers."
```

- [ ] **Step 2: Boot the engine on a spare port**

Run (from `engine/`, with `source ~/keys.sh` first if needed):

```bash
uv run illuvutar-engine ../demo_world --port 8099 --memory-words 40 --facts-words 20
```

Expected: `Uvicorn running on http://127.0.0.1:8099`.

- [ ] **Step 3: Let entities think, then confirm persistence appeared**

Wait ~30–60s (entities think every 50 ticks), then in another shell:

```bash
ls ../demo_world/.entities/
cat ../demo_world/.entities/*.json
```

Expected: one JSON per AI entity, each with `goal`, `memory`, `facts` fields; `memory`/`facts` within the word limits set on the CLI.

- [ ] **Step 4: Confirm memory feeds back into the prompt (continuity)**

```bash
curl -s http://127.0.0.1:8099/thoughts | tail -c 400
```

Expected: thoughts that reference remembered context over time (not fully stateless). Stop the server (Ctrl-C) and confirm `.entities/*.json` still present (shutdown flush).

- [ ] **Step 5: Restart and confirm memory survives**

Re-run Step 2's command; check `/thoughts` and the entity JSON reflect the *previously* evolved state (loaded from `.entities/`), proving cross-restart persistence.

- [ ] **Step 6: Commit any demo seed change**

```bash
git add demo_world/agents.yaml
git commit -m "chore(demo): seed guardian identity facts"
```

---

## Self-Review

**Spec coverage:**
- Word-budgeted memory the entity authors → Task 1 (`Mind.set_memory`) + Task 4 (`memory` field). ✓
- Identity facts, stored + editable → Task 1 (`Mind.set_facts`) + Task 4 (`facts`, `set_goal`); locked core has no writable field. ✓
- Configurable limits (CLI > constitution > default) → Task 3 (`_resolve`) + Task 5 (flags). ✓
- Persist across restart → Task 2 (persistence) + Task 3 (overlay) + Task 4 (write-through) + Task 5 (flush-on-stop). ✓
- Remove dead `memory_ref` → Task 1. ✓
- `.entities/` gitignored → Task 5. ✓
- Error handling (corrupt/atomic/best-effort/truncate) → Task 2 tests + `_truncate_words`. ✓

**Placeholder scan:** none — every code step has complete code.

**Type consistency:** `Mind.set_memory/set_facts -> bool`, `load_entity_state -> dict | None`, `save_entity_state(world_dir, id, goal, mind)`, `load_world(world_dir, memory_word_limit=None, facts_word_limit=None)`, `OllamaAISystem(..., world_dir=None)` + `flush_all()`, `TickLoop(..., world_dir=None)`, `create_app(..., world_dir=None)` — consistent across tasks.

**Deviation from spec (intentional):** persistence is write-through on change + `flush_all()` on shutdown, rather than a dirty-set + tick-debounce (simpler, same guarantee, rare writes). Shutdown uses the existing `@app.on_event`/`TickLoop.stop()` path, not a new lifespan handler (matches codebase).
