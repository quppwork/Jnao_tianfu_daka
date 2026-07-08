/** requirePageAuth — 刷新保登录集成测试 */
import { describe, it, expect, beforeEach, vi } from 'vitest'

const store = {}
beforeEach(() => {
  Object.keys(store).forEach((k) => delete store[k])
  vi.resetModules()
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
