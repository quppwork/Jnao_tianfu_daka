/** 后端 API — 用户身份与各模块数据（仅存 child_user_id 于 localStorage） */

const CHILD_KEY = 'jnao_child_user_id'
const GUEST_PHONE_KEY = 'jnao_guest_phone'
const GUEST_NICKNAME_KEY = 'jnao_guest_nickname'

export function getChildUserId() {
  try {
    const raw = localStorage.getItem(CHILD_KEY)
    if (raw) return parseInt(raw, 10)
  } catch (e) { /* ignore */ }
  return null
}

export function setChildUserId(id) {
  try {
    localStorage.setItem(CHILD_KEY, String(id))
  } catch (e) { /* ignore */ }
}

export function clearChildUserId() {
  try {
    localStorage.removeItem(CHILD_KEY)
    localStorage.removeItem(GUEST_PHONE_KEY)
    localStorage.removeItem(GUEST_NICKNAME_KEY)
  } catch (e) { /* ignore */ }
}

async function apiJson(url, options = {}) {
  const res = await fetch(url, options)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.detail || data.message || `HTTP ${res.status}`)
    err.status = res.status
    err.data = data
    throw err
  }
  return data
}

function withUser(url, userId) {
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}user_id=${userId}`
}

function getOrCreateGuestPhone() {
  try {
    const saved = localStorage.getItem(GUEST_PHONE_KEY)
    if (saved) return saved
    const phone = `13${String(Math.floor(Math.random() * 1e9)).padStart(9, '0')}`
    localStorage.setItem(GUEST_PHONE_KEY, phone)
    return phone
  } catch (e) {
    return `13${String(Date.now()).slice(-9)}`
  }
}

/** 登录：验证手机+昵称，不存在则报错 */
export async function loginUser(phone, nickname) {
  const data = await apiJson('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ parent_phone: phone, nickname }),
  })
  setChildUserId(data.child_user_id)
  return data
}

/** 注册：用手机+昵称创建新用户 */
export async function registerChild(phone, nickname) {
  const data = await apiJson('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ parent_phone: phone, nickname }),
  })
  setChildUserId(data.child_user_id)
  return data
}

function getOrCreateGuestNickname(fallback = '学员') {
  try {
    const saved = localStorage.getItem(GUEST_NICKNAME_KEY)
    if (saved) return saved
    localStorage.setItem(GUEST_NICKNAME_KEY, fallback)
    return fallback
  } catch (e) {
    return fallback
  }
}

function readLoginProfile() {
  try {
    const raw = localStorage.getItem('jnao_user')
    if (!raw) return null
    const user = JSON.parse(raw)
    if (!user?.name) return null
    return {
      nickname: String(user.name).trim(),
      phone: String(user.phone || '').trim(),
    }
  } catch (e) {
    return null
  }
}

async function registerChildUser(parentPhone, nickname) {
  const data = await apiJson('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ parent_phone: parentPhone, nickname }),
  })
  setChildUserId(data.child_user_id)
  try {
    localStorage.setItem(GUEST_PHONE_KEY, parentPhone)
    localStorage.setItem(GUEST_NICKNAME_KEY, nickname)
  } catch (e) { /* ignore */ }
  return data.child_user_id
}

/** 登录页：用手机号+昵称绑定已有账号或注册 */
export async function loginOrRegisterChildUser({ nickname, phone } = {}) {
  const loginProfile = readLoginProfile()
  const nick = (nickname || loginProfile?.nickname || getOrCreateGuestNickname()).trim() || '学员'
  const parentPhone = (phone || loginProfile?.phone || getOrCreateGuestPhone()).trim() || getOrCreateGuestPhone()
  return registerChildUser(parentPhone, nick)
}

/** 无则自动注册，返回 child_user_id（同一设备/浏览器会复用稳定身份） */
export async function ensureChildUser(nickname = '学员') {
  const existing = getChildUserId()
  if (existing) {
    try {
      await apiJson(withUser('/api/user/profile', existing))
      return existing
    } catch (e) {
      if (e.status !== 404) return existing
      clearChildUserId()
    }
  }

  const loginProfile = readLoginProfile()
  const nick = loginProfile?.nickname || getOrCreateGuestNickname(nickname)
  const phone = loginProfile?.phone || getOrCreateGuestPhone()
  return registerChildUser(phone, nick)
}

/** JNAO 外部 API 用的 uid（存于 child_user.jnao_uid） */
export async function ensureJnaoUid(userId) {
  const profile = await apiJson(withUser('/api/user/profile', userId))
  if (profile.jnao_uid) return parseInt(profile.jnao_uid, 10)
  const jnaoUid = userId * 1000 + (Date.now() % 1000)
  await apiJson(withUser('/api/user/profile', userId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jnao_uid: String(jnaoUid) }),
  })
  return jnaoUid
}

// ── 用户资料 ──

export async function fetchProfile(userId) {
  return apiJson(withUser('/api/user/profile', userId))
}

export async function saveProfile(userId, data) {
  return apiJson(withUser('/api/user/profile', userId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

// ── 天赋测评 ──

export async function fetchAssessmentHistory(userId) {
  const data = await apiJson(withUser('/api/talent/assessment/history', userId))
  return data.items || []
}

export async function fetchAssessmentReport(userId, assessmentId) {
  return apiJson(withUser(`/api/talent/assessment/${assessmentId}`, userId))
}

export async function deleteAssessmentReport(userId, assessmentId) {
  return apiJson(withUser(`/api/talent/assessment/${assessmentId}`, userId), {
    method: 'DELETE',
  })
}

export async function submitTalentReport(userId, { answer, jnaoUid, type }) {
  return apiJson('/api/talent/report', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      answer,
      uid: jnaoUid,
      type,
      child_user_id: userId,
    }),
  })
}

// ── 今日训练 ──

export async function fetchTrainingToday(userId) {
  try {
    const data = await apiJson(withUser('/api/training/today', userId))
    return { data }
  } catch (e) {
    if (e.status === 403) {
      return { error: 'assessment', message: e.data?.detail || '请先完成天赋测评' }
    }
    return { error: 'api', message: e.message }
  }
}

/** 强制重新生成 AI 今日方案（开发者/刷新用） */
export async function refreshTrainingReport(userId, force = true) {
  try {
    const data = await apiJson(withUser(`/api/training/report/today?force=${force ? '1' : '0'}`, userId))
    return { data }
  } catch (e) {
    if (e.status === 403) {
      return { error: 'assessment', message: e.data?.detail || '请先完成天赋测评' }
    }
    return { error: 'api', message: e.message }
  }
}

/** 按训练时长排课：豆包路由 A/B 音频 + 天赋视频 */
export async function scheduleTrainingPlan(userId, plannedMinutes) {
  try {
    const data = await apiJson(withUser('/api/training/schedule', userId), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ planned_minutes: plannedMinutes }),
    })
    return { data }
  } catch (e) {
    if (e.status === 403) {
      return { error: 'assessment', message: e.data?.detail || '请先完成天赋测评' }
    }
    return { error: 'api', message: e.message }
  }
}

/** 天赋固定训练视频 */
export async function fetchTalentTrainingVideo(userId) {
  return apiJson(withUser('/api/training/video/talent', userId))
}

export async function fetchTrainingProgress(userId) {
  return apiJson(withUser('/api/training/progress', userId))
}

export async function submitTrainingCheckin(userId, payload) {
  return apiJson(withUser('/api/training/checkin', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function fetchTodayCheckins(userId) {
  const data = await apiJson(withUser('/api/training/checkin/today', userId))
  return Array.isArray(data) ? data : []
}

export async function updateTrainingCheckin(userId, recordId, payload) {
  return apiJson(withUser(`/api/training/checkin/${recordId}`, userId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function deleteTrainingCheckin(userId, recordId) {
  return apiJson(withUser(`/api/training/checkin/${recordId}`, userId), {
    method: 'DELETE',
  })
}

export async function fetchTrainingHistory(userId, limit = 30) {
  const data = await apiJson(withUser(`/api/training/history?limit=${limit}`, userId))
  return data.items || []
}

// ── 首页引导对话 ──

export async function fetchGuideSession(userId) {
  return apiJson(withUser('/api/guide/session', userId))
}

export async function sendGuideMessage(userId, message, sessionId = null) {
  return apiJson(withUser('/api/guide/chat', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  })
}

// ── 学科答疑 ──

export async function fetchQaSession(userId, sessionId) {
  return apiJson(withUser(`/api/qa/sessions/${sessionId}`, userId))
}

export async function sendQaMessage(userId, message, sessionId = null, subject = null) {
  return apiJson(withUser('/api/qa/chat', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId, subject }),
  })
}

// ── 成长里程碑 ──

export async function fetchGrowthBadges(userId) {
  const data = await apiJson(withUser('/api/growth/badges', userId))
  return data.items || []
}

export async function fetchGrowthTimeline(userId) {
  const data = await apiJson(withUser('/api/growth/timeline', userId))
  return data.items || []
}

// ── 开发者工具（JNAO_DEV_MODE=1）──

export async function fetchDevTrainingStatus(userId) {
  return apiJson(withUser('/api/dev/training/status', userId))
}

export async function devResetTodayTraining(userId) {
  return apiJson(withUser('/api/dev/training/reset-today', userId), { method: 'POST' })
}

export async function devResetAllTraining(userId) {
  return apiJson(withUser('/api/dev/training/reset-all', userId), { method: 'POST' })
}

export async function devSimulateNextDay(userId) {
  return apiJson(withUser('/api/dev/training/next-day', userId), { method: 'POST' })
}
