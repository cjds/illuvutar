import { decodeTileRow } from './wrl_parser.js';
export function renderTiles(ctx, frame, camera, atlas) {
  if (!frame.tiles) return;
  const { width, height, rows } = frame.tiles;
  const ts = camera.tileSize;
  for (let y = 0; y < rows.length && y < height; y++) {
    const row = decodeTileRow(rows[y], width);
    for (let x = 0; x < row.length; x++) {
      const spriteName = frame.palette[row[x]] || 'void';
      const [sx, sy] = camera.worldToScreen(x, y);
      if (sx > -ts && sx < ctx.canvas.width + ts && sy > -ts && sy < ctx.canvas.height + ts) {
        ctx.drawImage(atlas.get(spriteName), sx, sy, ts, ts);
      }
    }
  }
}
