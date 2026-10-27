/**
 * 天赋学院三页共用的进页加载。先读上次目录，再向接口要新的。
 * 缓存 / 上次剧集按孩子 user_id 隔离，切底栏回来继续同一集。
 */
import { fetchAcademySector } from '../api/academy.js'
import { ensureChildUser, getChildUserId } from '../userApi.js'
import { fakeAcademySector } from './fake.js'

function sectorCacheKey(uid) {
  const id = uid || getChildUserId() || 0
  return id ? `jnao_academy_sector_${id}` : 'jnao_academy_sector'
}

function lastEpisodeKey(uid) {
  const id = uid || getChildUserId() || 0
  return id ? `jnao_academy_last_ep_${id}` : 'jnao_academy_last_ep'
}

export function rememberLastAcademyEpisode(episodeId, uid) {
  const ep = String(episodeId || '').trim().toUpperCase()
  if (!ep) return
  try {
    localStorage.setItem(lastEpisodeKey(uid), ep)
  } catch (_) { /* ignore */ }
}

export function readLastAcademyEpisode(uid) {
  try {
    const ep = String(localStorage.getItem(lastEpisodeKey(uid)) || '').trim().toUpperCase()
    if (ep) return ep
    const cached = readAcademyCache(uid)
    return String(cached?.episode?.id || '').trim().toUpperCase() || ''
  } catch (_) {
    return ''
  }
}

/** 路由 query > 记忆 > 缓存 */
export function resolveAcademyEpisodeId(queryEp, uid) {
  const fromQuery = String(queryEp || '').trim().toUpperCase()
  if (fromQuery) return fromQuery
  return readLastAcademyEpisode(uid) || ''
}

export function readAcademyCache(uid) {
  try {
    const key = sectorCacheKey(uid)
    let raw = JSON.parse(localStorage.getItem(key) || 'null')
    // 兼容旧无 uid 键：仅当 user_id 对得上当前孩子才用
    if (!raw || !raw.episode) {
      raw = JSON.parse(localStorage.getItem('jnao_academy_sector') || 'null')
    }
    const cur = Number(uid || getChildUserId() || 0)
    // uid 尚未写入时：扫一份带 episode 的 sector 缓存，避免首屏卡在「未解锁」
    if ((!raw || !raw.episode) && cur <= 0 && typeof localStorage !== 'undefined') {
      for (let i = 0; i < localStorage.length; i += 1) {
        const k = localStorage.key(i)
        if (!k || !k.startsWith('jnao_academy_sector_')) continue
        try {
          const cand = JSON.parse(localStorage.getItem(k) || 'null')
          if (cand && cand.episode && !cand.fake) {
            raw = cand
            break
          }
        } catch (_) { /* ignore */ }
      }
    }
    if (!raw || raw.fake || !raw.episode) return null
    const cachedUid = Number(raw.user_id || 0)
    // 有当前用户时：必须带匹配的 user_id，旧无 uid 缓存一律丢弃
    if (cur > 0 && cachedUid !== cur) return null
    return raw
  } catch (e) {
    return null
  }
}

function writeAcademyCache(data) {
  if (!data || data.fake || !data.episode) return
  try {
    const uid = Number(data.user_id || getChildUserId() || 0)
    // 勿把 _live 写入本地：下次冷启动会误当成「已确认锁定」
    const { _live, ...rest } = data
    localStorage.removeItem('jnao_academy_sector')
    localStorage.setItem(sectorCacheKey(uid), JSON.stringify(rest))
    if (data.episode.id) rememberLastAcademyEpisode(data.episode.id, uid)
  } catch (e) { /* 写不进就等下次接口 */ }
}

/** 进程内最近一次带 _live 的 sector；切 Tab 预热后进页可直接用，避免再闪「同步中」 */
let lastLiveSector = null

export function peekAcademyLiveSector() {
  return lastLiveSector
}

function rememberLiveSector(data) {
  if (data && typeof data === 'object' && data.episode) {
    data._live = true
    lastLiveSector = data
  }
  return data
}

export async function loadAcademySector(episodeId) {
  const want = String(episodeId || '').trim() || readLastAcademyEpisode()
  try {
    const uid = await ensureChildUser()
    const data = await fetchAcademySector(uid, want || undefined)
    rememberLiveSector(data)
    writeAcademyCache(data)
    return data
  } catch (e) {
    console.warn('[academy] sector fallback', e?.message || e)
    // 接口失败也要结束「同步中」：用缓存/假数据并标 _live，避免按钮永远 pending 却仍可点
    const fallback = readAcademyCache() || fakeAcademySector(want)
    return rememberLiveSector(fallback) || fallback
  }
}

/**
 * 底栏切到学院前短等接口（默认 ~560ms）：有结果立刻返回，超时用内存/缓存。
 * 切换略慢一点，换解锁态与后端对齐后再露页面。
 * @param {number} [maxMs]
 * @param {string} [episodeId] 指定集（历史剧情 ?ep=）；缺省用上次记忆
 */
export function warmAcademySector(maxMs = 560, episodeId) {
  const want = String(episodeId || '').trim() || readLastAcademyEpisode()
  if (want) rememberLastAcademyEpisode(want)
  const fetchP = loadAcademySector(want || '').catch(() => null)
  const timeoutP = new Promise((resolve) => {
    setTimeout(() => {
      const live = peekAcademyLiveSector()
      const cached = readAcademyCache()
      if (want) {
        const w = want.toUpperCase()
        if (live?.episode && String(live.episode.id || '').toUpperCase() === w) {
          resolve(live)
          return
        }
        if (cached?.episode && String(cached.episode.id || '').toUpperCase() === w) {
          resolve(cached)
          return
        }
        resolve(null)
        return
      }
      resolve(live || cached)
    }, Math.max(120, Number(maxMs) || 560))
  })
  return Promise.race([fetchP, timeoutP]).then((data) => {
    const w = want ? want.toUpperCase() : ''
    const ok = (row) => {
      if (!row?.episode) return false
      if (!w) return true
      return String(row.episode.id || '').toUpperCase() === w
    }
    if (ok(data)) return data
    return fetchP.then((live) => {
      if (ok(live)) return live
      if (!w) return peekAcademyLiveSector() || readAcademyCache()
      return null
    })
  })
}

/** 登录后静默预拉学院目录，写入本地缓存，进页不再先闪「未解锁」 */
export function prefetchAcademySectorAfterLogin() {
  try {
    const p = loadAcademySector('')
    if (p && typeof p.then === 'function') {
      p.catch((e) => console.warn('[academy] login prefetch', e?.message || e))
    }
  } catch (e) {
    console.warn('[academy] login prefetch', e?.message || e)
  }
}
