/**
 * guide API
 */
import { apiJson, withUser, streamPostSse } from './client.js'

// ── 首页引导对话 ──

export async function fetchGuideSession(userId) {
  return apiJson(withUser('/api/guide/session', userId))
}

export async function fetchGuideSessions(userId) {
  const data = await apiJson(withUser('/api/guide/sessions', userId))
  return data.items || []
}

export async function fetchGuideSessionById(userId, sessionId) {
  return apiJson(withUser(`/api/guide/sessions/${sessionId}`, userId))
}

export async function deleteGuideSession(userId, sessionId) {
  return apiJson(withUser(`/api/guide/sessions/${sessionId}`, userId), { method: 'DELETE' })
}

/** 进首页开场 Agent：按情境返回欢迎语 */
export async function fetchGuideBootstrap(userId, { force = false, use_llm = true, timeoutMs = 6000 } = {}) {
  return apiJson(withUser('/api/guide/bootstrap', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ force, use_llm }),
    timeoutMs,
  })
}

export async function clearGuideSession(userId) {
  return apiJson(withUser('/api/guide/clear', userId), { method: 'POST' })
}

/** R5：确认卡二次确认后的受控写 */
export async function confirmGuideWrite(userId, writeOp, args = {}) {
  return apiJson(withUser('/api/guide/confirm', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ write_op: writeOp, args: args || {} }),
  })
}

export async function sendGuideMessage(userId, message, sessionId = null, options = {}) {
  return apiJson(withUser('/api/guide/chat', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
    timeoutMs: options.timeoutMs ?? 150000,
    signal: options.signal,
  })
}

export function sendGuideMessageStream(userId, message, sessionId = null, handlers = {}) {
  const controller = new AbortController()
  const promise = streamPostSse(
    withUser('/api/guide/chat/stream', userId),
    { message, session_id: sessionId },
    { ...handlers, signal: controller.signal },
  )
  return { promise, abort: () => controller.abort() }
}

