/**
 * talent API
 */
import { apiJson, withUser } from './client.js'

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
