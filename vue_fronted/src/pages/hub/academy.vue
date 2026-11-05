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
  peekAcademyLiveSector,
  readAcademyCache,
  rememberLastAcademyEpisode,
  resolveAcademyEpisodeId,
  warmAcademySector,
} from '@/utils/academy/sector.js'

const hydrate = reactive({
  academy: peekAcademyLiveSector() || readAcademyCache(),
})
const collapseSignal = ref(0)
let episodeId = ''
let lastHydrateId = String(hydrate.academy?.episode?.id || '')
let loading = false
let reloadSeq = 0

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
    const live = !!data._live
    // 直播接口以服务端为准；缓存灌入时勿把本地已解锁盖回 false
    if (live) {
      ep.unlocked = !!data.episode.unlocked
    } else if (prev.episode.unlocked && !data.episode.unlocked) {
      ep.unlocked = true
    } else {
      ep.unlocked = !!data.episode.unlocked
    }
    if (prev.episode.play_url && !ep.play_url) ep.play_url = prev.episode.play_url
    hydrate.academy = {
      ...prev,
      ...data,
      episode: ep,
      _live: live || !!prev._live,
    }
  } else {
    hydrate.academy = data
  }
  lastHydrateId = nextId
  episodeId = nextId
}

async function reload({ force = false } = {}) {
  const queryEp = pageEpisodeId()
  episodeId = resolveAcademyEpisodeId(queryEp)
  if (queryEp) rememberLastAcademyEpisode(queryEp)

  const seq = ++reloadSeq
  const want = episodeId || String(hydrate.academy?.episode?.id || '')
  const wantU = String(want || '').toUpperCase()
  const matchesWant = (data) => {
    if (!data?.episode) return false
    if (!wantU) return true
    return String(data.episode.id || '').toUpperCase() === wantU
  }
  // 优先用切 Tab 预热留下的 _live；指定 ?ep= 时必须同集，避免历史剧情跳错集
  const live = peekAcademyLiveSector()
  if (matchesWant(live)) {
    applySector(live, { force: false })
  } else {
    const cached = readAcademyCache()
    if (cached?.episode?.unlocked && matchesWant(cached)) applySector(cached, { force: false })
  }

  if (loading && !force) {
    try {
      const data = await warmAcademySector(480, want)
      if (seq !== reloadSeq) return
      if (matchesWant(data)) applySector(data, { force: false })
    } catch (e) {
      console.warn('[academy] sector wait failed', e?.message || e)
    }
    return
  }

  loading = true
  try {
    // 进页再短等一轮：切 Tab 已预热时通常立刻命中；冷进页最多约 0.5s
    const data = force
      ? await loadAcademySector(want)
      : await warmAcademySector(520, want)
    if (seq !== reloadSeq) return
    if (matchesWant(data)) applySector(data, { force })
  } catch (e) {
    console.warn('[academy] sector failed', e?.message || e)
  } finally {
    if (seq === reloadSeq) loading = false
  }
}

onLoad((query) => {
  const q = readEpisodeQuery(query)
  episodeId = resolveAcademyEpisodeId(q)
  if (q) rememberLastAcademyEpisode(q)
})

onShow(async () => {
  // 先对齐 sector，再收起讨论，减少未对齐时的可点空窗
  await reload({ force: false })
  collapseSignal.value += 1
})
</script>
