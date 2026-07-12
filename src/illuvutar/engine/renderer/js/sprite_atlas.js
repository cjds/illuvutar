export class SpriteAtlas {
  constructor(basePath = '/sprites') {
    this.basePath = basePath;
    this._cache = {};
    this._missing = this._makeMissing();
  }
  _makeMissing() {
    const c = document.createElement('canvas'); c.width = 32; c.height = 32;
    const ctx = c.getContext('2d');
    ctx.fillStyle = '#f0f'; ctx.fillRect(0, 0, 32, 32);
    ctx.fillStyle = '#000'; ctx.fillRect(8, 8, 16, 16);
    return c;
  }
  get(name) {
    if (this._cache[name]) return this._cache[name];
    const img = new Image();
    img.src = `${this.basePath}/${name}.png`;
    img.onload = () => { this._cache[name] = img; };
    img.onerror = () => { this._cache[name] = this._missing; };
    this._cache[name] = this._missing;
    return this._missing;
  }
}
