<template>
  <view class="wrap">
    <dayu-frame page="answer.html" />
  </view>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import DayuFrame from '@/components/dayu-frame/dayu-frame.vue'
import { switchMainTab } from '@/utils/mainTabs.js'

function onMsg(ev) {
  const data = ev?.data
  if (!data) return
  if (data.type === 'dayu-nav' && data.path) {
    let path = String(data.path)
    if (path.startsWith('/pages/qa/index')) {
      uni.navigateTo({ url: path })
      return
    }
    const base = path.split('?')[0]
    if (base === '/pages/training/index') path = '/pages/training/dayu'
    if (base === '/pages/qa/index') path = '/pages/qa/dayu'
    const tabs = [
      '/pages/index',
      '/pages/training/dayu',
      '/pages/qa/dayu',
      '/pages/hub/academy',
      '/pages/hub/console',
    ]
    if (tabs.includes(base) || tabs.includes(path.split('?')[0])) {
      switchMainTab(path)
      return
    }
    uni.navigateTo({ url: path })
  }
}

onMounted(() => {
  // #ifdef H5
  window.addEventListener('message', onMsg)
  // #endif
})
onUnmounted(() => {
  // #ifdef H5
  window.removeEventListener('message', onMsg)
  // #endif
})
</script>

<style scoped>
.wrap {
  height: 100vh;
  height: 100dvh;
  background: #07090e;
}
</style>
