/**
 * 家长端：孩子 CRUD；家长/学生身份入口
 *
 * 身份约定：
 * - ensureParentUser / getParentUserId → 家长中心
 * - ensureChildUser（= ensureStudentUser）→ 学生业务页（训练/引导/答疑…）
 * 后端手机号「谁是正规家长」见 parent_identity_service + parent_reconcile_service
 */
import {
  apiJson,
  withUser,
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
 * 家长页入口：校验 parent session，返回家长 userId
 */
export async function ensureParentUser() {
  const auth = await requirePageAuth('parent')
  if (!auth.ok) throw new NeedLoginError('请先登录家长账号')
  return auth.userId
}

/**
 * 学生业务页入口（训练/首页引导/答疑/成长…）
 * 无有效学生 session 时跳转登录；家长 session 会踢到家长中心
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

/** 与 ensureChildUser 同义，语义更清晰 */
export const ensureStudentUser = ensureChildUser

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
