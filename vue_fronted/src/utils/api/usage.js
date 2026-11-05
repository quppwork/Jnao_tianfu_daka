/** 上游用量（豆包/百炼）— 开发可视化 / 算力中心 */
import { apiJson, withUser, getChildUserId } from './client.js'

export async function fetchUsageSummary(userId) {
  const uid = userId || getChildUserId()
  if (!uid) throw new Error('缺少 user_id')
  return apiJson(withUser('/api/usage/summary', uid))
}

export async function fetchUsageWallet(userId) {
  const uid = userId || getChildUserId()
  if (!uid) throw new Error('缺少 user_id')
  return apiJson(withUser('/api/usage/wallet', uid))
}

export async function fetchUsageByFeature(userId) {
  const uid = userId || getChildUserId()
  if (!uid) throw new Error('缺少 user_id')
  return apiJson(withUser('/api/usage/by-feature', uid))
}

export async function fetchUsageEvents(userId, { limit = 50, scope = 'household' } = {}) {
  const uid = userId || getChildUserId()
  if (!uid) throw new Error('缺少 user_id')
  const q = new URLSearchParams({ limit: String(limit), scope })
  return apiJson(withUser(`/api/usage/events?${q}`, uid))
}

export function formatTokenCount(n) {
  const v = Number(n) || 0
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
  if (v >= 10_000) return `${Math.round(v / 1000)}k`
  if (v >= 1000) return `${(v / 1000).toFixed(1)}k`
  return String(v)
}

export function formatYuan(n) {
  const v = Number(n) || 0
  if (v >= 1) return `¥${v.toFixed(2)}`
  if (v >= 0.01) return `¥${v.toFixed(3)}`
  return `¥${v.toFixed(4)}`
}
