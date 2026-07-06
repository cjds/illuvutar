# World Generation Subsystem Design

**Date:** 2026-07-05
**Status:** Draft

---

## Overview

The World Generation subsystem takes a human-provided palette (tileset files) and a
conversation with the god agent, and produces a complete 2D world-state — a structured
set of files that fully describes a world ready for simulation and rendering.

### Core Principles

- The **world-state directory** is the single source of truth. Every agent reads from it,
  writes to it, and it can stand alone without any agent running.
- The **god agent is autonomous** — it decides whether to spawn specialists, what to ask
  the human, and when the world is "done."
- **New concepts are introduced slowly** — the palette constrains what exists. The god
  cannot invent tiles that are not in the palette.
- **Designed as a standalone product** — a human provides a palette directory and starts
  the god agent. That is the entire entry point.

### Success Criteria

1. A valid world-state is produced that a renderer can display as a 2D tile map.
2. The world is coherent — tiles respect palette adjacency rules (via WFC), regions make
   geographic sense.
3. The god's decisions are traceable — the world-state records why regions exist, not
   just what they are.
4. A human with no knowledge of the internals can start the god, have a conversation,
   and get a world.

---

## World-State Format

The world-state is a directory of files. Each file represents one layer of reality so
agents can work on slices without loading everything.

```
world/
  constitution.yaml     # World name, palette used, core rules, tone — written first
  regions.yaml          # Named regions with boundaries, biome type, atmosphere notes
  tilemap.json          # The 2D grid: [{x, y, layer, tile_id, region}]
  factions.yaml         # Groups, territories, relationships (specialist output)
  history.yaml          # Seed events that happened before simulation starts
  palette.yaml          # Index of available tiles with adjacency rules (from palette dir)
  agents.yaml           # Initial agent roster — who exists at world start
  meta.yaml             # Generation log: which agents ran, decisions made, timestamps
```

### Key Rules

- `constitution.yaml` is written first by the god before any specialist runs. It is the
  constraint document — specialists cannot contradict it.
- `tilemap.json` is the terminal artifact. It is produced last, after regions and rules
  are settled, using WFC constrained by `palette.yaml` adjacency rules.
- `meta.yaml` makes the world traceable — a human or future agent can read why each
  decision was made.
- All files are human-readable text. The world-state is inspectable without running code.

---

## Agent Architecture

### The God Agent

The god is a persistent LLM session (local, ~8B params) that runs until world generation
is complete. It operates in three phases:

**Phase 1 — Discovery**
Converses with the human. Reads palette files via tool calls. Builds its understanding
of what tiles, biomes, and concepts are available. Asks clarifying questions about tone,
scale, and intent.

**Phase 2 — Planning**
Writes `constitution.yaml` and `regions.yaml`. Decides whether specialists are needed
and writes mandates for each. The god may handle a small world entirely itself; for
large or complex worlds it delegates.

**Phase 3 — Assembly**
Reviews specialist outputs, resolves conflicts with the constitution, finalizes
`tilemap.json` via the WFC pipeline, and writes `meta.yaml`.

**God agent tools:**
- `read_file(path)` — read any palette or world-state file
- `write_world_state(file, content)` — write to the world-state directory
- `spawn_specialist(mandate)` — launch a specialist agent with a mandate file
- `query_palette(description)` — RAG query against the palette index
- `run_wfc(regions)` — trigger the WFC tile placement pipeline

### Specialist Agents

Specialists are short-lived LLM sessions. The god writes a mandate file for each:

```
specialists/
  biome-agent-mandate.yaml
  faction-agent-mandate.yaml
  history-agent-mandate.yaml
```

Each mandate contains: which world-state files to read, what to produce, constraints
from the constitution, and the output file to write. Specialists never communicate with
each other — only with the world-state and their mandate. The god reviews all specialist
output before proceeding.

### RAG / Palette System

The palette directory is indexed at startup into a local vector store (ChromaDB or
equivalent embedding index). The god and specialists query it in natural language:

> "What tiles represent shallow water edges?"
> → returns tile IDs, adjacency rules, layer assignments

This keeps agent context windows clean — agents load only the tiles relevant to their
current task, not the full palette.

**Palette file format:**

```yaml
# palette.yaml (auto-generated from palette directory at startup)
tiles:
  - id: grass_plain
    sprite: tiles/nature/grass_plain.png
    layer: ground
    tags: [grass, open, walkable]
    adjacent: [grass_plain, grass_flowers, dirt_path, water_edge_n]
  - id: water_deep
    sprite: tiles/nature/water_deep.png
    layer: ground
    tags: [water, impassable]
    adjacent: [water_deep, water_shallow, water_edge_n, water_edge_s]
```

---

## Generation Pipeline

World generation follows a strict order to ensure coherence:

```
1. Palette indexing      → palette.yaml built from palette directory
2. God discovery         → conversation with human, RAG queries
3. Constitution          → constitution.yaml written by god
4. Region planning       → regions.yaml written by god (or biome specialist)
5. Specialist runs       → factions, history, agents written in parallel
6. Voronoi layout        → region boundaries rendered to a spatial grid
7. WFC tile placement    → tilemap.json filled using adjacency rules per region
8. God review            → god reads full world-state, writes meta.yaml
```

**Voronoi layout:** Region boundaries are computed using a Voronoi diagram seeded from
region centroids defined in `regions.yaml`. This produces organic, non-rectangular
region shapes suitable for a living world.

**WFC tile placement:** Within each region, Wave Function Collapse fills the tile grid
using the adjacency rules from `palette.yaml`. The biome tag on each region constrains
which tile IDs are eligible, so a forest region only considers forest-tagged tiles.

---

## Human-God Chat Interface

The god agent is accessed via a rich terminal UI (TUI). The interface has two panels:

```
┌─────────────────────────────┬─────────────────────────────┐
│  GOD CONVERSATION           │  WORLD STATE                │
│                             │                             │
│  > What palette have you    │  constitution: pending      │
│    prepared for me?         │  regions:      pending      │
│                             │  tilemap:      pending      │
│  Human: I have a forest     │  factions:     pending      │
│  pack and a ruins pack.     │  agents:       pending      │
│                             │                             │
│  God: I see 47 forest tiles │  Active agents:             │
│  and 23 ruin tiles. I will  │  ● God                      │
│  build a world of ancient   │                             │
│  woodland civilization...   │                             │
│                             │                             │
│  [input]                    │                             │
└─────────────────────────────┴─────────────────────────────┘
```

The right panel shows world-state file completion status and active specialist agents
in real time. The god's messages stream in as they are generated.

---

## Standalone Product Entry Point

```bash
illuvutar create-world --palette ./my-palette-dir
```

This command:
1. Indexes the palette directory into a local vector store
2. Starts the god agent session
3. Opens the TUI
4. The human converses with the god until world generation completes
5. Outputs `./world/` directory ready for simulation

No other configuration required.

---

## Open Questions (deferred to engine design)

- The exact format of the rendering language the world-state feeds into
- How `tilemap.json` maps to engine layers
- Physics constraints for entities placed via `agents.yaml`
- Tick model for the simulation that consumes this world

These are addressed in the Engine Design document.
