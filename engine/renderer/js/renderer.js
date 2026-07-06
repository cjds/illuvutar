import { parseFrame } from './wrl_parser.js';
import { SpriteAtlas } from './sprite_atlas.js';
import { Camera } from './camera.js';
import { renderTiles } from './tile_layer.js';
import { renderEntities } from './entity_layer.js';
import { renderEffects } from './effect_layer.js';
import { renderUI } from './ui_layer.js';

const worldCanvas = document.getElementById('world-canvas');
const effectCanvas = document.getElementById('effect-canvas');
const uiLayer = document.getElementById('ui-layer');
const ctx2d = worldCanvas.getContext('2d');
const gl = effectCanvas.getContext('webgl2');

function resize() {
  const w = window.innerWidth, h = window.innerHeight;
  worldCanvas.width = effectCanvas.width = w;
  worldCanvas.height = effectCanvas.height = h;
}
resize();
window.addEventListener('resize', resize);

const atlas = new SpriteAtlas('/sprites');
const camera = new Camera(32);
let tick = 0;

const evtSource = new EventSource('/frames');
evtSource.onmessage = (evt) => {
  if (evt.data === 'ping') return;
  const frame = parseFrame(evt.data);
  tick = frame.tick || tick;

  ctx2d.clearRect(0, 0, worldCanvas.width, worldCanvas.height);
  renderTiles(ctx2d, frame, camera, atlas);
  renderEntities(ctx2d, frame, camera, atlas);
  renderEffects(gl, frame, effectCanvas.width, effectCanvas.height, tick);
  renderUI(uiLayer, frame);
};

evtSource.onerror = () => console.warn('SSE connection lost, browser will reconnect.');

document.addEventListener('keydown', (e) => {
  const map = { ArrowUp: 'north', ArrowDown: 'south', ArrowLeft: 'west', ArrowRight: 'east' };
  if (!map[e.key]) return;
  fetch('/command', {
    method: 'POST',
    body: `[command]\ntick_submitted = ${tick}\nagent_id = "player"\naction = "move"\ndirection = "${map[e.key]}"\n`,
    headers: { 'Content-Type': 'text/plain' },
  });
});
