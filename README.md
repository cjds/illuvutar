# illuvutar

A living 2D world you generate with an LLM "god," then watch simulate itself. An
LLM **god agent** builds a world from a tile palette; a real-time **engine** runs
the simulation, where each entity thinks, speaks, and moves via its own LLM calls;
and a browser renderer streams the world and the entities' inner thoughts as it plays.

It all runs from **one command** — `studio` — a single web app where you build a
world by chatting with the god ("Forge"), then hit ▶ to play it. By default
everything runs locally against [Ollama](https://ollama.com/); an OpenAI-compatible
cloud endpoint can be used instead.

## Repository layout

One `uv` project, one package, three subpackages:

```
illuvutar/
├── pyproject.toml
├── src/illuvutar/
│   ├── god/         World generation: agents/, generation/, palette/, world_state/, llm/
│   ├── engine/      Simulation runtime — systems/, entities/, physics/, wrl/, server/
│   │   └── renderer/    Browser game HUD (canvas viewport + thought feed)
│   └── studio/      The web app: FastAPI "Forge" chat, mounts the engine sim at /sim
│       └── web/         Forge frontend (index.html, forge.js, studio.css)
├── palettes/        Tile palettes (e.g. verdant/) the god draws from
├── demo_world/      A generated world (constitution, regions, tilemap, sprites)
├── scripts/         Helpers (create_demo_world.py, generate_sprites.py)
├── tests/           god/, engine/, studio/ suites
└── docs/            Design specs and implementation plans
```

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for dependency management
- [Ollama](https://ollama.com/) running locally with a model pulled:
  ```sh
  ollama pull llama3.2
  ```
  (Or an OpenAI-compatible endpoint — see the flags below.)

## Quick start

Install dependencies:

```sh
uv sync
```

Launch the studio and open <http://127.0.0.1:8080>:

```sh
uv run studio --palette palettes/verdant --world demo_world --port 8080
```

1. **Forge** — chat with the god to build a world. It indexes the palette into a RAG
   index, then writes `constitution.yaml`, `regions.yaml`, a WFC-generated tilemap,
   and the populace into the `--world` directory. Sessions persist to
   `<world>/.god_memory.json`, so you can quit and resume.
2. **▶ Play this world** — once the world has a constitution, palette, and tilemap,
   the button starts the simulation and drops you into the renderer (served at `/sim`).
   Entities think on an interval; their inner monologue streams into the thought feed.
   Use the **◀ God** link to hop back to the Forge and keep editing; the world can be
   reloaded to pick up god edits without restarting.

### Options

| Flag | Default | Purpose |
|------|---------|---------|
| `--palette` | *(required)* | Directory of tile/sprite images the god draws from |
| `--world` | `world` | World directory to build into / play from |
| `--model` | `llama3.2` | Model the god agent uses to build the world |
| `--ai-model` | `llama3.2` | Model for in-sim entity thinking |
| `--llm-endpoint` | *(none)* | OpenAI-compatible base URL (instead of local Ollama) |
| `--llm-api-key` | *(none)* | API key for the endpoint above |
| `--port` | `8080` | Port to serve on |

## A note on performance

The god agent and every entity in the engine share **one** Ollama runner. If you
build and play on the same CPU-only machine, the god's responses slow down because
they queue behind the engine's entity-think flood. For a responsive god, use a GPU,
raise `OLLAMA_NUM_PARALLEL`, or finish building the world before you press Play.

## Testing

```sh
uv run pytest
```

Runs the god, engine, and studio suites together.

## Design docs

See `docs/superpowers/specs/` and `docs/superpowers/plans/`. Note that
`specs/2026-07-11-planes-timeline-power-design.md` is a forward-looking spec and is
not yet implemented.
