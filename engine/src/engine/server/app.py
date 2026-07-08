import asyncio
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from engine.entities.store import EntityStore
from engine.physics.passability import PassabilityMap
from engine.server.sse import SSEBroadcaster
from engine.server.command import parse_command
from engine.tick import TickLoop
from engine.systems.input import Command
from engine.wrl.serializer import serialize

RENDERER_DIR = Path(__file__).parent.parent.parent.parent / "renderer"


def create_app(
    store: EntityStore,
    passability: PassabilityMap,
    palette: dict[int, str],
    tilemap_data: list[dict],
    world_id: str,
    width: int,
    height: int,
    max_frames: int | None = None,
    sprite_dir: Path | None = None,
    ai_model: str = "llama3.2",
) -> FastAPI:
    app = FastAPI()
    broadcaster = SSEBroadcaster()

    async def on_frame(frame):
        await broadcaster.broadcast(serialize(frame))

    tick_loop = TickLoop(
        store=store, passability=passability, palette=palette,
        tilemap_data=tilemap_data, world_id=world_id,
        width=width, height=height, frame_callback=on_frame,
        ai_model=ai_model,
    )

    @app.on_event("startup")
    async def startup():
        asyncio.create_task(tick_loop.start())

    @app.on_event("shutdown")
    async def shutdown():
        tick_loop.stop()

    @app.get("/", response_class=HTMLResponse)
    async def root():
        html_path = RENDERER_DIR / "index.html"
        if html_path.exists():
            return html_path.read_text()
        return "<html><body><h1>Renderer not found</h1></body></html>"

    js_dir = RENDERER_DIR / "js"
    if js_dir.is_dir():
        app.mount("/js", StaticFiles(directory=js_dir), name="js")

    sprites_dir = RENDERER_DIR / "sprites"
    if sprites_dir.is_dir():
        app.mount("/sprites", StaticFiles(directory=sprites_dir), name="sprites")
    elif sprite_dir and sprite_dir.is_dir():
        app.mount("/sprites", StaticFiles(directory=str(sprite_dir)), name="sprites")

    @app.get("/frames")
    async def frames():
        async def event_stream():
            q = broadcaster.subscribe()
            sent = 0
            try:
                while max_frames is None or sent < max_frames:
                    try:
                        frame_toml = await asyncio.wait_for(q.get(), timeout=1.0)
                        sse_lines = "\n".join(f"data: {line}" for line in frame_toml.splitlines())
                        yield f"{sse_lines}\n\n"
                        sent += 1
                    except asyncio.TimeoutError:
                        yield "data: ping\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                broadcaster.unsubscribe(q)

        return StreamingResponse(event_stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/command")
    async def command(request: Request):
        body = await request.body()
        raw = parse_command(body.decode())
        if raw is None:
            return Response(content="Invalid command", status_code=400)
        tick_loop.enqueue_command(Command(entity_id=raw.agent_id, action=raw.action, params=raw.params))
        return {"ok": True}

    @app.post("/entity/{entity_id}/say")
    async def entity_say(entity_id: str, request: Request):
        body = await request.json()
        text = body.get("text", "")
        if not text:
            return Response(content="Missing text", status_code=400)
        tick_loop.inject_whisper(entity_id, text)
        return {"ok": True, "entity_id": entity_id}

    @app.get("/thoughts")
    async def get_thoughts():
        return tick_loop.recent_thoughts()

    return app
