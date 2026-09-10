<template>
  <dayu-frame :page="htmlPage" />
</template>
<script setup>
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import DayuFrame from '@/components/dayu-frame/dayu-frame.vue'

/** 一比一复刻 kimi report-kid / report-v3；旧 Vue 报告 UI 已下线 */
const htmlPage = ref('report-kid.html')

onLoad((opts) => {
  const mode = String(opts?.mode || '').toLowerCase()
  const type = String(opts?.type ?? '')
  const isAdult =
    mode === 'adult' || mode === 'adu' || mode === '0' || type === '0'
  htmlPage.value = isAdult ? 'report-v3.html' : 'report-kid.html'
  // assessment_id 保留在 URL，后续可做数据注入
})
</script>
