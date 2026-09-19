/** 训练打卡配合度选项 — 从巨页拆出便于复用 */
export const ATTITUDE_SCORES = [
  { pct: 100, emoji: '🔴', desc: '身体已透支，精神还要求进步' },
  { pct: 80, emoji: '🟡', desc: '能完成任务，但还有余力学习' },
  { pct: 60, emoji: '🔵', desc: '做基本任务，被动的低效训练' },
  { pct: 40, emoji: '🟤', desc: '不完成任务，不认真逃避训练' },
  { pct: 20, emoji: '⚫️', desc: '不完成任务，基本不配合训练' },
  { pct: 0, emoji: '☠️', desc: '不完成任务，严重不配合训练' },
]

export function attitudeDescFor(pct) {
  const hit = ATTITUDE_SCORES.find((s) => s.pct === Number(pct))
  return hit?.desc || ''
}

export function emptyCheckinForm() {
  return { time: '', wordCount: '', accuracy: '', note: '', attitude: 60 }
}
