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
  invalidateChildUserSession()
}

/** 会话内已验证 uid，避免重复 ping /api/user/profile */
let _sessionValidatedUid = null
let _validateInFlight = null

export function invalidateChildUserSession() {
  _sessionValidatedUid = null
  _validateInFlight = null
}

export function markChildUserSessionValid(uid) {
  if (uid) _sessionValidatedUid = uid
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

/** 答疑图片需带 user_id 鉴权，否则 <img> 请求会 401 */
export function resolveQaImageUrl(url, userId) {
  if (!url || !userId) return url
  if (url.startsWith('blob:') || url.startsWith('data:')) return url
  if (!url.includes('/api/qa/images/')) return url
  if (/[?&]user_id=/.test(url)) return url
  return withUser(url, userId)
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
  if (existing && _sessionValidatedUid === existing) {
    return existing
  }
  if (existing) {
    if (!_validateInFlight) {
      _validateInFlight = (async () => {
        try {
          await apiJson(withUser('/api/user/profile', existing))
          _sessionValidatedUid = existing
        } catch (e) {
          if (e.status === 404) {
            clearChildUserId()
          } else {
            _sessionValidatedUid = existing
          }
        } finally {
          _validateInFlight = null
        }
      })()
    }
    await _validateInFlight
    const uid = getChildUserId()
    if (uid) return uid
  }

  const loginProfile = readLoginProfile()
  const nick = loginProfile?.nickname || getOrCreateGuestNickname(nickname)
  const phone = loginProfile?.phone || getOrCreateGuestPhone()
  const id = await registerChildUser(phone, nick)
  _sessionValidatedUid = id
  return id
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

export async function fetchLatestAssessment(userId) {
  return apiJson(withUser('/api/talent/assessment/latest', userId))
}

export function gradeToSchoolStage(grade) {
  const g = String(grade || '')
  if (['一年级', '二年级', '三年级'].includes(g)) return 'primary_low'
  if (['四年级', '五年级', '六年级'].includes(g)) return 'primary_high'
  if (['初一', '初二', '初三'].includes(g)) return 'junior'
  if (['高一', '高二', '高三'].includes(g)) return 'senior'
  return 'primary_high'
}

export async function resolveTalentConflict(userId, action) {
  return apiJson(withUser('/api/user/talent/resolve-conflict', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action }),
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

export async function fetchTrainingEntry(userId) {
  return apiJson(withUser('/api/training/entry', userId))
}

export async function fetchTrainingToday(userId, options = {}) {
  const skipAi = options.skipAi ?? options.skip_ai ?? false
  const base = skipAi ? '/api/training/today?skip_ai=1' : '/api/training/today'
  try {
    const data = await apiJson(withUser(base, userId))
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

/** 按训练时长排课：框架内 LLM 路由生成 plan_item */
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

/** 孩子确认是否练习可选训练项（高效作业等） */
export async function confirmOptionalTraining(userId, skill, accept) {
  try {
    const data = await apiJson(withUser('/api/training/schedule/optional', userId), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ skill, accept }),
    })
    return { data }
  } catch (e) {
    return { error: 'api', message: e.message }
  }
}

/** 设定时长用尽 — 后端隐藏媒体 URL，打卡仍可用 */
export async function markPlanMediaExhausted(userId) {
  try {
    const data = await apiJson(withUser('/api/training/plan/media-exhausted', userId), {
      method: 'POST',
    })
    return { data }
  } catch (e) {
    return { error: 'api', message: e.message }
  }
}

/** 记录今日训练时段（用于后端判断计时是否结束） */
export async function setTrainingWindow(userId, startTime, endTime) {
  return apiJson(withUser('/api/training/window', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ start_time: startTime, end_time: endTime }),
  })
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

export async function postTrainingWatchProgress(userId, itemId, payload) {
  return apiJson(withUser(`/api/training/items/${itemId}/watch-progress`, userId), {
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

export async function fetchTrainingHistory(userId, limit = 30, { excludeToday = false } = {}) {
  const qs = `limit=${limit}&group_by_day=1${excludeToday ? '&exclude_today=1' : ''}`
  const data = await apiJson(withUser(`/api/training/history?${qs}`, userId))
  return { items: data.items || [], days: data.days || [] }
}

// ── 首页引导对话 ──

export async function fetchGuideSession(userId) {
  return apiJson(withUser('/api/guide/session', userId))
}

export async function clearGuideSession(userId) {
  return apiJson(withUser('/api/guide/clear', userId), { method: 'POST' })
}

export async function sendGuideMessage(userId, message, sessionId = null) {
  return apiJson(withUser('/api/guide/chat', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  })
}

// ── 学科答疑 ──

export async function fetchQaSessions(userId) {
  const data = await apiJson(withUser('/api/qa/sessions', userId))
  return data.items || []
}

export async function createQaSession(userId, subject = null) {
  return apiJson(withUser('/api/qa/sessions', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ subject: subject || null }),
  })
}

export async function deleteQaSession(userId, sessionId) {
  return apiJson(withUser(`/api/qa/sessions/${sessionId}`, userId), { method: 'DELETE' })
}

export async function fetchQaSession(userId, sessionId) {
  return apiJson(withUser(`/api/qa/sessions/${sessionId}`, userId))
}

export async function sendQaMessage(userId, message, sessionId = null, options = {}) {
  const subject = typeof options === 'string' ? options : options.subject
  const imageId = options.image_id || options.imageId || null
  const useRag = options.use_rag ?? options.useRag ?? null
  return apiJson(withUser('/api/qa/chat', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      subject: subject || null,
      image_id: imageId,
      use_rag: useRag,
    }),
  })
}

export async function uploadQaImage(userId, file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(withUser('/api/qa/upload-image', userId), {
    method: 'POST',
    body: form,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
  return data
}

export async function transcribeVoice(audioBlob, filename = 'speech.webm') {
  const form = new FormData()
  form.append('audio', audioBlob, filename)
  const res = await fetch('/api/voice/asr', { method: 'POST', body: form })
  const data = await res.json().catch(() => ({}))
  if (!res.ok || data.error) throw new Error(data.error || data.detail || '语音识别失败')
  return data.text || ''
}

/** uni.chooseImage / getRecorderManager 返回的临时路径 → 转写 */
export async function transcribeVoicePath(tempFilePath) {
  const resp = await fetch(tempFilePath)
  const blob = await resp.blob()
  const ext = (blob.type || '').includes('mpeg') ? 'mp3' : 'webm'
  return transcribeVoice(blob, `recording.${ext}`)
}

export async function updateLearnerProfile(userId, profile) {
  return apiJson(withUser('/api/user/learner-profile', userId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profile),
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

export async function fetchGrowthSummary(userId) {
  return apiJson(withUser('/api/growth/summary', userId))
}

export async function fetchGrowthMilestones(userId) {
  const data = await apiJson(withUser('/api/growth/milestones', userId))
  return data.items || []
}

export async function fetchGrowthShare(userId) {
  return apiJson(withUser('/api/growth/share', userId))
}

// ── 开发者工具（JNAO_DEV_MODE=1）──

export async function fetchDevTrainingStatus(userId) {
  return apiJson(withUser('/api/dev/training/status', userId))
}

export async function devResetTodayTraining(userId) {
  return apiJson(withUser('/api/dev/training/reset-today', userId), { method: 'POST' })
}

export async function devResetTrainingProgress(userId) {
  return apiJson(withUser('/api/dev/training/reset-progress', userId), { method: 'POST' })
}

export async function devResetAllTraining(userId) {
  return apiJson(withUser('/api/dev/training/reset-all', userId), { method: 'POST' })
}

export async function devSimulateNextDay(userId) {
  return apiJson(withUser('/api/dev/training/next-day', userId), { method: 'POST' })
}

export async function devSimulate4amCutoff(userId) {
  return apiJson(withUser('/api/dev/training/simulate-4am-cutoff', userId), { method: 'POST' })
}

export async function devResetTalent(userId) {
  return apiJson(withUser('/api/dev/training/reset-talent', userId), { method: 'POST' })
}
