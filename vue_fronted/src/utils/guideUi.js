/**
 * 引导页行动按钮 / 文案 — 与 backend handoff.ACTION_LABELS 对齐
 */

export const ACTION_LABEL_FALLBACK = {
  talent: '去天赋测试 ›',
  report: '去天赋报告 ›',
  train: '去今日修炼 ›',
  qa: '去学科答疑 ›',
  growth: '去中央电脑 ›',
  history: '去历史记录 ›',
  parent_pdata: '看数据分析 ›',
  parent_pcourse: '进家长课堂 ›',
  talent_hub: '去天赋测试 ›',
}

export const GUIDE_DIALOG_MESSAGE_LIMIT = 20

export function actionLabel(target) {
  return ACTION_LABEL_FALLBACK[target] || '前往 ›'
}

export function normalizeGuideActions(raw) {
  if (!Array.isArray(raw)) return []
  const out = []
  for (const a of raw) {
    if (!a || typeof a !== 'object') continue
    if (a.type === 'confirm' && a.write_op) {
      out.push({
        type: 'confirm',
        write_op: String(a.write_op),
        args: (a.args && typeof a.args === 'object') ? a.args : {},
        label: a.label || '确认记下',
        preview: a.preview || '',
        cancel_label: a.cancel_label || '暂不',
        _done: false,
        _dismissed: false,
        _busy: false,
      })
      continue
    }
    if (a.type === 'navigate') {
      const target = a.target || ''
      const path = a.path || GUIDE_NAV_ROUTES[target] || null
      // 已知目标、或带显式 path（家长端多孩跳转等）
      if (!path && !ACTION_LABEL_FALLBACK[target] && !a.path) continue
      out.push({
        type: 'navigate',
        target,
        label: a.label || actionLabel(target),
        path: a.path || path || undefined,
        child_id: a.child_id != null ? Number(a.child_id) : undefined,
        query: (a.query && typeof a.query === 'object') ? a.query : undefined,
      })
    }
  }
  return out
}

/** 文案已导学科答疑时，按钮必须同步 */
export function alignGuideActionsWithReply(reply, rawActions) {
  const actions = normalizeGuideActions(rawActions)
  const text = String(reply || '')
  const confirms = actions.filter((a) => a.type === 'confirm')
  if (text.includes('学科答疑')) {
    const qa = actions.filter((a) => a.type === 'navigate' && a.target === 'qa')
    if (qa.length) return [...confirms, ...qa]
    return [...confirms, { type: 'navigate', target: 'qa', label: actionLabel('qa') }]
  }
  return actions
}

export function normalizeNavigateActions(raw) {
  return normalizeGuideActions(raw).filter((a) => a.type === 'navigate')
}

export function trimGuideMessages(msgs) {
  const list = Array.isArray(msgs) ? msgs : []
  if (list.length <= GUIDE_DIALOG_MESSAGE_LIMIT) return list
  return list.slice(-GUIDE_DIALOG_MESSAGE_LIMIT)
}

/** 引导行动跳转目标（大宇改版路由） */
export const GUIDE_NAV_ROUTES = {
  talent: '/pages/talent/hub',
  talent_hub: '/pages/talent/hub',
  train: '/pages/training/dayu',
  qa: '/pages/qa/dayu',
  growth: '/pages/hub/console',
  history: '/pages/training/history',
  academy: '/pages/hub/academy',
  console: '/pages/hub/console',
  report: '/pages/report/index',
  parent_pdata: '/pages/parent/pdata',
  parent_pcourse: '/pages/parent/pcourse',
}
