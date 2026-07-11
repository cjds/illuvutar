# Studio — One Website for Building & Playing Worlds — Design

**Date:** 2026-07-11
**Status:** Approved (design; decisions delegated)
**Scope:** new `studio/` project; small `engine` renderer change; remove the `illuvutar` TUI

## Goal

Replace the Textual TUI with a single website that does both halves of illuvutar:

1. **Forge** — chat with the god in the browser to build/edit a world, watching its
   steps stream live (querying palette → wrote constitution → running WFC → populating).
2. **World** — watch and interact with the live simulation of that world.

One server, one URL, one process. The god and the engine become libraries the studio
drives; the TUI goes away.

## Decisions

- **`studio/`** is a new top-level uv project depending on `illuvutar` and `engine` (path
  deps). illuvutar stays the god library; engine stays the sim library; studio is the web
  orchestrator. Launched by a `studio` console script that replaces `illuvutar create-world`.
- **In-process**: the studio runs the god (imports `GodAgent`, `AgentTools`, `LLMClient`,
  `WorldStateWriter`) and hosts the sim by reusing the engine's `load_world` + `TickLoop`
  + serializer + `SSEBroadcaster` + renderer. No subprocess, no second port.
- **Streaming**: the god emits per-step events over SSE.
- **Vanilla frontend** (ES modules + HTML/CSS), consistent with the engine renderer; no
  build step.
- **MVP is single-world**: the studio is launched for one `--world` dir (like the old
  `create-world`) and serves Forge + World for it. A multi-world browser is a follow-up.

## Current state

- God: `illuvutar` `GodAgent.chat(msg) -> str` (blocking; runs the tool loop via
  `LLMClient`). Driven today only by the Textual `GodChatApp` (`tui/app.py`) launched from
  `cli.py create_world`.
- Sim: `engine` is already a FastAPI web app — `create_app(...)`, `TickLoop`,
  `SSEBroadcaster` (`server/sse.py`), `serialize` (`wrl/serializer.py`), `load_world`, and
  a vanilla renderer (`engine/renderer/`). Its renderer fetches **absolute** URLs
  (`/frames`, `/command`, `/thoughts`, `/entity/<id>/profile`), so it must be made
  base-path-aware to serve under a sub-path.

## Design

### Part A — God streaming API (`illuvutar`)

`GodAgent` gains an event-emitting turn so the studio can stream progress. Refactor the
tool loop to yield events; keep `chat()` as a thin consumer for back-compat.

```python
def chat_stream(self, human_message: str) -> Iterator[dict]:
    """Yield events as the god works, then persist memory:
       {"type": "tool_call",   "name": str, "args": dict}
       {"type": "tool_result", "name": str, "result": str}
       {"type": "message",     "text": str}
       {"type": "done",        "complete": bool}   # complete == is_done()"""
```

`chat(msg)` becomes `"".join(e["text"] for e in chat_stream(msg) if e["type"]=="message")`
(or keeps the last message) — existing callers/tests unaffected. Event granularity is
per-loop-step (each tool call, each assistant turn), which is the live "God ▸ …" feel; no
token-level streaming for the MVP.

### Part B — Studio server (`studio/`)

A FastAPI app (`studio/src/studio/app.py::create_studio_app(world_dir, palette_dir, client,
…)`) built at launch. It owns:

- **God session** (`studio/god_session.py`): holds the `GodAgent` + `WorldStateWriter` +
  `AgentTools`. A god turn runs in a threadpool (the god is sync); its `chat_stream` events
  are pushed onto an `asyncio.Queue` that an SSE endpoint drains. One turn at a time.
- **Sim holder** (`studio/sim.py`): lazily builds the engine app for the world on demand
  (`load_world(world_dir)` → `create_app(...)`), exposed under `/sim` via a **swappable
  ASGI dispatcher** (a mount whose target is `None` until the world is built, then the
  engine app; rebuildable when the world changes). This avoids runtime `app.mount()`
  fragility and makes "build, then play" work without a restart.

**Routes:**

| Route | Does |
|---|---|
| `GET /` | the studio shell (Forge + World tabs for the world) |
| `GET /forge/events` (SSE) | streams the current/So-far god turn's events |
| `POST /forge/message` `{text}` | starts a god turn (threadpool → event queue); 409 if one is already running |
| `GET /forge/status` | world-state file status (`WorldStateWriter.status()`) for a build checklist |
| `POST /sim/start` | (re)build the engine app for the world; returns ready/needs-build |
| `/sim/**` | the mounted engine app (renderer, `/sim/frames`, `/sim/command`, `/sim/entity/…`, `/sim/thoughts`) |

Static studio web assets served from `studio/web/`; the engine renderer is reused for the
World view.

### Part C — Engine renderer base-path awareness (`engine`)

The renderer must work whether served at `/` (standalone engine) or `/sim/` (under the
studio). Add a single base derived from the page (e.g. a `data-base` attribute on a root
element, defaulting to `""`), and route every network call through it:
`new EventSource(BASE + '/frames')`, `fetch(BASE + '/command')`, `.../thoughts`,
`.../entity/${id}/profile`. Touches `renderer.js`, `ui_layer.js`, `profile_panel.js`,
`index.html`. Standalone engine behavior is unchanged (BASE `""`).

### Part D — Forge web UI (`studio/web/`)

A chat page (vanilla): a transcript, an input, and a live build panel.
- Submitting posts to `/forge/message` and subscribes to `/forge/events` (SSE), rendering
  each event as it arrives — tool calls as dim step lines ("▸ running WFC…"), the god's
  message in full, a spinner while a turn is in flight.
- A side panel shows `/forge/status` (constitution ✓, regions ✓, tilemap ✓, roles ✓,
  agents ✓) so you can see the world take shape.
- A **Play** button calls `/sim/start` and switches to the World tab once ready.

### Part E — Remove the TUI, add the `studio` command

- Delete `src/illuvutar/tui/` (`GodChatApp`) and its tests; drop `textual` from
  `illuvutar` deps.
- `illuvutar create_world` (the TUI command) is removed; world-building now happens in the
  studio. `illuvutar` keeps its library role (god, tools, generation).
- New `studio` console script: `studio --palette <dir> --world <dir> [--port 8080]
  [--llm-endpoint …] [--model …] [--ai-model …]` → indexes the palette, builds the RAG +
  `LLMClient` + `GodAgent`, and runs the studio app with uvicorn. This is the single entry
  point that replaces both `illuvutar create-world` and `illuvutar-engine` for normal use
  (the engine's own CLI stays for headless/standalone runs).

## Components & boundaries

| Unit | Responsibility | Depends on |
|------|----------------|------------|
| `illuvutar` `GodAgent.chat_stream` | Emit per-step god events | `LLMClient`, `AgentTools` |
| `studio/god_session.py` | Run god turns in a threadpool; event queue → SSE | `GodAgent` |
| `studio/sim.py` | Lazy engine app per world behind a swappable `/sim` mount | `engine.load_world`, `engine.create_app` |
| `studio/app.py` | Wire routes + static + god + sim into one FastAPI app | the two above |
| `studio/__main__.py` | CLI → build deps → uvicorn | `illuvutar`, `studio.app` |
| `studio/web/` | Forge chat + shell (vanilla) | the SSE/HTTP routes |
| engine renderer | Base-path aware so it serves under `/sim` | — |

## Error handling

- A god turn already running → `POST /forge/message` returns 409; the UI disables send
  while a turn streams.
- God turn raises (LLM/endpoint down) → an `{"type":"error","message":…}` event is streamed
  and the turn ends cleanly; the UI shows it (no silent hang — the whole point).
- `/sim/start` before the world has a `tilemap` → returns "needs build" with the missing
  files; the World tab shows "build the world first."
- SSE disconnect → the browser reconnects (`EventSource` default); events are per-turn so a
  missed turn is acceptable (status panel reflects truth).
- Studio launched on a world dir that doesn't exist yet → created empty; Forge starts from
  a blank world.

## Testing

- **`GodAgent.chat_stream`** (mocked `LLMClient`): emits `tool_call`/`tool_result`/`message`
  events in order for a tool-then-answer turn; `done.complete` reflects "world is complete";
  `chat()` still returns the final text (back-compat test stays green).
- **`god_session`**: a turn's events reach the queue; a second concurrent turn is rejected.
- **`studio/app`** (FastAPI `TestClient`): `GET /` 200; `POST /forge/message` accepts +
  streams (drive the god with a mocked client); `/forge/status` returns the file map;
  `/sim/start` returns "needs build" on an empty world and "ready" once a tilemap exists;
  `/sim/**` reaches the mounted engine app once started.
- **engine renderer**: `node --check` on the changed JS; a small test that BASE defaults to
  `""` (standalone unchanged) — or manual, since JS is untested here.
- **Manual e2e**: `studio --palette … --world /tmp/w`, build a small world by chatting,
  watch steps stream, hit Play, see the sim.

## Migration & cleanup

- Remove `src/illuvutar/tui/` + `tests/test_tui.py`; drop `textual` dep; remove the
  `create_world` command from `cli.py` (or make it print "use `studio`").
- The engine and its `illuvutar-engine` CLI are unchanged (still usable headless).

## Out of scope (YAGNI)

- Multi-world browser / a worlds gallery (single `--world` MVP; add later).
- Auth / multi-user / the spectator-broadcast work from the scaling doc.
- Token-level god streaming (per-step events are enough).
- Editing the world by direct form UI (the god + chat is the editor).
- Packaging/deploy (a follow-up; this is the local dev studio first).

## Suggested phasing (for the plan)

1. **God events**: `GodAgent.chat_stream` (+ back-compat `chat`).
2. **Studio scaffold + Forge**: the `studio` project, god session, `/forge/*`, the chat UI,
   the `studio` command — this alone replaces the TUI.
3. **World view**: engine renderer base-path fix; `studio/sim.py` + `/sim/*`; the Play flow.
4. **Remove the TUI**: delete `tui/`, drop `textual`, retire `create_world`.
