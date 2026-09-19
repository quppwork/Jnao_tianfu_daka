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

onLoad((query) => {
  episodeId = query?.ep || query?.episode_id || ''
})

function reload() {
  loadAcademySector(episodeId)
    .then((data) => { hydrate.academy = data })
    .catch((e) => console.warn('[academy] sector failed', e?.message || e))
}

onShow(reload)
</script>
