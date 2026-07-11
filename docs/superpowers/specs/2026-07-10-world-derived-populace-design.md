# World-Derived, Model-Independent Populace — Design

**Date:** 2026-07-10
**Status:** Approved (design)
**Scope:** `illuvutar/` (god world-gen) + a small `engine/` schema change

## Goal

Replace the fixed 20-job catalog with a world-authored, unbiased populace, generated
by a focused specialist through a model-independent LLM interface:

1. **No baked catalog.** The god derives the roles that exist from its own world
   (`constitution`/`tone`) and writes `roles.yaml`. A desert world gets ash-scavengers
   and water-priests, not blacksmiths.
2. **People can hold multiple roles** (1–3), drawn and combined from `roles.yaml`.
3. **A populace specialist** — not the god's main loop — writes the people, given the
   world + roles.
4. **Model-independent.** The god and the specialist talk to any OpenAI-compatible
   endpoint (local ollama, vLLM, or a hosted API), chosen by config. No code assumes a
   model or provider.

Reliability comes from the capable model the operator points at, plus deterministic
placement and a fallback so generation never writes garbage.

## Decisions (from brainstorming)

- Roles are **god-authored per world** (world-derived, so unbiased-but-coherent).
- Generation is **god + one populace specialist** (focused sub-agent, not the god juggling
  everything).
- Backend is **any OpenAI-compatible endpoint**, config-driven, default local ollama.
- The god keeps **tool-calling** (needs a tool-capable endpoint); the **specialist is
  tool-free** (pure JSON generation) for maximum portability.
- This **supersedes** the fixed catalog (`jobs.py`) and the `populate_town` count-coercion
  fix — the coercion folds into the new tool.

## Current state (what changes)

- `src/illuvutar/generation/jobs.py` — the fixed `JOBS` catalog + name pools. **Deleted.**
- `src/illuvutar/generation/populace.py` — `generate_populace(jobs, …)` draws from `JOBS`;
  per-NPC `ollama.chat`. **Reworked** to role-based, batched, client-based.
- `src/illuvutar/agents/tools.py` — `populate_town` uses `JOBS[:count]`. **Replaced** by
  `populate_world`. `AgentTools` gains the LLM client.
- `src/illuvutar/agents/god.py` / `specialist.py` — call `ollama.chat` directly.
  **Switched** to the client. God prompt updated (author roles → populate).
- `src/illuvutar/cli.py` — construct the client from CLI/env; pass to god + tools.
- `engine` `Profile(job: str, backstory)` — **`job: str` → `roles: list[str]`**; loader,
  think-prompt, and `/profile` carry roles (with back-compat for old `job`).

## Design

### 1. Model-independent LLM client (`src/illuvutar/llm/`)

`LLMClient` wraps the standard OpenAI chat/tools API (the `openai` SDK, added as a
dependency). It works against **any** OpenAI-compatible base URL — local ollama exposes
`/v1`, as do vLLM and hosted providers — and the existing `AgentTools.definitions()`
are already in OpenAI function-tool shape.

```python
class LLMClient:
    def __init__(self, endpoint: str, model: str, api_key: str | None = None): ...
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMMessage:
        """Returns a normalized message: .content (str) and .tool_calls
        (list of objects with .function.name and .function.arguments as a dict)."""
```

- **Normalization:** the client maps the OpenAI response (`choices[0].message`,
  `tool_calls[].function.arguments` as a JSON string) to the shape the god's `_run_loop`
  already consumes (`msg.content`, `tc.function.name`, `tc.function.arguments` as a dict),
  so the orchestration logic is unchanged.
- **Config precedence:** CLI flag → env (`ILLUVUTAR_LLM_ENDPOINT`, `_MODEL`, `_API_KEY`)
  → defaults (`http://localhost:11434/v1`, model from `--model`, api_key `"ollama"`).
- **JSON extraction helper:** `parse_json(text) -> dict | None` that strips code fences and
  tolerates the ways different models wrap JSON — no model-specific assumptions.
- **Nothing else in the codebase imports a provider SDK directly** for the god path.
  (The engine's per-tick `ollama_ai` stays on ollama for now; it can adopt this client
  later — out of scope.)

### 2. God authors roles (`roles.yaml`)

No new tool needed — the god writes `roles.yaml` with the existing `write_world_state`.
Its Phase-3 prompt is updated to: after WFC, **derive the roles this world needs from the
constitution and write `roles.yaml`**, then call `populate_world`.

```yaml
roles:
  - id: ash-scavenger
    title: Ash-scavenger
    locale: The Dunes            # free text; best-effort matched to a region name
    blurb: sifts the grey drifts for buried metal
  - id: water-priest
    title: Water-priest
    locale: The Last Cistern
    blurb: rations the town's water and keeps its rites
```

No biome enum, no fixed professions — the set is whatever the god's world implies.

### 3. Populace specialist (`populate_world` tool + reworked `populace.py`)

`AgentTools.populate_world(count: int = 40)` **is** the specialist. It reads
`constitution`, `regions`, `tilemap`, and `roles.yaml`, then calls the reworked
`generate_populace(...)`, and writes `agents.yaml`.

- **Errors clearly** (no partial write) if `tilemap` or `roles.yaml` is missing.
- **`count` coercion** (folds in the dropped fix): `int(count)`, clamp `≥ 1`; a sane
  upper clamp (e.g. 1000) to avoid runaway. No 20-cap — roles repeat and combine.

`generate_populace(roles, tilemap, regions, walkable_tile_ids, client, world_name,
world_tone, count, batch_size=12) -> list[dict]`:

- **Batched generation for scale.** Hundreds of per-NPC calls is too slow; instead the
  specialist generates people in batches of ~12 via **one tool-free client call per batch**
  that returns a JSON array. 300 people ≈ ~25 calls, not 300. (Trades a little per-NPC
  depth for the ability to reach hundreds — acceptable per goal.)
- **Role assignment (coherence + coverage):** the tool pre-assigns each slot a **primary
  role** round-robin over `roles.yaml` (guarantees coverage), and asks the model to give
  each person their name, **0–2 additional roles from the list**, backstory, goal, and
  self-facts. The model owns the creative content; the tool owns coverage and placement.
- **Deterministic placement (unbiased):** each person's primary role `locale` is matched
  to a region by name (best-effort); a walkable cell in that region is chosen, unique and
  spread; fallback to any walkable cell. No hardcoded biome→role mapping.
- **Fallback:** on a malformed/absent batch or field, fill deterministically — a generic
  name from a small built-in syllable generator (not job-specific), a stock backstory from
  the role blurb, goal from the blurb, facts = "I am {name}, {roles}." Never raises; always
  returns exactly `count` valid entries.
- **Unique ids:** generated sequentially (`e_0`, `e_1`, …) — roles are no longer unique, so
  ids can't be role-derived. `kind` defaults to `humanoid` (existing sprite); no biased
  role→sprite mapping.

Output entry:

```yaml
- id: e_0
  kind: humanoid
  x: 12
  y: 5
  name: Vela Cistern
  roles: [water-priest, midwife]
  backstory: "..."
  behavior: "keep the cistern's ledger and its rites"   # goal
  facts: "I am Vela, water-priest and midwife."
```

### 4. Engine: multi-role `Profile`

- `Profile(job: str, backstory)` → **`Profile(roles: list[str] = [], backstory: str = "")`**.
- **Loader:** read `roles` (list). Back-compat: an old `job` string becomes `[job]`; absent
  → `[]`.
- **Think-prompt (`ollama_ai`):** the identity line's `role=` becomes the joined roles
  (`role=water-priest, midwife`); backstory unchanged.
- **`/entity/{id}/profile`:** returns `roles` (list) **and** `job` = `", ".join(roles)` for
  the existing browser panel, so the click-to-read UI needs no change.

## Components & boundaries

| Unit | Responsibility | Depends on |
|------|----------------|------------|
| `llm/client.py` | Model-independent chat/tools + JSON parse | `openai` SDK |
| `god.py` | Orchestrate build via tools; author roles | `LLMClient`, `AgentTools` |
| `populace.py` | Batched role-based generation + placement + fallback | `LLMClient` |
| `tools.populate_world` | Wire world files + roles → `populace` → `agents.yaml` | `populace` |
| `cli.py` | Build client from config; wire god + tools | `LLMClient` |
| `Profile` (engine) | Hold roles + backstory | nothing |

## Error handling

- Missing `roles.yaml`/`tilemap` → clear error from `populate_world`, no write.
- Malformed batch JSON / missing fields → per-slot deterministic fallback; never raises.
- `count` non-int or out of range → coerced/clamped.
- Endpoint unreachable / auth error → surfaced as a clear message from the client (the god
  sees a tool/among-turn error, not a crash).
- Weak endpoint without tool support → the **god** may stumble (documented; use a
  tool-capable model); the **specialist** is tool-free so it degrades to fallback content
  rather than failing.
- Old worlds (`job` string, or no roles) load unchanged via back-compat.

## Testing

- **`LLMClient`:** normalizes an OpenAI-shaped response to `.content` + `.tool_calls`
  (arguments as dict); config precedence CLI→env→default; `parse_json` strips fences and
  handles wrapped JSON. (Mock the SDK / HTTP; no live calls.)
- **`populace`:** batched generation with a mocked client → `count` people, each with
  `roles` (1–3, from the role set), name/backstory/goal/facts; primary-role coverage;
  placement on walkable tiles matched to the role locale; malformed batch → fallback still
  yields `count` valid entries; string/oversized `count` handled; unique ids.
- **`populate_world`:** errors without `roles.yaml`/`tilemap`; writes `agents.yaml` with
  `roles` + backstory.
- **god:** prompt instructs authoring `roles.yaml` then `populate_world`; god loop works
  through the client (mocked) end to end for a small build.
- **engine `Profile`:** loader builds `roles` from a list and from a legacy `job` string;
  prompt includes joined roles; `/profile` returns `roles` and a joined `job`.

## Migration & cleanup

- Delete `src/illuvutar/generation/jobs.py` and `tests/test_jobs.py`.
- Rework `populace.py` + its tests to the role model.
- `agents.yaml` schema: `job` → `roles`; loader accepts both.
- Add `openai` to `pyproject.toml` dependencies.

## Out of scope (YAGNI)

- Switching the engine's per-tick NPC thinking to the new client (it can, later).
- Per-district specialists (one populace specialist for now).
- Role→sprite mapping (default `humanoid`).
- A UI to edit roles/people (the god + `write_world_state` suffice).
- Streaming/parallel batch generation (sequential batches are enough).
