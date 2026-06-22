/** Fisher-Yates shuffle */
export function shuffle(arr) {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

/** Move timed-out question to latter half of remaining pool */
export function requeueAtBack(remaining, qid) {
  const pool = remaining.filter(x => x !== qid)
  if (pool.length === 0) return [qid]
  const backStart = Math.max(0, Math.floor(pool.length / 2))
  const insertIdx = backStart + Math.floor(Math.random() * (pool.length - backStart + 1))
  return [...pool.slice(0, insertIdx), qid, ...pool.slice(insertIdx)]
}

/** Get or create a persistent UID */
export function getOrCreateUid() {
  const key = 'jnao_uid'
  try {
    const stored = localStorage.getItem(key)
    if (stored) return parseInt(stored, 10)
    const uid = String(Math.floor(Date.now() / 1000) % 900000 + 100000 + Math.floor(Math.random() * 1000))
    localStorage.setItem(key, uid)
    return parseInt(uid, 10)
  } catch (e) {
    return Math.floor(Date.now() / 1000) % 900000 + 100000
  }
}

/** Encode answers to 35-bit string sorted by question ID */
export function encodeAnswers(questionOrder, answers) {
  return questionOrder
    .slice()
    .sort((a, b) => a - b)
    .map(qid => answers[qid] === '完全符合' ? '1' : '0')
    .join('')
}
