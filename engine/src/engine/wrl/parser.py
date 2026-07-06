"""WRL parser: converts TOML-format WRL text to a WRLFrame."""
import tomlkit
from engine.wrl.schema import (
    WRLFrame, WRLTileLayer, WRLEntity, WRLEffectLayer,
    WRLLight, WRLParticle, WRLOverlay, WRLUILayer, WRLTooltip, WRLHud,
)


def parse(toml_str: str) -> WRLFrame:
    doc = tomlkit.loads(toml_str)
    f = doc.get("frame", {})
    frame = WRLFrame(
        tick=int(f["tick"]),
        world_id=str(f["world_id"]),
        timestamp_ms=int(f["timestamp_ms"]),
        kind=str(f.get("kind", "full")),
        base_tick=f.get("base_tick"),
        for_agent=f.get("for_agent"),
        visibility_radius=f.get("visibility_radius"),
    )

    if "palette" in doc:
        frame.palette = {int(k): str(v) for k, v in doc["palette"].items()}

    layer = doc.get("layer", {})

    if "tiles" in layer:
        t = layer["tiles"]
        if isinstance(t, list):
            t = t[0]
        frame.tiles = WRLTileLayer(
            width=int(t["width"]),
            height=int(t["height"]),
            rows=list(t.get("rows", [])),
        )

    for e in layer.get("entities", {}).get("entity", []):
        frame.entities.append(WRLEntity(
            id=str(e["id"]), kind=str(e["kind"]),
            x=int(e["x"]), y=int(e["y"]),
            sprite=str(e["sprite"]),
            health=float(e.get("health", 1.0)),
            label=str(e.get("label", "")),
            facing=str(e.get("facing", "south")),
            state=str(e.get("state", "idle")),
            carrying=str(e.get("carrying", "none")),
            footprint=e.get("footprint"),
        ))

    effects = WRLEffectLayer()
    for light in layer.get("effects", {}).get("light", []):
        effects.lights.append(WRLLight(
            kind=str(light["kind"]), color=str(light["color"]),
            intensity=float(light["intensity"]),
            x=float(light.get("x", 0)), y=float(light.get("y", 0)),
            radius_tiles=float(light.get("radius_tiles", 0)),
            source=str(light.get("source", "")),
        ))
    for particle in layer.get("effects", {}).get("particle", []):
        effects.particles.append(WRLParticle(
            kind=str(particle["kind"]), intensity=float(particle["intensity"]),
            direction_deg=float(particle.get("direction_deg", 270)),
            wind_px_per_tick=float(particle.get("wind_px_per_tick", 0)),
        ))
    for overlay in layer.get("effects", {}).get("overlay", []):
        effects.overlays.append(WRLOverlay(kind=str(overlay["kind"]), strength=float(overlay.get("strength", 0))))
    frame.effects = effects

    ui = WRLUILayer()
    for tooltip in layer.get("ui", {}).get("tooltip", []):
        ui.tooltips.append(WRLTooltip(entity_id=str(tooltip["entity_id"]), text=str(tooltip["text"]), style=str(tooltip.get("style", "speech_bubble"))))
    for hud in layer.get("ui", {}).get("hud", []):
        ui.huds.append(WRLHud(kind=str(hud["kind"]), visible=bool(hud.get("visible", True))))
    frame.ui = ui

    return frame
