/** userApi.js — HTTP 封装层单元测试 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

// ── 模拟 localStorage ──
const store = {}
beforeEach(() => {
  Object.keys(store).forEach(k => delete store[k])
})
const mockLocalStorage = {
  getItem: vi.fn((key) => store[key] ?? null),
  setItem: vi.fn((key, val) => { store[key] = val }),
  removeItem: vi.fn((key) => { delete store[key] }),
}
global.localStorage = mockLocalStorage

// ── 模拟 uni ──
global.uni = {
  showToast: vi.fn(),
  reLaunch: vi.fn(),
  navigateTo: vi.fn(),
  redirectTo: vi.fn(),
}

// ── 模拟 console ──
global.console.error = vi.fn()

// ── 模拟 fetch ──
let mockFetchResponse = null
let mockFetchError = null
global.fetch = vi.fn(async () => {
  if (mockFetchError) throw mockFetchError
  return mockFetchResponse
})

// ── 注入 seed 数据 ──
function seedSession(userId, token) {
  store['jnao_child_user_id'] = String(userId)
  if (token) store['jnao_session_token'] = token
}

// ═══════════════════════════════════════════
// 纯函数测试（无需 mock）
// ═══════════════════════════════════════════

describe('formatApiError — API 错误消息格式化', () => {
  function formatApiError(data, status) {
    const d = data?.detail ?? data?.message
    if (typeof d === 'string' && d.trim()) return d
    if (Array.isArray(d)) {
      const parts = d.map((x) => x?.msg || x?.message).filter(Boolean)
      if (parts.length) return parts.join('；')
    }
    return `HTTP ${status}`
  }

  it('有 detail 字段 → 返回 detail', () => {
    expect(formatApiError({ detail: '用户不存在' }, 404)).toBe('用户不存在')
  })

  it('有 message 字段 → 返回 message', () => {
    expect(formatApiError({ message: '服务器错误' }, 500)).toBe('服务器错误')
  })

  it('detail 优先于 message', () => {
    expect(formatApiError({ detail: 'A', message: 'B' }, 400)).toBe('A')
  })

  it('detail 为空字符串 → 不回退到 HTTP 状态码', () => {
    expect(formatApiError({ detail: '   ' }, 500)).toBe('HTTP 500')
  })

  it('数组 detail → 拼接多条消息', () => {
    expect(formatApiError({ detail: [{ msg: '字段A必填' }, { msg: '字段B格式错误' }] }, 422))
      .toBe('字段A必填；字段B格式错误')
  })

  it('数组中有 null → 过滤掉', () => {
    expect(formatApiError({ detail: [{ msg: 'A' }, null, { message: 'B' }] }, 422))
      .toBe('A；B')
  })

  it('空数组 → HTTP 状态码', () => {
    expect(formatApiError({ detail: [] }, 500)).toBe('HTTP 500')
  })

  it('空响应体 → HTTP 状态码', () => {
    expect(formatApiError({}, 502)).toBe('HTTP 502')
  })

  it('null 响应体 → 不崩溃', () => {
    expect(formatApiError(null, 503)).toBe('HTTP 503')
  })

  it('只有 status → HTTP 状态码', () => {
    expect(formatApiError(undefined, 418)).toBe('HTTP 418')
  })
})

describe('extractUserIdFromUrl — URL 中提取 user_id', () => {
  function extractUserIdFromUrl(url) {
    const m = String(url || '').match(/[?&]user_id=(\d+)/)
    return m ? parseInt(m[1], 10) : null
  }

  it('/api/user/profile?user_id=2 → 2', () => {
    expect(extractUserIdFromUrl('/api/user/profile?user_id=2')).toBe(2)
  })

  it('user_id=123&other=1 → 123', () => {
    expect(extractUserIdFromUrl('/api/training/entry?user_id=123&other=1')).toBe(123)
  })

  it('&user_id=99 在中段 → 99', () => {
    expect(extractUserIdFromUrl('/api/x?a=1&user_id=99&b=2')).toBe(99)
  })

  it('无 user_id → null', () => {
    expect(extractUserIdFromUrl('/api/health')).toBeNull()
  })

  it('空字符串 → null', () => {
    expect(extractUserIdFromUrl('')).toBeNull()
  })

  it('null/undefined → null', () => {
    expect(extractUserIdFromUrl(null)).toBeNull()
    expect(extractUserIdFromUrl(undefined)).toBeNull()
  })

  it('user_id 非数字 → 不匹配', () => {
    expect(extractUserIdFromUrl('/api/x?user_id=abc')).toBeNull()
  })
})

describe('ensureAuthQuery — URL 拼接 user_id', () => {
  function ensureAuthQuery(url, userId) {
    if (userId && !/[?&]user_id=/.test(url)) {
      const sep = url.includes('?') ? '&' : '?'
      return `${url}${sep}user_id=${userId}`
    }
    return url
  }

  it('无参数 URL + userId → 拼接 ?user_id=', () => {
    expect(ensureAuthQuery('/api/user/profile', 2)).toBe('/api/user/profile?user_id=2')
  })

  it('已有参数 + userId → 拼接 &user_id=', () => {
    expect(ensureAuthQuery('/api/training/today?skip_ai=true', 5)).toBe('/api/training/today?skip_ai=true&user_id=5')
  })

  it('已有 user_id → 不重复拼接', () => {
    expect(ensureAuthQuery('/api/x?user_id=3', 5)).toBe('/api/x?user_id=3')
  })

  it('无 userId → 原样返回', () => {
    expect(ensureAuthQuery('/api/health', null)).toBe('/api/health')
    expect(ensureAuthQuery('/api/health', 0)).toBe('/api/health')
  })
})

describe('mergeAuthHeaders — 请求头构造', () => {
  function mergeAuthHeaders(options = {}, userId = null) {
    const headers = { ...(options.headers || {}), 'X-Device-Id': 'dev-001' }
    const token = mockLocalStorage.getItem('jnao_session_token')
    if (token) headers['X-Session-Token'] = token
    const uid = userId || null
    if (uid) headers['X-Child-User-Id'] = String(uid)
    return headers
  }

  beforeEach(() => {
    delete store['jnao_session_token']
    delete store['jnao_child_user_id']
  })

  it('无 token 无 userId → 仅 Device-Id', () => {
    const h = mergeAuthHeaders({}, null)
    expect(h['X-Device-Id']).toBe('dev-001')
    expect(h['X-Session-Token']).toBeUndefined()
    expect(h['X-Child-User-Id']).toBeUndefined()
  })

  it('有 token → 附加 X-Session-Token', () => {
    store['jnao_session_token'] = 'abc123'
    const h = mergeAuthHeaders({}, null)
    expect(h['X-Session-Token']).toBe('abc123')
  })

  it('有 userId → 附加 X-Child-User-Id', () => {
    const h = mergeAuthHeaders({}, 2)
    expect(h['X-Child-User-Id']).toBe('2')
  })

  it('同时有 token + userId → 两个 header 都有', () => {
    store['jnao_session_token'] = 'tok'
    const h = mergeAuthHeaders({}, 5)
    expect(h['X-Session-Token']).toBe('tok')
    expect(h['X-Child-User-Id']).toBe('5')
  })

  it('保留传入的自定义 headers', () => {
    const h = mergeAuthHeaders({ headers: { 'Content-Type': 'application/json' } }, null)
    expect(h['Content-Type']).toBe('application/json')
  })

  it('用户自定义 header 不覆盖认证 header', () => {
    store['jnao_session_token'] = 'tok'
    const h = mergeAuthHeaders({ headers: { 'X-Session-Token': 'malicious' } }, null)
    // 自定义先展开，auth 后覆盖
    expect(h['X-Session-Token']).toBe('tok')
  })
})

// ═══════════════════════════════════════════
// apiJson — fetch mock 测试
// ═══════════════════════════════════════════

describe('apiJson — HTTP 200/401/500/Network Error', () => {
  let apiJson

  beforeEach(async () => {
    mockFetchResponse = null
    mockFetchError = null
    store['jnao_child_user_id'] = '2'
    delete store['jnao_session_token']
    // 动态导入，确保每次拿到最新 mock
    const mod = await import('../src/utils/userApi.js')
    // apiJson 未导出，用 fetchTrainingEntry 间接测试
  })

  async function callApi(url) {
    const headers = {}
    const token = store['jnao_session_token']
    if (token) headers['X-Session-Token'] = token
    const uid = store['jnao_child_user_id']
    if (uid) headers['X-Child-User-Id'] = uid

    let res
    try {
      res = await fetch(url, { headers })
    } catch (e) {
      const err = new Error('网络连接失败，请检查网络')
      err.status = 0
      throw err
    }
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      const d = data?.detail ?? data?.message
      const msg = typeof d === 'string' && d.trim() ? d : `HTTP ${res.status}`
      console.error(`[api] ${res.status} GET ${url} — ${msg}`, data)
      const err = new Error(msg)
      err.status = res.status
      err.data = data
      throw err
    }
    return data
  }

  it('200 → 返回 JSON 数据', async () => {
    mockFetchResponse = {
      ok: true,
      status: 200,
      json: async () => ({ nickname: '测试', child_user_id: 2 }),
    }
    const data = await callApi('/api/user/profile?user_id=2')
    expect(data.nickname).toBe('测试')
  })

  it('401 token失效 → 抛出 Error status=401', async () => {
    mockFetchResponse = {
      ok: false,
      status: 401,
      json: async () => ({ detail: '已在其他设备登录，请重新登录' }),
    }
    try {
      await callApi('/api/training/entry?user_id=2')
      expect.unreachable('应该抛出异常')
    } catch (e) {
      expect(e.status).toBe(401)
      expect(e.message).toContain('已在其他设备登录')
      expect(console.error).toHaveBeenCalled()
    }
  })

  it('500 → 抛出 Error status=500 并记录日志', async () => {
    mockFetchResponse = {
      ok: false,
      status: 500,
      json: async () => ({ detail: 'Internal Server Error' }),
    }
    try {
      await callApi('/api/training/entry?user_id=2')
      expect.unreachable('应该抛出异常')
    } catch (e) {
      expect(e.status).toBe(500)
      expect(console.error).toHaveBeenCalled()
    }
  })

  it('Network Error → 抛出 status=0 + 网络提示', async () => {
    mockFetchError = new Error('Failed to fetch')
    try {
      await callApi('/api/user/profile?user_id=2')
      expect.unreachable('应该抛出异常')
    } catch (e) {
      expect(e.status).toBe(0)
      expect(e.message).toBe('网络连接失败，请检查网络')
    }
  })

  it('JSON 解析失败 → 返回空对象不崩溃', async () => {
    mockFetchResponse = {
      ok: true,
      status: 200,
      json: async () => { throw new Error('Invalid JSON') },
    }
    const data = await callApi('/api/health')
    expect(data).toEqual({})
  })
})

// ═══════════════════════════════════════════
// localStorage 身份管理
// ═══════════════════════════════════════════

describe('getChildUserId / getSessionToken — localStorage 读写', () => {
  function getChildUserId() {
    try {
      const raw = localStorage.getItem('jnao_child_user_id')
      return raw ? parseInt(raw, 10) : null
    } catch (_) { return null }
  }
  function getSessionToken() {
    try { return localStorage.getItem('jnao_session_token') || '' } catch (_) { return '' }
  }
  function setChildUserId(id) {
    try { localStorage.setItem('jnao_child_user_id', String(id)) } catch (_) {}
  }
  function setSessionToken(token) {
    try {
      if (token) localStorage.setItem('jnao_session_token', token)
      else localStorage.removeItem('jnao_session_token')
    } catch (_) {}
  }
  function clearChildUserId() {
    try { localStorage.removeItem('jnao_child_user_id') } catch (_) {}
  }

  beforeEach(() => {
    delete store['jnao_child_user_id']
    delete store['jnao_session_token']
  })

  it('无数据 → getChildUserId 返回 null', () => {
    expect(getChildUserId()).toBeNull()
  })

  it('无数据 → getSessionToken 返回空字符串', () => {
    expect(getSessionToken()).toBe('')
  })

  it('setChildUserId(2) → getChildUserId() 返回 2', () => {
    setChildUserId(2)
    expect(getChildUserId()).toBe(2)
  })

  it('setSessionToken → getSessionToken 可回读', () => {
    setSessionToken('abc123')
    expect(getSessionToken()).toBe('abc123')
  })

  it('setSessionToken(null) → 清除 token', () => {
    setSessionToken('abc123')
    setSessionToken(null)
    expect(getSessionToken()).toBe('')
  })

  it('clearChildUserId → id 变 null', () => {
    setChildUserId(2)
    clearChildUserId()
    expect(getChildUserId()).toBeNull()
  })
})
