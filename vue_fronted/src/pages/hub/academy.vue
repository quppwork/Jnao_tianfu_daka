<template>
  <dayu-frame page="drama.html" :hydrate="hydrate" />
</template>

<script setup>
import { onLoad, onShow } from '@dcloudio/uni-app'
import { reactive } from 'vue'
import DayuFrame from '@/components/dayu-frame/dayu-frame.vue'
import { loadAcademySector, readAcademyCache } from '@/utils/academy/sector.js'

const hydrate = reactive({ academy: readAcademyCache() })
let episodeId = ''

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

onLoad((query) => {
  episodeId = readEpisodeQuery(query)
})

let lastHydrateId = ''

function reload() {
  episodeId = pageEpisodeId()
  loadAcademySector(episodeId)
    .then((data) => {
      const nextId = data?.episode?.id || ''
      // 同集切回：合并字段，避免整页重绘冲掉 iframe 里已打开的讨论区
      if (lastHydrateId && nextId && lastHydrateId === nextId && hydrate.academy?.episode) {
        const prev = hydrate.academy
        hydrate.academy = {
          ...prev,
          ...data,
          episode: { ...prev.episode, ...data.episode },
        }
      } else {
        hydrate.academy = data
      }
      lastHydrateId = nextId || lastHydrateId
    })
    .catch((e) => console.warn('[academy] sector failed', e?.message || e))
}

onShow(reload)
</script>
