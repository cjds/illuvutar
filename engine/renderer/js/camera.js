export class Camera {
  constructor(tileSize = 32) {
    this.x = 0; this.y = 0;
    this.tileSize = tileSize;
    this.targetX = 0; this.targetY = 0;
    this.deadzone = 3;
  }
  follow(entityX, entityY, canvasW, canvasH) {
    const cx = canvasW / 2 / this.tileSize;
    const cy = canvasH / 2 / this.tileSize;
    if (Math.abs(entityX - (this.targetX + cx)) > this.deadzone) this.targetX = entityX - cx;
    if (Math.abs(entityY - (this.targetY + cy)) > this.deadzone) this.targetY = entityY - cy;
    this.x += (this.targetX - this.x) * 0.15;
    this.y += (this.targetY - this.y) * 0.15;
  }
  worldToScreen(worldX, worldY) {
    return [(worldX - this.x) * this.tileSize, (worldY - this.y) * this.tileSize];
  }
}
