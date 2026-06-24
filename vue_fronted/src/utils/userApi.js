/** 后端 API — 用户身份与各模块数据（仅存 child_user_id 于 localStorage） */

const CHILD_KEY = 'jnao_child_user_id'

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

/** 无则自动注册，返回 child_user_id */
export async function ensureChildUser(nickname = '学员') {
  const existing = getChildUserId()
  if (existing) return existing

  const phone = `13${String(Date.now()).slice(-9)}`
  const data = await apiJson('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ parent_phone: phone, nickname }),
  })
  setChildUserId(data.child_user_id)
  return data.child_user_id
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

// ── 天赋测评 ──

export async function fetchAssessmentHistory(userId) {
  const data = await apiJson(withUser('/api/talent/assessment/history', userId))
  return data.items || []
}

export async function fetchAssessmentReport(userId, assessmentId) {
  return apiJson(withUser(`/api/talent/assessment/${assessmentId}`, userId))
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

export async function fetchTrainingProgress(userId) {
  return apiJson(withUser('/api/training/progress', userId))
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
