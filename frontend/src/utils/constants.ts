const host = location.hostname

export const WS_URL = `ws://${host}/api/ws/audio`
export const WAKE_WS_URL = `ws://${host}/api/ws/wake`
export const API_URL = `http://${host}/api`

export const JARVIS_COLORS = {
  primary: '#00d4ff',
  secondary: '#0099cc',
  accent: '#66f0ff',
  warning: '#ffaa00',
  error: '#ff3355',
  success: '#00ff88',
  background: '#0a0a1a',
  surface: 'rgba(0, 20, 40, 0.6)',
  text: '#e0f0ff',
  textDim: 'rgba(180, 210, 240, 0.6)',
  glow: 'rgba(0, 212, 255, 0.15)',
}

export const ANIMATION = {
  pulseDuration: 2,
  rotateDuration: 8,
  fadeDuration: 0.6,
}

export const PARTICLES = {
  count: 200,
  size: 2,
  speed: 0.3,
  color: '#00d4ff',
}
