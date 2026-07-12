# Pause & Tweak — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pause/resume the live sim, hop to the god (Forge), and reload after edits — the loop ⏸ Pause → ◀ God → ⟳ Reload → ▶ Resume — without restarting the server.

**Architecture:** `TickLoop` gains a pause flag (skip ticking); `create_app` exposes `/pause`, `/resume`, `/status`; the renderer HUD gets base-aware Pause/God/Reload controls; the studio adds `SimHolder.reload()` + `/sim/reload`.

**Tech Stack:** Python 3.12, FastAPI, pytest + TestClient; vanilla JS renderer. Engine tests from `engine/`; studio tests from `studio/`.

## Global Constraints

- Pausing skips `_tick_once` entirely (no movement, no thinking, no frame broadcast); the loop stays alive.
- Endpoints on `create_app` work standalone AND under the studio `/sim` mount (renderer already uses `window.__BASE__`).
- `◀ God` and `⟳ Reload` HUD controls appear ONLY under the studio (`window.__BASE__` truthy); standalone hides them. `⏸ Pause` always shows.
- `SimHolder.reload()` stops the old tick loop before rebuilding (no orphaned loop, consistent with the idempotent-start fix).

## File Structure
**Modify:** `engine/src/engine/tick.py`, `engine/src/engine/server/app.py`, `engine/tests/test_tick.py`, `engine/tests/test_server.py`; `engine/renderer/index.html`, `engine/renderer/js/ui_layer.js`; `studio/src/studio/sim.py`, `studio/src/studio/app.py`, `studio/tests/test_studio_app.py`.

---

### Task 1: TickLoop pause + engine endpoints

**Files:** Modify `engine/src/engine/tick.py`, `engine/src/engine/server/app.py`; Test `engine/tests/test_tick.py`, `engine/tests/test_server.py`.

**Interfaces:**
- Produces: `TickLoop.pause()`, `.resume()`, `.paused` (bool property), `.tick` (int property); `create_app` routes `POST /pause`→`{"paused":True}`, `POST /resume`→`{"paused":False}`, `GET /status`→`{"paused":bool,"tick":int}`.

- [ ] **Step 1: Write the failing tests** — append to `engine/tests/test_tick.py`:

```python
import asyncio
import pytest
from engine.tick import TickLoop


def _loop(tmp_path=None):
    from engine.entities.store import EntityStore
    from engine.physics.passability import PassabilityMap
    store = EntityStore()
    pass_ = PassabilityMap(tilemap=[["g"] * 3 for _ in range(3)], rules={"g": "open"})
    async def noop(_f): return None
    return TickLoop(store=store, passability=pass_, palette={0: "g"}, tilemap_data=[],
                    world_id="w", width=3, height=3, frame_callback=noop, tick_interval=0.01)


def test_pause_resume_toggles_flag():
    lp = _loop()
    assert lp.paused is False
    lp.pause(); assert lp.paused is True
    lp.resume(); assert lp.paused is False


@pytest.mark.asyncio
async def test_paused_loop_does_not_tick():
    lp = _loop()
    calls = {"n": 0}
    async def counting_tick():
        calls["n"] += 1
    lp._tick_once = counting_tick
    lp.pause()
    task = asyncio.create_task(lp.start())
    await asyncio.sleep(0.05)          # several intervals
    paused_count = calls["n"]
    lp.resume()
    await asyncio.sleep(0.05)
    lp.stop()
    await asyncio.sleep(0.02)
    assert paused_count == 0           # no ticks while paused
    assert calls["n"] > 0              # ticked after resume
```

(`test_server.py` — add, reusing its app/client helper:)

```python
def test_pause_resume_status(client):
    assert client.post("/pause").json() == {"paused": True}
    assert client.get("/status").json()["paused"] is True
    assert client.post("/resume").json() == {"paused": False}
    assert client.get("/status").json()["paused"] is False
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && uv run pytest tests/test_tick.py tests/test_server.py -k "pause or status" -v`
Expected: FAIL.

- [ ] **Step 3: Implement.**

`tick.py` — in `__init__` add `self._paused = False`. Add properties + methods:
```python
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
```
Change `start()`:
```python
    async def start(self) -> None:
        self._running = True
        while self._running:
            if not self._paused:
                await self._tick_once()
            await asyncio.sleep(self._tick_interval)
```

`app.py` — add routes (near `/thoughts`), using the `tick_loop` in scope:
```python
    @app.post("/pause")
    async def pause():
        tick_loop.pause()
        return {"paused": True}

    @app.post("/resume")
    async def resume():
        tick_loop.resume()
        return {"paused": False}

    @app.get("/status")
    async def status():
        return {"paused": tick_loop.paused, "tick": tick_loop.tick}
```

- [ ] **Step 4: Run to verify pass + full engine suite**

Run: `cd engine && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/src/engine/tick.py engine/src/engine/server/app.py engine/tests/
git commit -m "feat(engine): pause/resume the tick loop + /pause /resume /status"
```

---

### Task 2: Studio sim reload

**Files:** Modify `studio/src/studio/sim.py`, `studio/src/studio/app.py`; Test `studio/tests/test_studio_app.py`.

**Interfaces:**
- Consumes: `SimHolder` (existing), `create_app.state.tick_loop`.
- Produces: `SimHolder.reload() -> bool` (stops old loop + rebuilds; False if missing); `POST /sim/reload` → `{"ready":bool,"missing":[...]}`.

- [ ] **Step 1: Write the failing test** — append to `studio/tests/test_studio_app.py`:

```python
@pytest.mark.asyncio
async def test_sim_reload_rebuilds_and_stops_old(tmp_path, monkeypatch):
    from unittest.mock import MagicMock, AsyncMock
    import studio.sim as sim_mod
    (tmp_path / "constitution.yaml").write_text("world_name: t")
    (tmp_path / "palette.yaml").write_text("tiles: []")
    (tmp_path / "tilemap.json").write_text("[]")
    built = []
    def fake_create_app(**kw):
        app = MagicMock(); app.state.tick_loop.start = AsyncMock(); built.append(app); return app
    monkeypatch.setattr(sim_mod, "load_world", lambda wd: MagicMock())
    monkeypatch.setattr(sim_mod, "create_app", fake_create_app)
    holder = sim_mod.SimHolder(tmp_path)
    assert holder.start() is True
    first = built[0]
    assert holder.reload() is True
    assert len(built) == 2                       # rebuilt
    first.state.tick_loop.stop.assert_called_once()   # old loop stopped


def test_sim_reload_needs_tilemap(tmp_path, fake_session):
    from studio.app import create_studio_app
    c = TestClient(create_studio_app(fake_session, world_dir=tmp_path))
    r = c.post("/sim/reload")
    assert r.status_code == 200 and r.json()["ready"] is False
```

- [ ] **Step 2: Run to verify fail**

Run: `cd studio && uv run pytest tests/test_studio_app.py -k reload -v`
Expected: FAIL.

- [ ] **Step 3: Implement.**

`sim.py` — refactor `start()`/add `reload()` around a shared `_build()`:
```python
    def _build(self) -> None:
        import asyncio
        data = load_world(self.world_dir)
        app = create_app(
            store=data.store, passability=data.passability, palette=data.palette,
            tilemap_data=data.tilemap_data, world_id=data.world_id,
            width=data.width, height=data.height, sprite_dir=data.sprite_dir,
            ai_model=self.ai_model, world_dir=self.world_dir,
        )
        asyncio.get_running_loop().create_task(app.state.tick_loop.start())
        self._app = app

    def start(self) -> bool:
        if self._app is not None:
            return True
        if self.missing():
            return False
        self._build()
        return True

    def reload(self) -> bool:
        if self.missing():
            return False
        if self._app is not None:
            try:
                self._app.state.tick_loop.stop()
            except Exception:
                pass
        self._build()
        return True
```

`app.py` — add the route next to `/sim/start`:
```python
    @app.post("/sim/reload")
    async def sim_reload():
        if sim is None:
            return {"ready": False, "missing": ["world"]}
        missing = sim.missing()
        if missing:
            return {"ready": False, "missing": missing}
        sim.reload()
        return {"ready": True, "missing": []}
```

- [ ] **Step 4: Run to verify pass + full studio suite**

Run: `cd studio && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add studio/src/studio/sim.py studio/src/studio/app.py studio/tests/
git commit -m "feat(studio): SimHolder.reload + POST /sim/reload to pick up god edits"
```

---

### Task 3: World HUD controls (Pause / God / Reload)

**Files:** Modify `engine/renderer/index.html`, `engine/renderer/js/ui_layer.js`. (No unit test; `node --check` + manual.)

**Interfaces:** Consumes `/pause`, `/resume`, `/status` (Task 1), `/sim/reload` (Task 2), `window.__BASE__` (base path).

- [ ] **Step 1: Add the controls to the status bar.** In `engine/renderer/index.html`, inside `#status-bar` (after `#conn-status`), add:
```html
    <span id="controls" style="margin-left:auto; display:flex; gap:8px;">
      <button id="pause-btn" class="hud-btn">⏸ Pause</button>
      <button id="reload-btn" class="hud-btn" style="display:none">⟳ Reload</button>
      <a id="god-link" class="hud-btn" href="/" style="display:none; text-decoration:none">◀ God</a>
    </span>
```
Add a small `.hud-btn` style near the other status-bar CSS (compact, dark, hover). 

- [ ] **Step 2: Wire them in `ui_layer.js`.** In `setupUI()` add:
```js
  const BASE = window.__BASE__ || "";
  const pauseBtn = document.getElementById('pause-btn');
  let paused = false;
  function renderPause() { pauseBtn.textContent = paused ? '▶ Resume' : '⏸ Pause'; }
  fetch(BASE + '/status').then(r => r.json()).then(s => { paused = !!s.paused; renderPause(); }).catch(() => {});
  pauseBtn?.addEventListener('click', async () => {
    const path = paused ? '/resume' : '/pause';
    const r = await fetch(BASE + path, { method: 'POST' }).then(r => r.json()).catch(() => null);
    if (r) { paused = r.paused; renderPause(); }
  });
  // studio-only controls: God link + Reload
  if (BASE) {
    const god = document.getElementById('god-link'); if (god) god.style.display = 'inline-block';
    const reload = document.getElementById('reload-btn');
    if (reload) {
      reload.style.display = 'inline-block';
      reload.addEventListener('click', async () => {
        const r = await fetch('/sim/reload', { method: 'POST' }).then(r => r.json()).catch(() => null);
        if (r && r.ready) location.reload();
      });
    }
  }
```
(`setupUI` is already called once from `renderer.js`; if it isn't `export`ed with a body that runs at load, place this in the existing `setupUI` function.)

- [ ] **Step 3: Verify** — `node --check` (via `.mjs` copies) on `ui_layer.js`; confirm `renderer.js` still `node --check`s. Manual smoke happens in Task 4.

- [ ] **Step 4: Commit**

```bash
git add engine/renderer/index.html engine/renderer/js/ui_layer.js
git commit -m "feat(renderer): World HUD — pause/resume, and (under studio) God + Reload"
```

---

### Task 4: End-to-end + restart the server

**Files:** none (manual).

- [ ] **Step 1: Both suites green** — `cd engine && uv run pytest -q` and `cd studio && uv run pytest -q`.

- [ ] **Step 2: Drive it via TestClient** (deterministic, no LLM) — build `create_studio_app` on a copy of `demo_world`, `POST /sim/start`, then: `POST /pause` → the mounted engine returns `{"paused":true}` at `/sim/pause`; `GET /sim/status` shows paused; `POST /sim/resume`; `POST /sim/reload` → `{"ready":true}`; `GET /sim/` still serves the renderer with the HUD markup (`pause-btn`, `god-link`).

- [ ] **Step 3: Restart the live studio** (if one is running: `fuser -k -TERM 8080/tcp`), then relaunch `studio --palette ../palettes/verdant --world ../myworld --port 8080` and confirm in the browser: Play → the World shows `⏸ Pause` (toggles, world freezes/resumes), `◀ God` returns to the Forge, `⟳ Reload` rebuilds.

---

## Self-Review

**Spec coverage:** pause/resume + endpoints → Task 1; reload → Task 2; HUD Pause/God/Reload → Task 3; e2e + restart → Task 4. ✓
**Placeholder scan:** `.hud-btn` CSS is described (presentational) — acceptable; all logic steps have complete code.
**Type consistency:** `TickLoop.pause/resume/paused/tick`; `/pause`/`/resume`/`/status` shapes; `SimHolder.reload()`; `/sim/reload` shape; `window.__BASE__` gating — consistent across tasks.
