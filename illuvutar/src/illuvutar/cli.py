"""CLI entry point for illuvutar world generation."""
import click
from pathlib import Path
from illuvutar.palette.indexer import index_palette
from illuvutar.palette.rag import PaletteRAG
from illuvutar.world_state.writer import WorldStateWriter
from illuvutar.agents.tools import AgentTools
from illuvutar.agents.god import GodAgent
from illuvutar.agents.memory import GodMemory
from illuvutar.tui.app import GodChatApp


@click.group()
def main():
    pass


@main.command()
@click.option("--palette", required=True, type=click.Path(exists=True), help="Path to palette directory")
@click.option("--world", default="world", help="Output world directory")
@click.option("--model", default="llama3.2", help="Ollama model name")
def create_world(palette, world, model):
    """Start the god agent to generate a new world."""
    palette_dir = Path(palette)
    world_dir = Path(world)

    click.echo(f"Indexing palette from {palette_dir}...")
    tiles = index_palette(palette_dir)
    click.echo(f"Found {len(tiles)} tiles. Building RAG index...")

    rag_dir = world_dir / ".rag"
    rag = PaletteRAG.build(tiles, persist_dir=str(rag_dir))

    writer = WorldStateWriter(world_dir)
    tools = AgentTools(writer=writer, rag=rag, tiles=tiles, palette_dir=palette_dir)

    # God memory persists at world_dir/.god_memory.json
    memory = GodMemory(world_dir / ".god_memory.json")
    god = GodAgent(model=model, tools=tools, memory=memory)

    if memory.load():
        click.echo("Resuming previous god session from memory.")

    app = GodChatApp(god_agent=god, writer=writer)
    app.run()
