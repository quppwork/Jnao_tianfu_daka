/**
 * 管理员 API（session 读写在 client.js）
 */
import { clearSessionsExcept } from '../appSession.js'
import {
  apiJson,
  withAdmin,
  markFreshLogin,
  invalidatePageAuthCache,
  invalidateChildUserSession,
  persistAdminLocalSession,
  resetSessionExpiryGuard,
} from './client.js'

// ── 管理员 ──

export async function loginAdmin(loginName, password) {
  clearSessionsExcept('admin')
  invalidatePageAuthCache('parent')
  invalidatePageAuthCache('student')
  invalidateChildUserSession()
  const data = await apiJson('/api/admin/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ login_name: loginName, password }),
  })
  persistAdminLocalSession(data)
  resetSessionExpiryGuard()
  markFreshLogin()
  return data
}

export async function fetchAdminParents(adminId, q = '') {
  const qs = q ? `?q=${encodeURIComponent(q)}` : ''
  const data = await apiJson(withAdmin(`/api/admin/parents${qs}`, adminId))
  return data.parents || []
}

export async function fetchAdminRemovedParents(adminId, q = '') {
  const qs = q ? `?q=${encodeURIComponent(q)}` : ''
  const data = await apiJson(withAdmin(`/api/admin/parents/removed${qs}`, adminId))
  return data.parents || []
}

export async function createAdminParent(adminId, body) {
  return apiJson(withAdmin('/api/admin/parents', adminId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function restoreAdminParent(adminId, parentId) {
  return apiJson(withAdmin(`/api/admin/parents/${parentId}/restore`, adminId), {
    method: 'POST',
  })
}

export async function restoreAdminParentByPhone(adminId, { phone, nickname } = {}) {
  return apiJson(withAdmin('/api/admin/parents/restore-by-phone', adminId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone, nickname }),
  })
}

export async function restoreAdminChild(adminId, childId) {
  return apiJson(withAdmin(`/api/admin/children/${childId}/restore`, adminId), {
    method: 'POST',
  })
}

export async function updateAdminParent(adminId, parentId, body) {
  return apiJson(withAdmin(`/api/admin/parents/${parentId}`, adminId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function deleteAdminParent(adminId, parentId) {
  return apiJson(withAdmin(`/api/admin/parents/${parentId}`, adminId), { method: 'DELETE' })
}

export async function fetchAdminChildren(adminId, { parentId = null, q = '' } = {}) {
  const params = []
  if (parentId) params.push(`parent_id=${parentId}`)
  if (q) params.push(`q=${encodeURIComponent(q)}`)
  const qs = params.length ? `?${params.join('&')}` : ''
  const data = await apiJson(withAdmin(`/api/admin/children${qs}`, adminId))
  return data.children || []
}

export async function createAdminChild(adminId, body) {
  return apiJson(withAdmin('/api/admin/children', adminId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function updateAdminChild(adminId, childId, body) {
  return apiJson(withAdmin(`/api/admin/children/${childId}`, adminId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function deleteAdminChild(adminId, childId) {
  return apiJson(withAdmin(`/api/admin/children/${childId}`, adminId), { method: 'DELETE' })
}

export async function bindAdminChild(adminId, childId, parentId) {
  return apiJson(withAdmin(`/api/admin/children/${childId}/bind`, adminId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ parent_id: parentId }),
  })
}

export async function unbindAdminChild(adminId, childId) {
  return apiJson(withAdmin(`/api/admin/children/${childId}/bind`, adminId), { method: 'DELETE' })
}

export async function fetchAdminBlacklist(adminId) {
  return apiJson(withAdmin('/api/admin/blacklist', adminId))
}

export async function removeAdminBlacklist(adminId, kind, value) {
  const enc = encodeURIComponent(value)
  return apiJson(withAdmin(`/api/admin/blacklist/${kind}/${enc}`, adminId), { method: 'DELETE' })
}

export async function fetchAdminSettings(adminId) {
  return apiJson(withAdmin('/api/admin/settings', adminId))
}

export async function updateAdminSettings(adminId, body) {
  return apiJson(withAdmin('/api/admin/settings', adminId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function fetchAdminParentDetail(adminId, parentId) {
  return apiJson(withAdmin(`/api/admin/parents/${parentId}/detail`, adminId))
}

export async function reconcileAdminParent(adminId, parentId) {
  return apiJson(withAdmin(`/api/admin/parents/${parentId}/reconcile`, adminId), {
    method: 'POST',
  })
}

export async function fetchAdminChildDetail(adminId, childId) {
  return apiJson(withAdmin(`/api/admin/children/${childId}/detail`, adminId))
}

export async function fetchChildTalentQuota(adminId, childId) {
  return apiJson(withAdmin(`/api/admin/children/${childId}/talent-quota`, adminId))
}

export async function updateChildTalentQuota(adminId, childId, add) {
  return apiJson(withAdmin(`/api/admin/children/${childId}/talent-quota`, adminId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ add }),
  })
}

export async function batchUpdateTalentQuota(adminId, { childIds, add } = {}) {
  return apiJson(withAdmin('/api/admin/children/talent-quota/batch', adminId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ child_ids: childIds, add }),
  })
}

export async function fetchAdminChildAssessments(adminId, childId) {
  return apiJson(withAdmin(`/api/admin/children/${childId}/talent-assessments`, adminId))
}

