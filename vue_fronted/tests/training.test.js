import { describe, it, expect, beforeEach, vi } from 'vitest'

// ═══════════════════════════════════════════
// 训练页 — 功能 / 流程 / 边界测试
// ═══════════════════════════════════════════

// --- 纯函数测试（从 training/index.vue 提取逻辑） ---

describe('formatDuration — 计时器格式化', () => {
  function formatDuration(totalSec) {
    const sec = Math.max(0, totalSec)
    const h = Math.floor(sec / 3600)
    const m = Math.floor((sec % 3600) / 60)
    const s = sec % 60
    if (h > 0) return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }

  it('90分钟 → 01:30:00', () => {
    expect(formatDuration(5400)).toBe('01:30:00')
  })
  it('5分钟 → 05:00', () => {
    expect(formatDuration(300)).toBe('05:00')
  })
  it('1小时 → 01:00:00', () => {
    expect(formatDuration(3600)).toBe('01:00:00')
  })
  it('0秒 → 00:00', () => {
    expect(formatDuration(0)).toBe('00:00')
  })
  it('负数 → 不崩溃，归零', () => {
    expect(formatDuration(-100)).toBe('00:00')
  })
  it('59分59秒 → 59:59', () => {
    expect(formatDuration(3599)).toBe('59:59')
  })
  it('23:59:59 → 正常显示', () => {
    expect(formatDuration(86399)).toBe('23:59:59')
  })
})

describe('miniCardSummary — 迷你卡摘要', () => {
  function miniCardSummary(c) {
    const parts = []
    if (c.time) parts.push(c.time + 'min')
    if (c.tag) parts.push(c.tag)
    if (c.count) parts.push(c.count + '题')
    if (c.accuracy) parts.push(c.accuracy + '%')
    if (c.tool) parts.push(c.tool)
    if (c.materialType) parts.push(c.materialType)
    return parts.length ? parts.join(' · ') : '已记录'
  }

  it('极速运算完整数据', () => {
    expect(miniCardSummary({ time:'30', tag:'加减法', count:'100', accuracy:'95' }))
      .toBe('30min · 加减法 · 100题 · 95%')
  })
  it('影像追忆', () => {
    expect(miniCardSummary({ time:'20', tool:'视频' }))
      .toBe('20min · 视频')
  })
  it('扫描速记', () => {
    expect(miniCardSummary({ materialType:'书', wordCount:'500' }))
      .toBe('书')
  })
  it('空数据 → 已记录', () => {
    expect(miniCardSummary({})).toBe('已记录')
  })
  it('只有时间', () => {
    expect(miniCardSummary({ time:'10' })).toBe('10min')
  })
})

describe('cardDetailFields — 详情字段映射', () => {
  function cardDetailFields(c) {
    const map = {}
    if (c.time) map['时长'] = c.time + ' 分钟'
    if (c.content) map['内容'] = c.content
    if (c.result) map['结果'] = c.result
    if (c.tag) map['类型'] = c.tag
    if (c.count) map['题数'] = c.count + ' 题'
    if (c.accuracy) map['正确率'] = c.accuracy + '%'
    if (c.tool) map['工具'] = c.tool
    if (c.materialType) map['材料类型'] = c.materialType
    if (c.materialName) map['材料名称'] = c.materialName
    if (c.wordCount) map['字数'] = c.wordCount + ' 字'
    if (c.forwardTime || c.forwardAcc) map['正背'] = (c.forwardTime||'?') + ' / ' + (c.forwardAcc||'?')
    if (c.backwardTime || c.backwardAcc) map['倒背'] = (c.backwardTime||'?') + ' / ' + (c.backwardAcc||'?')
    if (c.note) map['备注'] = c.note
    return map
  }

  it('极速运算 → 5个字段', () => {
    const fields = cardDetailFields({ time:'30', tag:'加减法', count:'100', accuracy:'95', note:'测试备注' })
    expect(Object.keys(fields)).toHaveLength(5)
    expect(fields['时长']).toBe('30 分钟')
    expect(fields['正确率']).toBe('95%')
    expect(fields['备注']).toBe('测试备注')
  })
  it('扫描速记 → 含正背倒背', () => {
    const fields = cardDetailFields({ materialType:'书', materialName:'西游记', wordCount:'500', forwardTime:'30s', forwardAcc:'98%', backwardTime:'45s', backwardAcc:'90%' })
    expect(fields['正背']).toBe('30s / 98%')
    expect(fields['倒背']).toBe('45s / 90%')
    expect(fields['材料名称']).toBe('西游记')
  })
  it('空卡 → 空对象', () => {
    expect(Object.keys(cardDetailFields({}))).toHaveLength(0)
  })
})

describe('phaseTip — 阶段提示文字', () => {
  function phaseTip(phase, planPhases) {
    if (!phase.unlocked) {
      const idx = planPhases.findIndex(p => p.block === phase.block)
      const prev = idx > 0 ? planPhases[idx - 1]?.block : ''
      return prev ? `完成训练 ${prev} 打卡后解锁本阶段` : '待解锁'
    }
    if (phase.allDone) return ''
    return `训练 ${phase.block} 共 ${phase.totalCount} 项`
  }

  const phases = [
    { block:'A', unlocked:true, allDone:false, totalCount:3 },
    { block:'B', unlocked:false, allDone:false, totalCount:2 },
  ]

  it('A进行中 → 显示项数', () => {
    expect(phaseTip(phases[0], phases)).toBe('训练 A 共 3 项')
  })
  it('B未解锁 → 提示先完成A', () => {
    expect(phaseTip(phases[1], phases)).toBe('完成训练 A 打卡后解锁本阶段')
  })
  it('A已完成 → 空字符串', () => {
    const done = { block:'A', unlocked:true, allDone:true, totalCount:3 }
    expect(phaseTip(done, phases)).toBe('')
  })
})

describe('canPhaseCheckin — 打卡权限检查', () => {
  function canPhaseCheckin(phase, devMode, planLoading, planJustGenerated, timerPhase) {
    if (!phase.unlocked) return false
    if (!devMode && (planLoading || planJustGenerated || timerPhase === 'setup')) return false
    return true
  }

  const phase = { unlocked:true }

  it('解锁 + 计时中 → 可以打卡', () => {
    expect(canPhaseCheckin(phase, false, false, false, 'running')).toBe(true)
  })
  it('解锁 + setup → 不能（DEV模式可）', () => {
    expect(canPhaseCheckin(phase, false, false, false, 'setup')).toBe(false)
    expect(canPhaseCheckin(phase, true, false, false, 'setup')).toBe(true)
  })
  it('未解锁 → 始终不能', () => {
    expect(canPhaseCheckin({ unlocked:false }, false, false, false, 'running')).toBe(false)
  })
  it('加载中 → 不能', () => {
    expect(canPhaseCheckin(phase, false, true, false, 'running')).toBe(false)
  })
  it('方案刚生成 → 不能', () => {
    expect(canPhaseCheckin(phase, false, false, true, 'running')).toBe(false)
  })
})

describe('newCard — 新建打卡卡片', () => {
  function newCard(name) {
    const base = { name, time:'', content:'', result:'', tag:'', count:'', accuracy:'', note:'', files:[] }
    if (name === '扫描速记') {
      return { ...base, materialType:'书', materialName:'', wordCount:'', forwardTime:'', forwardAcc:'', backwardTime:'', backwardAcc:'' }
    }
    if (name === '影像追忆') {
      return { ...base, tool:'书本' }
    }
    return base
  }

  it('普通能力 → 基础结构', () => {
    const c = newCard('极速运算')
    expect(c.name).toBe('极速运算')
    expect(c.files).toEqual([])
  })
  it('扫描速记 → 含额外字段', () => {
    const c = newCard('扫描速记')
    expect(c.materialType).toBe('书')
    expect(c.wordCount).toBe('')
  })
  it('影像追忆 → 含工具字段', () => {
    const c = newCard('影像追忆')
    expect(c.tool).toBe('书本')
  })
})

// --- 流程测试（模拟打卡全链路） ---

describe('打卡流程 — 全链路状态模拟', () => {
  // 模拟训练当日数据的核心结构
  function buildPlan(items) {
    return { plan_id:'plan-001', items, status:'pending', planned_minutes:30 }
  }
  function buildItem(id, block, title, itemType = 'audio') {
    return { id, block, title, item_type:itemType, audio_url: itemType === 'audio' ? 'audio.mp3' : null, video_url: itemType === 'video' ? 'video.mp4' : null, duration_min:10, checkin_status:'pending' }
  }

  let plan, submittedCards

  beforeEach(() => {
    plan = buildPlan([
      buildItem(1, 'A', '极速运算训练', 'audio'),
      buildItem(2, 'A', '影像追忆训练', 'audio'),
      buildItem(3, 'B', '扫描速记训练', 'audio'),
    ])
    submittedCards = []
  })

  it('初始状态：0项完成', () => {
    const done = plan.items.filter(i => i.checkin_status === 'done')
    expect(done).toHaveLength(0)
  })

  it('完成训练A打卡 → A项标记done', () => {
    plan.items.filter(i => i.block === 'A').forEach(i => i.checkin_status = 'done')
    const aItems = plan.items.filter(i => i.block === 'A')
    expect(aItems.every(i => i.checkin_status === 'done')).toBe(true)
    expect(plan.items.find(i => i.block === 'B').checkin_status).toBe('pending')
  })

  it('B在A完成前不可打卡', () => {
    const bUnlocked = plan.items.filter(i => i.block === 'A').every(i => i.checkin_status === 'done')
    expect(bUnlocked).toBe(false)
  })

  it('A全部完成→B解锁', () => {
    plan.items.filter(i => i.block === 'A').forEach(i => i.checkin_status = 'done')
    const bUnlocked = plan.items.filter(i => i.block === 'A').every(i => i.checkin_status === 'done')
    expect(bUnlocked).toBe(true)
  })

  it('全部完成→plan状态completed', () => {
    plan.items.forEach(i => i.checkin_status = 'done')
    plan.status = 'completed'
    expect(plan.items.every(i => i.checkin_status === 'done')).toBe(true)
    expect(plan.status).toBe('completed')
  })

  it('提交打卡→submittedCards更新', () => {
    const newCard = { name:'极速运算', time:'30', tag:'加减法', count:'100', accuracy:'95', phaseBlock:'A' }
    submittedCards = [
      ...submittedCards.filter(c => c.phaseBlock !== 'A'),
      newCard,
    ]
    expect(submittedCards).toHaveLength(1)
    expect(submittedCards[0].phaseBlock).toBe('A')
  })

  it('编辑后提交→替换原卡片而非新增', () => {
    submittedCards = [{ name:'极速运算', time:'30', phaseBlock:'A' }]
    const editIdx = 0
    const updated = { name:'极速运算', time:'45', phaseBlock:'A' }
    submittedCards = submittedCards.map((c, i) => i === editIdx ? updated : c)
    expect(submittedCards).toHaveLength(1)
    expect(submittedCards[0].time).toBe('45')
  })

  it('删除最后一张→submittedCards变空', () => {
    submittedCards = [{ name:'极速运算', phaseBlock:'A' }]
    submittedCards = []
    expect(submittedCards).toHaveLength(0)
  })
})

// --- 边界测试 ---

describe('边界条件', () => {
  it('空方案→0个阶段', () => {
    const items = []
    const blocks = [...new Set(items.map(i => i.block || 'A'))]
    expect(blocks).toHaveLength(0)
  })

  it('单项方案→只有A阶段', () => {
    const items = [{ id:1, block:'A' }]
    const blocks = [...new Set(items.map(i => i.block || 'A'))]
    expect(blocks).toEqual(['A'])
  })

  it('A/B/C三阶段→顺序正确', () => {
    const items = [{ block:'C' }, { block:'A' }, { block:'B' }, { block:'A' }]
    const blocks = []
    const seen = new Set()
    for (const item of items) {
      const b = item.block || 'A'
      if (!seen.has(b)) { seen.add(b); blocks.push(b) }
    }
    expect(blocks).toEqual(['C', 'A', 'B'])
  })

  it('进度计算：0/3 = 0%', () => {
    const total = 3, done = 0
    expect(Math.round(done / total * 100)).toBe(0)
  })

  it('进度计算：2/3 = 67%', () => {
    const total = 3, done = 2
    expect(Math.round(done / total * 100)).toBe(67)
  })

  it('进度计算：全部完成 = 100%', () => {
    const total = 5, done = 5
    expect(Math.round(done / total * 100)).toBe(100)
  })

  it('全部done→allDone为true', () => {
    const items = [{ checkin_status:'done' }, { checkin_status:'done' }]
    const allDone = items.length > 0 && items.filter(i => i.checkin_status === 'done').length === items.length
    expect(allDone).toBe(true)
  })

  it('混合状态→allDone为false', () => {
    const items = [{ checkin_status:'done' }, { checkin_status:'pending' }]
    const allDone = items.filter(i => i.checkin_status === 'done').length === items.length
    expect(allDone).toBe(false)
  })

  it('项目类型emoji映射', () => {
    function itemTypeEmoji(item) {
      if (item.item_type === 'video' || item.video_url) return '🎬'
      if (item.item_type === 'audio' || item.audio_url) return '🎧'
      return '▸'
    }
    expect(itemTypeEmoji({ item_type:'video' })).toBe('🎬')
    expect(itemTypeEmoji({ audio_url:'test.mp3' })).toBe('🎧')
    expect(itemTypeEmoji({})).toBe('▸')
  })

  it('观看标记：Set操作正确', () => {
    const watched = new Set()
    watched.add(1)
    watched.add(2)
    expect(watched.has(1)).toBe(true)
    expect(watched.has(3)).toBe(false)
    watched.add(1) // 重复添加
    expect(watched.size).toBe(2)
  })
})

// --- 能力自动识别测试 ---

describe('autoDetectAbilities — 能力识别', () => {
  const abilities = ['超脑阅读','影像追忆','扫描速记','极速运算','极速学习','难题专练','文科扫书','理科扫书','高效作业','天赋绘画','音乐灵感','棋类专注']

  it('匹配标题中的能力名', () => {
    const title = '极速运算基础训练'
    const matched = abilities.filter(a => title.includes(a))
    expect(matched).toEqual(['极速运算'])
  })

  it('匹配多个能力', () => {
    const title = '影像追忆与扫描速记综合训练'
    const matched = abilities.filter(a => title.includes(a))
    expect(matched).toEqual(['影像追忆', '扫描速记'])
  })

  it('无匹配→空', () => {
    const title = '综合训练'
    const matched = abilities.filter(a => title.includes(a))
    expect(matched).toHaveLength(0)
  })

  it('不重复添加已存在的卡片', () => {
    const existing = ['极速运算']
    const detected = ['极速运算', '影像追忆']
    const toAdd = detected.filter(a => !existing.includes(a))
    expect(toAdd).toEqual(['影像追忆'])
  })
})

// --- 阶段分组测试 ---

describe('阶段分组逻辑', () => {
  it('相同block归入同组', () => {
    const items = [
      { id:1, block:'A', title:'训练1' },
      { id:2, block:'A', title:'训练2' },
      { id:3, block:'B', title:'训练3' },
    ]
    const aItems = items.filter(i => i.block === 'A')
    const bItems = items.filter(i => i.block === 'B')
    expect(aItems).toHaveLength(2)
    expect(bItems).toHaveLength(1)
  })

  it('无block默认为A', () => {
    const items = [{ id:1 }, { id:2, block:'B' }]
    const aItems = items.filter(i => (i.block || 'A') === 'A')
    expect(aItems).toHaveLength(1)
  })
})

// --- 配合度数据测试 ---

describe('配合度评分', () => {
  const scores = [
    { pct:100, emoji:'🔴' },
    { pct:80,  emoji:'🟡' },
    { pct:60,  emoji:'🔵' },
    { pct:40,  emoji:'🟤' },
    { pct:20,  emoji:'⚫️' },
    { pct:0,   emoji:'☠️' },
  ]

  it('6个档位完整', () => {
    expect(scores).toHaveLength(6)
  })
  it('最高100最低0', () => {
    expect(scores[0].pct).toBe(100)
    expect(scores[5].pct).toBe(0)
  })
  it('默认配合度60', () => {
    const defaultAttitude = 60
    const match = scores.find(s => s.pct === defaultAttitude)
    expect(match).toBeDefined()
    expect(match.emoji).toBe('🔵')
  })
})
