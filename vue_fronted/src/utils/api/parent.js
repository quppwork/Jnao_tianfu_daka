/**
 * 家长端：孩子 CRUD / ensureChildUser
 */
import {
  apiJson,
  withUser,
  getChildUserId,
  setChildUserId,
  markChildUserSessionValid,
  invalidateChildUserSession,
  requirePageAuth,
  NeedLoginError,
} from './client.js'
import { _readStoredRole } from './auth.js'

// ── 家长端 ──

export async function fetchParentChildren(parentId) {
  const data = await apiJson(withUser('/api/parent/children', parentId))
  return data.children || []
}

export async function fetchParentQuota(parentId) {
  return apiJson(withUser('/api/parent/quota', parentId))
}

export async function createParentChild(parentId, { loginName, nickname, password, grade, age }) {
  return apiJson(withUser('/api/parent/children', parentId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      login_name: loginName,
      nickname,
      password,
      grade: grade || null,
      age: age || null,
    }),
  })
}

export async function updateParentChild(parentId, childId, { nickname, password, grade, age } = {}) {
  const body = {}
  if (nickname != null) body.nickname = nickname
  if (password != null) body.password = password
  if (grade != null) body.grade = grade
  if (age != null) body.age = age
  return apiJson(withUser(`/api/parent/children/${childId}`, parentId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function deleteParentChild(parentId, childId) {
  return apiJson(withUser(`/api/parent/children/${childId}`, parentId), {
    method: 'DELETE',
  })
}

/**
 * 全局用户入口 — 学生页 onMounted 调用
 * 无有效学生 session 时跳转登录，不再自动 guest 注册
 */
export async function ensureChildUser(nickname = '学员') {
  const role = _readStoredRole()
  if (role === 'parent') {
    try { uni.reLaunch({ url: '/pages/parent/index' }) } catch (e) { /* ignore */ }
    throw new NeedLoginError('请使用学生账号登录')
  }

  const auth = await requirePageAuth('student')
  if (!auth.ok) throw new NeedLoginError()
  return auth.userId
}

/** JNAO 外部 API 用的 uid（存于 child_user.jnao_uid） */
export async function ensureJnaoUid(userId) {
  const profile = await apiJson(withUser('/api/user/profile', userId))
  if (profile.jnao_uid) return parseInt(profile.jnao_uid, 10)
  const jnaoUid = userId * 1000 + (Date.now() % 1000)
  await apiJson(withUser('/api/user/profile', userId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jnao_uid: String(jnaoUid) }),
  })
  return jnaoUid
}

