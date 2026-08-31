/**
 * growth API
 */
import { apiJson, withUser } from './client.js'

// ── 成长里程碑 ──

export async function fetchGrowthBadges(userId) {
  const data = await apiJson(withUser('/api/growth/badges', userId))
  return data.items || []
}

export async function fetchGrowthTimeline(userId) {
  const data = await apiJson(withUser('/api/growth/timeline', userId))
  return data.items || []
}

export async function fetchGrowthCalendar(userId) {
  const data = await apiJson(withUser('/api/growth/calendar', userId))
  return data.items || []
}

// 六级九段轻量摘要（全局角标 / 训练页状态卡用）
export async function fetchGrowthTier(userId) {
  return apiJson(withUser('/api/growth/tier', userId))
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

export async function fetchAcademicPlan(userId, refresh = false) {
  return apiJson(withUser('/api/growth/academic-plan' + (refresh ? '?refresh=true' : ''), userId))
}

