/** 训练打卡卡片展示 — 今日摘要与历史页共用 */

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
