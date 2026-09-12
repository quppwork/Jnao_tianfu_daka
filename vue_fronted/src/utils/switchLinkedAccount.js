/**
 * 学生 ↔ 关联家长 账户切换（同绑定关系）
 */
import { prepareRoleLoginEntry } from '@/utils/appSession.js'
import { switchParentAccount, switchStudentAccount } from '@/utils/api/account.js'
import {
  applySwitchChildSession,
  applySwitchParentSession,
} from '@/utils/api/auth.js'
import { getChildUserId, invalidatePageAuthCache } from '@/utils/api/client.js'

const LAST_STUDENT_KEY = 'jnao_last_student_id'

export function rememberLastStudentId(uid) {
  if (!uid) return
  try {
    localStorage.setItem(LAST_STUDENT_KEY, String(uid))
  } catch (_) { /* ignore */ }
}

export function readLastStudentId() {
  try {
    const n = Number(localStorage.getItem(LAST_STUDENT_KEY) || 0)
    return n > 0 ? n : null
  } catch (_) {
    return null
  }
}

/** 学生端：切到关联家长，进入家长版大宇首页 */
export async function goLinkedParentHome() {
  const uid = getChildUserId()
  if (!uid) {
    prepareRoleLoginEntry('parent')
    invalidatePageAuthCache()
    uni.reLaunch({ url: '/pages/login/index?role=parent' })
    return
  }
  try {
    uni.showLoading({ title: '切换中…', mask: true })
    rememberLastStudentId(uid)
    const data = await switchParentAccount(uid)
    applySwitchParentSession(data)
    uni.reLaunch({
      url: '/pages/parent/dayu',
      complete: () => { try { uni.hideLoading() } catch (_) { /* ignore */ } },
    })
  } catch (e) {
    try { uni.hideLoading() } catch (_) { /* ignore */ }
    const msg = e?.message || '切换失败'
    uni.showToast({
      title: e?.status === 403 || /绑定|家长/.test(msg) ? '未绑定家长账户' : msg,
      icon: 'none',
    })
  }
}

/** 家长端：切回训练账户（优先上次学生） */
export async function goLinkedStudentHome() {
  const parentId = getChildUserId()
  if (!parentId) {
    uni.showToast({ title: '请先登录家长账户', icon: 'none' })
    return
  }
  try {
    uni.showLoading({ title: '切换中…', mask: true })
    const target = readLastStudentId()
    const data = await switchStudentAccount(parentId, target || undefined)
    applySwitchChildSession(data)
    uni.reLaunch({
      url: '/pages/dayu/home',
      complete: () => { try { uni.hideLoading() } catch (_) { /* ignore */ } },
    })
  } catch (e) {
    try { uni.hideLoading() } catch (_) { /* ignore */ }
    uni.showToast({ title: e?.message || '暂无可用训练账户', icon: 'none' })
  }
}
