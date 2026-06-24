/** 孩子用户 ID + 训练相关 API */

const CHILD_KEY = 'jnao_child_user_id'

export function getChildUserId() {
  try {
    const raw = localStorage.getItem(CHILD_KEY)
    if (raw) return parseInt(raw, 10)
  } catch (e) { /* ignore */ }
  return null
}

export function setChildUserId(id) {
  try {
    localStorage.setItem(CHILD_KEY, String(id))
  } catch (e) { /* ignore */ }
}

/** 无则自动注册，返回 child_user_id */
export async function ensureChildUser(nickname = '学员') {
  const existing = getChildUserId()
  if (existing) return existing

  const phone = `13${String(Date.now()).slice(-9)}`
  const res = await fetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ parent_phone: phone, nickname }),
  })
  if (!res.ok) throw new Error('注册失败')
  const data = await res.json()
  setChildUserId(data.child_user_id)
  return data.child_user_id
}

export async function fetchTrainingToday(userId) {
  const res = await fetch(`/api/training/today?user_id=${userId}`)
  const data = await res.json().catch(() => ({}))
  if (res.status === 403) {
    return { error: 'assessment', message: data.detail || '请先完成天赋测评' }
  }
  if (!res.ok) {
    return { error: 'api', message: data.detail || `HTTP ${res.status}` }
  }
  return { data }
}

export async function fetchTrainingProgress(userId) {
  const res = await fetch(`/api/training/progress?user_id=${userId}`)
  if (!res.ok) return null
  return res.json()
}
