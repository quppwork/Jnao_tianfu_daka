/**
 * talent API
 */
import { apiJson, withUser, requirePageAuth, NeedLoginError, streamPostSse } from './client.js'
import { readAuthSnapshot } from '../appSession.js'

// ── 天赋测评 ──

/** 报告/测评页：家长或学生，谁登录用谁（报告归属当前用户）。 */
export async function ensureReportUser() {
  const snap = readAuthSnapshot()
  const preferParent =
    snap.role === 'parent' || (!!snap.parent?.userId && !snap.student?.userId)
  const order = preferParent ? ['parent', 'student'] : ['student', 'parent']
  for (const kind of order) {
    const session = kind === 'parent' ? snap.parent : snap.student
    if (!session?.userId) continue
    const auth = await requirePageAuth(kind)
    if (auth.ok) return auth.userId
  }
  throw new NeedLoginError('请先登录后再查看报告')
}

export async function fetchAssessmentHistory(userId) {
  const data = await apiJson(withUser('/api/talent/assessment/history', userId))
  return data.items || []
}

export async function fetchAssessmentReport(userId, assessmentId) {
  return apiJson(withUser(`/api/talent/assessment/${assessmentId}`, userId))
}

export async function fetchReportTalentChat(userId, assessmentId) {
  return apiJson(withUser(`/api/talent/assessment/${assessmentId}/chat`, userId))
}

export async function sendReportTalentChat(userId, assessmentId, content) {
  return apiJson(withUser(`/api/talent/assessment/${assessmentId}/chat`, userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
}

/** 流式天赋解答：onToken 增量 / onReplace 整段替换 / onDone 权威消息 */
export function streamReportTalentChat(userId, assessmentId, content, handlers = {}) {
  return streamPostSse(
    withUser(`/api/talent/assessment/${assessmentId}/chat/stream`, userId),
    { content },
    handlers,
  )
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
  return apiJson(withUser('/api/talent/report', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      answer,
      uid: jnaoUid,
      type,
    }),
  })
}

// ── 今日训练（核心模块：入口→排课→打卡→历史）──

/** 训练入口：校验天赋状态 + 检查今日方案是否存在 */
