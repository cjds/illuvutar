# illuvutar

A living 2D world you generate with an LLM "god," then watch simulate itself. An
LLM **god agent** builds a world from a tile palette; a real-time **engine** runs
the simulation, where each entity thinks, speaks, and moves via its own LLM calls;
and a browser renderer streams the world and the entities' inner thoughts as it plays.

Everything runs locally against [Ollama](https://ollama.com/) — no cloud API required.

## Repository layout

This is a monorepo with two independent Python projects plus shared assets:

```
illuvutar/            ← repo root (this folder)
├── illuvutar/        World generation: the god agent + TUI (project "illuvutar")
│   └── src/illuvutar/    agents/, tui/, palette/, world_state/, generation/
├── engine/           Simulation runtime: ECS tick loop, entity AI, web server + renderer
│   └── src/engine/       systems/, entities/, physics/, server/, renderer/
├── palettes/         Tile palettes (e.g. verdant/) the god draws from
├── demo_world/       A generated world (constitution, regions, tilemap, sprites)
├── scripts/          Helpers (create_demo_world.py, generate_sprites.py)
└── docs/             Design specs and implementation plans
```

> **Why the nested `illuvutar/illuvutar/src/illuvutar/`?** The outer folder is the
> repo, the middle is the *sub-project*, and the inner is the importable *package*
> (standard `src/` layout). All three share the project name; none is redundant.

Each sub-project (`illuvutar/` and `engine/`) is a self-contained
[uv](https://docs.astral.sh/uv/) project with its own `pyproject.toml`, `.venv`, and
tests.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for dependency management
- [Ollama](https://ollama.com/) running locally with a model pulled:
  ```sh
  ollama pull llama3.2
  ```

## Quick start

### 1. Generate a world (god agent)

```sh
cd illuvutar
uv run illuvutar create-world \
    --palette ../palettes/verdant \
    --world ../demo_world \
    --model llama3.2
```

This opens a TUI where you converse with the god. It indexes the palette into a RAG
index, then writes `constitution.yaml`, `regions.yaml`, and a WFC-generated tilemap
into the world directory. Sessions persist to `<world>/.god_memory.json`, so you can
quit and resume.

### 2. Run the simulation (engine)

```sh
cd engine
uv run python3 -m engine ../demo_world --port 8080 --ai-model llama3.2
# (equivalently: uv run illuvutar-engine ../demo_world --port 8080)
```

Then open <http://localhost:8080> to watch the world tick. Entities think on an
interval; their inner monologue streams into the thought feed.

### 3. Talk to the world (optional)

While the engine is running, start the god TUI with `--engine-url` to whisper to
entities and read their thoughts:

```sh
cd illuvutar
uv run illuvutar create-world --palette ../palettes/verdant --world ../demo_world \
    --engine-url http://localhost:8080
```

- `/whisper <entity_id> <message>` — plant a message an entity hears on its next think
- `/thoughts` — pull the most recent entity thoughts from the engine

## A note on performance

The god agent and every entity in the engine share **one** Ollama runner. If you run
both at once on a CPU-only machine, the god's responses will be slow because they
queue behind the engine's entity-think flood. For a responsive god, use a GPU, raise
`OLLAMA_NUM_PARALLEL`, or generate the world *before* starting the engine.

## Testing

Each project is tested independently:

```sh
cd illuvutar && uv run pytest      # world generation + TUI
cd engine    && uv run pytest      # engine, physics, server
```

## Design docs

See `docs/superpowers/specs/` and `docs/superpowers/plans/` for the world-generation
and engine designs.
