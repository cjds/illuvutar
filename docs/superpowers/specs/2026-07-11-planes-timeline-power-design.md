# Deeper Worlds — Planes, Timeline & Power — Design

**Date:** 2026-07-11
**Status:** Approved (design; scope calls delegated)
**Scope:** `illuvutar` (god generation) + `engine` (entity attributes)

## Goal

Expand the lore the god can conceive and generate, so its worlds have depth along three
axes, and so the inhabitants *embody* that depth in identity and behavior:

1. **Planes** — multiple realms (material, spirit, underworld, dream, celestial, …), each
   with its own nature; every being has a home plane.
2. **Timeline** — a full arc from deep past → present → prophesied future; every being is
   anchored to an era and references what came before and what is foretold.
3. **Power** — beings span tiers from mortal to primordial; power shapes who they are and
   what they can do.

This is a **lore + attribute layer**: the god authors it, `populate_world` assigns it,
and the engine carries it into each being's prompt and profile. It reuses the
world-derived-populace pipeline and the memory/identity system already shipped.

## Scope call (delegated)

Build the layer that lets the god **generate** and entities **embody** planes/eras/power —
NOT the heavier simulation of inter-plane travel, time-travel, or power combat. Those are
explicit follow-ups the layer enables. The sim still renders one playable map (the
material plane) this increment.

## Current state

- The god writes world-state files: `constitution`, `regions`, `factions`, `history`
  (already era-tagged!), `palette`, `roles`, `agents`, `meta`, `tilemap`. It authors them
  via `write_world_state` / dedicated tools; `populate_world` generates the populace from
  `roles.yaml`.
- Engine: each agent loads a `Profile(roles, backstory)` + `Mind` (memory/facts); the
  think-prompt states name/kind/roles/backstory/facts/memory; `/entity/<id>/profile`
  returns them.
- Nothing models planes, a forward timeline, or power.

## Design

### The three new/extended world files (god-authored)

**`planes.yaml`** — the realms of this world:
```yaml
planes:
  - id: material
    name: The Waking World
    nature: stone, breath, and daylight — where mortals live and die
    kind: material
  - id: ashen-veil
    name: The Ashen Veil
    nature: a grey between-place of spirits and the recently dead
    kind: spirit
```
One plane is flagged the **playable** plane (the material map the sim renders) — either
`kind: material` or a `constitution.play_plane` id (default: the first `material` kind).

**`timeline.yaml`** — the arc of ages (extends today's `history`):
```yaml
ages:
  - id: dawn
    name: The First Dawn
    when: past
    summary: the planes were sung apart and the first powers walked
  - id: cinders
    name: The Age of Cinders
    when: present
    summary: the veil thins; the mighty have withdrawn
  - id: unmaking
    name: The Foretold Unmaking
    when: future
    summary: prophecy says the planes will fold back into one
events:
  - age: dawn
    text: A primordial bound the Ashen Veil to the Waking World.
  - age: unmaking
    text: "Prophecy: a mortal will cross every plane and end the ages."
```
`when ∈ {past, present, future}`; the god may author several past ages and future
prophecies. One age is the **present** (`constitution.present_age`, default first
`when: present`).

**Power tiers** — a fixed 6-tier ladder in `illuvutar` (not god-invented, so it stays
coherent): `mortal < adept < champion < legend < demigod < primordial`. Each **role** in
`roles.yaml` gains an optional `power` (the role's typical tier; default `mortal`). Roles
may also gain an optional `plane` (home plane id; default the playable plane).

### Generation (`illuvutar`)

- **God prompt** (`GOD_SYSTEM_PROMPT`): a new step to author `planes.yaml` and
  `timeline.yaml` from the constitution before populating, and guidance to give roles a
  `power` and a `plane`, and to conceive beings across the tiers and realms.
- **`populate_world`** reads `planes.yaml` + `timeline.yaml` + the tier ladder and passes
  them to `generate_populace`, which for each being:
  - assigns `power` (from its role's tier, with occasional ±1 variation) and `home_plane`
    (role's plane, else the playable plane);
  - prompts the backstory/goal/facts with the being's **plane nature**, the **present age**
    (+ a past age and a prophecy for color), and its **power tier** — so identity is
    world-anchored;
  - writes each `agents.yaml` entry with `power` and `plane` alongside the existing fields.
  - Placement: beings whose `home_plane` is the playable plane are placed on the map as
    today; beings native to other planes are still written (lore/roster) and placed on the
    playable map at the plane's "threshold" region if named, else any walkable cell (they're
    present as visitors/manifestations this increment).

### Engine (attributes only)

- `Profile(roles, backstory)` → gains **`power: str = "mortal"`** and **`plane: str = ""`**.
- Loader reads `power`/`plane` from each `agents.yaml` entry (absent → defaults).
- Think-prompt (`ollama_ai`): add a line — e.g.
  `You are a {power} of {plane}, in the age of {present_age}.` The present age comes from
  the world (loaded from `constitution.present_age`/`timeline`); planes/timeline are static
  world context the loader threads to the AI system (a small addition to `WorldData` +
  `OllamaAISystem`), or, simplest, the being's own `plane`/`power` on `Profile` plus the
  age string. (MVP: use `Profile.power`/`Profile.plane` + a single world `present_age`
  string threaded from the loader.)
- `/entity/<id>/profile` returns `power` and `plane`.
- Back-compat: worlds without these keys load with defaults (`mortal`, `""`); the prompt
  line degrades gracefully.

## Components & boundaries

| Unit | Responsibility | Depends on |
|------|----------------|------------|
| `generation/tiers.py` (new) | The fixed power-tier ladder + helpers | nothing |
| god prompt | Author planes.yaml + timeline.yaml; tier/realm guidance | — |
| `populate_world` / `populace` | Assign power+plane, prompt with plane/age/power | `tiers`, world files |
| `Profile` (engine) | Carry power + plane | nothing |
| loader | Read power/plane + present_age; thread age to AI system | `Profile` |
| `ollama_ai` | Put power/plane/age in the prompt | `Profile`, present_age |
| `/profile` | Return power + plane | `Profile` |

## Error handling

- Missing `planes.yaml`/`timeline.yaml` at populate time → `populate_world` proceeds with a
  single default material plane + a generic "present" age (never blocks; the layer is
  additive). Malformed entries are skipped (never raises — the populace generator's
  never-raises contract holds).
- Unknown/absent `power` on a role or agent → `mortal`. Unknown `plane` → the playable plane.
- Old worlds (no power/plane/planes/timeline) load and run unchanged.

## Testing

- **`tiers`**: the 6-tier ladder is ordered, unique, defaulting to `mortal`; a
  `clamp/vary` helper stays in-range.
- **`populace`** (mocked client): each being gets a valid `power` tier and a `plane`;
  the batch prompt includes the being's plane nature + present age + power; role `power`
  drives the assignment; malformed planes/timeline → defaults, never raises; agents carry
  `power`/`plane` keys.
- **`populate_world`**: reads planes/timeline; writes agents with power/plane; works with
  those files absent (defaults).
- **engine `Profile`**: loader reads `power`/`plane` (defaults when absent); prompt
  contains the power/plane/age line; `/profile` returns power + plane; legacy world
  unaffected.

## Out of scope (YAGNI / follow-ups)

- Per-plane tilemaps and travel between planes (the playable map stays single this
  increment).
- Simulating different eras / the world changing over time.
- Power-based mechanics (combat, plane-crossing gates, ability checks).
- Routing power tiers to different model brains (natural follow-up; the `power` attribute
  is the hook).
- A visual plane/era switcher in the studio.
