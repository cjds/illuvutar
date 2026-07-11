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
        if self._app is not None:
            return True   # already running for this world — idempotent, no leaked loop
        if self.missing():
            return False
        data = load_world(self.world_dir)
        app = create_app(
            store=data.store, passability=data.passability, palette=data.palette,
            tilemap_data=data.tilemap_data, world_id=data.world_id,
            width=data.width, height=data.height, sprite_dir=data.sprite_dir,
            ai_model=self.ai_model, world_dir=self.world_dir,
        )
        asyncio.get_running_loop().create_task(app.state.tick_loop.start())
        self._app = app
        return True

    async def __call__(self, scope, receive, send):
        if self._app is None:
            await PlainTextResponse("Build the world first, then Play.", status_code=503)(scope, receive, send)
            return
        await self._app(scope, receive, send)
