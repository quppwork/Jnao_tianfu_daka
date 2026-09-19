/**
 * 天赋学院板块 API — 频道 / 历史剧情 / 课程共用
 */
import { apiJson, withUser } from './client.js'

export async function fetchAcademySector(userId, episodeId) {
  const q = episodeId ? `?episode_id=${encodeURIComponent(episodeId)}` : ''
  return apiJson(withUser(`/api/academy/sector${q}`, userId))
}
