// Minimal TOML-like WRL parser for browser use.
// Handles the specific structure the engine emits — not a full TOML parser.
export function parseFrame(text) {
  const frame = { palette: {}, entities: [], effects: { lights: [], particles: [], overlays: [] }, ui: { tooltips: [], huds: [] } };
  let current = null;
  let section = null;

  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;

    if (line === '[frame]') { current = frame; section = 'frame'; continue; }
    if (line === '[palette]') { current = frame.palette; section = 'palette'; continue; }
    if (line === '[[layer.tiles]]') { frame.tiles = { rows: [] }; current = frame.tiles; section = 'tiles'; continue; }
    if (line === '[[layer.entities.entity]]') { const e = {}; frame.entities.push(e); current = e; section = 'entity'; continue; }
    if (line === '[[layer.effects.light]]') { const l = {}; frame.effects.lights.push(l); current = l; section = 'light'; continue; }
    if (line === '[[layer.effects.particle]]') { const p = {}; frame.effects.particles.push(p); current = p; section = 'particle'; continue; }
    if (line === '[[layer.effects.overlay]]') { const o = {}; frame.effects.overlays.push(o); current = o; section = 'overlay'; continue; }
    if (line === '[[layer.ui.tooltip]]') { const t = {}; frame.ui.tooltips.push(t); current = t; section = 'tooltip'; continue; }
    if (line === '[[layer.ui.hud]]') { const h = {}; frame.ui.huds.push(h); current = h; section = 'hud'; continue; }

    const eqIdx = line.indexOf('=');
    if (eqIdx === -1) continue;
    const key = line.slice(0, eqIdx).trim();
    const rawVal = line.slice(eqIdx + 1).trim();

    if (section === 'tiles' && key === 'rows') { current.rows = []; continue; }
    if (section === 'tiles' && current.rows !== undefined && rawVal.startsWith('"')) {
      current.rows.push(rawVal.slice(1, -2)); continue;
    }
    if (!current) continue;
    if (rawVal.startsWith('"')) { current[key] = rawVal.slice(1, -1); }
    else if (rawVal === 'true') { current[key] = true; }
    else if (rawVal === 'false') { current[key] = false; }
    else { current[key] = parseFloat(rawVal); }
  }
  return frame;
}

export function decodeTileRow(row, width) {
  const tiles = new Array(width).fill(0);
  for (const segment of row.split(',')) {
    const [range, tileIdx] = segment.trim().split(':');
    const idx = parseInt(tileIdx, 10);
    if (range.includes('-')) {
      const [start, end] = range.split('-').map(Number);
      for (let x = start; x <= end && x < width; x++) tiles[x] = idx;
    } else {
      const x = parseInt(range, 10);
      if (x < width) tiles[x] = idx;
    }
  }
  return tiles;
}
