<template>
  <view class="dayu-frame-wrap">
    <!-- #ifdef H5 -->
    <iframe
      class="dayu-iframe"
      :src="src"
      frameborder="0"
      allow="autoplay; fullscreen"
      @load="onLoad"
    />
    <!-- #endif -->
    <!-- #ifndef H5 -->
    <web-view :src="src" />
    <!-- #endif -->
  </view>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { switchMainTab } from '@/utils/mainTabs.js'

const props = defineProps({
  page: { type: String, required: true },
})

const src = `/static/dayu/html/${props.page}`

function handleMessage(ev) {
  const data = ev?.data
  if (!data || data.type !== 'dayu-nav' || !data.path) return
  let path = String(data.path)
  const base = path.split('?')[0]
  const tabBases = [
    '/pages/dayu/home',
    '/pages/index',
    '/pages/training/dayu',
    '/pages/training/index',
    '/pages/qa/dayu',
    '/pages/qa/index',
    '/pages/hub/academy',
    '/pages/hub/console',
  ]
  if (base === '/pages/training/index') path = '/pages/training/dayu'
  if (base === '/pages/qa/index' && !path.includes('?')) path = '/pages/qa/dayu'
  if (base === '/pages/index' && path.includes('chat=1')) {
    uni.navigateTo({ url: path })
    return
  }
  if (tabBases.includes(path.split('?')[0])) {
    switchMainTab(path)
    return
  }
  uni.navigateTo({ url: path })
}

function onLoad() {
  /* iframe ready */
}

onMounted(() => {
  // #ifdef H5
  window.addEventListener('message', handleMessage)
  // #endif
})

onUnmounted(() => {
  // #ifdef H5
  window.removeEventListener('message', handleMessage)
  // #endif
})
</script>

<style scoped>
.dayu-frame-wrap {
  width: 100%;
  height: 100vh;
  height: 100dvh;
  max-width: var(--app-max-width, 480px);
  margin: 0 auto;
  background: #07090e;
  overflow: hidden;
}
.dayu-iframe {
  width: 100%;
  height: 100%;
  border: 0;
  display: block;
  background: #07090e;
}
</style>
