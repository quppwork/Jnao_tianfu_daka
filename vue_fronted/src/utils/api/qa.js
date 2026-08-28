/**
 * qa API
 */
import { apiJson, withUser, streamPostSse } from '../userApiCore.js'

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

export function sendQaMessageStream(userId, message, sessionId = null, options = {}, handlers = {}) {
  const subject = typeof options === 'string' ? options : options.subject
  const imageId = options.image_id || options.imageId || null
  const useRag = options.use_rag ?? options.useRag ?? null
  const controller = new AbortController()
  const promise = streamPostSse(
    withUser('/api/qa/chat/stream', userId),
    {
      message,
      session_id: sessionId,
      subject: subject || null,
      image_id: imageId,
      use_rag: useRag,
    },
    { ...handlers, signal: controller.signal },
  )
  return { promise, abort: () => controller.abort() }
}

export async function uploadQaImage(userId, file) {
  const form = new FormData()
  form.append('file', file)
  const headers = mergeAuthHeaders({}, userId)
  const res = await fetch(withUser('/api/qa/upload-image', userId), {
    method: 'POST',
    headers,
    body: form,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
  return data
}

export async function transcribeVoice(audioBlob, filename = 'speech.webm') {
  const userId = getChildUserId()
  if (!userId || !hasUserSession()) throw new NeedLoginError()
  const form = new FormData()
  form.append('audio', audioBlob, filename)
  const headers = mergeAuthHeaders({}, userId)
  const res = await fetch(withUser('/api/voice/asr', userId), { method: 'POST', headers, body: form })
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

