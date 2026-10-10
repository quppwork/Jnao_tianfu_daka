<template>
  <dayu-frame
    page="drama.html"
    :hydrate="hydrate"
    :academy-collapse-signal="collapseSignal"
  />
</template>

<script setup>
import { onLoad, onShow } from '@dcloudio/uni-app'
import { reactive, ref } from 'vue'
import DayuFrame from '@/components/dayu-frame/dayu-frame.vue'
import {
  loadAcademySector,
  readAcademyCache,
  rememberLastAcademyEpisode,
  resolveAcademyEpisodeId,
} from '@/utils/academy/sector.js'

const hydrate = reactive({ academy: readAcademyCache() })
const collapseSignal = ref(0)
let episodeId = ''
let lastHydrateId = String(hydrate.academy?.episode?.id || '')
let loading = false

function readEpisodeQuery(query) {
  const q = query || {}
  return String(q.ep || q.episode_id || '').trim()
}

function pageEpisodeId() {
  try {
    const pages = getCurrentPages()
    const page = pages[pages.length - 1]
    const opts = (page && (page.options || page.$page?.options)) || {}
    return readEpisodeQuery(opts) || episodeId
  } catch (_) {
    return episodeId
  }
}

function applySector(data, { force = false } = {}) {
  const nextId = String(data?.episode?.id || '').trim()
  if (!data || !nextId) return
  rememberLastAcademyEpisode(nextId)
  const prevId = String(hydrate.academy?.episode?.id || lastHydrateId || '')
  // 同集切回：合并字段，避免整页重绘冲掉 iframe 里播放/讨论状态
  if (!force && prevId && prevId === nextId && hydrate.academy?.episode) {
    const prev = hydrate.academy
    const ep = { ...prev.episode, ...data.episode }
    // 解锁以服务端为准，避免本地误标 unlocked 后反复打 /open → 403 刷屏
    ep.unlocked = !!data.episode.unlocked
    if (prev.episode.play_url && !ep.play_url) ep.play_url = prev.episode.play_url
    hydrate.academy = {
      ...prev,
      ...data,
      episode: ep,
    }
  } else {
    hydrate.academy = data
  }
  lastHydrateId = nextId
  episodeId = nextId
}

function reload({ force = false } = {}) {
  const queryEp = pageEpisodeId()
  episodeId = resolveAcademyEpisodeId(queryEp)
  if (queryEp) rememberLastAcademyEpisode(queryEp)

  // 先灌本地 sector（含 unlocked），再等接口；避免首屏长时间停在「看完才能进讨论」
  const cached = readAcademyCache()
  if (cached?.episode) {
    applySector(cached, { force: false })
  }

  const have = String(hydrate.academy?.episode?.id || '')
  // 底栏软切回：已有同集且非强制 → 不请求覆盖（iframe DOM 仍在）
  if (!force && have && (!episodeId || episodeId === have)) {
    rememberLastAcademyEpisode(have)
    // 仍后台刷新一次解锁态（首次进页缓存可能偏旧）
    if (!force && !loading) {
      loading = true
      loadAcademySector(have || episodeId)
        .then((data) => applySector(data, { force: false }))
        .catch((e) => console.warn('[academy] sector failed', e?.message || e))
        .finally(() => { loading = false })
    }
    return
  }

  if (loading) return
  loading = true
  loadAcademySector(episodeId)
    .then((data) => applySector(data, { force }))
    .catch((e) => console.warn('[academy] sector failed', e?.message || e))
    .finally(() => { loading = false })
}

onLoad((query) => {
  const q = readEpisodeQuery(query)
  episodeId = resolveAcademyEpisodeId(q)
  if (q) rememberLastAcademyEpisode(q)
})

onShow(() => {
  // 每次进学院：收起讨论，需用户手动点进（含底栏软切回）
  collapseSignal.value += 1
  reload({ force: false })
})
</script>
