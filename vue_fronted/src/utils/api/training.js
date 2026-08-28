/**
 * training API
 */
import { apiJson, withUser } from '../userApiCore.js'

// ── 今日训练（核心模块：入口→排课→打卡→历史）──

/** 训练入口：校验天赋状态 + 检查今日方案是否存在 */
export async function fetchTrainingEntry(userId) {
  return apiJson(withUser('/api/training/entry', userId))
}

/** 获取今日训练方案，skipAi=1 跳过 LLM 报告生成（首屏加速） */
export async function fetchTrainingToday(userId, options = {}) {
  const skipAi = options.skipAi ?? options.skip_ai ?? false
  const base = skipAi ? '/api/training/today?skip_ai=1' : '/api/training/today'
  try {
    const data = await apiJson(withUser(base, userId))
    return { data }
  } catch (e) {
    if (e.status === 403) {
      return { error: 'assessment', message: e.data?.detail || '请先完成天赋测评' }
    }
    return { error: 'api', message: e.message }
  }
}

/** 强制重新生成 AI 今日方案（开发者/刷新用） */
export async function refreshTrainingReport(userId, force = true) {
  try {
    const data = await apiJson(withUser(`/api/training/report/today?force=${force ? '1' : '0'}`, userId))
    return { data }
  } catch (e) {
    if (e.status === 403) {
      return { error: 'assessment', message: e.data?.detail || '请先完成天赋测评' }
    }
    return { error: 'api', message: e.message }
  }
}

/** 按训练时长排课（规则引擎） */
export async function scheduleTrainingPlan(userId, plannedMinutes) {
  try {
    const data = await apiJson(withUser('/api/training/schedule', userId), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        planned_minutes: plannedMinutes,
      }),
    })
    return { data }
  } catch (e) {
    if (e.status === 403) {
      return { error: 'assessment', message: e.data?.detail || '请先完成天赋测评' }
    }
    return { error: 'api', message: e.message }
  }
}

/** 设定时长用尽 — 后端隐藏媒体 URL，打卡仍可用 */
export async function markPlanMediaExhausted(userId) {
  try {
    const data = await apiJson(withUser('/api/training/plan/media-exhausted', userId), {
      method: 'POST',
    })
    return { data }
  } catch (e) {
    return { error: 'api', message: e.message }
  }
}

/** 记录今日训练时段（用于后端判断计时是否结束） */
export async function setTrainingWindow(userId, startTime, endTime) {
  return apiJson(withUser('/api/training/window', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ start_time: startTime, end_time: endTime }),
  })
}

export async function clearTrainingWindow(userId) {
  return apiJson(withUser('/api/training/window', userId), { method: 'DELETE' })
}

/** 天赋固定训练视频 */
export async function fetchTalentTrainingVideo(userId) {
  return apiJson(withUser('/api/training/video/talent', userId))
}

export async function fetchTrainingProgress(userId) {
  return apiJson(withUser('/api/training/progress', userId))
}

export async function submitTrainingCheckin(userId, payload) {
  return apiJson(withUser('/api/training/checkin', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function postTrainingWatchProgress(userId, itemId, payload) {
  return apiJson(withUser(`/api/training/items/${itemId}/watch-progress`, userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function fetchTodayCheckins(userId) {
  const data = await apiJson(withUser('/api/training/checkin/today', userId))
  return Array.isArray(data) ? data : []
}

export async function updateTrainingCheckin(userId, recordId, payload) {
  return apiJson(withUser(`/api/training/checkin/${recordId}`, userId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function deleteTrainingCheckin(userId, recordId) {
  return apiJson(withUser(`/api/training/checkin/${recordId}`, userId), {
    method: 'DELETE',
  })
}

export async function fetchTrainingHistory(userId, limit = 30, { excludeToday = false } = {}) {
  const qs = `limit=${limit}&group_by_day=1${excludeToday ? '&exclude_today=1' : ''}`
  const data = await apiJson(withUser(`/api/training/history?${qs}`, userId))
  return { items: data.items || [], days: data.days || [] }
}

// ── v2.0 选修弹窗 ──

/** 获取可用的选修技能列表 */
export async function fetchElectiveList(plannedMinutes = 0, overallTier = 1) {
  const data = await apiJson(`/api/training/elective/list?planned_minutes=${plannedMinutes}&overall_tier=${overallTier}`)
  return { offers: data.offers || [] }
}

/** 提交选修打卡（多元感知等） */
export async function submitElectiveCheckin(userId, payload) {
  return apiJson(withUser('/api/training/elective', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

/** 整体替换今日方案中的训练项目（不改等级进度） */
export async function customizePlan(userId, planId, skills) {
  return apiJson(withUser('/api/training/plan/customize', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan_id: planId, skills }),
  })
}

/** 开关选修项：action="add" 追加到末尾，action="remove" 从方案移除 */
export async function toggleElectiveItem(userId, planId, skill, action) {
  return apiJson(withUser('/api/training/plan/elective-toggle', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan_id: planId, skill, action }),
  })
}

