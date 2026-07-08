"""WRL serializer: converts a WRLFrame to TOML-format WRL text."""
import json
from engine.wrl.schema import WRLFrame


def serialize(frame: WRLFrame) -> str:
    lines = [f"# WRL Frame — tick {frame.tick}", ""]
    lines += ["[frame]", f"tick = {frame.tick}", f'world_id = "{frame.world_id}"',
              f"timestamp_ms = {frame.timestamp_ms}", f'kind = "{frame.kind}"']
    if frame.kind == "delta" and frame.base_tick is not None:
        lines.append(f"base_tick = {frame.base_tick}")
    if frame.for_agent:
        lines += [f'for_agent = "{frame.for_agent}"', f"visibility_radius = {frame.visibility_radius}"]
    lines.append("")

    if frame.palette:
        lines.append("[palette]")
        for idx, name in sorted(frame.palette.items()):
            lines.append(f'{idx} = "{name}"')
        lines.append("")

    if frame.tiles:
        lines += ["[[layer.tiles]]", f"width = {frame.tiles.width}", f"height = {frame.tiles.height}", "rows = ["]
        for row in frame.tiles.rows:
            lines.append(f'  "{row}",')
        lines += ["]", ""]

    for entity in frame.entities:
        lines += ["[[layer.entities.entity]]",
                  f'id = "{entity.id}"', f'kind = "{entity.kind}"',
                  f"x = {entity.x}", f"y = {entity.y}",
                  f'sprite = "{entity.sprite}"', f'label = "{entity.label}"',
                  f'facing = "{entity.facing}"', f'state = "{entity.state}"',
                  f"health = {entity.health}", f'carrying = "{entity.carrying}"']
        if entity.footprint:
            footprint_str = str(entity.footprint)
            lines.append(f"footprint = {footprint_str}")
        lines.append("")

    for light in frame.effects.lights:
        lines += ["[[layer.effects.light]]", f'kind = "{light.kind}"',
                  f'color = "{light.color}"', f"intensity = {light.intensity}"]
        if light.kind == "point":
            lines += [f"x = {light.x}", f"y = {light.y}", f"radius_tiles = {light.radius_tiles}"]
            if light.source:
                lines.append(f'source = "{light.source}"')
        lines.append("")

    for particle in frame.effects.particles:
        lines += ["[[layer.effects.particle]]", f'kind = "{particle.kind}"',
                  f"intensity = {particle.intensity}", f"direction_deg = {particle.direction_deg}",
                  f"wind_px_per_tick = {particle.wind_px_per_tick}", ""]

    for overlay in frame.effects.overlays:
        lines += ["[[layer.effects.overlay]]", f'kind = "{overlay.kind}"',
                  f"strength = {overlay.strength}", ""]

    for tooltip in frame.ui.tooltips:
        lines += ["[[layer.ui.tooltip]]", f'entity_id = "{tooltip.entity_id}"',
                  f'text = "{tooltip.text}"', f'style = "{tooltip.style}"', ""]

    for hud in frame.ui.huds:
        lines += ["[[layer.ui.hud]]", f'kind = "{hud.kind}"',
                  f"visible = {str(hud.visible).lower()}", ""]

    for thought in frame.thoughts:
        lines += [
            "[[layer.thoughts.thought]]",
            f'entity_id = "{thought.entity_id}"',
            f"tick = {thought.tick}",
            f'text = "{json.dumps(thought.text)[1:-1]}"',
            "",
        ]

    return "\n".join(lines)
