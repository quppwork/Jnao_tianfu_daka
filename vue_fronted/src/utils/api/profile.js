/**
 * profile API
 */
import { apiJson, withUser } from '../userApiCore.js'

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

