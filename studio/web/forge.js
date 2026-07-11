const log = document.getElementById('log');
const statusEl = document.getElementById('status');
const playBtn = document.getElementById('play');

function line(cls, html) {
  const d = document.createElement('div');
  d.className = 'line ' + cls; d.innerHTML = html;
  log.appendChild(d); log.scrollTop = log.scrollHeight; return d;
}

const es = new EventSource('/forge/events');
es.onmessage = (e) => {
  const ev = JSON.parse(e.data);
  if (ev.type === 'tool_call') line('step', `▸ ${ev.name}…`);
  else if (ev.type === 'tool_result') { /* keep quiet; status panel reflects it */ refreshStatus(); }
  else if (ev.type === 'message') line('god', `<b>God:</b> ${ev.text}`);
  else if (ev.type === 'error') line('err', `⚠ ${ev.message}`);
  else if (ev.type === 'turn_end') { setBusy(false); refreshStatus(); }
};

const form = document.getElementById('composer');
const input = document.getElementById('msg');
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = input.value.trim(); if (!text) return;
  line('you', `<b>You:</b> ${text}`); input.value = ''; setBusy(true);
  const r = await fetch('/forge/message', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text})});
  if (r.status === 409) { line('err', 'Still building — wait for the current turn.'); setBusy(false); }
});

function setBusy(b) { input.disabled = b; form.querySelector('button').disabled = b; }

async function refreshStatus() {
  const s = await fetch('/forge/status').then(r => r.json()).catch(() => ({}));
  statusEl.innerHTML = Object.entries(s).map(([k,v]) => `<li class="${v?'ok':'no'}">${v?'✓':'○'} ${k}</li>`).join('');
  playBtn.disabled = !s.tilemap;
}
playBtn.addEventListener('click', async () => {
  const r = await fetch('/sim/start', {method:'POST'}).then(r=>r.json()).catch(()=>({}));
  if (r.ready) location.href = '/sim/';
  else line('err', 'World needs a tilemap first — ask the god to run WFC.');
});
refreshStatus();
