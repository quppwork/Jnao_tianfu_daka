const DEV_KEY = 'jnao_dev_mode'

export function getDevMode() {
  try {
    return sessionStorage.getItem(DEV_KEY) === '1'
  } catch (_) {
    return false
  }
}

export function setDevMode(on) {
  try {
    if (on) sessionStorage.setItem(DEV_KEY, '1')
    else sessionStorage.removeItem(DEV_KEY)
  } catch (_) { /* ignore */ }
}
