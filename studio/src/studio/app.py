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
