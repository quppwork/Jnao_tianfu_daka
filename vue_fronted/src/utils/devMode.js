const DEV_KEY = 'jnao_dev_mode'

/**
 * 前端是否展示开发者开关：
 * - Vite 开发服 `import.meta.env.DEV`
 * - 或显式 `VITE_DEV_TOOLS=1` / `VITE_JNAO_DEV_MODE=1`（生产构建也可开）
 * 实际 /api/dev/* 仍需后端 `JNAO_DEV_MODE=1`。
 */
export function isDevToolsAvailable() {
  if (import.meta.env.DEV) return true
  const flag = String(
    import.meta.env.VITE_DEV_TOOLS || import.meta.env.VITE_JNAO_DEV_MODE || '',
  ).trim().toLowerCase()
  return flag === '1' || flag === 'true' || flag === 'yes'
}

export function getDevMode() {
  if (!isDevToolsAvailable()) return false
  try {
    return sessionStorage.getItem(DEV_KEY) === '1'
  } catch (_) {
    return false
  }
}

export function setDevMode(on) {
  if (!isDevToolsAvailable()) return
  try {
    if (on) sessionStorage.setItem(DEV_KEY, '1')
    else sessionStorage.removeItem(DEV_KEY)
  } catch (_) { /* ignore */ }
}
