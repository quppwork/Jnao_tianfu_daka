<template>
  <dayu-frame page="history.html" :hydrate="hydrate" />
</template>

<script setup>
import { onShow } from '@dcloudio/uni-app'
import { reactive } from 'vue'
import DayuFrame from '@/components/dayu-frame/dayu-frame.vue'
import { loadAcademySector, readAcademyCache } from '@/utils/academy/sector.js'

const hydrate = reactive({ academy: readAcademyCache() })

function reload() {
  loadAcademySector()
    .then((data) => { hydrate.academy = data })
    .catch((e) => console.warn('[story] sector failed', e?.message || e))
}

onShow(reload)
</script>
