// Entity color palette — deterministic hash so each entity always gets the same colour
const COLORS = ['#7dd3fc','#c4b5fd','#fda4af','#86efac','#fcd34d','#fb923c','#a5f3fc','#f9a8d4'];
function entityColor(id) {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  return COLORS[h % COLORS.length];
}

function escapeHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// Client-side thought history (all thoughts received this session, newest first)
const thoughtHistory = [];
let panelCollapsed = false;
let activeFilter  = 'all';
let searchQuery   = '';

// ── Setup (call once on page load) ─────────────────────────────────────────
export function setupUI() {
  // Collapse / expand the live feed
  document.getElementById('collapse-btn')?.addEventListener('click', () => {
    panelCollapsed = !panelCollapsed;
    const feed = document.getElementById('thought-feed');
    if (feed) feed.style.display = panelCollapsed ? 'none' : '';
    const btn = document.getElementById('collapse-btn');
    if (btn) btn.textContent = panelCollapsed ? '▶' : '▼';
  });

  // History modal open
  document.getElementById('history-btn')?.addEventListener('click', openHistory);
  document.getElementById('history-close')?.addEventListener('click', closeHistory);

  // Click backdrop to close
  document.getElementById('history-modal')?.addEventListener('click', (e) => {
    if (e.target.id === 'history-modal') closeHistory();
  });

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT') return; // don't intercept search box
    if (e.key === 'h' || e.key === 'H') {
      const m = document.getElementById('history-modal');
      m?.classList.contains('hidden') ? openHistory() : closeHistory();
    }
    if (e.key === 'Escape') closeHistory();
  });

  // Search box in history panel
  document.getElementById('history-search')?.addEventListener('input', (e) => {
    searchQuery = e.target.value.toLowerCase();
    renderHistoryList();
  });

  // World HUD controls: Pause/Resume (always), God + Reload (studio-only)
  const BASE = window.__BASE__ || "";
  const pauseBtn = document.getElementById('pause-btn');
  let paused = false;
  function renderPause() { pauseBtn.textContent = paused ? '▶ Resume' : '⏸ Pause'; }
  fetch(BASE + '/status').then(r => r.json()).then(s => { paused = !!s.paused; renderPause(); }).catch(() => {});
  pauseBtn?.addEventListener('click', async () => {
    const path = paused ? '/resume' : '/pause';
    const r = await fetch(BASE + path, { method: 'POST' }).then(r => r.json()).catch(() => null);
    if (r) { paused = r.paused; renderPause(); }
  });
  // studio-only controls: God link + Reload
  if (BASE) {
    const god = document.getElementById('god-link'); if (god) god.style.display = 'inline-block';
    const reload = document.getElementById('reload-btn');
    if (reload) {
      reload.style.display = 'inline-block';
      reload.addEventListener('click', async () => {
        const r = await fetch('/sim/reload', { method: 'POST' }).then(r => r.json()).catch(() => null);
        if (r && r.ready) location.reload();
      });
    }
  }
}

// ── History modal ───────────────────────────────────────────────────────────
function openHistory() {
  const modal = document.getElementById('history-modal');
  if (!modal) return;
  modal.classList.remove('hidden');
  renderHistoryList();

  // Refresh from server — older thoughts the server has that we may have missed
  fetch((window.__BASE__||'') + '/thoughts')
    .then(r => r.json())
    .then(serverThoughts => {
      const seen = new Set(thoughtHistory.map(t => `${t.entity_id}:${t.tick}:${t.text}`));
      let added = false;
      for (const t of serverThoughts) {
        const key = `${t.entity_id}:${t.tick}:${t.text}`;
        if (!seen.has(key)) {
          thoughtHistory.push(t); // append — we'll re-sort below
          seen.add(key);
          added = true;
        }
      }
      if (added) {
        thoughtHistory.sort((a, b) => (b.tick || 0) - (a.tick || 0));
        renderHistoryList();
      }
    })
    .catch(() => {}); // engine may not be running
}

function closeHistory() {
  document.getElementById('history-modal')?.classList.add('hidden');
  // Reset search so next open is fresh
  searchQuery = '';
  const s = document.getElementById('history-search');
  if (s) s.value = '';
}

function renderHistoryList() {
  const list    = document.getElementById('history-list');
  const filters = document.getElementById('history-filters');
  const count   = document.getElementById('history-count');
  if (!list || !filters) return;

  // Build entity set
  const entities = ['all', ...new Set(thoughtHistory.map(t => t.entity_id).filter(Boolean))];
  if (!entities.includes(activeFilter)) activeFilter = 'all';

  // Re-render filter buttons (keep the search input intact)
  const searchInput = document.getElementById('history-search');
  filters.innerHTML = entities.map(id =>
    `<button class="filter-btn ${activeFilter === id ? 'active' : ''}" data-entity="${id}"
      style="${id !== 'all' ? `color:${entityColor(id)};border-color:${entityColor(id)}40` : ''}"
    >${id === 'all' ? 'All' : id}</button>`
  ).join('');
  if (searchInput) filters.appendChild(searchInput);

  filters.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      activeFilter = btn.dataset.entity;
      renderHistoryList();
    });
  });

  // Filter + search
  let filtered = activeFilter === 'all'
    ? thoughtHistory
    : thoughtHistory.filter(t => t.entity_id === activeFilter);
  if (searchQuery) {
    filtered = filtered.filter(t =>
      (t.text || '').toLowerCase().includes(searchQuery) ||
      (t.entity_id || '').toLowerCase().includes(searchQuery)
    );
  }

  if (count) count.textContent = `${filtered.length} thought${filtered.length !== 1 ? 's' : ''}`;

  if (filtered.length === 0) {
    list.innerHTML = '<div class="history-empty">No thoughts yet.<br>Entities think every ~5 seconds once the engine is running.</div>';
    return;
  }

  list.innerHTML = filtered.map(t => {
    const color = entityColor(t.entity_id || '');
    const tickLabel = t.tick !== undefined ? t.tick : '?';
    return `<div class="history-entry">
      <div class="h-meta">
        <span class="h-tick">t.${tickLabel}</span>
        <span class="h-who" style="color:${color}">${escapeHtml(t.entity_id || 'unknown')}</span>
      </div>
      <div class="h-body">${escapeHtml(t.text || '')}</div>
    </div>`;
  }).join('');
}

// ── Per-frame render (called by renderer.js on every SSE frame) ─────────────
export function renderUI(uiLayer, frame) {
  // Tooltips
  let html = '';
  for (const tt of (frame.ui?.tooltips || [])) {
    html += `<div style="position:absolute;left:${tt.x||0}px;top:${tt.y||0}px;background:#0d0d1a;border:1px solid #2a1f4e;padding:4px 9px;border-radius:5px;color:#e2e8f0;font-family:monospace;font-size:11px;pointer-events:none;white-space:nowrap">${tt.entity_id ? `<span style="color:${entityColor(tt.entity_id)};font-weight:bold">${escapeHtml(tt.entity_id)}</span>: ` : ''}${escapeHtml(tt.text || '')}</div>`;
  }
  uiLayer.innerHTML = html;

  // Live thought feed
  const feed = document.getElementById('thought-feed');
  if (!feed || !(frame.thoughts?.length)) return;

  for (const thought of frame.thoughts) {
    const who = thought.entity_id || 'unknown';
    const msg = thought.text || '';
    const tick = thought.tick;

    // Store in session history (newest first)
    thoughtHistory.unshift({ entity_id: who, text: msg, tick });
    if (thoughtHistory.length > 500) thoughtHistory.pop();

    // Append to live feed
    if (!panelCollapsed) {
      const div = document.createElement('div');
      div.className = 'thought-entry';
      const color = entityColor(who);
      div.innerHTML =
        `<span class="thought-tick">t.${tick ?? '?'}</span>` +
        `<span class="thought-who" style="color:${color}">${escapeHtml(who)}</span>` +
        `<span class="thought-msg">${escapeHtml(msg)}</span>`;
      feed.prepend(div);
      while (feed.children.length > 30) feed.removeChild(feed.lastChild);
    }
  }

  // Keep history modal in sync if it's open
  const modal = document.getElementById('history-modal');
  if (modal && !modal.classList.contains('hidden')) {
    renderHistoryList();
  }
}
