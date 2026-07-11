import { parseFrame } from './wrl_parser.js';
import { SpriteAtlas } from './sprite_atlas.js';
import { Camera } from './camera.js';
import { renderTiles } from './tile_layer.js';
import { renderEntities } from './entity_layer.js';
import { renderEffects } from './effect_layer.js';
import { renderUI, setupUI } from './ui_layer.js';
import { setupProfilePanel } from './profile_panel.js';

const BASE = window.__BASE__ || "";

const worldCanvas = document.getElementById('world-canvas');
const effectCanvas = document.getElementById('effect-canvas');
const uiLayer = document.getElementById('ui-layer');
const ctx2d = worldCanvas.getContext('2d');
const gl = effectCanvas.getContext('webgl2');

setupUI();

function resize() {
  const w = window.innerWidth, h = window.innerHeight;
  worldCanvas.width = effectCanvas.width = w;
  worldCanvas.height = effectCanvas.height = h;
}
resize();
window.addEventListener('resize', resize);

const atlas = new SpriteAtlas(BASE + '/sprites');
const camera = new Camera(32);
let tick = 0;
let currentFrame = null;
setupProfilePanel(worldCanvas, camera, () => currentFrame);

const tickEl = document.getElementById('tick-display');
const connEl = document.getElementById('conn-status');

const evtSource = new EventSource(BASE + '/frames');
evtSource.onmessage = (evt) => {
  if (evt.data === 'ping') return;
  const frame = parseFrame(evt.data);
  currentFrame = frame;
  tick = frame.tick || tick;

  if (tickEl) tickEl.textContent = `Tick ${tick}`;

  ctx2d.clearRect(0, 0, worldCanvas.width, worldCanvas.height);
  renderTiles(ctx2d, frame, camera, atlas);
  renderEntities(ctx2d, frame, camera, atlas);
  renderEffects(gl, frame, effectCanvas.width, effectCanvas.height, tick);
  renderUI(uiLayer, frame);
};

evtSource.onerror = () => {
  console.warn('SSE connection lost, browser will reconnect.');
  if (connEl) { connEl.textContent = '● Reconnecting'; connEl.className = 'err'; }
};
evtSource.onopen = () => {
  if (connEl) { connEl.textContent = '● Connected'; connEl.className = 'ok'; }
};

document.addEventListener('keydown', (e) => {
  const map = { ArrowUp: 'north', ArrowDown: 'south', ArrowLeft: 'west', ArrowRight: 'east' };
  if (!map[e.key]) return;
  fetch(BASE + '/command', {
    method: 'POST',
    body: `[command]\ntick_submitted = ${tick}\nagent_id = "player"\naction = "move"\ndirection = "${map[e.key]}"\n`,
    headers: { 'Content-Type': 'text/plain' },
  });
});
