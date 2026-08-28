/**
 * account API
 */
import { apiJson, withUser, setChildUserId, markChildUserSessionValid, invalidatePageAuthCache } from '../userApiCore.js'

// ── 切换账户 ──
export async function fetchSiblings(userId) {
  return apiJson(withUser('/api/auth/siblings', userId))
}

export async function switchChildAccount(userId, targetChildId) {
  return apiJson(withUser(`/api/auth/switch-child?target_child_id=${targetChildId}`, userId), {
    method: 'POST',
  })
}
