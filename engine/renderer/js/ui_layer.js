export function renderUI(uiDiv, frame) {
  uiDiv.innerHTML = '';
  for (const tooltip of frame.ui.tooltips) {
    const el = document.createElement('div');
    el.style.cssText = 'position:absolute;background:#222c;color:#fff;padding:4px 8px;border-radius:4px;font:12px monospace;top:10px;left:10px;pointer-events:none;';
    el.textContent = `${tooltip.entity_id}: ${tooltip.text}`;
    uiDiv.appendChild(el);
  }
}
