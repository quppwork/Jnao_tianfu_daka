/** requirePageAuth — 刷新保登录集成测试 */
import { describe, it, expect, beforeEach, vi } from 'vitest'

const store = {}
beforeEach(() => {
  Object.keys(store).forEach((k) => delete store[k])
  vi.resetModules()
  global.fetch.mockClear()
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

function seedStudent(id = 2, token = 'tok-stu') {
  store.jnao_child_user_id = String(id)
  store.jnao_session_token = token
  store.jnao_user = JSON.stringify({ id, role: 'student' })
  store.jnao_logged_in = '1'
}

function seedAdmin(id = 1, token = 'tok-adm') {
  store.jnao_admin_user = JSON.stringify({ id, name: 'admin' })
  store.jnao_admin_token = token
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

describe('requirePageAuth', () => {
  it('有效 token 刷新后校验通过', async () => {
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
    expect(store.jnao_session_token).toBe('tok-stu')
    expect(global.uni.reLaunch).not.toHaveBeenCalled()
  })

  it('401 才清除 session 并跳转登录', async () => {
    seedStudent()
    mock401()
    const { requirePageAuth } = await import('../src/utils/userApi.js')
    const r = await requirePageAuth('student')
    expect(r.ok).toBe(false)
    expect(store.jnao_session_token).toBeUndefined()
    expect(global.uni.reLaunch).toHaveBeenCalled()
  })

  it('家长 session 误入学生页 → 跳转家长中心', async () => {
    store.jnao_child_user_id = '20'
    store.jnao_session_token = 'par-tok'
    store.jnao_user = JSON.stringify({ id: 20, role: 'parent' })
    store.jnao_logged_in = '1'
    const { requirePageAuth } = await import('../src/utils/userApi.js')
    const r = await requirePageAuth('student')
    expect(r.ok).toBe(false)
    expect(r.reason).toBe('wrong_role')
    expect(store.jnao_session_token).toBe('par-tok')
    expect(global.uni.reLaunch).toHaveBeenCalledWith({ url: '/pages/parent/index' })
    expect(global.fetch).not.toHaveBeenCalled()
  })

  it('管理员 401 不清学生 token', async () => {
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
    expect(store.jnao_admin_token).toBeUndefined()
    expect(store.jnao_session_token).toBe('tok-stu')
  })
})

describe('resolveQaImageUrl — session_token', () => {
  beforeEach(() => {
    Object.keys(store).forEach((k) => delete store[k])
    vi.resetModules()
  })

  it('图片 URL 附带 session_token', async () => {
    store.jnao_session_token = 'img-tok'
    const { resolveQaImageUrl } = await import('../src/utils/userApi.js')
    const url = resolveQaImageUrl('/api/qa/images/abc123', 5)
    expect(url).toContain('user_id=5')
    expect(url).toContain('session_token=img-tok')
  })
})

describe('mergeAuthHeaders — admin 隔离', () => {
  beforeEach(() => {
    Object.keys(store).forEach((k) => delete store[k])
  })

  it('admin API 使用 admin token 而非 student token', async () => {
    store.jnao_session_token = 'stu-tok'
    store.jnao_admin_token = 'adm-tok'
    store.jnao_admin_user = JSON.stringify({ id: 1 })
    const { fetchAdminParents, getAdminUserId } = await import('../src/utils/userApi.js')
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ parents: [] }),
    })
    await fetchAdminParents(getAdminUserId())
    const headers = global.fetch.mock.calls[0][1].headers
    expect(headers['X-Session-Token']).toBe('adm-tok')
  })
})
