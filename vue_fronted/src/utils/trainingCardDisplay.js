/** 训练打卡卡片展示 — 今日摘要与历史页共用 */

export const TRAINING_ABILITIES = [
  '超脑阅读', '影像追忆', '扫描速记', '极速运算', '极速学习', '难题专练',
  '文科扫书', '理科扫书', '高效作业', '天赋绘画', '音乐灵感', '棋类专注',
]

/** 🆕 v2.0 打卡卡片字段定义（按技能类型） */
export const CARD_FIELDS = {
  '超脑阅读': { required: ['time', 'wordCount'], optional: ['result', 'note'] },
  '影像追忆': { required: ['wordCount', 'accuracy'], optional: ['time', 'content', 'note'] },
  '扫描速记': { required: ['wordCount', 'time', 'reverseRecite'], optional: ['materialName', 'note'] },
  '极速运算': { required: ['completed'], optional: ['time', 'tag', 'count', 'accuracy', 'note'] },
  '极速学习': { required: ['completed'], optional: ['time', 'note'] },
}

/** 🆕 v2.0 选修能力（不阻塞、可打可不打） */
export const ELECTIVE_ABILITIES = ['精力恢复', '多元感知', '高效作业']

/** 获取指定技能需要填写的字段标签 */
export function getCardFieldLabels(skillName) {
  const labels = {
    time: '用时(分钟)', wordCount: '完成字数', accuracy: '准确率(%)',
    completed: '已完成', reverseRecite: '可逐字倒背',
    tag: '类型', count: '题数', content: '材料描述',
    materialName: '材料名称', result: '训练效果', note: '备注',
  }
  return labels
}

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
