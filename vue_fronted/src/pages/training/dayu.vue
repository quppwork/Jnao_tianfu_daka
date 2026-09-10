<template>
  <view class="wrap">
    <dayu-frame page="train.html" />
  </view>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import DayuFrame from '@/components/dayu-frame/dayu-frame.vue'
import { switchMainTab } from '@/utils/mainTabs.js'

function onMsg(ev) {
  const data = ev?.data
  if (!data) return
  if (data.type === 'dayu-train-confirm') {
    const minutes = Math.max(15, Number(data.minutes) || 480)
    uni.navigateTo({
      url: `/pages/training/index?dayu_minutes=${minutes}`,
    })
    return
  }
  if (data.type === 'dayu-nav' && data.path) {
    const path = String(data.path)
    const base = path.split('?')[0]
    if (
      [
        '/pages/index',
        '/pages/training/dayu',
        '/pages/training/index',
        '/pages/qa/index',
        '/pages/qa/dayu',
        '/pages/hub/academy',
        '/pages/hub/console',
      ].includes(base)
    ) {
      // map demo train.html tab to dayu entry
      if (base === '/pages/training/index') {
        switchMainTab('/pages/training/dayu')
        return
      }
      switchMainTab(path.startsWith('/pages/training') ? '/pages/training/dayu' : path)
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
