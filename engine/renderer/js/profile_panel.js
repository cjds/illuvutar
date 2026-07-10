export function setupProfilePanel(canvas, camera, getFrame) {
  const panel = document.getElementById('profile-panel');
  const els = {
    name: document.getElementById('profile-name'),
    job: document.getElementById('profile-job'),
    backstory: document.getElementById('profile-backstory'),
    goal: document.getElementById('profile-goal'),
  };
  const hide = () => { panel.style.display = 'none'; };
  document.getElementById('profile-close')?.addEventListener('click', hide);

  canvas.addEventListener('click', (e) => {
    const frame = getFrame();
    if (!frame) return;
    const rect = canvas.getBoundingClientRect();
    const cx = e.clientX - rect.left, cy = e.clientY - rect.top;
    const ts = camera.tileSize;
    // topmost entity (highest y drawn last) under the click
    let hit = null;
    for (const en of frame.entities) {
      const [sx, sy] = camera.worldToScreen(en.x, en.y);
      if (cx >= sx && cx <= sx + ts && cy >= sy && cy <= sy + ts) {
        if (!hit || en.y > hit.y) hit = en;
      }
    }
    if (!hit) { hide(); return; }
    fetch(`/entity/${encodeURIComponent(hit.id)}/profile`)
      .then((r) => (r.ok ? r.json() : null))
      .then((p) => {
        if (!p) return;
        els.name.textContent = p.name || p.id;
        els.job.textContent = p.job || '';
        els.backstory.textContent = p.backstory || '(no story recorded)';
        els.goal.textContent = p.goal ? `Goal: ${p.goal}` : '';
        panel.style.display = 'block';
      })
      .catch(() => {});
  });
}
