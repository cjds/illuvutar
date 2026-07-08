export function renderUI(uiLayer, frame) {
  // Tooltips (existing)
  let html = '';
  for (const tt of (frame.ui?.tooltips || [])) {
    html += `<div style="position:absolute;left:${tt.x || 0}px;top:${tt.y || 0}px;background:#222c;padding:4px 8px;border-radius:4px;color:#fff;font-family:monospace;font-size:12px;pointer-events:none">${tt.entity_id ? tt.entity_id + ': ' : ''}${tt.text || ''}</div>`;
  }
  uiLayer.innerHTML = html;

  // Thought log
  let thoughtLog = document.getElementById('thought-log');
  if (!thoughtLog) return;

  for (const thought of (frame.thoughts || [])) {
    const div = document.createElement('div');
    div.className = 'thought-entry';
    const who = thought.entity_id || 'unknown';
    const msg = thought.text || '';
    div.innerHTML = `<span class="thought-who">${who}</span>: ${msg}`;
    thoughtLog.appendChild(div);
    // Keep last 20 thoughts
    while (thoughtLog.children.length > 20) {
      thoughtLog.removeChild(thoughtLog.firstChild);
    }
  }
}
