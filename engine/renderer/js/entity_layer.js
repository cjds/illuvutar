export function renderEntities(ctx, frame, camera, atlas) {
  const ts = camera.tileSize;
  const sorted = [...frame.entities].sort((a, b) => a.y - b.y || a.id.localeCompare(b.id));
  for (const entity of sorted) {
    const [sx, sy] = camera.worldToScreen(entity.x, entity.y);
    if (sx < -ts || sx > ctx.canvas.width + ts) continue;
    ctx.drawImage(atlas.get(entity.sprite), sx, sy, ts, ts);
    if (entity.label) {
      ctx.fillStyle = '#fff'; ctx.font = '10px monospace';
      ctx.fillText(entity.label, sx + ts / 2 - ctx.measureText(entity.label).width / 2, sy - 4);
    }
    if (entity.health < 1.0) {
      ctx.fillStyle = '#333'; ctx.fillRect(sx, sy + ts, ts, 4);
      ctx.fillStyle = '#4f4'; ctx.fillRect(sx, sy + ts, ts * entity.health, 4);
    }
  }
}
