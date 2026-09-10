<template>
  <view class="wrap">
    <dayu-frame page="train.html" />
  </view>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import DayuFrame from '@/components/dayu-frame/dayu-frame.vue'

/** 修炼壳：确认时长后进入真实训练页（底栏由 dayu-frame 统一处理） */
function onMsg(ev) {
  const data = ev?.data
  if (!data || data.type !== 'dayu-train-confirm') return
  const minutes = Math.max(15, Number(data.minutes) || 480)
  uni.navigateTo({
    url: `/pages/training/index?dayu_minutes=${minutes}`,
  })
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
