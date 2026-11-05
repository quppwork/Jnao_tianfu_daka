/** 训练打卡配合度选项 — 从巨页拆出便于复用 */
export const ATTITUDE_SCORES = [
  { pct: 100, emoji: '🔴', desc: '身体已透支，精神还要求进步' },
  { pct: 80, emoji: '🟡', desc: '能完成任务，但还有余力学习' },
  { pct: 60, emoji: '🔵', desc: '做基本任务，被动的低效训练' },
  { pct: 40, emoji: '🟤', desc: '不完成任务，不认真逃避训练' },
  { pct: 20, emoji: '⚫️', desc: '不完成任务，基本不配合训练' },
  { pct: 0, emoji: '☠️', desc: '不完成任务，严重不配合训练' },
]

/**
 * 字/分钟软上限（对齐晋升表最高合理档，仅提醒不拦提交）：
 * - 超脑阅读：二阶高中 5000字/5分 → 1000
 * - 影像追忆：四阶初中 12000字/10分 → 1200（不含五阶极端）
 * - 扫描速记：记忆档最高 300字/分
 */
export const WORD_SPEED_SOFT_LIMITS = {
  超脑阅读: 1000,
  影像追忆: 1200,
  扫描速记: 300,
}

export function attitudeDescFor(pct) {
  const hit = ATTITUDE_SCORES.find((s) => s.pct === Number(pct))
  return hit?.desc || ''
}

export function emptyCheckinForm() {
  return { time: '', wordCount: '', accuracy: '', note: '', attitude: 60 }
}

export function wordSpeedSoftLimit(skill) {
  return WORD_SPEED_SOFT_LIMITS[skill] || 0
}

/** @returns {{ wpm: number, limit: number } | null} 超限时返回字速与上限 */
export function abnormalWordSpeed(skill, time, wordCount) {
  const limit = wordSpeedSoftLimit(skill)
  if (!limit) return null
  const t = Number(time)
  const w = Number(wordCount)
  if (!(t > 0) || !(w > 0)) return null
  const wpm = w / t
  if (wpm <= limit) return null
  return { wpm: Math.round(wpm * 10) / 10, limit }
}

export function findAbnormalWordSpeedCards(cards) {
  const names = []
  for (const c of cards || []) {
    if (abnormalWordSpeed(c.name, c.time, c.wordCount)) names.push(c.name)
  }
  return names
}
