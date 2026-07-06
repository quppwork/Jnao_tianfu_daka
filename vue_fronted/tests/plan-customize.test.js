import { describe, it, expect } from 'vitest'

// 从 training/index.vue 提取的方案编辑纯逻辑

function parseItemInstructions(raw) {
  if (!raw) return {}
  try {
    return typeof raw === 'string' ? JSON.parse(raw) : raw
  } catch {
    return {}
  }
}

function filterEditableItems(items) {
  return (items || []).filter(i => i.checkin_status !== 'done').filter(i => {
    const inst = parseItemInstructions(i.instructions)
    return inst.item_type !== 'elective' && inst.blocks_next !== false
  })
}

function buildCustomizePayload(editableItems, editorSkills) {
  const skills = editorSkills.map(s => s.split(':')[1])
  return { skills }
}

describe('方案编辑 — 可见性', () => {
  function canShowCustomize(plan) {
    return !!plan?.can_customize_plan
  }

  it('未打卡且未编辑时可显示', () => {
    expect(canShowCustomize({ can_customize_plan: true })).toBe(true)
  })

  it('已编辑后不可显示', () => {
    expect(canShowCustomize({ can_customize_plan: false, plan_customized: true })).toBe(false)
  })

  it('已有打卡后不可显示', () => {
    expect(canShowCustomize({ can_customize_plan: false, has_checkin: true })).toBe(false)
  })
})

describe('方案编辑 — editableItems 过滤', () => {
  const items = [
    { id: 1, checkin_status: 'done', instructions: JSON.stringify({ skill: '超脑阅读', item_type: 'required' }) },
    { id: 2, checkin_status: 'pending', instructions: JSON.stringify({ skill: '影像追忆', item_type: 'required' }) },
    { id: 3, checkin_status: 'pending', instructions: JSON.stringify({ skill: '多元感知', item_type: 'elective' }) },
    { id: 4, checkin_status: 'pending', instructions: JSON.stringify({ skill: '高效作业', item_type: 'elective', blocks_next: false }) },
  ]

  it('排除已打卡项', () => {
    const editable = filterEditableItems(items)
    expect(editable.map(i => i.id)).not.toContain(1)
  })

  it('排除选修项', () => {
    const editable = filterEditableItems(items)
    expect(editable.map(i => i.id)).toEqual([2])
  })

  it('无待编辑项时不可定制', () => {
    const doneOnly = items.map(i => ({ ...i, checkin_status: 'done' }))
    expect(filterEditableItems(doneOnly)).toHaveLength(0)
  })
})

describe('方案编辑 — customize 请求体', () => {
  it('editorSkills 解析为技能名列表', () => {
    const payload = buildCustomizePayload(
      [{ id: 10 }, { id: 11 }],
      ['10:扫描速记', '11:极速运算'],
    )
    expect(payload.skills).toEqual(['扫描速记', '极速运算'])
  })
})

describe('天赋历史头像 — 英文文件名', () => {
  const talentAvatar = {
    学者: '/static/talent-xuezhe.png',
    思者: '/static/talent-sizhe.png',
    行者: '/static/talent-xingzhe.png',
    德者: '/static/talent-dezhe.png',
    赢者: '/static/talent-yingzhe.png',
  }

  it('五者天赋均有英文 PNG 路径', () => {
    Object.values(talentAvatar).forEach(path => {
      expect(path).toMatch(/^\/static\/talent-[a-z]+\.png$/)
      expect(path).not.toMatch(/[\u4e00-\u9fff]/)
    })
  })
})
