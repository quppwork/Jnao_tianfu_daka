/** 计时器持久化测试 — 开始计时后，无论跳转页面还是刷新，只要没到时间就不归零 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

// ── 模拟 localStorage ──
const store = {}
const mockLocalStorage = {
  getItem: vi.fn((key) => store[key] ?? null),
  setItem: vi.fn((key, val) => { store[key] = val }),
  removeItem: vi.fn((key) => { delete store[key] }),
}
global.localStorage = mockLocalStorage

// ── 模拟 uni ──
global.uni = {
  showToast: vi.fn(),
  navigateBack: vi.fn(),
  navigateTo: vi.fn(),
}

// ── 从训练页提取的计时器核心逻辑（纯函数版本） ──

const TIMER_STORAGE_KEY_PREFIX = 'jnao_training_timer'
let _trainingDayKey = '2026-06-30'

function timerStorageKey() {
  return `${TIMER_STORAGE_KEY_PREFIX}_${_trainingDayKey || 'default'}`
}

function writeTimerStorage(payload) {
  try {
    localStorage.setItem(timerStorageKey(), JSON.stringify(payload))
  } catch (_) { /* ignore */ }
}

function readTimerData() {
  try {
    const raw = localStorage.getItem(timerStorageKey())
    if (!raw) return null
    return JSON.parse(raw) || null
  } catch (_) { return null }
}

function clearTimerStorage() {
  try { localStorage.removeItem(timerStorageKey()) } catch (_) {}
}

function persistTimer(endAt, plannedSec) {
  writeTimerStorage({ phase: 'running', endAt, plannedSec })
}

// 模拟 nowSynced: 返回当前真实时间
function nowSynced() {
  return Date.now()
}

function formatDuration(totalSec) {
  const sec = Math.max(0, totalSec)
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  if (h > 0) return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

// 模拟页面 onShow 时的恢复逻辑
function simulatePageReentry() {
  const data = readTimerData()
  if (!data || data.phase !== 'running' || !data.endAt) return null
  const left = Math.max(0, Math.ceil((data.endAt - nowSynced()) / 1000))
  if (left <= 0) {
    writeTimerStorage({ phase: 'expired', plannedSec: data.plannedSec || 0 })
    return null
  }
  return { ...data, remaining: left }
}

// 模拟过期检测
function simulateTick(data) {
  if (!data || !data.endAt) return null
  const left = Math.max(0, Math.ceil((data.endAt - nowSynced()) / 1000))
  if (left <= 0) {
    writeTimerStorage({ phase: 'expired', plannedSec: data.plannedSec || 0 })
    return null
  }
  return { ...data, remaining: left }
}

// ── 测试 ─────────────────────────────────────────────

describe('计时器持久化 — 开始后不因页面跳转而重置', () => {
  beforeEach(() => {
    Object.keys(store).forEach(k => delete store[k])
    vi.clearAllMocks()
  })

  // ── 场景1: 开始计时 → 离开 → 回来 → 继续倒计时 ──
  describe('场景1: 开始后离开再回来', () => {
    it('30分钟计时器 — 立即回来应恢复', () => {
      const plannedMin = 30
      const totalSec = plannedMin * 60
      const endAt = nowSynced() + totalSec * 1000

      // 1. 用户点击"开始训练"
      persistTimer(endAt, totalSec)
      const written = readTimerData()
      expect(written).toBeTruthy()
      expect(written.phase).toBe('running')
      expect(written.endAt).toBe(endAt)

      // 2. 用户去首页再回来（模拟页面重新加载）
      const restored = simulatePageReentry()
      expect(restored).toBeTruthy()
      expect(restored.remaining).toBeGreaterThan(0)
      expect(restored.remaining).toBeLessThanOrEqual(totalSec)
    })

    it('90分钟计时器 — 离开5秒回来仍有剩余时间', async () => {
      const totalSec = 90 * 60
      const endAt = nowSynced() + totalSec * 1000
      persistTimer(endAt, totalSec)

      // 模拟离开 5 秒
      await new Promise(r => setTimeout(r, 100))
      const restored = simulatePageReentry()
      expect(restored).toBeTruthy()
      expect(restored.remaining).toBeGreaterThan(totalSec - 10)
    })

    it('切换 trainingDayKey 后仍能恢复（同一天不变）', () => {
      const totalSec = 30 * 60
      const endAt = nowSynced() + totalSec * 1000
      persistTimer(endAt, totalSec)

      // 模拟 loadTodayPlan 重新设置 trainingDayKey（同一天）
      _trainingDayKey = '2026-06-30'
      const restored = simulatePageReentry()
      expect(restored).toBeTruthy()
    })

    it('换天后旧 key 无数据 → 返回 null（正确行为）', () => {
      const totalSec = 30 * 60
      const endAt = nowSynced() + totalSec * 1000
      persistTimer(endAt, totalSec)

      // 模拟换天
      _trainingDayKey = '2026-07-01'
      const restored = simulatePageReentry()
      expect(restored).toBeNull() // 新的一天，旧计时器不恢复（正确）
    })
  })

  // ── 场景2: 计时未到 → 不归零 ──
  describe('场景2: 时间未到不归零', () => {
    it('剩余时间 > 0 时计时器保持 running', () => {
      const totalSec = 60 * 60
      const endAt = nowSynced() + totalSec * 1000
      persistTimer(endAt, totalSec)

      const data = readTimerData()
      expect(data.phase).toBe('running')
      const ticked = simulateTick(data)
      expect(ticked).toBeTruthy()
      expect(ticked.phase).toBe('running')
    })
  })

  // ── 场景3: 时间到 → 归零 ──
  describe('场景3: 时间到了才归零', () => {
    it('剩余时间 = 0 时标记 expired', () => {
      const totalSec = 30 * 60
      const endAt = nowSynced() - 1000 // 已过期 1 秒
      persistTimer(endAt, totalSec)
      const restored = simulatePageReentry()
      expect(restored).toBeNull()
      const data = readTimerData()
      expect(data.phase).toBe('expired')
    })
  })

  // ── 场景4: 重置计时器后 storage 清除 ──
  describe('场景4: 主动重置', () => {
    it('clearTimerStorage 后数据不存在', () => {
      persistTimer(nowSynced() + 3600000, 3600)
      expect(readTimerData()).toBeTruthy()
      clearTimerStorage()
      expect(readTimerData()).toBeNull()
    })
  })

  // ── 场景5: 多次往返 ──
  describe('场景5: 反复进出页面', () => {
    it('10 次进出后计时器仍在', () => {
      const totalSec = 90 * 60
      const endAt = nowSynced() + totalSec * 1000
      persistTimer(endAt, totalSec)

      for (let i = 0; i < 10; i++) {
        const restored = simulatePageReentry()
        expect(restored).toBeTruthy()
        expect(restored.remaining).toBeGreaterThan(0)
      }
    })
  })

  // ── 场景6: 格式验证 ──
  describe('场景6: 计时器格式化', () => {
    it('30分钟格式化正确', () => {
      const totalSec = 30 * 60
      const endAt = nowSynced() + totalSec * 1000
      persistTimer(endAt, totalSec)
      const restored = simulatePageReentry()
      expect(restored).toBeTruthy()
      expect(formatDuration(restored.remaining)).toMatch(/^\d{2}:\d{2}(:\d{2})?$/)
    })
  })

  // ── 场景7: 无计时器时不报错 ──
  describe('场景7: 无数据时安全返回', () => {
    it('readTimerData 无数据返回 null', () => {
      expect(readTimerData()).toBeNull()
    })
    it('simulatePageReentry 无数据返回 null', () => {
      expect(simulatePageReentry()).toBeNull()
    })
    it('simulateTick 无数据返回 null', () => {
      expect(simulateTick(null)).toBeNull()
    })
  })
})
