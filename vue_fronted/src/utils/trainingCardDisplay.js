/** 训练打卡卡片展示 — 今日摘要与历史页共用 */

export const TRAINING_ABILITIES = [
  '超脑阅读', '影像追忆', '扫描速记', '极速运算', '极速学习', '难题专练',
  '文科扫书', '理科扫书', '高效作业', '天赋绘画', '音乐灵感', '棋类专注',
]

/** 从今日方案训练项解析打卡能力名（instructions.skill / 标题匹配） */
export function resolvePlanItemSkill(item, abilityList = TRAINING_ABILITIES) {
  if (!item) return null
  const inst = item.instructions
  if (typeof inst === 'string' && inst.trim().startsWith('{')) {
    try {
      const payload = JSON.parse(inst)
      const sk = (payload.skill || '').trim()
      if (sk && abilityList.includes(sk)) return sk
    } catch (_) { /* ignore */ }
  }
  const texts = [item.title, item.lesson_title, item.ability_type]
    .filter(Boolean)
    .map(s => String(s).replace(/\s+/g, ''))
  for (const text of texts) {
    for (const ability of abilityList) {
      if (text.includes(ability)) return ability
    }
    if (text.includes('超脑速读')) return '超脑阅读'
  }
  return null
}

/** 打卡卡片一行摘要：用时+题数+正确率拼接，如 "20min · 30题 · 85%" */
export function miniCardSummary(c) {
  if (!c) return '已记录'
  const parts = []
  if (c.time) parts.push(`${c.time}min`)
  if (c.wordCount) parts.push(`${c.wordCount}字`)
  if (c.tag) parts.push(c.tag)
  if (c.count) parts.push(`${c.count}题`)
  if (c.accuracy) parts.push(`${c.accuracy}%`)
  if (c.tool) parts.push(c.tool)
  if (c.materialType) parts.push(c.materialType)
  if (c.materialName) parts.push(`《${c.materialName}》`)
  if (c.content && !c.wordCount) parts.push(c.content)
  return parts.length ? parts.join(' · ') : '已记录'
}

/** 将 API 打卡记录展开为与今日页一致的 cards 列表 */
export function cardsFromRecord(record) {
  if (!record) return []
  const raw = Array.isArray(record.cards) ? record.cards : []
  if (raw.length) {
    return raw.map(c => ({
      ...c,
      phaseBlock: c.phaseBlock || (record.phase_blocks && record.phase_blocks[0]) || '',
    }))
  }
  const name = (record.ability_type || '训练记录').split('、')[0].trim()
  return [{
    name,
    content: record.content || '',
    result: record.result || '',
    note: record.note || '',
    phaseBlock: (record.phase_blocks && record.phase_blocks[0]) || '',
  }]
}

export function attitudeEmoji(pct) {
  if (pct >= 100) return '🔴'
  if (pct >= 80) return '🟡'
  if (pct >= 60) return '🔵'
  if (pct >= 40) return '🟤'
  if (pct >= 20) return '⚫️'
  return '☠️'
}
