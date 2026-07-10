# Rich Town of Job-Holding NPCs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The god populates its world with ~20 job-holding NPCs, each with a generated backstory that other characters and the human can read (`/entity/<id>/profile` + a browser panel) and interact with (`/whisper`).

**Architecture:** Two phases. **Engine substrate** (independently testable with a hand-authored `agents.yaml`): a `Profile(job, backstory)` component loaded from two new optional keys, fed into the think-prompt, exposed at a profile endpoint, and shown via a click-to-read browser panel. **God generation:** a fixed 20-job catalog + a per-NPC populace generator (LLM call with deterministic fallback + deterministic placement) driven by a new `populate_town` god tool.

**Tech Stack:** Python 3.12, dataclasses, ollama, FastAPI, pytest/pytest-asyncio. Engine tests: `cd engine && uv run pytest`. Illuvutar (god) tests: `uv run pytest` from repo root. Browser: vanilla ES modules in `engine/renderer/`.

## Global Constraints

- New `agents.yaml` keys `job` and `backstory` are **optional**; worlds without them stay valid (absent → empty `Profile`).
- The catalog has **exactly 20 jobs**, unique ids, every field non-empty, `biome ∈ {grassland, forest, water, ruins}`.
- `generate_populace` **never raises** and **always returns exactly `len(jobs)` entries**, each with all of `{id, kind, x, y, name, job, backstory, behavior, facts}`, unique ids, unique positions on walkable tiles.
- Backstory ≤ 60 words; facts ≤ 30 words (truncate at generation).
- `populate_town` requires `tilemap.json` (WFC first); errors clearly otherwise, no partial write.
- No new sprites (reuse `humanoid`/`scholar`/`guardian`); no demo-world changes; interaction stays on `/whisper`.
- Follow existing patterns: dataclass components, `store.get_component`, ollama via `ollama.chat`/`AsyncClient`.

## File Structure

**Create:**
- `illuvutar/src/illuvutar/generation/jobs.py` — 20-job catalog
- `illuvutar/src/illuvutar/generation/populace.py` — placement + per-NPC generation
- `engine/renderer/js/profile_panel.js` — click-to-read panel
- Tests: `illuvutar/tests/test_jobs.py`, `illuvutar/tests/test_populace.py`, `illuvutar/tests/test_populate_town.py`, `engine/tests/test_profile.py`

**Modify:**
- `engine/src/engine/entities/components.py` — add `Profile`
- `engine/src/engine/loader.py` — build `Profile`
- `engine/src/engine/systems/ollama_ai.py` — job/backstory in prompt
- `engine/src/engine/server/app.py` — `/entity/{id}/profile`
- `engine/renderer/index.html`, `engine/renderer/js/renderer.js` — wire the panel
- `engine/tests/test_loader.py`, `engine/tests/test_ollama_ai.py`
- `illuvutar/src/illuvutar/agents/tools.py` — `populate_town` + definition
- `illuvutar/src/illuvutar/agents/god.py` — Phase 3 guidance
- `illuvutar/src/illuvutar/cli.py` — pass `model` to `AgentTools`

---

## PHASE 1 — ENGINE SUBSTRATE

### Task 1: `Profile` component + loader

**Files:**
- Modify: `engine/src/engine/entities/components.py`, `engine/src/engine/loader.py`
- Test: `engine/tests/test_loader.py`

**Interfaces:**
- Produces: `Profile(job: str = "", backstory: str = "")` dataclass component; every agent loaded from `agents.yaml` carries a `Profile` (empty when keys absent).

- [ ] **Step 1: Write the failing tests** — append to `engine/tests/test_loader.py`:

```python
from engine.entities.components import Profile


def test_entity_gets_empty_profile_by_default(world_dir):
    data = load_world(world_dir)
    prof = data.store.get_component("e1", Profile)
    assert prof is not None
    assert prof.job == "" and prof.backstory == ""


def test_profile_loaded_from_agents_yaml(world_dir):
    import yaml
    (world_dir / "agents.yaml").write_text(yaml.dump([
        {"id": "e1", "kind": "humanoid", "x": 1, "y": 1, "name": "Bram",
         "behavior": "forge", "job": "Blacksmith",
         "backstory": "Took the forge after the fever winter."},
    ]))
    data = load_world(world_dir)
    prof = data.store.get_component("e1", Profile)
    assert prof.job == "Blacksmith"
    assert "fever winter" in prof.backstory
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && uv run pytest tests/test_loader.py -k profile -v`
Expected: FAIL (`Profile` undefined / not attached).

- [ ] **Step 3: Implement**

In `engine/src/engine/entities/components.py`, add:

```python
@dataclass
class Profile:
    job: str = ""
    backstory: str = ""
```

In `engine/src/engine/loader.py`: add `Profile` to the components import line, and in the agents loop (where the entity is built with `Mind`), read the two keys and append a `Profile`:

```python
            job = str(agent.get("job", ""))
            backstory = str(agent.get("backstory", ""))
```
Add `Profile(job=job, backstory=backstory)` to the `store.create(eid, kind, [ ... ])` component list (next to `AIComponent(...)`, `mind`).

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && uv run pytest tests/test_loader.py -v`
Expected: PASS (existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add engine/src/engine/entities/components.py engine/src/engine/loader.py engine/tests/test_loader.py
git commit -m "feat(engine): Profile component (job + backstory) loaded from agents.yaml"
```

---

### Task 2: Job + backstory in the think-prompt

**Files:**
- Modify: `engine/src/engine/systems/ollama_ai.py`
- Test: `engine/tests/test_ollama_ai.py`

**Interfaces:**
- Consumes: `Profile` (Task 1).
- Produces: `_think` reads the entity's `Profile` and includes its job (as `role=`) and backstory in the prompt.

- [ ] **Step 1: Write the failing test** — append to `engine/tests/test_ollama_ai.py`:

```python
from engine.entities.components import Profile


@pytest.mark.asyncio
async def test_prompt_includes_job_and_backstory(passability, tmp_path):
    s = EntityStore()
    s.create("smith", "humanoid", [
        Position(2, 2), Label("Bram"),
        AIComponent(agent_id="smith", goal="forge"),
        Tags(["agent"]), PhysicsComponent(),
        Mind(memory="", facts=""),
        Profile(job="Blacksmith", backstory="Took the forge after the fever winter."),
    ])
    sys = OllamaAISystem(s, passability, world_dir=tmp_path)
    captured = {}

    async def fake_chat(*, model, messages):
        captured["p"] = messages[0]["content"]
        m = MagicMock(); m.message.content = json.dumps({"action": "rest", "thought": "x"})
        return m

    with patch("engine.systems.ollama_ai.ollama") as mock_ollama:
        mock_ollama.AsyncClient.return_value.chat = AsyncMock(side_effect=fake_chat)
        await sys.schedule_thinks(tick=50)
        await asyncio.sleep(0.1)
        await sys.drain_results()

    assert "Blacksmith" in captured["p"]
    assert "fever winter" in captured["p"]
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && uv run pytest tests/test_ollama_ai.py -k job_and_backstory -v`
Expected: FAIL (prompt lacks job/backstory).

- [ ] **Step 3: Implement**

In `engine/src/engine/systems/ollama_ai.py`:

Add `Profile` to the components import.

In `_THINK_PROMPT`, change the identity line and add a background line. Replace:
```
Who you are (you cannot change these): name={name}, kind={kind}.
```
with:
```
Who you are (you cannot change these): name={name}, kind={kind}, role={job}.
Your background: {backstory}
```

In `_think`, before the `prompt = _THINK_PROMPT.format(...)` call, read the profile:
```python
        profile = self._store.get_component(entity_id, Profile)
        job = profile.job if profile and profile.job else kind
        backstory = profile.backstory if profile and profile.backstory else "unknown"
```
Add `job=job, backstory=backstory` to the `.format(...)` keyword args.

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && uv run pytest tests/test_ollama_ai.py -v`
Expected: PASS (existing + new).

- [ ] **Step 5: Commit**

```bash
git add engine/src/engine/systems/ollama_ai.py engine/tests/test_ollama_ai.py
git commit -m "feat(engine): entity job + backstory feed the think-prompt"
```

---

### Task 3: `/entity/{id}/profile` endpoint

**Files:**
- Modify: `engine/src/engine/server/app.py`
- Test: `engine/tests/test_profile.py` (create)

**Interfaces:**
- Consumes: `Profile`, `Mind`, `Label`, `AIComponent`, the `store` already passed to `create_app`.
- Produces: `GET /entity/{entity_id}/profile` → 200 `{id, name, job, backstory, facts, goal}`; 404 if unknown.

- [ ] **Step 1: Write the failing test** — create `engine/tests/test_profile.py`:

```python
from fastapi.testclient import TestClient
from engine.entities.store import EntityStore
from engine.entities.components import (
    Position, Label, AIComponent, Tags, PhysicsComponent, Mind, Profile
)
from engine.physics.passability import PassabilityMap
from engine.server.app import create_app


def _client():
    store = EntityStore()
    store.create("smith", "humanoid", [
        Position(2, 2), Label("Bram"),
        AIComponent(agent_id="smith", goal="forge iron"),
        Tags(["agent"]), PhysicsComponent(),
        Mind(memory="hot work today", facts="I am proud of my craft"),
        Profile(job="Blacksmith", backstory="Took the forge after the fever winter."),
    ])
    passability = PassabilityMap(tilemap=[["g"] * 4 for _ in range(4)], rules={"g": "open"})
    app = create_app(store=store, passability=passability, palette={0: "g"},
                     tilemap_data=[], world_id="w", width=4, height=4)
    return TestClient(app)


def test_profile_returns_full_shape():
    r = _client().get("/entity/smith/profile")
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "id": "smith", "name": "Bram", "job": "Blacksmith",
        "backstory": "Took the forge after the fever winter.",
        "facts": "I am proud of my craft", "goal": "forge iron",
    }


def test_profile_unknown_entity_404():
    assert _client().get("/entity/nobody/profile").status_code == 404
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && uv run pytest tests/test_profile.py -v`
Expected: FAIL (404 route missing → 404 for both, so the shape test fails).

- [ ] **Step 3: Implement**

In `engine/src/engine/server/app.py`, add the import:
```python
from engine.entities.components import Label, Profile, Mind, AIComponent
```
Add the route (near `/entity/{entity_id}/say`), closing over `store`:
```python
    @app.get("/entity/{entity_id}/profile")
    async def entity_profile(entity_id: str):
        if entity_id not in store.all_ids():
            return Response(content="Unknown entity", status_code=404)
        label = store.get_component(entity_id, Label)
        prof = store.get_component(entity_id, Profile)
        mind = store.get_component(entity_id, Mind)
        ai = store.get_component(entity_id, AIComponent)
        return {
            "id": entity_id,
            "name": label.name if label else entity_id,
            "job": prof.job if prof else "",
            "backstory": prof.backstory if prof else "",
            "facts": mind.facts if mind else "",
            "goal": ai.goal if ai else "",
        }
```

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && uv run pytest tests/test_profile.py -v`
Expected: PASS (2).

- [ ] **Step 5: Commit**

```bash
git add engine/src/engine/server/app.py engine/tests/test_profile.py
git commit -m "feat(engine): GET /entity/<id>/profile returns name/job/backstory/facts/goal"
```

---

### Task 4: Click-to-read browser profile panel

**Files:**
- Create: `engine/renderer/js/profile_panel.js`
- Modify: `engine/renderer/index.html`, `engine/renderer/js/renderer.js`

**Interfaces:**
- Consumes: `/entity/{id}/profile`, `camera.worldToScreen`, the current frame.
- Produces: clicking an entity opens a panel with name/job/backstory/goal; click-away closes it.

No unit test (browser); verified manually in Task 8. Keep it small and defensive.

- [ ] **Step 1: Add panel markup + styles**

In `engine/renderer/index.html`, before `</body>` (mirroring `#thought-panel`'s dark styling), add:
```html
<div id="profile-panel" style="display:none; position:absolute; top:12px; right:12px;
     width:280px; max-height:70vh; overflow:auto; background:rgba(10,10,20,.92);
     border:1px solid #3b0764; border-radius:8px; padding:12px 14px; color:#e5e7eb;
     font:12px/1.5 system-ui,sans-serif; z-index:20;">
  <div style="display:flex; justify-content:space-between; align-items:baseline;">
    <strong id="profile-name" style="color:#c4b5fd; font-size:14px;"></strong>
    <button id="profile-close" style="background:none;border:none;color:#94a3b8;cursor:pointer;font-size:14px;">✕</button>
  </div>
  <div id="profile-job" style="color:#a78bfa; font-style:italic; margin:2px 0 8px;"></div>
  <div id="profile-backstory" style="color:#cbd5e1;"></div>
  <div id="profile-goal" style="color:#64748b; margin-top:8px; font-size:11px;"></div>
</div>
```

- [ ] **Step 2: Implement the panel module**

Create `engine/renderer/js/profile_panel.js`:
```js
export function setupProfilePanel(canvas, camera, getFrame) {
  const panel = document.getElementById('profile-panel');
  const els = {
    name: document.getElementById('profile-name'),
    job: document.getElementById('profile-job'),
    backstory: document.getElementById('profile-backstory'),
    goal: document.getElementById('profile-goal'),
  };
  const hide = () => { panel.style.display = 'none'; };
  document.getElementById('profile-close')?.addEventListener('click', hide);

  canvas.addEventListener('click', (e) => {
    const frame = getFrame();
    if (!frame) return;
    const rect = canvas.getBoundingClientRect();
    const cx = e.clientX - rect.left, cy = e.clientY - rect.top;
    const ts = camera.tileSize;
    // topmost entity (highest y drawn last) under the click
    let hit = null;
    for (const en of frame.entities) {
      const [sx, sy] = camera.worldToScreen(en.x, en.y);
      if (cx >= sx && cx <= sx + ts && cy >= sy && cy <= sy + ts) {
        if (!hit || en.y > hit.y) hit = en;
      }
    }
    if (!hit) { hide(); return; }
    fetch(`/entity/${encodeURIComponent(hit.id)}/profile`)
      .then((r) => (r.ok ? r.json() : null))
      .then((p) => {
        if (!p) return;
        els.name.textContent = p.name || p.id;
        els.job.textContent = p.job || '';
        els.backstory.textContent = p.backstory || '(no story recorded)';
        els.goal.textContent = p.goal ? `Goal: ${p.goal}` : '';
        panel.style.display = 'block';
      })
      .catch(() => {});
  });
}
```

- [ ] **Step 3: Wire it in `renderer.js`**

Import it and keep the latest frame. Add near the other imports:
```js
import { setupProfilePanel } from './profile_panel.js';
```
Add a module var and set it each frame. Change the SSE handler to store the frame, and set up the panel once after `camera` is created:
```js
let currentFrame = null;
setupProfilePanel(worldCanvas, camera, () => currentFrame);
```
In `evtSource.onmessage`, after `const frame = parseFrame(evt.data);`, add `currentFrame = frame;`.

- [ ] **Step 4: Manual smoke (deferred to Task 8)** — nothing to run here; the endpoint tests already cover the data path.

- [ ] **Step 5: Commit**

```bash
git add engine/renderer/js/profile_panel.js engine/renderer/index.html engine/renderer/js/renderer.js
git commit -m "feat(renderer): click an NPC to read its profile (name/job/backstory/goal)"
```

---

## PHASE 2 — GOD GENERATION

### Task 5: The 20-job catalog

**Files:**
- Create: `illuvutar/src/illuvutar/generation/jobs.py`
- Test: `illuvutar/tests/test_jobs.py`

**Interfaces:**
- Produces: `Job(id, title, site, biome, blurb)` frozen dataclass; `JOBS: list[Job]` of 20; helper `name_pool(job_id) -> list[str]` (≥3 names per job, for fallback).

- [ ] **Step 1: Write the failing test** — create `illuvutar/tests/test_jobs.py`:

```python
from illuvutar.generation.jobs import JOBS, Job, name_pool

VALID_BIOMES = {"grassland", "forest", "water", "ruins"}


def test_exactly_twenty_unique_jobs():
    assert len(JOBS) == 20
    assert len({j.id for j in JOBS}) == 20


def test_all_fields_present_and_valid():
    for j in JOBS:
        assert isinstance(j, Job)
        assert j.id and j.title and j.site and j.blurb
        assert j.biome in VALID_BIOMES


def test_name_pool_has_options_for_every_job():
    for j in JOBS:
        assert len(name_pool(j.id)) >= 3
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest illuvutar/tests/test_jobs.py -v` (from repo root)
Expected: FAIL (module missing).

Wait — tests run from repo root with `uv run pytest tests/...`? The illuvutar project root IS the repo root (after the earlier hoist). So: `uv run pytest tests/test_jobs.py -v`.

- [ ] **Step 3: Implement**

Create `illuvutar/src/illuvutar/generation/jobs.py`:
```python
"""Fixed catalog of 20 jobs the god uses to populate a town."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Job:
    id: str
    title: str
    site: str
    biome: str        # grassland | forest | water | ruins
    blurb: str


JOBS: list[Job] = [
    Job("blacksmith", "Blacksmith", "Forge Lane", "grassland", "shapes iron and steel for the town"),
    Job("carpenter", "Carpenter", "Timber Yard", "grassland", "raises beams and mends roofs"),
    Job("baker", "Baker", "Market Row", "grassland", "bakes the town's daily bread"),
    Job("brewer", "Brewer", "The Malthouse", "grassland", "brews ale for the inn"),
    Job("innkeeper", "Innkeeper", "The Crossroads Inn", "grassland", "keeps beds and gossip for travelers"),
    Job("merchant", "Merchant", "Market Row", "grassland", "trades goods from distant roads"),
    Job("weaver", "Weaver", "Loom Street", "grassland", "spins wool into cloth"),
    Job("tanner", "Tanner", "The Tannery", "grassland", "cures hides at the town's edge"),
    Job("healer", "Healer", "The Infirmary", "grassland", "tends the sick and wounded"),
    Job("priest", "Priest", "Temple Yard", "grassland", "keeps the rites and comforts the grieving"),
    Job("scribe", "Scribe", "The Archive", "grassland", "copies letters and keeps the town's records"),
    Job("watchman", "Watchman", "The Gate", "grassland", "guards the road and watches for strangers"),
    Job("midwife", "Midwife", "Willow Row", "grassland", "births the town's children"),
    Job("potter", "Potter", "The Kiln", "grassland", "throws jars and bowls of river clay"),
    Job("hunter", "Hunter", "The Wood", "forest", "tracks game beneath the canopy"),
    Job("forester", "Forester", "The Wood", "forest", "fells timber and keeps the woodland paths"),
    Job("herbalist", "Herbalist", "The Wood's Edge", "forest", "gathers healing herbs and roots"),
    Job("fisher", "Fisher", "The Docks", "water", "casts nets on the mirror lake"),
    Job("ferryman", "Ferryman", "The Docks", "water", "poles travelers across the lake"),
    Job("scholar", "Scholar", "The Ruined Keep", "ruins", "reads the ruins for lost knowledge"),
]

_NAME_POOLS: dict[str, list[str]] = {
    "blacksmith": ["Bram Ashfoot", "Doren Ironhand", "Sela Cinder"],
    "carpenter": ["Tobin Oakes", "Marta Plank", "Ewan Sawyer"],
    "baker": ["Nessa Crumb", "Aldo Wheatley", "Perrin Dough"],
    "brewer": ["Hollis Mash", "Greta Barley", "Cob Hopwood"],
    "innkeeper": ["母 Wendel Roon", "Ferra Tallow", "Ottis Ledger"],
    "merchant": ["Silas Vane", "Ruta Coin", "Amberly Trade"],
    "weaver": ["Linna Spindle", "Cael Warp", "Odette Skein"],
    "tanner": ["Garrick Hyde", "Bela Cure", "Nym Leather"],
    "healer": ["Mira Salve", "Edwin Poultice", "Rosa Fenn"],
    "priest": ["Father Alric", "Sister Vesna", "Brother Ode"],
    "scribe": ["Quill Marrow", "Lena Inkwell", "Petro Vellum"],
    "watchman": ["Kael Stern", "Bors Watch", "Dilla Ward"],
    "midwife": ["Anna Willow", "Sefa Birch", "Corra Mild"],
    "potter": ["Jem Clayborn", "Ula Kiln", "Pip Sherd"],
    "hunter": ["Fenn Quiver", "Rue Track", "Alder Snare"],
    "forester": ["Bryn Timber", "Hazel Grove", "Corin Bough"],
    "herbalist": ["Wynn Nettle", "Isolde Root", "Tam Sage"],
    "fisher": ["Marlo Netter", "Sib Roe", "Dunn Cormar"],
    "ferryman": ["Osric Pole", "Vela Reed", "Hob Skiff"],
    "scholar": ["Doran Vale", "Ysra Palimpsest", "Emmet Cairn"],
}


def name_pool(job_id: str) -> list[str]:
    return _NAME_POOLS.get(job_id, ["Wanderer", "Stranger", "Traveler"])
```
(Replace the stray non-ASCII in the innkeeper pool with a plain name — e.g. `"Wendel Roon"`.)

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_jobs.py -v`
Expected: PASS (3).

- [ ] **Step 5: Commit**

```bash
git add illuvutar/src/illuvutar/generation/jobs.py illuvutar/tests/test_jobs.py
git commit -m "feat(illuvutar): fixed 20-job catalog with fallback name pools"
```

---

### Task 6: Populace generator (placement + per-NPC LLM + fallback)

**Files:**
- Create: `illuvutar/src/illuvutar/generation/populace.py`
- Test: `illuvutar/tests/test_populace.py`

**Interfaces:**
- Consumes: `Job`, `name_pool` (Task 5), `ollama`.
- Produces:
  `generate_populace(jobs, tilemap, regions, walkable_tile_ids, model, facts_word_limit=30, backstory_word_limit=60) -> list[dict]`
  returning one dict per job: `{id, kind, x, y, name, job, backstory, behavior, facts}`. Never raises; always `len(jobs)` entries; unique ids; unique walkable positions.

- [ ] **Step 1: Write the failing tests** — create `illuvutar/tests/test_populace.py`:

```python
import json
from unittest.mock import patch, MagicMock
from illuvutar.generation.jobs import JOBS
from illuvutar.generation.populace import generate_populace

# 6x6 map: region 0 grassland everywhere except a forest strip (region 1) and water (region 2)
def _tilemap():
    cells = []
    for y in range(6):
        for x in range(6):
            if y == 0:
                tid, reg = "forest_floor", 1
            elif y == 5:
                tid, reg = "water_shallow", 2
            else:
                tid, reg = "grass_plain", 0
            cells.append({"x": x, "y": y, "tile_id": tid, "region": reg})
    return cells

_REGIONS = [
    {"id": 0, "name": "Plains", "biome": "grassland"},
    {"id": 1, "name": "Wood", "biome": "forest"},
    {"id": 2, "name": "Lake", "biome": "water"},
]
_WALKABLE = {"grass_plain", "forest_floor"}  # water excluded


def _mock_ok(name="Bram", story="A short life story.", goal="work", facts="I am proud."):
    m = MagicMock()
    m.message.content = json.dumps({"name": name, "backstory": story, "goal": goal, "facts": facts})
    return m


def test_generates_one_valid_npc_per_job():
    jobs = JOBS[:5]
    with patch("illuvutar.generation.populace.ollama") as mo:
        mo.chat.return_value = _mock_ok()
        people = generate_populace(jobs, _tilemap(), _REGIONS, _WALKABLE, model="m")
    assert len(people) == len(jobs)
    for p in people:
        assert p["name"] and p["backstory"] and p["job"] and p["behavior"] and p["facts"]
    ids = [p["id"] for p in people]
    assert len(set(ids)) == len(ids)
    positions = [(p["x"], p["y"]) for p in people]
    assert len(set(positions)) == len(positions)


def test_positions_are_walkable_and_never_on_water():
    with patch("illuvutar.generation.populace.ollama") as mo:
        mo.chat.return_value = _mock_ok()
        people = generate_populace(JOBS, _tilemap(), _REGIONS, _WALKABLE, model="m")
    tile_at = {(c["x"], c["y"]): c["tile_id"] for c in _tilemap()}
    for p in people:
        assert tile_at[(p["x"], p["y"])] in _WALKABLE


def test_llm_failure_falls_back_and_still_returns_all():
    with patch("illuvutar.generation.populace.ollama") as mo:
        mo.chat.side_effect = RuntimeError("ollama down")
        people = generate_populace(JOBS[:8], _tilemap(), _REGIONS, _WALKABLE, model="m")
    assert len(people) == 8
    for p in people:                       # fallback still fills every field
        assert p["name"] and p["backstory"] and p["facts"]


def test_backstory_truncated_to_word_limit():
    long_story = " ".join(["word"] * 200)
    with patch("illuvutar.generation.populace.ollama") as mo:
        mo.chat.return_value = _mock_ok(story=long_story)
        people = generate_populace(JOBS[:1], _tilemap(), _REGIONS, _WALKABLE, model="m", backstory_word_limit=12)
    assert len(people[0]["backstory"].split()) == 12
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_populace.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

Create `illuvutar/src/illuvutar/generation/populace.py`:
```python
"""Generate a town populace: one NPC per job, placed on walkable tiles, with per-NPC
LLM-generated backstories and a deterministic fallback so it never fails."""
import json
import ollama
from illuvutar.generation.jobs import Job, name_pool

_KIND_FOR_JOB = {"scholar": "scholar", "watchman": "guardian"}  # reuse existing sprites


def _truncate_words(text: str, limit: int) -> str:
    return " ".join((text or "").split()[:limit])


def _region_ids_for_biome(regions: list[dict], biome: str) -> set[int]:
    return {int(r["id"]) for r in regions if r.get("biome") == biome}


def _walkable_cells(tilemap: list[dict], region_ids: set[int], walkable: set[str]) -> list[dict]:
    cells = [c for c in tilemap
             if c.get("tile_id") in walkable and int(c.get("region", -1)) in region_ids]
    return cells


def _prompt(job: Job, world_name: str, world_tone: str) -> str:
    return (
        f"Invent a resident of the town of {world_name or 'the crossroads'}.\n"
        f"Tone: {world_tone or 'a quiet world of forest, ruin, and still water'}.\n"
        f"They are the {job.title} at {job.site} — they {job.blurb}.\n"
        "Respond with ONLY valid JSON (no markdown):\n"
        '{"name": "...", "backstory": "2-3 vivid sentences of their history", '
        '"goal": "their current aim", "facts": "one line of self-belief"}'
    )


def generate_populace(
    jobs: list[Job],
    tilemap: list[dict],
    regions: list[dict],
    walkable_tile_ids: set[str],
    model: str,
    world_name: str = "",
    world_tone: str = "",
    facts_word_limit: int = 30,
    backstory_word_limit: int = 60,
) -> list[dict]:
    all_walkable = [c for c in tilemap if c.get("tile_id") in walkable_tile_ids]
    used: set[tuple[int, int]] = set()
    people: list[dict] = []

    for i, job in enumerate(jobs):
        # --- placement (deterministic): prefer the job's biome region ---
        region_ids = _region_ids_for_biome(regions, job.biome)
        candidates = _walkable_cells(tilemap, region_ids, walkable_tile_ids) or all_walkable
        cell = None
        for c in candidates:
            if (c["x"], c["y"]) not in used:
                cell = c
                break
        if cell is None:  # every candidate taken — reuse any free walkable cell
            for c in all_walkable:
                if (c["x"], c["y"]) not in used:
                    cell = c
                    break
        if cell is None:  # map has fewer walkable tiles than jobs — stack as last resort
            cell = (candidates or all_walkable or [{"x": 0, "y": 0}])[0]
        x, y = int(cell["x"]), int(cell["y"])
        used.add((x, y))

        # --- generation (per-NPC LLM with deterministic fallback) ---
        pool = name_pool(job.id)
        name = pool[i % len(pool)]
        backstory = f"{name} has served as the {job.title} of {job.site} for many years."
        goal = job.blurb
        facts = f"I am {name}, the {job.title}."
        try:
            resp = ollama.chat(model=model, messages=[{"role": "user",
                     "content": _prompt(job, world_name, world_tone)}])
            data = json.loads((resp.message.content or "").strip().strip("`"))
            name = str(data.get("name") or name).strip() or name
            backstory = str(data.get("backstory") or backstory).strip() or backstory
            goal = str(data.get("goal") or goal).strip() or goal
            facts = str(data.get("facts") or facts).strip() or facts
        except Exception:
            pass  # deterministic fallback values already set

        people.append({
            "id": job.id,
            "kind": _KIND_FOR_JOB.get(job.id, "humanoid"),
            "x": x, "y": y,
            "name": name,
            "job": job.title,
            "backstory": _truncate_words(backstory, backstory_word_limit),
            "behavior": goal,
            "facts": _truncate_words(facts, facts_word_limit),
        })
    return people
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_populace.py -v`
Expected: PASS (4).

- [ ] **Step 5: Commit**

```bash
git add illuvutar/src/illuvutar/generation/populace.py illuvutar/tests/test_populace.py
git commit -m "feat(illuvutar): populace generator — placement + per-NPC LLM with fallback"
```

---

### Task 7: `populate_town` god tool + wiring + prompt

**Files:**
- Modify: `illuvutar/src/illuvutar/agents/tools.py`, `illuvutar/src/illuvutar/agents/god.py`, `illuvutar/src/illuvutar/cli.py`
- Test: `illuvutar/tests/test_populate_town.py` (create)

**Interfaces:**
- Consumes: `JOBS`, `generate_populace` (Tasks 5–6), the writer.
- Produces: `AgentTools.__init__` gains `model: str = "llama3.2"`; method `populate_town(self, count: int = 20) -> str`; a `definitions()` entry; `cli.py` passes `model`.

- [ ] **Step 1: Write the failing test** — create `illuvutar/tests/test_populate_town.py`:

```python
import json
from unittest.mock import patch, MagicMock
from pathlib import Path
from illuvutar.world_state.writer import WorldStateWriter
from illuvutar.palette.indexer import Tile
from illuvutar.agents.tools import AgentTools


def _tools(tmp_path):
    writer = WorldStateWriter(tmp_path)
    tiles = [
        Tile(id="grass_plain", sprite_path="", layer="ground", tags=["walkable"], adjacent=[]),
        Tile(id="water_shallow", sprite_path="", layer="ground", tags=["wading"], adjacent=[]),
    ]
    return AgentTools(writer=writer, rag=MagicMock(), tiles=tiles,
                      palette_dir=Path(tmp_path), model="m"), writer


def test_populate_town_requires_tilemap(tmp_path):
    tools, _ = _tools(tmp_path)
    out = tools.populate_town()
    assert "tilemap" in out.lower() or "wfc" in out.lower()


def test_populate_town_writes_agents_with_job_and_backstory(tmp_path):
    tools, writer = _tools(tmp_path)
    writer.write("regions", {"regions": [{"id": 0, "name": "Plains", "biome": "grassland"}]})
    writer.write("tilemap", [{"x": x, "y": 0, "tile_id": "grass_plain", "region": 0} for x in range(20)])
    with patch("illuvutar.generation.populace.ollama") as mo:
        m = MagicMock(); m.message.content = json.dumps(
            {"name": "Bram", "backstory": "A life of iron.", "goal": "forge", "facts": "I forge."})
        mo.chat.return_value = m
        out = tools.populate_town(count=5)
    agents = writer.read("agents")
    assert len(agents) == 5
    assert all("job" in a and "backstory" in a for a in agents)
    assert "5" in out
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_populate_town.py -v`
Expected: FAIL (`model` kwarg / `populate_town` missing).

- [ ] **Step 3: Implement**

In `illuvutar/src/illuvutar/agents/tools.py`:
- Add imports: `from illuvutar.generation.jobs import JOBS` and `from illuvutar.generation.populace import generate_populace`.
- Add `model` to `__init__`:
```python
    def __init__(self, writer, rag, tiles, palette_dir, model: str = "llama3.2"):
        ...
        self.model = model
```
- Add the method:
```python
    _BLOCKED_TAGS = {"blocked", "impassable", "structure", "high", "void"}

    def populate_town(self, count: int = 20) -> str:
        tilemap = self.writer.read("tilemap")
        regions_data = self.writer.read("regions")
        if not tilemap:
            return "Error: tilemap.json missing — run run_wfc first."
        regions = (regions_data or {}).get("regions", []) if isinstance(regions_data, dict) else []
        walkable = {
            t.id for t in self.tiles
            if not (set(t.tags) & self._BLOCKED_TAGS) and not t.id.startswith("water")
        }
        if not walkable:
            return "Error: no walkable tiles in palette."
        constitution = self.writer.read("constitution") or {}
        people = generate_populace(
            JOBS[:count], tilemap, regions, walkable, model=self.model,
            world_name=(constitution.get("world_name", "") if isinstance(constitution, dict) else ""),
            world_tone=(constitution.get("tone", "") if isinstance(constitution, dict) else ""),
        )
        self.writer.write("agents", people)
        return f"Populated {len(people)} NPCs across the town."
```
- Add to `definitions()` (a new entry in the returned list):
```python
            {
                "type": "function",
                "function": {
                    "name": "populate_town",
                    "description": "Populate agents.yaml with job-holding townsfolk and backstories. Requires tilemap.json (run run_wfc first).",
                    "parameters": {
                        "type": "object",
                        "properties": {"count": {"type": "integer", "description": "How many NPCs (default 20)"}},
                        "required": [],
                    },
                },
            },
```

In `illuvutar/src/illuvutar/cli.py`, pass the model:
```python
    tools = AgentTools(writer=writer, rag=rag, tiles=tiles, palette_dir=palette_dir, model=model)
```

In `illuvutar/src/illuvutar/agents/god.py`, extend Phase 3 of `GOD_SYSTEM_PROMPT`:
```
Run WFC to generate the tilemap.
Then call populate_town to fill the world with townsfolk — each has a job and a backstory that other characters can read.
```
(Insert the `populate_town` line right after the WFC line.)

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_populate_town.py -v`
Expected: PASS (2).

- [ ] **Step 5: Run both full suites**

Run: `uv run pytest -q` (root) and `cd engine && uv run pytest -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add illuvutar/src/illuvutar/agents/tools.py illuvutar/src/illuvutar/agents/god.py illuvutar/src/illuvutar/cli.py illuvutar/tests/test_populate_town.py
git commit -m "feat(illuvutar): populate_town god tool wires catalog+populace into agents.yaml"
```

---

### Task 8: End-to-end verification

**Files:** none (manual; temporary throwaway world).

- [ ] **Step 1: Engine + browser via a hand-authored world**

Create a temp world dir (do NOT commit) with a tiny map and 3 NPCs carrying `job`/`backstory`, e.g. copy `demo_world/` to `/tmp/town_test/` and hand-edit its `agents.yaml` to add `job:`/`backstory:` to each agent. Boot:
```bash
cd engine && uv run illuvutar-engine /tmp/town_test --port 8096
```
- `curl -s http://127.0.0.1:8096/entity/<id>/profile` → returns name/job/backstory/facts/goal.
- Open http://localhost:8096, click an NPC → the profile panel shows their story. Whisper via the TUI and confirm the reply reflects the backstory (best-effort, LLM-dependent).

- [ ] **Step 2: God path smoke (optional, slow)**

Run a real `uv run illuvutar create-world --palette palettes/verdant --world /tmp/godtown ...`, drive the god to run WFC then `populate_town`. Confirm `/tmp/godtown/agents.yaml` has ~20 entries each with `job`/`backstory`. (Fallback guarantees success even if `llama3.2` output is poor.)

- [ ] **Step 3: Clean up** — remove temp worlds; no commit.

---

## Self-Review

**Spec coverage:**
- 20-job catalog → Task 5. ✓
- Per-NPC generation + fallback + placement → Task 6. ✓
- `populate_town` god tool + model wiring + god prompt → Task 7. ✓
- `agents.yaml` job/backstory schema → Task 1 (loader) + Task 6/7 (writer). ✓
- `Profile` component + loader → Task 1. ✓
- Backstory in think-prompt → Task 2. ✓
- Profile endpoint → Task 3. ✓
- Browser click-to-read → Task 4. ✓
- Reuse memory/identity (facts) → Tasks 2/3/6 (facts seeded + surfaced). ✓
- Verification (hand-world + god smoke) → Task 8. ✓

**Placeholder scan:** none — all code is complete. (Note in Task 5: replace the flagged non-ASCII placeholder name with a plain string — called out inline.)

**Type consistency:** `Profile(job, backstory)`, `generate_populace(jobs, tilemap, regions, walkable_tile_ids, model, world_name="", world_tone="", facts_word_limit=30, backstory_word_limit=60) -> list[dict]`, `populate_town(count=20) -> str`, `AgentTools(..., model="llama3.2")`, `/entity/{id}/profile` shape `{id,name,job,backstory,facts,goal}`, `name_pool(job_id) -> list[str]` — consistent across tasks.

**Verified:** `Tile` is `illuvutar.palette.indexer.Tile` with fields `id, sprite_path, layer, tags, adjacent` (Task 7 fixture uses these). Illuvutar tests run from repo root (`uv run pytest tests/...`, `pythonpath=["src"]`); engine tests from `engine/`.
