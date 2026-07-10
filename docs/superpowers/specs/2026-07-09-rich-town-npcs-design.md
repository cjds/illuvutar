# Rich Town of Job-Holding NPCs with Readable Backstories — Design

**Date:** 2026-07-09
**Status:** Approved (design)
**Scope:** `illuvutar/` (god world-gen) + `engine/` (loading, prompt, reading/interaction)

## Goal

Make the world the god creates feel lived-in instead of barren. The god populates
its world with **~20 NPCs, one per job** from a fixed catalog, each with a generated
**backstory**. Other characters — and the human — can **read** an NPC's backstory and
**interact** with them, with the NPC responding in character. Reuses the entity
memory/identity system already shipped (backstory feeds the think-prompt; `/whisper`
is the interaction channel).

Decisions locked in brainstorming:
- **Generation lives in the god path** (a new `populate_town` capability). No changes to
  the demo world; the engine-side reading/interaction works on any world that carries
  the new schema keys.
- **Per-NPC generation** (one focused LLM call each) **with a deterministic template
  fallback**, so a malformed/absent LLM response never breaks the town.
- **Town = population + job-sites** using existing tiles/regions. No procedural
  architecture.
- **Reading/interaction reuses the memory/identity system**: seed facts + a readable
  backstory, a profile endpoint, a click-to-read browser panel, and existing `/whisper`.

## Current state

- The god (`illuvutar create-world`) writes constitution → regions → runs WFC
  (`AgentTools.run_wfc`) → can `write_world_state`/`spawn_specialist`. Nothing guides it
  to populate a town; `agents.yaml` is typically tiny or absent.
- `engine/loader.py` reads `agents.yaml` entries `{id, kind, x, y, name, behavior, facts?}`
  into components (incl. `Mind` from the memory feature). It does **not** read job/backstory.
- `OllamaAISystem._think` prompts with name/kind/goal/facts/memory. `GET /thoughts` and
  `POST /entity/{id}/say` (whisper) already exist. The renderer shows a thought feed and
  an entity tooltip; it fetches `/thoughts`.

## Design

### Part A — The job catalog (`illuvutar/`)

New `illuvutar/src/illuvutar/generation/jobs.py`:

```python
@dataclass(frozen=True)
class Job:
    id: str            # "blacksmith"
    title: str         # "Blacksmith"
    site: str          # "Forge Lane" — named place shown in prompts/backstory
    biome: str         # region biome this job prefers: grassland|forest|water|ruins
    blurb: str         # "shapes iron and steel for the town"

JOBS: list[Job] = [ ... 20 entries ... ]
```

Twenty jobs, spread across the four verdant biomes so placement has somewhere to land:

- **grassland / town (14):** blacksmith, carpenter, baker, brewer, innkeeper, merchant,
  weaver, tanner, healer, priest, scribe, watchman, midwife, potter
- **forest (3):** hunter, forester, herbalist
- **water (2):** fisher, ferryman
- **ruins (1):** scholar

Invariants (tested): 20 entries, unique ids, every field non-empty, every `biome` is one
of the four.

### Part B — Populace generation (`illuvutar/`)

New `illuvutar/src/illuvutar/generation/populace.py`:

```python
def generate_populace(
    jobs: list[Job],
    tilemap: list[dict],          # [{x,y,tile_id,region}, ...]
    regions: list[dict],          # regions.yaml 'regions'
    walkable_tile_ids: set[str],  # tile_ids an entity may stand on
    model: str,
    facts_word_limit: int = 30,
    backstory_word_limit: int = 60,
) -> list[dict]:
    """One agent dict per job. Deterministic placement + per-NPC LLM call with fallback.
    Returns entries: {id, kind, x, y, name, job, backstory, behavior, facts}."""
```

Per job:
1. **Placement (deterministic):** map the job's `biome` to the region(s) with that biome;
   collect that region's `walkable` tilemap cells; pick one, spreading NPCs out (e.g.
   round-robin / farthest-from-used). If the biome has no walkable cell, fall back to any
   walkable cell in the map. Positions are unique per NPC.
2. **LLM call (per NPC, focused):** ask `model` for JSON
   `{name, backstory, goal, facts}` given the job title/site/blurb + world name/tone.
   `backstory` truncated to `backstory_word_limit` words; `facts` to `facts_word_limit`.
3. **Fallback (deterministic):** on any parse/network failure or missing field, fill from
   templates — name from a per-job name pool, `backstory` a stock line
   (`"{name} has worked as the {title} of {site} for many years."`), `goal` from the
   blurb, `facts` = `"I am {name}, the {title}."`. **The function never raises and always
   returns exactly `len(jobs)` valid entries.**
4. **kind:** mapped from job to an existing sprite kind (default `"humanoid"`; reuse
   `scholar`/`guardian` where they fit) — no new sprites (YAGNI).

Ids are the job id, de-duplicated if a job repeats (won't, ids are unique).

### Part C — The `populate_town` god tool (`illuvutar/`)

Add to `AgentTools` (`agents/tools.py`) a method + `definitions()` entry:

```python
def populate_town(self, count: int = 20) -> str:
    """Populate agents.yaml with job-holding NPCs. Requires tilemap.json (run WFC first)."""
```

- Reads `tilemap` and `regions` via `self.writer`; errors clearly if tilemap is missing
  ("run_wfc first").
- Derives `walkable_tile_ids` from the palette tiles' tags (a tile is walkable if none of
  its tags map to a blocked class — same tag set the engine loader uses:
  blocked/impassable/structure/high/void/water → not walkable).
- Calls `generate_populace(JOBS[:count], ...)` and `self.writer.write("agents", entries)`.
- Returns a summary (`"Populated 20 NPCs across the town."`).

Model: `AgentTools` gains a `model` field (the god's model) so it can drive per-NPC
generation. Wired in `cli.py` where `AgentTools(...)` is constructed.

**God guidance:** extend `GOD_SYSTEM_PROMPT` Phase 3 to instruct: after WFC, call
`populate_town` to bring the world to life, then review the result.

### Part D — Engine: load, prompt, expose (`engine/`)

1. **`Profile` component** (`entities/components.py`):
   ```python
   @dataclass
   class Profile:
       job: str = ""
       backstory: str = ""
   ```
   Backstory is longer-form, so it lives here — not in the word-capped `Mind.facts`.

2. **Loader** (`loader.py`): read optional `job`/`backstory` from each `agents.yaml`
   entry into a `Profile` component (absent → empty `Profile`). Existing worlds stay valid.

3. **Think-prompt** (`ollama_ai.py`): when an entity has a non-empty `Profile`, add its
   job and backstory as static context lines, so it answers in character. Plugs directly
   into the memory/identity prompt block already there.

4. **Profile endpoint** (`server/app.py`):
   ```
   GET /entity/{entity_id}/profile
   → 200 {"id", "name", "job", "backstory", "facts", "goal"}   # from Label/Profile/Mind/AIComponent
   → 404 if the entity does not exist
   ```

### Part E — Reading in the browser (`engine/renderer/`)

A light **click-to-read profile panel** (reusing the existing thought-panel styling, not a
redesign):
- Clicking an entity's tile fetches `/entity/{id}/profile` and shows a panel with
  **name — job** and the **backstory** (plus current goal). A close/click-away dismisses it.
- "Interact" is the existing `/whisper` (TUI) / player `say`; no new interaction channel.
- Implementation detail (walk the actual renderer files at build time): reuse the entity
  screen-position mapping the tooltip already uses to hit-test the click.

## Components & boundaries

| Unit | Responsibility | Depends on |
|------|----------------|------------|
| `jobs.py` | The fixed 20-job catalog | nothing |
| `populace.py` | Per-NPC placement + LLM/fallback generation | `jobs`, ollama |
| `AgentTools.populate_town` | Wire catalog+populace to world files; walkability | `populace`, writer, palette |
| god prompt | Tell the god to call `populate_town` after WFC | — |
| `Profile` (component) | Hold job + backstory | nothing |
| `loader` | Build `Profile` from `agents.yaml` | `Profile` |
| `ollama_ai` | Put job/backstory in the prompt | `Profile` |
| `app.py` | `/entity/{id}/profile` | `Profile`, `Mind`, `Label`, `AIComponent` |
| renderer | Click-to-read panel | profile endpoint |

## Error handling

- LLM failure/garbage per NPC → deterministic template fallback; `generate_populace`
  never raises and always returns exactly N valid, uniquely-placed NPCs.
- `populate_town` before WFC → clear error string (no tilemap), no partial write.
- Region/biome with no walkable cells → fall back to any walkable cell; if the map has no
  walkable cell at all, error clearly.
- Loader with absent `job`/`backstory` → empty `Profile`; existing worlds unaffected.
- Profile endpoint for unknown entity → 404.

## Testing

- **`jobs`:** 20 unique ids; all fields present; biomes valid.
- **`populace`:** with mocked ollama returning valid JSON → N NPCs, all fields, backstory
  ≤ limit; with ollama raising / returning garbage → fallback fills, still N valid NPCs;
  placements are on `walkable` tiles, unique, and biased to the job's biome region; ids
  unique.
- **`populate_town`:** errors without tilemap; with a small fixture world writes
  `agents.yaml` carrying `job`/`backstory`; derives walkability from palette tags.
- **`loader`:** builds `Profile` from job/backstory; absent keys → empty Profile; other
  loading unaffected.
- **`ollama_ai`:** prompt contains job + backstory when Profile present (mock ollama).
- **`app`:** `/entity/{id}/profile` returns the documented shape; 404 for unknown id.
- **Renderer:** manual (click an NPC → panel shows name/job/backstory).

## Verification

- Unit tests across both projects (`cd engine && uv run pytest`, root `uv run pytest`).
- Engine/browser path driven by a **temporary hand-authored world** (a small `agents.yaml`
  with `job`/`backstory`) — boot the engine, hit `/entity/<id>/profile`, click an NPC.
  (No committed demo-world changes, per scope.)
- God path: an optional live `illuvutar create-world` smoke run (slow on CPU ollama) to
  confirm `populate_town` writes a full `agents.yaml`; fallback guarantees success even if
  the model output is poor.

## Out of scope (YAGNI)

- Procedural building architecture (walls/interiors).
- New per-job sprites (reuse existing humanoid/scholar/guardian).
- A dialogue-tree subsystem (interaction stays on `/whisper` + the think loop).
- Updating the committed demo world.
- NPC-to-NPC relationship graphs beyond what a backstory mentions.

## Suggested phasing (for the plan)

Two coherent groups; engine-side is independently testable via a hand-authored world:
1. **Engine substrate:** `Profile` component → loader → prompt → profile endpoint →
   browser panel.
2. **God generation:** `jobs` catalog → `populace` generator → `populate_town` tool +
   `AgentTools.model` wiring → god prompt guidance.
