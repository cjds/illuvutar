"""`studio` CLI: build god deps for a world and serve the studio web app."""
import click
import uvicorn
from pathlib import Path
from illuvutar.god.palette.indexer import index_palette
from illuvutar.god.palette.rag import PaletteRAG
from illuvutar.god.world_state.writer import WorldStateWriter
from illuvutar.god.agents.tools import AgentTools
from illuvutar.god.agents.god import GodAgent
from illuvutar.god.agents.memory import GodMemory
from illuvutar.god.llm.client import LLMClient
from illuvutar.studio.god_session import GodSession
from illuvutar.studio.app import create_studio_app


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


if __name__ == "__main__":
    main()
