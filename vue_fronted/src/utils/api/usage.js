/** 上游用量（豆包/百炼）— 开发可视化 */
import { apiJson, withUser, getChildUserId } from './client.js'

export async function fetchUsageSummary(userId) {
  const uid = userId || getChildUserId()
  if (!uid) throw new Error('缺少 user_id')
  return apiJson(withUser('/api/usage/summary', uid))
}

export function formatTokenCount(n) {
  const v = Number(n) || 0
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
  if (v >= 10_000) return `${Math.round(v / 1000)}k`
  if (v >= 1000) return `${(v / 1000).toFixed(1)}k`
  return String(v)
}
