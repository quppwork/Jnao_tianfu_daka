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
    if (!raw || raw.fake || !raw.episode) return null
    const cur = Number(uid || getChildUserId() || 0)
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
    localStorage.removeItem('jnao_academy_sector')
    localStorage.setItem(sectorCacheKey(uid), JSON.stringify(data))
    if (data.episode.id) rememberLastAcademyEpisode(data.episode.id, uid)
  } catch (e) { /* 写不进就等下次接口 */ }
}

export async function loadAcademySector(episodeId) {
  const want = String(episodeId || '').trim() || readLastAcademyEpisode()
  try {
    const uid = await ensureChildUser()
    const data = await fetchAcademySector(uid, want || undefined)
    writeAcademyCache(data)
    return data
  } catch (e) {
    console.warn('[academy] sector fallback', e?.message || e)
    return readAcademyCache() || fakeAcademySector(want)
  }
}
