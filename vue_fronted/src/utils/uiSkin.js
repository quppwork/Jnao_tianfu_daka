/**
 * 登录页可选 UI 皮肤：大宇壳（默认）/ 旧版原生首页。
 * 持久化在 localStorage，登录后各端按此跳转。
 */
export const UI_SKIN_KEY = 'jnao_ui_skin'
export const UI_SKIN_DAYU = 'dayu'
export const UI_SKIN_CLASSIC = 'classic'

export function getUiSkin() {
  try {
    const v = String(localStorage.getItem(UI_SKIN_KEY) || '').trim().toLowerCase()
    if (v === UI_SKIN_CLASSIC) return UI_SKIN_CLASSIC
  } catch (_) { /* ignore */ }
  return UI_SKIN_DAYU
}

export function setUiSkin(skin) {
  const next = skin === UI_SKIN_CLASSIC ? UI_SKIN_CLASSIC : UI_SKIN_DAYU
  try {
    localStorage.setItem(UI_SKIN_KEY, next)
  } catch (_) { /* ignore */ }
  return next
}

export function isClassicUi() {
  return getUiSkin() === UI_SKIN_CLASSIC
}

/** 学生登录后首页 */
export function studentHomeUrl() {
  return isClassicUi() ? '/pages/index' : '/pages/dayu/home'
}

/** 家长登录后首页（资料已齐） */
export function parentHomeUrl() {
  return isClassicUi() ? '/pages/parent/index' : '/pages/parent/dayu'
}
