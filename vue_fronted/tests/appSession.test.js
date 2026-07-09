/** appSession.js — 刷新保会话 / 401 分级 单元测试 */
import { describe, it, expect, beforeEach } from 'vitest'
import {
  inferAuthKindFromPath,
  isPublicPath,
  readAuthSnapshot,
  isTransientError,
  isAuthExpiredError,
  shouldLogoutOnError,
  sessionKeysForKind,
  normalizePath,
} from '../src/utils/appSession.js'

describe('normalizePath / inferAuthKindFromPath', () => {
  it('hash 路由去前缀', () => {
    expect(normalizePath('#/pages/admin/index')).toBe('/pages/admin/index')
  })

  it('管理员详情页 → admin', () => {
    expect(inferAuthKindFromPath('/pages/admin/parent-detail')).toBe('admin')
  })

  it('家长中心 → parent', () => {
    expect(inferAuthKindFromPath('/pages/parent/index')).toBe('parent')
  })

  it('学生首页 → student', () => {
    expect(inferAuthKindFromPath('/pages/index')).toBe('student')
    expect(inferAuthKindFromPath('/pages/training/index')).toBe('student')
  })

  it('登录页 → null', () => {
    expect(inferAuthKindFromPath('/pages/login/index')).toBeNull()
    expect(isPublicPath('/pages/login/register-parent')).toBe(true)
  })
})

describe('readAuthSnapshot — 三端 session 槽位互不干扰', () => {
  const store = {}

  function getItem(k) {
    return store[k] ?? null
  }

  beforeEach(() => {
    Object.keys(store).forEach((k) => delete store[k])
  })

  it('学生：child_user_id + token', () => {
    store.jnao_child_user_id = '10'
    store.jnao_session_token = 'stu-tok'
    store.jnao_user = JSON.stringify({ id: 10, role: 'student' })
    store.jnao_logged_in = '1'
    const snap = readAuthSnapshot(getItem)
    expect(snap.student).toEqual({ userId: 10, token: 'stu-tok' })
    expect(snap.parent).toBeNull()
    expect(snap.admin).toBeNull()
  })

  it('家长：jnao_user role=parent + token', () => {
    store.jnao_child_user_id = '20'
    store.jnao_session_token = 'par-tok'
    store.jnao_user = JSON.stringify({ id: 20, role: 'parent' })
    store.jnao_logged_in = '1'
    const snap = readAuthSnapshot(getItem)
    expect(snap.parent).toEqual({ userId: 20, token: 'par-tok' })
    expect(snap.student).toBeNull()
  })

  it('管理员：独立 admin token，不影响学生槽', () => {
    store.jnao_admin_user = JSON.stringify({ id: 1, name: 'admin' })
    store.jnao_admin_token = 'adm-tok'
    store.jnao_child_user_id = '10'
    store.jnao_session_token = 'stu-tok'
    store.jnao_user = JSON.stringify({ id: 10, role: 'student' })
    const snap = readAuthSnapshot(getItem)
    expect(snap.admin).toEqual({ userId: 1, token: 'adm-tok' })
    expect(snap.student).toEqual({ userId: 10, token: 'stu-tok' })
  })

  it('仅有 logged_in 无 token → 各槽为空', () => {
    store.jnao_logged_in = '1'
    store.jnao_user = JSON.stringify({ id: 5, role: 'parent' })
    const snap = readAuthSnapshot(getItem)
    expect(snap.parent).toBeNull()
  })
})

describe('isTransientError / isAuthExpiredError / shouldLogoutOnError', () => {
  it('网络/网关错误视为 transient', () => {
    expect(isTransientError(0)).toBe(true)
    expect(isTransientError(502)).toBe(true)
    expect(isTransientError(503)).toBe(true)
  })

  it('401 为会话失效', () => {
    expect(isAuthExpiredError(401)).toBe(true)
    expect(isAuthExpiredError(403)).toBe(false)
  })

  it('仅 401 应登出；500/0 不应', () => {
    expect(shouldLogoutOnError({ status: 401 })).toBe(true)
    expect(shouldLogoutOnError({ status: 0 })).toBe(false)
    expect(shouldLogoutOnError({ status: 500 })).toBe(false)
    expect(shouldLogoutOnError({ status: 502 })).toBe(false)
  })
})

describe('consumePostLoginRoute — 按角色隔离跳转', () => {
  const store = {}

  beforeEach(() => {
    Object.keys(store).forEach((k) => delete store[k])
    global.sessionStorage = {
      getItem: (k) => store[k] ?? null,
      setItem: (k, v) => { store[k] = v },
      removeItem: (k) => { delete store[k] },
    }
  })

  it('家长登录不恢复管理员上次页面', async () => {
    const { saveRouteSnapshot, consumePostLoginRoute } = await import('../src/utils/appSession.js')
    saveRouteSnapshot('/pages/admin/index')
    saveRouteSnapshot('/pages/parent/children')
    expect(consumePostLoginRoute('/pages/parent/index', 'parent')).toBe('/pages/parent/children')
    expect(consumePostLoginRoute('/pages/parent/index', 'parent')).toBe('/pages/parent/index')
  })

  it('学生登录不恢复家长/管理员页面', async () => {
    const { saveRouteSnapshot, consumePostLoginRoute } = await import('../src/utils/appSession.js')
    saveRouteSnapshot('/pages/admin/index')
    saveRouteSnapshot('/pages/index')
    expect(consumePostLoginRoute('/pages/index', 'student')).toBe('/pages/index')
  })
})
describe('repairAuthStorage / sanitizeAuthForLoginEntry', () => {
  const store = {}

  beforeEach(() => {
    Object.keys(store).forEach((k) => delete store[k])
    global.localStorage = {
      getItem: (k) => store[k] ?? null,
      setItem: (k, v) => { store[k] = v },
      removeItem: (k) => { delete store[k] },
    }
    global.sessionStorage = {
      getItem: () => null,
      setItem: () => {},
      removeItem: () => {},
    }
  })

  it('用户登录页进入时清除管理员残留', async () => {
    const { sanitizeAuthForLoginEntry, readAuthSnapshot } = await import('../src/utils/appSession.js')
    store.jnao_admin_user = JSON.stringify({ id: 1 })
    store.jnao_admin_token = 'adm'
    sanitizeAuthForLoginEntry('/pages/login/index')
    const snap = readAuthSnapshot((k) => store[k])
    expect(snap.admin).toBeNull()
  })

  it('repair 清除 logged_in 但无 token 的脏数据', async () => {
    const { repairAuthStorage } = await import('../src/utils/appSession.js')
    store.jnao_logged_in = '1'
    store.jnao_user = JSON.stringify({ id: 2, role: 'parent' })
    const fixed = repairAuthStorage()
    expect(fixed).toContain('logged_in_without_session')
    expect(store.jnao_logged_in).toBeUndefined()
  })
})

describe('sessionKeysForKind — 清 session 不串槽', () => {
  it('admin 只清 admin 键', () => {
    const keys = sessionKeysForKind('admin')
    expect(keys).toContain('jnao_admin_user')
    expect(keys).toContain('jnao_admin_token')
    expect(keys).not.toContain('jnao_session_token')
  })

  it('parent/student 清用户键但不清 admin', () => {
    const pKeys = sessionKeysForKind('parent')
    expect(pKeys).toContain('jnao_session_token')
    expect(pKeys).not.toContain('jnao_admin_token')
  })
})

describe('prepareRoleLoginEntry — 切到学生登录前清家长 session', () => {
  const store = {}

  beforeEach(() => {
    Object.keys(store).forEach((k) => delete store[k])
    global.localStorage = {
      getItem: (k) => store[k] ?? null,
      setItem: (k, v) => { store[k] = v },
      removeItem: (k) => { delete store[k] },
    }
    global.sessionStorage = {
      getItem: () => null,
      setItem: () => {},
      removeItem: () => {},
    }
  })

  it('清除家长 token 与 jnao_user，避免学生登录后进家长页', async () => {
    const { prepareRoleLoginEntry, readAuthSnapshot } = await import('../src/utils/appSession.js')
    store.jnao_parent_user_id = '9'
    store.jnao_session_token = 'parent-tok'
    store.jnao_user = JSON.stringify({ id: 9, role: 'parent' })
    store.jnao_logged_in = '1'
    store.jnao_child_user_id = '9'

    prepareRoleLoginEntry('student')

    const snap = readAuthSnapshot((k) => store[k] ?? null)
    expect(snap.parent).toBeNull()
    expect(store.jnao_session_token).toBeUndefined()
    expect(store.jnao_user).toBeUndefined()
  })
})
