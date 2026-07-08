export function renderUI(uiLayer, frame) {
  // Tooltips (existing)
  let html = '';
  for (const tt of (frame.ui?.tooltips || [])) {
    html += `<div class="tooltip" style="left:${tt.x || 0}px;top:${tt.y || 0}px">${tt.text}</div>`;
  }
  uiLayer.innerHTML = html;

  // Thought log
  let thoughtLog = document.getElementById('thought-log');
  if (!thoughtLog) return;

  for (const thought of (frame.thoughts || [])) {
    const div = document.createElement('div');
    div.className = 'thought-entry';
    div.innerHTML = `<span class="thought-who">${thought.entity_id}</span>: ${thought.text}`;
    thoughtLog.appendChild(div);
    // Keep last 20 thoughts
    while (thoughtLog.children.length > 20) {
      thoughtLog.removeChild(thoughtLog.firstChild);
    }
  }
}
