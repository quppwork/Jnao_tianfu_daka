/**
 * 天赋学院三页共用的进页加载。先读上次目录，再向接口要新的。
 */
import { fetchAcademySector } from '../api/academy.js'
import { ensureChildUser } from '../userApi.js'
import { fakeAcademySector } from './fake.js'

const CACHE_KEY = 'jnao_academy_sector'

export function readAcademyCache() {
  try {
    const raw = JSON.parse(localStorage.getItem(CACHE_KEY) || 'null')
    if (!raw || raw.fake || !raw.episode) return null
    return raw
  } catch (e) {
    return null
  }
}

function writeAcademyCache(data) {
  if (!data || data.fake || !data.episode) return
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(data))
  } catch (e) { /* 写不进就等下次接口 */ }
}

export async function loadAcademySector(episodeId) {
  try {
    const uid = await ensureChildUser()
    const data = await fetchAcademySector(uid, episodeId)
    writeAcademyCache(data)
    return data
  } catch (e) {
    console.warn('[academy] sector fallback', e?.message || e)
    return readAcademyCache() || fakeAcademySector(episodeId)
  }
}
