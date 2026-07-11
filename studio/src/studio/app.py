import asyncio
import json
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from studio.sim import SimHolder

WEB_DIR = Path(__file__).parent.parent.parent / "web"


def create_studio_app(session, world_dir=None, palette_dir=None, ai_model="llama3.2") -> FastAPI:
    app = FastAPI()
    sim = SimHolder(world_dir, ai_model) if world_dir else None

    @app.get("/", response_class=HTMLResponse)
    async def shell():
        html = WEB_DIR / "index.html"
        return html.read_text() if html.exists() else "<h1>Forge</h1>"

    @app.get("/forge/status")
    async def forge_status():
        return session.status()

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

    @app.post("/sim/start")
    async def sim_start():
        if sim is None:
            return {"ready": False, "missing": ["world"]}
        missing = sim.missing()
        if missing:
            return {"ready": False, "missing": missing}
        sim.start()
        return {"ready": True, "missing": []}

    if WEB_DIR.is_dir():
        app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")

    if sim is not None:
        app.mount("/sim", sim)

    return app
