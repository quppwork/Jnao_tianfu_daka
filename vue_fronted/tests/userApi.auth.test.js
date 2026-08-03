/** requirePageAuth — Cookie 会话模式集成测试 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { resolveParentAuthTarget } from '../src/utils/userApi.js'

const store = {}
beforeEach(() => {
  Object.keys(store).forEach((k) => delete store[k])
  vi.resetModules()
  global.fetch.mockClear()
  global.uni.reLaunch.mockClear()
})

global.localStorage = {
  getItem: vi.fn((k) => store[k] ?? null),
  setItem: vi.fn((k, v) => { store[k] = v }),
  removeItem: vi.fn((k) => { delete store[k] }),
}

global.sessionStorage = {
  getItem: vi.fn(() => null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
}

global.uni = {
  reLaunch: vi.fn(),
  redirectTo: vi.fn(),
}

global.fetch = vi.fn()
global.console.error = vi.fn()

function seedStudent(id = 2) {
  store.jnao_child_user_id = String(id)
  store.jnao_student_user_id = String(id)
  store.jnao_user = JSON.stringify({ id, role: 'student' })
  store.jnao_logged_in = '1'
}

function seedAdmin(id = 1) {
  store.jnao_admin_user = JSON.stringify({ id, name: 'admin' })
  store.jnao_admin_logged_in = '1'
}

function mockOk() {
  global.fetch.mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({}),
  })
}

function mock401() {
  global.fetch.mockResolvedValue({
    ok: false,
    status: 401,
    json: async () => ({ detail: '会话失效' }),
  })
}

function mockNetworkFail() {
  global.fetch.mockRejectedValue(new Error('Failed to fetch'))
}

describe('resolveParentAuthTarget', () => {
  it('bind-phone 返回 __bind_phone__', () => {
    expect(resolveParentAuthTarget({ role: 'parent', next_step: 'bind-phone' })).toBe('__bind_phone__')
  })

  it('账户就绪时进家长中心', () => {
    expect(resolveParentAuthTarget({ role: 'parent', account_ready: true, profile_complete: true }))
      .toBe('/pages/parent/index')
  })
})

describe('requirePageAuth', () => {
  it('有效会话刷新后校验通过', async () => {
    seedStudent()
    mockOk()
    const { requirePageAuth } = await import('../src/utils/userApi.js')
    const r = await requirePageAuth('student')
    expect(r.ok).toBe(true)
    expect(r.userId).toBe(2)
    expect(global.uni.reLaunch).not.toHaveBeenCalled()
  })

  it('502 网络异常不登出，允许离线继续', async () => {
    seedStudent()
    mockNetworkFail()
    const { requirePageAuth } = await import('../src/utils/userApi.js')
    const r = await requirePageAuth('student')
    expect(r.ok).toBe(true)
    expect(r.offline).toBe(true)
    expect(store.jnao_logged_in).toBe('1')
    expect(global.uni.reLaunch).not.toHaveBeenCalled()
  })

  it('401 才清除 session 并跳转登录', async () => {
    seedStudent()
    // 先 profile 401，后续 logout 请求放行（redirect 在 logout finally 里异步触发）
    global.fetch
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: '会话失效' }),
      })
      .mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({}),
      })
    const { requirePageAuth } = await import('../src/utils/userApi.js')
    const r = await requirePageAuth('student')
    expect(r.ok).toBe(false)
    expect(r.reason).toBe('expired')
    expect(store.jnao_logged_in).toBeUndefined()
    await vi.waitFor(() => {
      expect(global.uni.reLaunch).toHaveBeenCalled()
    })
  })
  it('家长 session 误入学生页 → 引导学生登录入口', async () => {
    store.jnao_child_user_id = '20'
    store.jnao_parent_user_id = '20'
    store.jnao_user = JSON.stringify({ id: 20, role: 'parent' })
    store.jnao_logged_in = '1'
    const { requirePageAuth } = await import('../src/utils/userApi.js')
    const r = await requirePageAuth('student')
    expect(r.ok).toBe(false)
    expect(r.reason).toBe('wrong_role')
    expect(global.uni.reLaunch).toHaveBeenCalledWith({ url: '/pages/login/index?role=student' })
    expect(global.fetch).not.toHaveBeenCalled()
  })

  it('管理员 401 不清学生登录态', async () => {
    seedStudent()
    seedAdmin()
    global.fetch.mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: '管理员会话失效' }),
    })
    const { requirePageAuth } = await import('../src/utils/userApi.js')
    const r = await requirePageAuth('admin')
    expect(r.ok).toBe(false)
    expect(store.jnao_admin_logged_in).toBeUndefined()
    expect(store.jnao_logged_in).toBe('1')
  })
})

describe('resolveQaImageUrl — Cookie 鉴权', () => {
  beforeEach(() => {
    Object.keys(store).forEach((k) => delete store[k])
    vi.resetModules()
  })

  it('图片 URL 附带 user_id（session 走 Cookie）', async () => {
    const { resolveQaImageUrl } = await import('../src/utils/userApi.js')
    const url = resolveQaImageUrl('/api/qa/images/abc123', 5)
    expect(url).toContain('user_id=5')
    expect(url).not.toContain('session_token=')
  })
})

describe('mergeAuthHeaders — admin 隔离', () => {
  beforeEach(() => {
    Object.keys(store).forEach((k) => delete store[k])
    vi.resetModules()
    global.fetch.mockClear()
  })

  it('admin API 使用 admin userId 请求头', async () => {
    store.jnao_child_user_id = '9'
    store.jnao_admin_user = JSON.stringify({ id: 1 })
    store.jnao_admin_logged_in = '1'
    const { fetchAdminParents, getAdminUserId } = await import('../src/utils/userApi.js')
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ parents: [] }),
    })
    await fetchAdminParents(getAdminUserId())
    const headers = global.fetch.mock.calls[0][1].headers
    expect(headers['X-Child-User-Id']).toBe('1')
    expect(headers['X-Session-Token']).toBeUndefined()
  })
})
