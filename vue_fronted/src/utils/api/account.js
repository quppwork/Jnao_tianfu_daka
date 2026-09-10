/**
 * account API
 */
import { apiJson, withUser, setChildUserId, markChildUserSessionValid, invalidatePageAuthCache } from './client.js'

// ── 切换账户 ──
export async function fetchSiblings(userId) {
  return apiJson(withUser('/api/auth/siblings', userId))
}

export async function switchChildAccount(userId, targetChildId) {
  return apiJson(withUser(`/api/auth/switch-child?target_child_id=${targetChildId}`, userId), {
    method: 'POST',
  })
}

export async function switchParentAccount(userId) {
  return apiJson(withUser('/api/auth/switch-parent', userId), {
    method: 'POST',
  })
}

export async function switchStudentAccount(parentId, targetChildId) {
  const q = targetChildId
    ? `?target_child_id=${encodeURIComponent(targetChildId)}`
    : ''
  return apiJson(withUser(`/api/auth/switch-student${q}`, parentId), {
    method: 'POST',
  })
}
