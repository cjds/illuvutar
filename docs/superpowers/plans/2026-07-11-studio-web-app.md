# Studio Web App — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One website — a Forge screen that streams the god building a world, and a World screen that runs the live sim — replacing the Textual TUI.

**Architecture:** A new `studio/` FastAPI app depends on `illuvutar` (god) and `engine` (sim) as libraries and runs both in-process. `GodAgent` gains a streaming `chat_stream`; the studio runs a god turn in a threadpool and fans its events out over SSE. The engine renderer is made base-path-aware and served under `/sim`, whose engine app is built lazily (with its tick loop started manually, since mounted sub-apps don't get lifespan events).

**Tech Stack:** Python 3.12, FastAPI/uvicorn, `openai` (via illuvutar's LLMClient), pytest + FastAPI TestClient. Vanilla ES-module frontend. `illuvutar` tests run from repo ROOT; `engine` tests from `engine/`; new `studio` tests from `studio/`.

## Global Constraints

- `studio/` is a new top-level uv project; deps on `illuvutar` and `engine` via `[tool.uv.sources]` editable path deps (`illuvutar` → `..`, `engine` → `../engine`). Console script `studio = "studio.__main__:main"`.
- The god runs **in a threadpool** (it's synchronous); its `chat_stream` events reach the event loop via `loop.call_soon_threadsafe`. **One god turn at a time** (409 if busy).
- God event shapes: `{"type":"tool_call","name","args"}`, `{"type":"tool_result","name","result"}`, `{"type":"message","text"}`, `{"type":"done","complete":bool}`, `{"type":"error","message"}`.
- `chat()` stays working (returns the final message text) — existing god tests must stay green.
- The engine renderer must work at `/` (standalone) AND `/sim/` (under studio): `BASE = window.__BASE__ || ""`, injected by the engine `/` route from `request.scope["root_path"]`; standalone BASE is `""` (unchanged behavior).
- Mounted engine sub-app: its tick loop is started **manually** by the studio (mounted apps don't receive lifespan/startup) — `create_app` exposes `app.state.tick_loop`.
- The Textual TUI (`src/illuvutar/tui/`, `tests/test_tui.py`, the `textual` dep, the `create_world` CLI command) is removed.

## File Structure

**Create:** `studio/pyproject.toml`, `studio/src/studio/__init__.py`, `studio/src/studio/__main__.py`, `studio/src/studio/app.py`, `studio/src/studio/god_session.py`, `studio/src/studio/sim.py`, `studio/web/index.html`, `studio/web/forge.js`, `studio/web/studio.css`, `studio/tests/test_studio_app.py`, `studio/tests/test_god_session.py`, `studio/tests/conftest.py`.
**Modify:** `src/illuvutar/agents/god.py` (chat_stream), `tests/test_god.py`; `engine/src/engine/server/app.py` (BASE inject + `app.state.tick_loop`), `engine/renderer/index.html`, `engine/renderer/js/renderer.js`, `engine/renderer/js/ui_layer.js`, `engine/renderer/js/profile_panel.js`, `engine/tests/test_server.py`; `src/illuvutar/cli.py` (drop `create_world`), `pyproject.toml` (drop `textual`).
**Delete:** `src/illuvutar/tui/` (`app.py`, `__init__.py`), `tests/test_tui.py`.

---

### Task 1: God streaming (`chat_stream`)

**Files:** Modify `src/illuvutar/agents/god.py`; Test `tests/test_god.py`.

**Interfaces:**
- Produces: `GodAgent.chat_stream(human_message: str) -> Iterator[dict]` yielding the event shapes above and saving memory at the end; `chat()` reimplemented on top of it (returns final message text).

- [ ] **Step 1: Write the failing test** — append to `tests/test_god.py`:

```python
def test_chat_stream_emits_tool_and_message_events(mock_tools):
    tc = ToolCall(id="c1", name="query_palette", arguments={"description": "grass"})
    first = LLMMessage(content="", tool_calls=[tc],
                       raw={"role": "assistant", "content": "", "tool_calls": [
                           {"id": "c1", "type": "function",
                            "function": {"name": "query_palette", "arguments": "{}"}}]})
    second = LLMMessage(content="The world is complete.", tool_calls=[],
                        raw={"role": "assistant", "content": "The world is complete."})
    agent = GodAgent(client=_client(first, second), tools=mock_tools)
    events = list(agent.chat_stream("build it"))
    kinds = [e["type"] for e in events]
    assert kinds == ["tool_call", "tool_result", "message", "done"]
    assert events[0]["name"] == "query_palette" and events[0]["args"] == {"description": "grass"}
    assert events[-1]["complete"] is True
    assert agent.is_done()


def test_chat_still_returns_final_text(mock_tools):
    c = _client(LLMMessage(content="A forest.", tool_calls=[],
                           raw={"role": "assistant", "content": "A forest."}))
    assert "forest" in GodAgent(client=c, tools=mock_tools).chat("go")
```

(`mock_tools`, `_client`, `LLMMessage`, `ToolCall` already exist in the file from prior tasks.)

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_god.py -k chat_stream -v`
Expected: FAIL (`chat_stream` missing).

- [ ] **Step 3: Implement** — in `god.py`, replace `chat` and `_run_loop` with:

```python
    def chat(self, human_message: str) -> str:
        text = ""
        for event in self.chat_stream(human_message):
            if event["type"] == "message":
                text = event["text"]
        return text

    def chat_stream(self, human_message: str):
        self.messages.append({"role": "user", "content": human_message})
        tool_defs = AgentTools.definitions()
        while True:
            msg = self.client.chat(self.messages, tools=tool_defs or None)
            self.messages.append(msg.raw)
            if not msg.tool_calls:
                text = msg.content or ""
                if text:
                    yield {"type": "message", "text": text}
                    if "world is complete" in text.lower():
                        self._done = True
                break
            for tc in msg.tool_calls:
                yield {"type": "tool_call", "name": tc.name, "args": tc.arguments}
                result = self._dispatch(tc.name, tc.arguments)
                self.messages.append({"role": "tool", "tool_call_id": tc.id,
                                      "content": str(result)})
                yield {"type": "tool_result", "name": tc.name, "result": str(result)}
        yield {"type": "done", "complete": self._done}
        if self._memory:
            self._memory.save(self.messages)
```

(Keep `is_done`, `_dispatch`, `_sanitize`, `__init__` unchanged.)

- [ ] **Step 4: Run to verify pass + full root suite**

Run: `uv run pytest tests/test_god.py -v` then `uv run pytest -q`.
Expected: PASS (existing `chat` tests still green).

- [ ] **Step 5: Commit**

```bash
git add src/illuvutar/agents/god.py tests/test_god.py
git commit -m "feat(illuvutar): GodAgent.chat_stream emits per-step build events"
```

---

### Task 2: Studio scaffold + shell + status

**Files:** Create `studio/pyproject.toml`, `studio/src/studio/__init__.py`, `studio/src/studio/app.py`, `studio/src/studio/god_session.py` (minimal), `studio/tests/conftest.py`, `studio/tests/test_studio_app.py`.

**Interfaces:**
- Produces: `create_studio_app(session) -> FastAPI` with `GET /` (shell HTML) and `GET /forge/status` (world-state map). `GodSession(god, writer)` with `.status() -> dict`.

- [ ] **Step 1: Create the project.** `studio/pyproject.toml`:

```toml
[project]
name = "studio"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["fastapi[standard]>=0.111", "uvicorn>=0.30", "illuvutar", "engine"]

[project.scripts]
studio = "studio.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv.sources]
illuvutar = { path = "..", editable = true }
engine = { path = "../engine", editable = true }

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
asyncio_mode = "auto"

[dependency-groups]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23", "httpx>=0.27"]
```

Create `studio/src/studio/__init__.py` (empty).

- [ ] **Step 2: Write the failing test** — `studio/tests/conftest.py`:

```python
from unittest.mock import MagicMock
import pytest
from studio.god_session import GodSession


@pytest.fixture
def fake_session():
    writer = MagicMock()
    writer.status.return_value = {"constitution": True, "tilemap": False}
    return GodSession(god=MagicMock(), writer=writer)
```

`studio/tests/test_studio_app.py`:

```python
from fastapi.testclient import TestClient
from studio.app import create_studio_app


def test_shell_served(fake_session):
    c = TestClient(create_studio_app(fake_session))
    r = c.get("/")
    assert r.status_code == 200 and "Forge" in r.text


def test_forge_status(fake_session):
    c = TestClient(create_studio_app(fake_session))
    r = c.get("/forge/status")
    assert r.status_code == 200
    assert r.json() == {"constitution": True, "tilemap": False}
```

- [ ] **Step 3: Run to verify fail**

Run: `cd studio && uv run pytest -q`
Expected: FAIL (modules missing). (`uv sync` first if needed.)

- [ ] **Step 4: Implement.** `studio/src/studio/god_session.py`:

```python
"""Owns the god agent and streams a turn's events to SSE subscribers."""
import asyncio


class GodSession:
    def __init__(self, god, writer):
        self.god = god
        self.writer = writer
        self._subscribers: list[asyncio.Queue] = []
        self._running = False

    def status(self) -> dict:
        return self.writer.status()
```

`studio/src/studio/app.py`:

```python
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

WEB_DIR = Path(__file__).parent.parent.parent / "web"


def create_studio_app(session) -> FastAPI:
    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    async def shell():
        html = WEB_DIR / "index.html"
        return html.read_text() if html.exists() else "<h1>Forge</h1>"

    @app.get("/forge/status")
    async def forge_status():
        return session.status()

    if WEB_DIR.is_dir():
        app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")
    return app
```

Create a minimal `studio/web/index.html` so the shell test passes:

```html
<!doctype html><html><head><meta charset="utf-8"><title>illuvutar studio</title>
<link rel="stylesheet" href="/web/studio.css"></head>
<body><h1>Forge</h1><div id="app"></div>
<script type="module" src="/web/forge.js"></script></body></html>
```

Create empty `studio/web/studio.css` and `studio/web/forge.js` (filled in Task 4).

- [ ] **Step 5: Run to verify pass**

Run: `cd studio && uv run pytest -q`
Expected: PASS (2).

- [ ] **Step 6: Commit**

```bash
git add studio/
git commit -m "feat(studio): project scaffold, shell + /forge/status"
```

---

### Task 3: Forge streaming (god turns over SSE)

**Files:** Modify `studio/src/studio/god_session.py`, `studio/src/studio/app.py`; Test `studio/tests/test_god_session.py`, extend `studio/tests/test_studio_app.py`.

**Interfaces:**
- Consumes: `GodAgent.chat_stream` (Task 1).
- Produces: `GodSession.run_turn(text) -> bool` (False if a turn is already running); `GodSession.subscribe()/unsubscribe()`; SSE `GET /forge/events`; `POST /forge/message {text}` (409 if busy).

- [ ] **Step 1: Write the failing test** — `studio/tests/test_god_session.py`:

```python
import asyncio
import pytest
from unittest.mock import MagicMock
from studio.god_session import GodSession


@pytest.mark.asyncio
async def test_run_turn_streams_events_then_rejects_concurrent():
    god = MagicMock()
    god.chat_stream.return_value = iter([
        {"type": "tool_call", "name": "run_wfc", "args": {}},
        {"type": "message", "text": "done"},
        {"type": "done", "complete": True},
    ])
    s = GodSession(god=god, writer=MagicMock())
    q = s.subscribe()
    assert await s.run_turn("build") is True
    assert await s.run_turn("again") is False          # one turn at a time
    seen = []
    while True:
        e = await asyncio.wait_for(q.get(), timeout=2)
        seen.append(e)
        if e.get("type") == "turn_end":
            break
    kinds = [e["type"] for e in seen]
    assert "tool_call" in kinds and "message" in kinds and kinds[-1] == "turn_end"
    assert await s.run_turn("now free") is True         # freed after turn_end
```

- [ ] **Step 2: Run to verify fail**

Run: `cd studio && uv run pytest tests/test_god_session.py -v`
Expected: FAIL (`run_turn`/`subscribe` missing).

- [ ] **Step 3: Implement.** Extend `god_session.py`:

```python
    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    def _emit(self, event: dict) -> None:
        for q in list(self._subscribers):
            q.put_nowait(event)

    async def run_turn(self, text: str) -> bool:
        if self._running:
            return False
        self._running = True
        loop = asyncio.get_running_loop()

        def work():
            try:
                for event in self.god.chat_stream(text):
                    loop.call_soon_threadsafe(self._emit, event)
            except Exception as ex:
                loop.call_soon_threadsafe(self._emit, {"type": "error", "message": str(ex)})
            finally:
                loop.call_soon_threadsafe(self._finish)

        loop.run_in_executor(None, work)
        return True

    def _finish(self) -> None:
        self._running = False
        self._emit({"type": "turn_end"})
```

Add SSE + message routes to `app.py` (imports `asyncio`, `json`, `Request`, `Response`, `StreamingResponse`):

```python
    @app.post("/forge/message")
    async def forge_message(request: Request):
        body = await request.json()
        text = (body.get("text") or "").strip()
        if not text:
            return Response("Missing text", status_code=400)
        if not await session.run_turn(text):
            return Response("A build turn is already running", status_code=409)
        return {"ok": True}

    @app.get("/forge/events")
    async def forge_events():
        q = session.subscribe()

        async def stream():
            try:
                while True:
                    event = await q.get()
                    yield f"data: {json.dumps(event)}\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                session.unsubscribe(q)

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

- [ ] **Step 4: Add an app-level test** — append to `test_studio_app.py`:

```python
def test_forge_message_triggers_turn(fake_session, monkeypatch):
    import asyncio
    async def ok(text): return True
    fake_session.run_turn = ok
    c = TestClient(create_studio_app(fake_session))
    assert c.post("/forge/message", json={"text": "build"}).status_code == 200
    assert c.post("/forge/message", json={"text": ""}).status_code == 400
```

- [ ] **Step 5: Run to verify pass**

Run: `cd studio && uv run pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add studio/src/studio/god_session.py studio/src/studio/app.py studio/tests/
git commit -m "feat(studio): stream god build turns over SSE (one at a time)"
```

---

### Task 4: Forge web UI + the `studio` command

**Files:** Modify `studio/web/index.html`, `studio/web/forge.js`, `studio/web/studio.css`; Create `studio/src/studio/__main__.py`. (No unit test for the JS; the `studio` command is smoke-tested manually + `--help`.)

**Interfaces:**
- Consumes: `/forge/message`, `/forge/events`, `/forge/status`.
- Produces: the Forge page (chat + live steps + status checklist); `studio` console script builds god deps and runs uvicorn.

- [ ] **Step 1: Implement the Forge page.** `studio/web/index.html`:

```html
<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>illuvutar studio</title><link rel="stylesheet" href="/web/studio.css"></head>
<body>
  <header><b>illuvutar</b> studio <span id="phase">Forge</span></header>
  <main>
    <section id="chat"><div id="log"></div>
      <form id="composer"><input id="msg" placeholder="Tell the god what world to build…" autocomplete="off"><button>Send</button></form>
    </section>
    <aside id="build">
      <h3>World</h3><ul id="status"></ul>
      <button id="play" disabled>▶ Play this world</button>
    </aside>
  </main>
  <script type="module" src="/web/forge.js"></script>
</body></html>
```

`studio/web/forge.js`:

```js
const log = document.getElementById('log');
const statusEl = document.getElementById('status');
const playBtn = document.getElementById('play');

function line(cls, html) {
  const d = document.createElement('div');
  d.className = 'line ' + cls; d.innerHTML = html;
  log.appendChild(d); log.scrollTop = log.scrollHeight; return d;
}

const es = new EventSource('/forge/events');
es.onmessage = (e) => {
  const ev = JSON.parse(e.data);
  if (ev.type === 'tool_call') line('step', `▸ ${ev.name}…`);
  else if (ev.type === 'tool_result') { /* keep quiet; status panel reflects it */ refreshStatus(); }
  else if (ev.type === 'message') line('god', `<b>God:</b> ${ev.text}`);
  else if (ev.type === 'error') line('err', `⚠ ${ev.message}`);
  else if (ev.type === 'turn_end') { setBusy(false); refreshStatus(); }
};

const form = document.getElementById('composer');
const input = document.getElementById('msg');
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = input.value.trim(); if (!text) return;
  line('you', `<b>You:</b> ${text}`); input.value = ''; setBusy(true);
  const r = await fetch('/forge/message', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text})});
  if (r.status === 409) { line('err', 'Still building — wait for the current turn.'); setBusy(false); }
});

function setBusy(b) { input.disabled = b; form.querySelector('button').disabled = b; }

async function refreshStatus() {
  const s = await fetch('/forge/status').then(r => r.json()).catch(() => ({}));
  statusEl.innerHTML = Object.entries(s).map(([k,v]) => `<li class="${v?'ok':'no'}">${v?'✓':'○'} ${k}</li>`).join('');
  playBtn.disabled = !s.tilemap;
}
playBtn.addEventListener('click', async () => {
  const r = await fetch('/sim/start', {method:'POST'}).then(r=>r.json()).catch(()=>({}));
  if (r.ready) location.href = '/sim/';
  else line('err', 'World needs a tilemap first — ask the god to run WFC.');
});
refreshStatus();
```

`studio/web/studio.css` — a small dark theme (header bar; `main` a 2-col grid: `#chat` left, `#build` right; `.line.step` dim, `.god` accent, `.you` muted, `.err` red; `#status li.ok` green, `.no` grey). Keep it tasteful and compact.

- [ ] **Step 2: Implement the `studio` command.** `studio/src/studio/__main__.py`:

```python
"""`studio` CLI: build god deps for a world and serve the studio web app."""
import click
import uvicorn
from pathlib import Path
from illuvutar.palette.indexer import index_palette
from illuvutar.palette.rag import PaletteRAG
from illuvutar.world_state.writer import WorldStateWriter
from illuvutar.agents.tools import AgentTools
from illuvutar.agents.god import GodAgent
from illuvutar.agents.memory import GodMemory
from illuvutar.llm.client import LLMClient
from studio.god_session import GodSession
from studio.app import create_studio_app


@click.command()
@click.option("--palette", required=True, type=click.Path(exists=True))
@click.option("--world", default="world")
@click.option("--model", default="llama3.2")
@click.option("--llm-endpoint", default=None)
@click.option("--llm-api-key", default=None)
@click.option("--ai-model", default="llama3.2", help="Model for in-sim entity thinking")
@click.option("--port", default=8080)
def main(palette, world, model, llm_endpoint, llm_api_key, ai_model, port):
    palette_dir, world_dir = Path(palette), Path(world)
    world_dir.mkdir(parents=True, exist_ok=True)
    tiles = index_palette(palette_dir)
    rag = PaletteRAG.build(tiles, persist_dir=str(world_dir / ".rag"))
    client = LLMClient(endpoint=llm_endpoint, model=model, api_key=llm_api_key)
    writer = WorldStateWriter(world_dir)
    tools = AgentTools(writer=writer, rag=rag, tiles=tiles, palette_dir=palette_dir, client=client)
    god = GodAgent(client=client, tools=tools, memory=GodMemory(world_dir / ".god_memory.json"))
    session = GodSession(god=god, writer=writer)
    app = create_studio_app(session, world_dir=world_dir, palette_dir=palette_dir, ai_model=ai_model)
    print(f"Studio ready → http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port)
```

(`create_studio_app` gains `world_dir`, `palette_dir`, `ai_model` params in Task 6 for the sim; for now accept and ignore extras — update its signature to `create_studio_app(session, world_dir=None, palette_dir=None, ai_model="llama3.2")`.)

- [ ] **Step 3: Verify** — `node --check` each JS via a `.mjs` copy; `cd studio && uv run studio --help` prints options; `cd studio && uv run pytest -q` stays green (update the Task 2 shell test's `create_studio_app(fake_session)` calls still work with the new optional params).

- [ ] **Step 4: Commit**

```bash
git add studio/
git commit -m "feat(studio): Forge chat UI + `studio` command"
```

---

### Task 5: Engine renderer base-path awareness

**Files:** Modify `engine/src/engine/server/app.py`, `engine/renderer/index.html`, `engine/renderer/js/renderer.js`, `engine/renderer/js/ui_layer.js`, `engine/renderer/js/profile_panel.js`; Test `engine/tests/test_server.py`.

**Interfaces:**
- Produces: renderer uses `BASE = window.__BASE__ || ""` for all network calls + sprite root; the engine `/` route injects `window.__BASE__` from `request.scope["root_path"]` (standalone `""`).

- [ ] **Step 1: Write the failing test** — append to `engine/tests/test_server.py` (it already builds an app via `create_app` + `TestClient`; reuse that fixture/pattern):

```python
def test_root_injects_empty_base_standalone(client):
    r = client.get("/")
    assert r.status_code == 200
    assert 'window.__BASE__ = ""' in r.text
```

(If `test_server.py` has no `client` fixture, construct one with the module's existing `create_app` helper.)

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && uv run pytest tests/test_server.py -k base -v`
Expected: FAIL (no injection).

- [ ] **Step 3: Implement.**

`app.py` — change the root route to inject the base from `root_path` (import `Request` if not already):

```python
    @app.get("/", response_class=HTMLResponse)
    async def root(request: Request):
        html_path = RENDERER_DIR / "index.html"
        if not html_path.exists():
            return "<html><body><h1>Renderer not found</h1></body></html>"
        base = request.scope.get("root_path", "")
        inject = f'<script>window.__BASE__ = "{base}";</script>'
        return html_path.read_text().replace("</head>", inject + "</head>", 1)
```

`engine/renderer/index.html:247` — make the script src relative so it resolves under any mount:
`<script type="module" src="js/renderer.js"></script>`

`engine/renderer/js/renderer.js` — add at top: `const BASE = window.__BASE__ || "";` then:
- `new EventSource('/frames')` → `new EventSource(BASE + '/frames')`
- `fetch('/command', {...})` → `fetch(BASE + '/command', {...})`
- `new SpriteAtlas('/sprites')` → `new SpriteAtlas(BASE + '/sprites')`

`engine/renderer/js/ui_layer.js` — `fetch('/thoughts')` → `fetch((window.__BASE__||'') + '/thoughts')`.

`engine/renderer/js/profile_panel.js` — `fetch('/entity/${…}/profile')` → prefix `(window.__BASE__||'')`.

- [ ] **Step 4: Run to verify pass + full engine suite**

Run: `cd engine && uv run pytest -q`; also `node --check` the three JS files (via `.mjs` copies).
Expected: PASS; standalone renderer unchanged (BASE `""`).

- [ ] **Step 5: Commit**

```bash
git add engine/src/engine/server/app.py engine/renderer/ engine/tests/test_server.py
git commit -m "feat(engine): renderer honors a base path so it can be mounted under /sim"
```

---

### Task 6: Studio World view (mount the sim + Play)

**Files:** Modify `engine/src/engine/server/app.py` (expose tick loop), `studio/src/studio/app.py`, `studio/src/studio/sim.py` (create); Test `studio/tests/test_studio_app.py`, `engine/tests/test_server.py`.

**Interfaces:**
- Consumes: `engine.load_world`, `engine.server.app.create_app`, the base-aware renderer (Task 5).
- Produces: `SimHolder(world_dir, ai_model)` with `.start() -> bool` and ASGI `__call__` (503 until started); studio mounts it at `/sim`; `POST /sim/start` returns `{"ready": bool, "missing": [...]}`. `create_app` sets `app.state.tick_loop`.

- [ ] **Step 1: Write the failing tests.**

`engine/tests/test_server.py` — assert the tick loop is exposed:

```python
def test_create_app_exposes_tick_loop():
    app = _make_app()   # the module's existing helper that builds a create_app() app
    assert hasattr(app.state, "tick_loop")
```

`studio/tests/test_studio_app.py`:

```python
def test_sim_start_needs_tilemap(tmp_path, fake_session):
    from studio.app import create_studio_app
    c = TestClient(create_studio_app(fake_session, world_dir=tmp_path))
    r = c.post("/sim/start")
    assert r.status_code == 200 and r.json()["ready"] is False
    assert "tilemap" in r.json()["missing"]
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && uv run pytest tests/test_server.py -k tick_loop -v` and `cd studio && uv run pytest tests/test_studio_app.py -k sim_start -v`.
Expected: FAIL.

- [ ] **Step 3: Implement.**

`engine/src/engine/server/app.py` — after `tick_loop = TickLoop(...)` add: `app.state.tick_loop = tick_loop`. (The existing `@app.on_event("startup")` that starts it stays for standalone use; under a studio mount it won't fire, so the studio starts it manually — see below.)

`studio/src/studio/sim.py`:

```python
"""Lazily builds and serves the engine app for a world, behind a swappable /sim mount."""
import asyncio
from pathlib import Path
from starlette.responses import PlainTextResponse
from engine.loader import load_world
from engine.server.app import create_app

_REQUIRED = ["constitution", "palette", "tilemap"]


class SimHolder:
    def __init__(self, world_dir, ai_model: str = "llama3.2"):
        self.world_dir = Path(world_dir)
        self.ai_model = ai_model
        self._app = None

    def missing(self) -> list[str]:
        out = []
        for name in _REQUIRED:
            if not ((self.world_dir / f"{name}.yaml").exists() or
                    (self.world_dir / f"{name}.json").exists()):
                out.append(name)
        return out

    def start(self) -> bool:
        if self.missing():
            return False
        data = load_world(self.world_dir)
        app = create_app(
            store=data.store, passability=data.passability, palette=data.palette,
            tilemap_data=data.tilemap_data, world_id=data.world_id,
            width=data.width, height=data.height, sprite_dir=data.sprite_dir,
            ai_model=self.ai_model, world_dir=self.world_dir,
        )
        asyncio.get_event_loop().create_task(app.state.tick_loop.start())
        self._app = app
        return True

    async def __call__(self, scope, receive, send):
        if self._app is None:
            await PlainTextResponse("Build the world first, then Play.", status_code=503)(scope, receive, send)
            return
        await self._app(scope, receive, send)
```

`studio/src/studio/app.py` — accept the sim params, create a `SimHolder`, mount it, and add `/sim/start`:

```python
from studio.sim import SimHolder
...
def create_studio_app(session, world_dir=None, palette_dir=None, ai_model="llama3.2") -> FastAPI:
    app = FastAPI()
    sim = SimHolder(world_dir, ai_model) if world_dir else None
    ...  # existing / and /forge routes

    @app.post("/sim/start")
    async def sim_start():
        if sim is None:
            return {"ready": False, "missing": ["world"]}
        missing = sim.missing()
        if missing:
            return {"ready": False, "missing": missing}
        sim.start()
        return {"ready": True, "missing": []}

    if sim is not None:
        app.mount("/sim", sim)
    ...
    return app
```

- [ ] **Step 4: Run to verify pass + suites**

Run: `cd engine && uv run pytest -q` and `cd studio && uv run pytest -q`.
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/src/engine/server/app.py studio/src/studio/ studio/tests/ engine/tests/test_server.py
git commit -m "feat(studio): mount the live sim under /sim with a Play flow; engine exposes its tick loop"
```

---

### Task 7: Remove the Textual TUI

**Files:** Delete `src/illuvutar/tui/`, `tests/test_tui.py`; Modify `src/illuvutar/cli.py`, `pyproject.toml`.

**Interfaces:** Produces: no TUI; `illuvutar` CLI no longer has `create_world` (world-building is the studio); `textual`/`httpx` TUI deps dropped where unused.

- [ ] **Step 1: Delete + retire.**

```bash
git rm -r src/illuvutar/tui tests/test_tui.py
```

`src/illuvutar/cli.py` — remove the `create_world` command and the now-unused imports (`WorldStateWriter`, `AgentTools`, `GodAgent`, `GodMemory`, `GodChatApp`, `index_palette`, `PaletteRAG`, `LLMClient`, `Path`). Leave the `main` click group; if it now has no subcommands, add a one-line `create_world` stub that errors with guidance:

```python
import click


@click.group()
def main():
    pass


@main.command()
def create_world():
    """Deprecated — build worlds in the studio: `studio --palette <dir> --world <dir>`."""
    raise SystemExit("world-building moved to the studio: `studio --palette <dir> --world <dir>`")
```

`pyproject.toml` — remove `"textual>=0.60"` from `dependencies` (the studio replaces the TUI). Keep `httpx` only if still imported elsewhere in `illuvutar` (grep; the TUI was its main user — if nothing else imports it, remove it too).

- [ ] **Step 2: Run + verify**

Run: `uv sync` then `uv run pytest -q` (root) — the TUI test is gone; nothing imports `illuvutar.tui`. `cd engine && uv run pytest -q` and `cd studio && uv run pytest -q` stay green.
Expected: PASS; `uv run python3 -c "import illuvutar.cli"` works; `grep -rn "illuvutar.tui\|textual\|GodChatApp" src tests` is empty.

- [ ] **Step 3: Commit**

```bash
git add -A src/illuvutar/cli.py pyproject.toml uv.lock tests
git commit -m "chore(illuvutar): remove Textual TUI; world-building lives in the studio"
```

---

### Task 8: End-to-end verification

**Files:** none (manual).

- [ ] **Step 1: Sync the studio project.** `cd studio && uv sync` (pulls illuvutar + engine as editable path deps).

- [ ] **Step 2: Launch + build a world.** With a capable endpoint (or local ollama):

```bash
cd studio && source ~/keys.sh
uv run studio --palette ../palettes/verdant --world /tmp/studioworld --port 8080 \
  --llm-endpoint <url-or-omit-for-ollama> --model <model>
```
Open http://127.0.0.1:8080 — chat "build a small world and populate it"; watch step lines stream (`▸ run_wfc…`, `▸ populate_world…`) and the status checklist fill (constitution ✓ … tilemap ✓ … agents ✓).

- [ ] **Step 3: Play.** Once `tilemap ✓`, the **▶ Play** button enables → click → lands on `/sim/` showing the live renderer; confirm entities render, thoughts stream, and clicking an NPC opens the profile panel (proves the base-path mount works).

- [ ] **Step 4: Clean up** — Ctrl-C; `rm -rf /tmp/studioworld`.

---

## Self-Review

**Spec coverage:** god streaming → Task 1; studio scaffold/shell/status → Task 2; Forge SSE turns → Task 3; Forge UI + `studio` command → Task 4; renderer base path → Task 5; World view + Play + tick-loop exposure → Task 6; TUI removal → Task 7; e2e → Task 8. ✓

**Placeholder scan:** CSS in Task 4 Step 1 is described rather than fully written (it's presentational, not logic) — acceptable; every logic/route/JS-behavior step has complete code.

**Type consistency:** `chat_stream -> Iterator[dict]` event shapes used identically in Task 1/3/4; `GodSession(god, writer)` + `.run_turn/.subscribe/.status`; `create_studio_app(session, world_dir=None, palette_dir=None, ai_model=...)` consistent across Tasks 2/4/6; `SimHolder(world_dir, ai_model).start()/.missing()/__call__`; `create_app(...).state.tick_loop`; `window.__BASE__` used in Tasks 5/6. Consistent.

**Note:** mounted sub-apps don't receive lifespan events, so the sim's tick loop is started manually via `app.state.tick_loop` (Task 6) — the one non-obvious integration point, called out in the plan and the spec.
