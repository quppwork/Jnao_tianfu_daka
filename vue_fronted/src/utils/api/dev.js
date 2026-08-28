/**
 * dev API
 */
import { apiJson, withUser } from '../userApiCore.js'

// ── 开发者工具（JNAO_DEV_MODE=1）──

export async function fetchDevTrainingStatus(userId) {
  return apiJson(withUser('/api/dev/training/status', userId))
}

export async function devResetTodayTraining(userId) {
  return apiJson(withUser('/api/dev/training/reset-today', userId), { method: 'POST' })
}

export async function devResetTrainingProgress(userId) {
  return apiJson(withUser('/api/dev/training/reset-progress', userId), { method: 'POST' })
}

export async function devResetAllTraining(userId) {
  return apiJson(withUser('/api/dev/training/reset-all', userId), { method: 'POST' })
}

export async function devSimulateNextDay(userId) {
  return apiJson(withUser('/api/dev/training/next-day', userId), { method: 'POST' })
}

export async function devSimulate4amCutoff(userId) {
  return apiJson(withUser('/api/dev/training/simulate-4am-cutoff', userId), { method: 'POST' })
}

export async function devResetTalent(userId) {
  return apiJson(withUser('/api/dev/training/reset-talent', userId), { method: 'POST' })
}

export async function devResetClock(userId) {
  return apiJson(withUser('/api/dev/training/reset-clock', userId), { method: 'POST' })
}
