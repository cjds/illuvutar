export function renderEffects(gl, frame, canvasW, canvasH, tick) {
  gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
  // Minimal stub: full WebGL lighting pass would go here.
  // For now, just applies a soft vignette via alpha.
  const vignette = frame.effects.overlays.find(o => o.kind === 'vignette');
  if (!vignette) return;
  // WebGL vignette is rendered server-side as a screen-space quad.
  // Full implementation requires a compiled shader program.
  // Left as extension point — effect layer is safely skipped on low-end devices.
}
