# Pause & Tweak — Control the Live World, Hop to the God — Design

**Date:** 2026-07-11
**Status:** Approved (design; decisions delegated)
**Scope:** `engine` (tick pause + endpoints + renderer HUD) + `studio` (reload)

## Goal

While the studio is running, let the player **pause the live simulation**, **hop to the god**
(the Forge) to change the world by chat, **reload** so those edits take effect, and **resume** —
without restarting the server. The god chat itself already exists (the Forge screen); this adds
the control surface around the running World.

The loop: **⏸ Pause → ◀ God (edit the world) → ⟳ Reload → ▶ Resume.**

## Decisions

- Pause is a `TickLoop` flag that skips ticking (the world freezes; the renderer holds its last
  frame; no entity thinking / no LLM calls while paused). Endpoints live on the engine
  `create_app`, so they work standalone AND under the studio's `/sim` mount (the renderer is
  already base-path aware).
- The god is reached from the World via a link to the studio root `/` (the Forge), shown only
  when running under the studio (`window.__BASE__` set).
- Reload is a studio concern (`SimHolder.reload()`): stop the current tick loop, rebuild the
  engine app from the (now god-edited) world files. This is the missing piece that makes
  "edit with the god, then see it" work, given `SimHolder.start()` is idempotent.

## Design

### Part A — Pause/Resume the tick loop (`engine`)

`TickLoop`:
- `self._paused = False` in `__init__`.
- `pause()` sets it True; `resume()` sets it False; `paused` property returns it.
- `start()`: `while self._running: if not self._paused: await self._tick_once(); await asyncio.sleep(self._tick_interval)`. Paused → the loop stays alive but advances no ticks (no movement, no thinking, no frame broadcast).

`create_app` routes:
- `POST /pause` → `tick_loop.pause()`, returns `{"paused": True}`.
- `POST /resume` → `tick_loop.resume()`, returns `{"paused": False}`.
- `GET /status` → `{"paused": tick_loop.paused, "tick": tick_loop.tick}` (add a `tick` read-only property to `TickLoop` exposing `self._tick`).

### Part B — World HUD controls (`engine/renderer`)

In the renderer status bar (`#status-bar`), add:
- A **Pause/Resume toggle** button: POSTs `${BASE}/pause` or `${BASE}/resume`, flips its label
  (`⏸ Pause` ↔ `▶ Resume`). On load, reads `${BASE}/status` to show the right label.
- A **`◀ God`** link, shown only when `window.__BASE__` is truthy (under the studio), href `/`
  (the studio Forge). Hidden for the standalone engine.
- A **`⟳ Reload`** button, shown only under the studio: POSTs `${BASE}/../sim/reload`? — no; the
  reload endpoint is a studio route, and from `/sim/` the studio root is `/`, so the button
  POSTs `/sim/reload` (absolute studio path, valid because the World page is served by the
  studio). Standalone engine: hidden (no studio to reload). On success it reloads the page so the
  fresh sim renders.

All three live in the existing `ui_layer.js`/`index.html`; base-aware via `window.__BASE__`.

### Part C — Reload the sim after god edits (`studio`)

`SimHolder`:
- `reload() -> bool`: if `missing()`, return False. If a sim is running, `self._app.state.tick_loop.stop()` (halt the old loop), then rebuild exactly as `start()` does (load_world → create_app → schedule the new tick loop) and replace `self._app`. Returns True.
- (Refactor: `start()` and `reload()` share a private `_build()`; `start()` keeps its idempotent
  "already running → return True", `reload()` always rebuilds.)

`studio/app.py`: `POST /sim/reload` → `{"ready": bool, "missing": [...]}` (parallels `/sim/start`).

## Error handling

- `/pause`/`/resume` when the sim isn't started (studio, before Play): the `/sim` mount returns
  503 (existing behavior) — the HUD buttons only appear on the loaded renderer, so this is moot in
  practice; standalone always has a loop.
- `/sim/reload` before the world is built → `{"ready": False, "missing": [...]}`, no rebuild.
- Reload stops the prior loop before building the new one (no orphaned loop — consistent with the
  idempotent-start fix).

## Testing

- **`TickLoop`**: `pause()`/`resume()` toggle `paused`; `start()` does not advance `_tick` while
  paused and resumes advancing after `resume()` (drive a few iterations with a tiny
  `tick_interval`); `tick` property reads `_tick`.
- **`create_app`** (TestClient): `POST /pause` → `{"paused": True}` and the loop's `paused` is set;
  `POST /resume` → `{"paused": False}`; `GET /status` reflects it.
- **`SimHolder.reload`** (studio, async + fakes like the idempotent-start test): reload rebuilds
  (create_app called again) and stops the previous loop; reload on a missing world → False.
- **`/sim/reload`** route → `{"ready": ...}` shape.
- **Renderer**: `node --check`; manual — pause freezes the world, `◀ God` returns to Forge,
  `⟳ Reload` picks up edits.

## Out of scope (YAGNI)

- Per-entity pause / time controls (speed up/slow down) — just pause/resume.
- Hot state-diff reload that preserves evolved entity memory across a reload (reload reloads from
  files; `.entities/<id>.json` persistence already carries evolved state, so a reload keeps it).
- A pause indicator overlay beyond the button label.
