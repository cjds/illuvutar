# Entity Memory & Mutable Identity — Design

**Date:** 2026-07-09
**Status:** Approved (design)
**Scope:** engine (`engine/src/engine/…`)

## Goal

Give every AI entity in the simulation:

1. A **limited-size episodic memory** it fills itself (agentic).
2. **Facts about its own identity** it can accumulate.
3. The ability to **edit some of its identity** (its goal and its self-facts),
   while a locked core (id, kind, name) stays fixed.

State persists across engine restarts so entities genuinely accumulate a history,
mirroring the god agent's persistent memory.

## Current state (what exists today)

- Entities load from `world_dir/agents.yaml` in `engine/loader.py`; each gets an
  `AIComponent(agent_id, goal, memory_ref="")`. **`memory_ref` is declared but
  unused** — dead code, removed by this work.
- `OllamaAISystem._think` (`engine/systems/ollama_ai.py`) is **stateless**: every
  `think_interval` ticks it rebuilds a prompt from name/kind/goal/position/nearby/
  whispers and returns a decision. Entities remember nothing and have no self beyond
  name/kind/goal/tags.
- Locked identity is already modeled: `id` (store key), `kind` (`store.kind`),
  `name` (`Label`).

## Design

### 1. `Mind` component

One cohesive component holds the entity's mutable inner life
(`engine/entities/components.py`):

```python
@dataclass
class Mind:
    memory: list[str] = field(default_factory=list)   # episodic — "what happened"
    facts:  list[str] = field(default_factory=list)   # self-beliefs — "who I am"
    memory_capacity: int = 10
    facts_capacity:  int = 5

    def remember(self, note: str) -> bool:
        """Append an episodic note; FIFO-trim to capacity. Returns True if changed."""

    def add_fact(self, fact: str) -> bool:
        """Append a self-belief; dedup; FIFO-trim to capacity. Returns True if changed."""
```

- Both methods strip input, ignore empties, return whether they mutated (drives the
  persistence dirty flag).
- `remember`: plain FIFO — oldest note drops when over `memory_capacity`.
- `add_fact`: dedup (skip if already present), then FIFO-trim to `facts_capacity`.
- The editable **goal** stays on `AIComponent.goal` (already read by the prompt).

`AIComponent.memory_ref` is removed.

### 2. Think loop — read & write (`ollama_ai.py`)

**Prompt gains a self/memory block** (read), built from the entity's `Mind` +
`AIComponent.goal` + `Label`:

```
Who you are: {name}, a {kind}.
What you believe about yourself: {facts joined by " | " or "nothing yet"}
Your goal: {goal}
What you remember: {memory joined by " | " or "nothing yet"}
```

**Decision JSON gains three optional fields** (write):

```jsonc
{ "action": "...", "thought": "...",
  "remember": "a short note to keep in memory",   // → Mind.remember()
  "add_fact": "a lasting belief about myself",     // → Mind.add_fact()
  "set_goal": "a new goal (replaces current)" }    // → AIComponent.goal
```

- Locked fields (id/kind/name) have no JSON field, so they can't be edited.
- Applying mutations: `_think` already reads store components after its single
  `await` (the ollama call). In this cooperative single-threaded asyncio model,
  nothing else runs between that await returning and `_think` finishing, so `_think`
  applies the mutations **directly** to the entity's `Mind`/`AIComponent` and records
  the entity id in a `self._dirty: set[str]` for persistence. `set_goal` replaces the
  goal verbatim (trimmed, ignored if empty).
- The existing fallback (parse/network failure → idle thought) leaves memory/identity
  untouched.

### 3. Persistence

```
world_dir/
  agents.yaml          ← seed (unchanged file, one new optional key)
  .entities/
    <id>.json          ← evolved state: { "goal", "memory": [], "facts": [] }
```

New module `engine/entities/persistence.py`:

```python
def load_entity_state(world_dir, entity_id) -> dict | None
def save_entity_state(world_dir, entity_id, goal: str, mind: Mind) -> None
```

- **Startup (loader):** build the entity from `agents.yaml`, construct its `Mind`
  (seeding `facts` from an optional `facts:` list in the agent entry), then, if
  `.entities/<id>.json` exists, **overlay** it — persisted `goal`/`memory`/`facts`
  win over the seed. Capacities stay at the component defaults; overlaid lists are
  trimmed to capacity on load.
- **Save:** `OllamaAISystem` flushes every entity in `self._dirty` on a debounce —
  once per `_think` scheduling pass (every `think_interval` ticks) — and a full flush
  of all AI entities on shutdown.
- **Shutdown hook:** `engine/server/app.py` exposes an async shutdown that calls the
  AI system's `flush_all()`. (Replaces the deprecated `@app.on_event("shutdown")`
  with a lifespan handler.)
- `.entities/` is added to the repo `.gitignore` (runtime state, not source).

### 4. `agents.yaml` seed extension

One new **optional** key per agent; existing files stay valid:

```yaml
- id: guardian
  kind: guardian
  name: The Sentinel
  x: 5
  y: 5
  behavior: guard the ruins     # → AIComponent.goal (as today)
  facts:                        # NEW, optional — initial self-beliefs
    - I distrust strangers
```

## Components & boundaries

| Unit | Responsibility | Depends on |
|------|----------------|------------|
| `Mind` (component) | Hold + cap memory and facts | nothing |
| `persistence.py` | Serialize/deserialize evolved state to `.entities/<id>.json` | `Mind` |
| `loader.py` | Seed entity, overlay persisted state | `Mind`, `persistence`, `agents.yaml` |
| `OllamaAISystem` | Build prompt from `Mind`, parse/apply updates, track dirty, flush | `Mind`, `persistence` |
| `app.py` | Flush-all on shutdown | `OllamaAISystem` |

## Error handling

- Corrupt/unreadable `.entities/<id>.json` → ignored (fall back to seed), logged once.
- `save_entity_state` writes atomically (temp file + rename) so a crash mid-write
  can't corrupt state; failures are swallowed (best-effort persistence, never crash
  the tick loop).
- Malformed decision JSON → existing idle-thought fallback; no state change.
- Over-capacity overlaid lists → trimmed on load.

## Testing (TDD)

- **`Mind`:** `remember` FIFO cap; `add_fact` dedup + cap; empties ignored; return flags.
- **`persistence`:** save→load round-trip; missing file → `None`; corrupt file → `None`;
  atomic write leaves no partial file.
- **`loader`:** seeds `facts` from `agents.yaml`; overlays `.entities/<id>.json` over
  seed; trims over-capacity overlay; absent `facts:` key still valid.
- **`OllamaAISystem` (mocked ollama):** prompt contains memory + facts; a decision with
  `remember`/`add_fact`/`set_goal` mutates the components and marks dirty; fallback path
  leaves state untouched; `flush_all` writes every AI entity.

## Out of scope (YAGNI)

- Removing/replacing a specific fact (add-only with aging is enough).
- Editing name/kind/id by the entity.
- Semantic retrieval / embeddings over memory (it's a small FIFO in the prompt).
- Sharing memory between entities.
