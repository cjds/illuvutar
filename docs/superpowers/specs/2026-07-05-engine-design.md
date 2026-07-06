# Engine Design: 2D World Simulation

**Date:** 2026-07-05
**Status:** Draft
**Scope:** Core engine architecture for a god-agent-driven 2D tile world with browser rendering

---

## 1. Overview and Design Philosophy

This engine powers a living 2D world generated and managed by a god agent (local ~8B LLM) and populated by AI agents running on embedded/laptop hardware. The core constraint shaping every decision: **the rendering pipeline must be LLM-readable and LLM-writable**.

That single constraint rules out binary formats, rules out tightly coupled renderer APIs, and rules out implicit state. Everything the simulation wants to express must be expressible as legible text that a language model can produce without hallucinating structure it cannot see.

A secondary constraint shapes the simulation side: **constrained, not continuous, physics**. Agents live on a discrete tile grid. The physics model describes what moves are legal, not how bodies interact under forces. This makes the engine tractable for small LLMs to reason about.

### Major subsystems

```
┌─────────────────────────────────────────────┐
│               God Agent / AI Agents          │
│          (generate world events, commands)   │
└──────────────────┬──────────────────────────┘
                   │  (simulation commands)
                   ▼
┌─────────────────────────────────────────────┐
│           Simulation Engine                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │  Entity   │  │  Tick    │  │ Physics   │  │
│  │  System   │  │  Loop    │  │ Resolver  │  │
│  └──────────┘  └──────────┘  └───────────┘  │
└──────────────────┬──────────────────────────┘
                   │  (World Render Language — WRL)
                   ▼
┌─────────────────────────────────────────────┐
│          Web Renderer                        │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │  Tile    │  │  Pixel/  │  │  UI       │  │
│  │  Layer   │  │  Effect  │  │  Overlay  │  │
│  └──────────┘  └──────────┘  └───────────┘  │
└─────────────────────────────────────────────┘
```

---

## 2. World Render Language (WRL)

### 2.1 Design rationale

The rendering language sits between the simulation and any display surface. It must satisfy three audiences simultaneously:

- **LLMs**: must be token-efficient, self-documenting, unambiguous. JSON arrays of magic integers fail here. Named keys win.
- **Renderers**: must be complete enough that a renderer can draw a frame without querying back into the simulation. Each frame is a self-contained snapshot.
- **Humans**: must be skimmable during debugging without tooling.

**Recommendation: Declarative per-tick snapshot, not a command stream.**

A command stream (draw-call sequence) requires the renderer to maintain state. Snapshots do not. The simulation owns all state; the renderer is stateless and can restart mid-session. This also means an LLM generating a partial snapshot does not need to track what it already "drew" — it describes what exists, not what to do.

The format is **TOML-like structured text** with a custom schema (not JSON, not YAML). Reasoning:
- TOML has no trailing-comma footguns, no indentation sensitivity, and is easy for LLMs to emit correctly.
- Each section header is a clear landmark token.
- Numbers stay readable without quotes.

### 2.2 Frame structure

A WRL frame represents one simulation tick. It is emitted once per tick by the engine and consumed by the renderer.

```toml
# WRL Frame — tick 1042

[frame]
tick = 1042
world_id = "illuvutar-prime"
timestamp_ms = 104200

[palette]
# Tile sprite mappings — index → sprite name
0 = "void"
1 = "grass_plain"
2 = "grass_long"
3 = "stone_path"
4 = "water_shallow"
5 = "water_deep"
6 = "tree_oak"
7 = "tree_pine"
8 = "wall_stone"
9 = "floor_wood"

[[layer.tiles]]
# Tile layer: run-length encoded rows, top to bottom
# Format: "col:tile_index" or "col-endcol:tile_index" for runs
width = 64
height = 64
rows = [
  "0-63:0",                          # row 0: all void
  "0-63:1",                          # row 1: all grass
  "0-5:1,6:6,7-20:1,21:6,22-63:1",  # row 2: grass with oak trees at col 6, 21
  "0-63:1",
]

[[layer.entities]]
# Entity layer: all visible entities this tick
[[layer.entities.entity]]
id = "agent-042"
kind = "humanoid"
x = 14
y = 8
sprite = "human_idle_south"
label = "Mira"
facing = "south"
state = "idle"
health = 0.85        # normalized 0.0–1.0
carrying = "none"

[[layer.entities.entity]]
id = "agent-007"
kind = "humanoid"
x = 22
y = 15
sprite = "human_walk_east"
label = "Tarven"
facing = "east"
state = "walking"
health = 1.0
carrying = "wood_log"

[[layer.entities.entity]]
id = "npc-deer-3"
kind = "animal"
x = 30
y = 12
sprite = "deer_idle"
label = ""
facing = "west"
state = "idle"

[[layer.effects]]
# Pixel/effect layer: layered on top of tiles and entities

[[layer.effects.light]]
kind = "ambient"
color = "#c8a87a"    # warm late-afternoon
intensity = 0.6

[[layer.effects.light]]
kind = "point"
x = 14
y = 8
radius_tiles = 3.5
color = "#ffdd99"
intensity = 0.9
source = "agent-042"

[[layer.effects.particle]]
kind = "weather_rain"
intensity = 0.3
direction_deg = 260
wind_px_per_tick = 2

[[layer.effects.overlay]]
kind = "vignette"
strength = 0.4

[[layer.ui]]
# UI overlays

[[layer.ui.tooltip]]
entity_id = "agent-042"
text = "Mira is gathering wood"
style = "speech_bubble"

[[layer.ui.hud]]
kind = "minimap"
visible = true

[[layer.ui.hud]]
kind = "clock"
time_of_day = "dusk"
display = "17:42"
```

### 2.3 Tile encoding

Tiles use run-length encoding per row because:
- A 64×64 grid is 4,096 cells. Listing each individually bloats the frame.
- RLE compresses uniform terrain (ocean, sky, plains) dramatically.
- The format stays text-based and LLM-writable: an LLM describing "a field of grass with a river through the middle" can emit RLE rows naturally.

The palette is declared in the frame header and referenced by integer index in tile rows. The palette is small (typically <64 entries). This keeps tile rows compact while keeping the renderer fully self-contained per frame.

### 2.4 Effect layer semantics

Effects are additive composites applied in declaration order. The renderer processes them bottom to top:

1. Render tile layer (opaque base)
2. Render entity layer (sprites at tile coordinates)
3. Apply each effect in `[[layer.effects]]` order:
   - Lights: composited as a light map (multiply blend)
   - Particles: drawn above entities
   - Overlays: full-screen post-processing (vignette, color grading)
4. Render UI layer (always on top, not affected by world lighting)

This ordering is fixed and deterministic, allowing renderers to be written in any target language without negotiating draw order.

### 2.5 Partial frames (delta frames)

For bandwidth efficiency on slow connections, the engine can emit delta frames after the first full frame:

```toml
[frame]
tick = 1043
kind = "delta"            # signals: only changed fields present
base_tick = 1042

[[layer.entities.entity]]
id = "agent-042"
x = 14
y = 9                     # moved one tile south
sprite = "human_walk_south"
state = "walking"
# all other fields omitted — renderer retains prior values

[[layer.effects.light]]
kind = "ambient"
intensity = 0.58          # slight darkening as dusk deepens
```

Delta frames always reference a `base_tick`. If the renderer dropped the base frame, it must request a full frame. Full frames are the default; delta frames are an optimization.

---

## 3. Entity and Component Model

### 3.1 Recommendation: flat component table, not deep inheritance

The entity system uses a **component table** approach. An entity is an ID. Components are named data bags attached to that ID. This is commonly called ECS (Entity Component System) but the implementation here is deliberately simple — no archetype chunking, no SIMD layout. The world is small (hundreds of entities, not millions).

```
Entity ID (string, stable across ticks)
└── ComponentStore
    ├── Position      { x, y, layer }
    ├── Sprite        { sprite_name, facing, animation_state, frame }
    ├── Health        { current, max }
    ├── Inventory     { slots: [ItemStack] }
    ├── AI            { agent_id, goal, memory_ref }
    ├── Physics       { blocking, passable_by: [EntityKind] }
    ├── Label         { name, visible }
    └── Tags          { ["npc", "animal", "hostile", ...] }
```

Components are plain data. Logic lives in **systems** (see Section 4). An entity without a given component simply does not have that capability — no null-checking, no default behavior.

### 3.2 Entity kinds

Rather than a deep type hierarchy, entities carry a `kind` tag and a set of components. The kind is a hint to renderers and AI agents, not a class:

| Kind | Typical components |
|------|-------------------|
| `humanoid` | Position, Sprite, Health, Inventory, AI, Label, Physics |
| `animal` | Position, Sprite, Health, AI, Physics |
| `object` | Position, Sprite, Physics (no AI, no health unless destructible) |
| `structure` | Position, Sprite, Physics (large, multi-tile) |
| `item_drop` | Position, Sprite (no physics blocking) |
| `effect_anchor` | Position (invisible, used to anchor particle effects) |

### 3.3 Multi-tile entities

Structures (buildings, large trees) occupy multiple tiles. The canonical representation is a single entity at an **anchor tile** (top-left corner), with a `footprint` field listing relative offsets:

```toml
[[layer.entities.entity]]
id = "building-inn-1"
kind = "structure"
x = 10          # anchor tile
y = 20
sprite = "inn_large"
footprint = [[0,0],[1,0],[2,0],[0,1],[1,1],[2,1]]   # 3×2 tiles
```

The physics resolver registers all footprint tiles as blocked. The renderer draws the sprite anchored at (x, y) spanning the footprint.

---

## 4. Simulation Engine

### 4.1 Tick model

**Recommendation: fixed-tick with event accumulation.**

A pure event-driven system (no regular tick) is difficult for small LLMs to reason about — they must model causality chains and timing simultaneously. A fixed tick rate gives the simulation a clear heartbeat that both the god agent and AI agents can plan against.

Tick rate: **10 ticks/second** (100ms per tick). This is fast enough for smooth-feeling world movement, slow enough for local LLMs to process a tick and respond within budget.

```
Tick N:
  1. Collect inputs (agent decisions, god agent commands, user interactions)
  2. Run physics resolver (validate moves, resolve conflicts)
  3. Run systems (AI, health regen, weather, day-night cycle)
  4. Emit WRL frame
  5. Advance tick counter
```

Events that occur between ticks (e.g., agent messages arriving mid-tick) are **buffered and applied at the start of the next tick**. This prevents race conditions without locks.

### 4.2 System execution order

Systems run in deterministic order each tick:

```
1. InputSystem          — apply buffered commands
2. AIDecisionSystem     — poll agent decisions, translate to intent
3. PhysicsSystem        — validate and apply movement, collision
4. InteractionSystem    — item pickup, NPC dialogue triggers, door use
5. EnvironmentSystem    — weather, day-night cycle, growth/decay
6. HealthSystem         — damage, regeneration, death
7. InventorySystem      — item transfers, crafting results
8. RenderOutputSystem   — emit WRL frame
```

This order is intentional: inputs and decisions are committed before physics resolves them. Physics resolves before interactions (you must be at the door to open it). Environment runs before health (weather can cause cold damage). Render output is always last.

### 4.3 Simulation command protocol

AI agents and the god agent communicate with the simulation via a **command protocol** — also text-based, also LLM-writable. Commands are queued and consumed by InputSystem on the next tick.

```toml
# Agent command — submitted by agent-042's local LLM

[command]
tick_submitted = 1041
agent_id = "agent-042"
action = "move"
direction = "south"

---

[command]
tick_submitted = 1041
agent_id = "agent-042"
action = "pick_up"
target_entity_id = "item-drop-woodlog-77"

---

[command]
tick_submitted = 1042
agent_id = "god"
action = "spawn_entity"
kind = "animal"
x = 45
y = 10
sprite = "deer_idle"
label = ""
components = { AI = { behavior = "wander_passive" }, Physics = { blocking = false } }

---

[command]
tick_submitted = 1042
agent_id = "god"
action = "modify_tile"
x = 20
y = 30
new_tile = 4    # water_shallow — river flood event
```

Valid top-level `action` values:
- `move` — move one tile in a cardinal direction (or diagonal if rules allow)
- `interact` — interact with adjacent entity or structure
- `pick_up` — pick up item at current position
- `drop` — drop item from inventory to current position
- `speak` — emit dialogue (captured by InteractionSystem, rendered as UI tooltip)
- `spawn_entity` — god only
- `despawn_entity` — god only
- `modify_tile` — god only
- `set_weather` — god only
- `set_time` — god only

The `god` agent identifier is privileged. The physics resolver bypasses movement validation for god commands (gods can teleport entities, place entities on blocked tiles, etc).

---

## 5. Physics Model

### 5.1 Constrained tile physics (not rigid-body)

Physics in a tile world is a rulebook, not a solver. The question is never "what force acts on this body" but "is this move legal, and what happens if two entities want the same tile?"

The physics resolver answers three questions each tick:

1. **Blocking**: can entity E enter tile (x, y)?
2. **Conflict**: what happens when two entities move to the same destination?
3. **Interaction zone**: which entities are adjacent to each other?

### 5.2 Tile passability

Each tile has a passability class determined by its palette index:

| Passability class | Examples | Effect |
|------------------|----------|--------|
| `open` | grass, floor, path | Any entity may enter |
| `blocked` | wall, deep tree, water_deep | No entity may enter |
| `slow` | water_shallow, mud | Entity may enter, costs 2 ticks of movement budget |
| `conditional` | door | Passable only to entities with `can_open_doors` tag |

Tile passability is a static lookup table set at world generation. The god agent can modify tile types (triggering passability recalculation), but individual tiles do not have dynamic passability otherwise.

### 5.3 Entity collision

Entity-entity collision is handled by a **priority queue** per destination tile:

1. Collect all move intents for this tick.
2. For each destination tile, gather all entities intending to enter it.
3. If only one entity intends to enter, the move succeeds (subject to tile passability).
4. If multiple entities intend to enter the same tile:
   - Check tags: entities with `can_share_tile` (items, effects) always succeed.
   - For blocking entities: the entity with the highest `collision_priority` wins. Others are rejected (their move fails; they stay in place).
   - Collision priority order: player-controlled > humanoid AI > animal > object.
   - Ties in priority broken by entity ID string sort (deterministic, arbitrary).

Rejected moves are not retried within the same tick. The AI agent for that entity receives a `move_blocked` event in the next tick's event feed and can replan.

### 5.4 Movement budget

Each entity has a movement budget of 1 tile per tick by default. Components can modify this:

- `slow` terrain costs 2 ticks per move (entity waits one extra tick, consuming no budget action)
- Carrying heavy items may reduce budget (optional, configurable per world)
- AI agents cannot queue more than 1 move command per tick

This keeps movement predictable for small LLMs: one intent, one outcome, one tick.

### 5.5 Adjacency and interaction zones

Interactions (picking up items, talking to NPCs, opening doors) require the acting entity to be in an **interaction zone**:

- Default interaction zone: the 8 tiles surrounding the entity (Moore neighborhood, radius 1)
- Extended zone: radius 2 for ranged abilities (bow attack, throwing)
- Zone checks run in InteractionSystem after physics resolves movement

```
Interaction zone for entity at (10, 10):
  [ ][ ][ ][ ][ ]
  [ ][X][X][X][ ]
  [ ][X][E][X][ ]   E = entity, X = interaction zone
  [ ][X][X][X][ ]
  [ ][ ][ ][ ][ ]
```

---

## 6. Web Renderer

### 6.1 Architecture

The web renderer is a **stateless WRL consumer**. It holds no simulation state. Each received WRL frame completely describes what to draw. If a frame is dropped, the renderer waits for the next one — no interpolation, no state repair.

The renderer is a single-page browser application with no build step required (plain ES modules, no bundler). This keeps it deployable anywhere and inspectable by developers without tooling.

```
WebSocket (or SSE)
    │
    ▼
WRL Parser
    │
    ▼
Frame Dispatcher
    ├──► TileLayerRenderer    (Canvas 2D — bottom layer)
    ├──► EntityLayerRenderer  (Canvas 2D — entity sprites)
    ├──► EffectLayerRenderer  (WebGL shader pass — lighting, weather)
    └──► UILayerRenderer      (DOM — tooltips, HUD, overlays)
```

### 6.2 Rendering layers

**Two Canvas elements, one DOM layer:**

```html
<div id="world-viewport">
  <canvas id="world-canvas" />   <!-- tile + entity layers (Canvas 2D) -->
  <canvas id="effect-canvas" />  <!-- lighting + weather (WebGL) -->
  <div id="ui-layer" />          <!-- DOM UI overlays -->
</div>
```

The Canvas 2D context handles tile and entity rendering because it is fast, predictable, and does not require shader knowledge to modify. The WebGL canvas sits on top with `pointer-events: none` and handles effects that benefit from GPU acceleration (light maps, weather particle shaders). The DOM UI layer sits topmost and renders tooltips and HUD elements as styled HTML.

This separation means:
- The effect layer can be disabled entirely (for low-end devices) without touching the rest of the renderer.
- A future renderer in another language (SDL, Pygame, terminal) can implement only the tile and entity layers and still produce a valid world view.

### 6.3 Tile rendering

Tiles are drawn as a grid of `TILE_SIZE × TILE_SIZE` pixel squares (default 32px). The renderer:

1. Parses the palette from the WRL frame header. Maps sprite names to loaded `<img>` elements.
2. Decodes RLE tile rows into a flat array of tile indices.
3. Iterates the visible viewport region (not the full world — camera culling).
4. Draws each tile as `ctx.drawImage(sprite, x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)`.

The renderer maintains a sprite atlas loaded at startup. Sprite names from the WRL palette must match atlas keys. Unknown sprite names fall back to a checkerboard "missing" tile so errors are visible without crashing.

### 6.4 Entity rendering

Entities are drawn after tiles. Each entity in `[[layer.entities.entity]]` is:

1. Located by `(x, y)` tile coordinates, converted to pixel coordinates.
2. The `sprite` field selects the sprite. Sprites are directional (`human_walk_south`, `human_walk_east`) — the renderer looks up the exact name, no implicit direction logic.
3. Drawn centered on the tile's pixel center.
4. Labels (if `label` is non-empty) drawn as small text above the sprite.
5. Health bars drawn below the sprite if `health < 1.0`.

Entity draw order: sorted by `y` coordinate (painter's algorithm — entities lower on screen appear in front). Ties broken by entity ID for determinism.

### 6.5 Effect rendering (WebGL)

The effect canvas uses a simple WebGL pipeline:

**Lighting**: A 2D light map texture is built from `[[layer.effects.light]]` entries. Ambient light sets the base. Point lights are additive Gaussian blobs at tile positions. The light map is then composited over the world-canvas as a multiply blend (WebGL framebuffer operation).

**Weather particles**: Rain, snow, and other particle effects are implemented as WebGL point sprites. The WRL `intensity` and `direction_deg` fields drive particle velocity and density. Particles are not tracked across frames — they are regenerated each frame from the WRL parameters, using the tick number as a deterministic seed so the renderer stays stateless.

**Overlays**: Full-screen effects (vignette, color grading) are implemented as screen-space fragment shaders applied to the composited frame buffer.

### 6.6 WRL delivery mechanism

**Recommendation: Server-Sent Events (SSE), not WebSockets.**

SSE is unidirectional (server → client). The renderer only needs to receive frames — it never sends simulation commands back. SSE:
- Requires no handshake beyond HTTP
- Is natively reconnect-aware (browser auto-reconnects on disconnect)
- Works through HTTP/1.1 proxies and CDNs without special configuration
- Is simpler to implement server-side than WebSocket

Simulation commands (player input) travel via a separate `POST /command` endpoint. This clean separation means the frame feed and the command channel can be scaled independently.

Full frames are sent at tick intervals. Delta frames can be requested by the client by appending `?delta=1` to the SSE endpoint URL — the server then sends delta frames after the first full frame.

### 6.7 Camera and viewport

The renderer maintains a camera position (tile coordinates, float). The visible viewport is `(CANVAS_WIDTH / TILE_SIZE) × (CANVAS_HEIGHT / TILE_SIZE)` tiles. The camera follows the player entity by default, with a configurable deadzone (player can move N tiles from center before camera pans).

Camera pan is smooth (lerp toward target position). This is entirely client-side — the WRL frame is always in world coordinates, never camera-relative.

---

## 7. Integration Flow: End to End

```
1. God agent generates world tiles → emits spawn/modify_tile commands
2. Simulation ingests commands, populates entity store and tile map
3. Each 100ms tick:
   a. AI agents (local LLMs) submit move/interact commands via POST /command
   b. InputSystem buffers commands
   c. Systems run in order (physics, AI, environment, health, …)
   d. RenderOutputSystem serializes current world state as WRL frame
   e. Frame emitted via SSE to all connected renderers
4. Web renderer receives WRL frame, parses, draws tile+entity+effect+UI layers
5. Player input (keyboard) captured by renderer → POST /command → queued for next tick
```

### 7.1 AI agent perception

AI agents receive the WRL frame as their perception input (or a filtered subset — the engine can emit an agent-local frame showing only what is within the agent's line-of-sight radius). The agent LLM reads the WRL, reasons about it, and emits a command. The WRL is intentionally LLM-readable because this is the primary read path for AI agents.

A minimal perception frame for an agent's turn:

```toml
[frame]
tick = 1042
for_agent = "agent-042"
visibility_radius = 8

[self]
x = 14
y = 8
health = 0.85
carrying = "none"
facing = "south"

# Only tiles within visibility_radius are included
[[layer.tiles]]
# ... (clipped to 8-tile radius around agent)

[[layer.entities.entity]]
# ... (only visible entities)

[[layer.events]]
# Events since last tick relevant to this agent
[[layer.events.event]]
kind = "move_succeeded"
direction = "south"

[[layer.events.event]]
kind = "entity_nearby"
entity_id = "npc-deer-3"
distance_tiles = 3
```

---

## 8. Key Design Decisions Summary

| Decision | Choice | Reasoning |
|----------|--------|-----------|
| Rendering language format | Declarative TOML-like snapshot | LLM-writable, stateless renderer, debuggable |
| Frame delivery | SSE (full frame default, delta optional) | Unidirectional, auto-reconnect, proxy-friendly |
| Tick model | Fixed 10 ticks/sec with event buffering | Predictable for LLMs, avoids race conditions |
| Physics model | Tile passability + priority-queue collision | Tractable for small LLMs, deterministic |
| Entity model | Component table (ECS-lite) | Flexible, no deep inheritance, easy to serialize |
| Effect rendering | WebGL over Canvas 2D base | GPU for lighting/particles, CPU for simple tiles |
| Multi-tile entities | Anchor tile + footprint offset list | Simple, fully expressible in WRL |
| Tile encoding | RLE per row | Compact text encoding, LLM-writable |
| UI layer | DOM (not canvas) | Accessible, easy to style, no pixel math |
| Command protocol | TOML text over POST | Same LLM-readable format as WRL |

---

## 9. What is Explicitly Out of Scope

- **Rigid-body physics**: no torque, no velocity vectors, no continuous collision detection. Entities move one tile per tick.
- **Multiplayer synchronization**: the tick loop is authoritative. Multiple clients can observe the same world via SSE but there is one simulation instance.
- **Procedural animation**: sprites are pre-made and named. The engine selects by name; it does not interpolate between poses.
- **3D or isometric projection**: this is a flat top-down 2D tile world. Isometric is a renderer concern and could be layered on top of the WRL without changing the simulation.
- **Pathfinding**: AI agents do their own pathfinding using the tile layer from their perception frame. The engine provides adjacency data, not A*.
- **Persistence**: world state serialization (save/load) is a storage concern outside the engine's runtime scope.
