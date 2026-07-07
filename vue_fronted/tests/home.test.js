/** 首页逻辑测试 — 欢迎卡片、快捷操作、profile */
import { describe, it, expect } from 'vitest'

// ── showQuickActions computed ──

describe('showQuickActions — 无用户消息时显示欢迎卡片', () => {
  function computeShowQuickActions(messages) {
    return !messages.some(m => m.role === 'user')
  }

  it('空消息列表 → true（首次加载）', () => {
    expect(computeShowQuickActions([])).toBe(true)
  })

  it('仅有 AI 消息 → true（服务端历史或默认问候）', () => {
    expect(computeShowQuickActions([
      { role: 'ai', text: '你好，我是张宇老师' },
    ])).toBe(true)
  })

  it('有多条 AI 消息但无用户消息 → true', () => {
    expect(computeShowQuickActions([
      { role: 'ai', text: '你好' },
      { role: 'ai', text: '今天想练什么？' },
    ])).toBe(true)
  })

  it('有一条用户消息 → false（已交互）', () => {
    expect(computeShowQuickActions([
      { role: 'ai', text: '你好' },
      { role: 'user', text: '你好' },
    ])).toBe(false)
  })

  it('清空对话后 → true（自动重现）', () => {
    // 模拟：clearGuideChat → messages = []
    expect(computeShowQuickActions([])).toBe(true)
  })
})

// ── 天赋检测 ──

describe('userHasTalent — 从 profile 判断', () => {
  function hasTalent(profileData) {
    if (!profileData) return false
    const pj = profileData.profile_json || {}
    if (pj.talent_display) return true
    if (pj.talent_primary || pj.talent) return true
    if (profileData.talent_primary) return true
    if (pj.onboarding?.self_reported_talent) return true
    return false
  }

  it('profile_json.talent_display 存在 → true', () => {
    expect(hasTalent({ profile_json: { talent_display: '学者' } })).toBe(true)
  })

  it('profile_json.talent_primary 存在 → true', () => {
    expect(hasTalent({ profile_json: { talent_primary: '学者' } })).toBe(true)
  })

  it('onboarding self_reported_talent → true', () => {
    expect(hasTalent({ profile_json: { onboarding: { self_reported_talent: '学者' } } })).toBe(true)
  })

  it('profile 顶层 talent_primary → true', () => {
    expect(hasTalent({ talent_primary: '学者' })).toBe(true)
  })

  it('全新用户 → false', () => {
    expect(hasTalent({ nickname: '学员' })).toBe(false)
  })

  it('profile 为 null → false', () => {
    expect(hasTalent(null)).toBe(false)
  })
})
