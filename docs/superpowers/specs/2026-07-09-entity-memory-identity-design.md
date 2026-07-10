# Entity Memory & Mutable Identity — Design

**Date:** 2026-07-09
**Status:** Approved (design)
**Scope:** engine (`engine/src/engine/…`)

## Goal

Give every AI entity in the simulation:

1. A **word-budgeted episodic memory** it authors itself (agentic).
2. **Facts about its own identity** it can accumulate and revise.
3. The ability to **edit some of its identity** (its goal and its self-facts),
   while a locked core (id, kind, name) stays fixed.

State persists across engine restarts so entities genuinely accumulate a history,
mirroring the god agent's persistent memory.

## The memory model: word budget, entity-curated

Memory and facts are **free-form text with a maximum word count** — *not* a
fixed-length queue of items. The engine never drops "the oldest item." Instead:

- Each tick the entity sees its current memory/facts text **and its word limit**.
- The entity may **rewrite** either blob to whatever it wants to keep — consolidating,
  dropping, rephrasing, adding — as long as it fits the budget.
- The engine's only enforcement is a hard cap: if submitted text exceeds the limit it
  is truncated to the first N words (safety net; the entity is told the limit and is
  expected to self-manage).

So the entity is "free to fit what it can" within the limit and owns the editorial
decisions. This is more agentic than FIFO and produces natural summarization.

### Configuring the word limits

The two limits are configurable, resolved with this precedence (first that is set wins):

1. **Engine CLI flags** — `--memory-words N`, `--facts-words N` (runtime override).
2. **`constitution.yaml`** — optional world-level keys `memory_word_limit`,
   `facts_word_limit` (persist with the world; a world can theme its beings' memory).
3. **Built-in defaults** — memory = 60 words, facts = 30 words.

The resolved values are applied uniformly to every entity's `Mind` at load. (Per-entity
overrides are out of scope — YAGNI.)

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
    memory: str = ""                 # episodic — "what happened", word-budgeted
    facts:  str = ""                 # self-beliefs — "who I am", word-budgeted
    memory_word_limit: int = 60
    facts_word_limit:  int = 30

    def set_memory(self, text: str) -> bool:
        """Replace memory with text, truncated to memory_word_limit words.
        Returns True if the stored value changed."""

    def set_facts(self, text: str) -> bool:
        """Replace facts with text, truncated to facts_word_limit words.
        Returns True if the stored value changed."""
```

- Word count = whitespace split; truncation keeps the first N words and rejoins with
  single spaces. Input is stripped; empty input clears the blob.
- Methods return whether they changed the stored value (drives the persistence dirty
  flag).
- The editable **goal** stays on `AIComponent.goal` (already read by the prompt).

`AIComponent.memory_ref` is removed.

### 2. Think loop — read & write (`ollama_ai.py`)

**Prompt gains a self/memory block** (read), built from the entity's `Mind` +
`AIComponent.goal` + `Label`, and it states the word limits so the model self-manages:

```
Who you are: {name}, a {kind}.
What you believe about yourself (identity, keep within {facts_word_limit} words):
  {facts or "nothing yet"}
Your goal: {goal}
What you remember (keep within {memory_word_limit} words, in your own words):
  {memory or "nothing yet"}

You may rewrite "memory" and "facts" to keep only what matters within the limits.
```

**Decision JSON gains three optional fields** (write):

```jsonc
{ "action": "...", "thought": "...",
  "memory":   "the full text I want to remember (<= 60 words)",  // → Mind.set_memory()
  "facts":    "my identity beliefs (<= 30 words)",                // → Mind.set_facts()
  "set_goal": "a new goal (replaces current)" }                   // → AIComponent.goal
```

- Each field is a **wholesale replacement** of that blob (not an append), so the entity
  curates. Absent field = leave that blob unchanged. Over-limit text is truncated by
  the component.
- Locked fields (id/kind/name) have no JSON field, so they can't be edited.
- Applying mutations: `_think` already reads store components after its single `await`
  (the ollama call). In this cooperative single-threaded asyncio model, nothing else
  runs between that await returning and `_think` finishing, so `_think` applies the
  mutations **directly** to the entity's `Mind`/`AIComponent` and records the entity id
  in `self._dirty: set[str]` for persistence. `set_goal` replaces the goal verbatim
  (trimmed, ignored if empty).
- The existing fallback (parse/network failure → idle thought) leaves memory/identity
  untouched.

### 3. Persistence

```
world_dir/
  agents.yaml          ← seed (unchanged file, one new optional key)
  .entities/
    <id>.json          ← evolved state: { "goal", "memory": "", "facts": "" }
```

New module `engine/entities/persistence.py`:

```python
def load_entity_state(world_dir, entity_id) -> dict | None
def save_entity_state(world_dir, entity_id, goal: str, mind: Mind) -> None
```

- **Startup (loader):** `load_world` resolves the word limits (CLI override →
  `constitution.yaml` → defaults) and accepts them as `memory_word_limit` /
  `facts_word_limit` args. It builds each entity from `agents.yaml`, constructs its
  `Mind` **with the resolved limits** (seeding `facts` from an optional `facts:` key —
  string, or a list joined into text), then, if `.entities/<id>.json` exists, **overlay**
  it — persisted `goal`/`memory`/`facts` win over the seed. Overlaid blobs are
  re-truncated to the resolved word limits on load.
- **Config flow:** `engine/__main__.py` parses `--memory-words` / `--facts-words`
  (default `None` = "not set"), passes them to `load_world`, which reads
  `constitution.yaml` for world-level values and falls back to the built-in defaults.
  The resolved integers are what land on every `Mind`.
- **Save:** `OllamaAISystem` flushes every entity in `self._dirty` on a debounce — once
  per `_think` scheduling pass (every `think_interval` ticks) — and a full flush of all
  AI entities on shutdown.
- **Shutdown hook:** `engine/server/app.py` calls the AI system's `flush_all()` via a
  lifespan handler (replacing the deprecated `@app.on_event("shutdown")`).
- `.entities/` is added to the repo `.gitignore` (runtime state, not source).

### 4. `agents.yaml` seed extension

One new **optional** key per agent; existing files stay valid. `facts` may be a string
or a list (a list is joined into a single text blob):

```yaml
- id: guardian
  kind: guardian
  name: The Sentinel
  x: 5
  y: 5
  behavior: guard the ruins     # → AIComponent.goal (as today)
  facts: "I distrust strangers. I am sworn to the eastern ruins."   # NEW, optional
```

## Components & boundaries

| Unit | Responsibility | Depends on |
|------|----------------|------------|
| `Mind` (component) | Hold memory/facts text; enforce word limits | nothing |
| `persistence.py` | Serialize/deserialize evolved state to `.entities/<id>.json` | `Mind` |
| `loader.py` | Seed entity, overlay persisted state | `Mind`, `persistence`, `agents.yaml` |
| `OllamaAISystem` | Build prompt from `Mind`, parse/apply updates, track dirty, flush | `Mind`, `persistence` |
| `app.py` | Flush-all on shutdown | `OllamaAISystem` |

## Error handling

- Corrupt/unreadable `.entities/<id>.json` → ignored (fall back to seed), logged once.
- `save_entity_state` writes atomically (temp file + rename) so a crash mid-write can't
  corrupt state; failures are swallowed (best-effort persistence, never crash the tick
  loop).
- Malformed decision JSON → existing idle-thought fallback; no state change.
- Over-limit memory/facts (from the model or an overlaid file) → truncated to the word
  limit by the component.

## Testing (TDD)

- **`Mind`:** `set_memory`/`set_facts` truncate to the word limit; under-limit text kept
  verbatim; empty input clears; change-flag return is correct.
- **`persistence`:** save→load round-trip; missing file → `None`; corrupt file → `None`;
  atomic write leaves no partial file on simulated failure.
- **`loader`:** seeds `facts` from `agents.yaml` (string and list forms); overlays
  `.entities/<id>.json` over seed; re-truncates over-limit overlay; absent `facts:` key
  still valid.
- **Config resolution:** CLI arg wins over `constitution.yaml`; `constitution.yaml`
  wins over the built-in default; resolved limits land on every entity's `Mind`.
- **`OllamaAISystem` (mocked ollama):** prompt contains memory + facts + the word
  limits; a decision with `memory`/`facts`/`set_goal` replaces the components and marks
  dirty; over-limit `memory` is truncated; fallback path leaves state untouched;
  `flush_all` writes every AI entity.

## Out of scope (YAGNI)

- Editing name/kind/id by the entity.
- Semantic retrieval / embeddings over memory (it's a small word-budgeted blob in the
  prompt).
- Sharing memory between entities.
- Automatic engine-side summarization (the entity does its own compaction).
