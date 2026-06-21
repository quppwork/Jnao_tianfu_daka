/** Pure functions for the talent test — no side effects, no React dependency. */

/** Fisher-Yates shuffle */
export function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/**
 * Move timed-out question to a random position in the latter half
 * of the remaining pool.
 */
export function requeueAtBack(remaining: number[], qid: number): number[] {
  const pool = remaining.filter((x) => x !== qid);
  if (pool.length === 0) return [qid];
  const backStart = Math.max(0, Math.floor(pool.length / 2));
  const insertIdx = backStart + Math.floor(Math.random() * (pool.length - backStart + 1));
  return [...pool.slice(0, insertIdx), qid, ...pool.slice(insertIdx)];
}

/** Get or create a persistent UID stored in localStorage. */
export function getOrCreateUid(): number {
  const key = "jnao_uid";
  const stored = localStorage.getItem(key);
  if (stored) return parseInt(stored, 10);
  const uid = (Math.floor(Date.now() / 1000) % 900000) + 100000 + Math.floor(Math.random() * 1000);
  localStorage.setItem(key, String(uid));
  return uid;
}

/**
 * Encode answers to a 35-bit string sorted by question ID.
 * "完全符合" → "1", anything else → "0"
 */
export function encodeAnswers(questionOrder: number[], answers: Record<number, string>): string {
  return questionOrder
    .slice()
    .sort((a, b) => a - b)
    .map((qid) => (answers[qid] === "完全符合" ? "1" : "0"))
    .join("");
}
