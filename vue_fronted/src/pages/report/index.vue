<template>
  <dayu-frame :page="htmlPage" :back-path="backPath" />
</template>
<script setup>
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import DayuFrame from '@/components/dayu-frame/dayu-frame.vue'

/** 一比一复刻 kimi report-kid / report-v3；旧 Vue 报告 UI 已下线 */
const htmlPage = ref('report-kid.html')
/** 做什么报告回什么页：儿童→训练/天赋；成人→天赋大厅 */
const backPath = ref('')

function resolveBackPath(from, isAdult) {
  const f = String(from || '').toLowerCase()
  if (f === 'training') return '/pages/training/dayu'
  if (f === 'onboarding') return '/pages/dayu/home'
  if (f === 'hub' || f === 'talent') return '/pages/talent/hub'
  // 默认：儿童卷回训练，成人卷回天赋大厅
  return isAdult ? '/pages/talent/hub' : '/pages/training/dayu'
}

onLoad((opts) => {
  const mode = String(opts?.mode || '').toLowerCase()
  const type = String(opts?.type ?? '')
  const isAdult =
    mode === 'adult' || mode === 'adu' || mode === '0' || type === '0'
  // lock=1：报告页内禁止儿童/成人版互跳
  htmlPage.value = (isAdult ? 'report-v3.html' : 'report-kid.html') + '?lock=1&v=rpt1'
  backPath.value = resolveBackPath(opts?.from, isAdult)
})
</script>
