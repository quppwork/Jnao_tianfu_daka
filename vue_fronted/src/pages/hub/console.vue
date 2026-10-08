<template>
  <dayu-frame page="milestone.html?v=console6" :hydrate="hydrate" />
</template>

<script setup>
import { onShow } from '@dcloudio/uni-app'
import { nextTick, reactive } from 'vue'
import DayuFrame from '@/components/dayu-frame/dayu-frame.vue'
import { ensureChildUser, fetchGrowthConsole } from '@/utils/userApi.js'

const hydrate = reactive({
  nickname: '',
  theme: '',
  console: null,
})

let loading = false
let loadedOnce = false

async function loadConsole({ force = false } = {}) {
  if (loading) return
  if (loadedOnce && !force && hydrate.console) return
  loading = true
  try {
    const theme = localStorage.getItem('jn_theme') || ''
    hydrate.theme = theme === 'lt' ? 'lt' : ''
  } catch (_) { /* ignore */ }

  try {
    const uid = await ensureChildUser()
    const data = await fetchGrowthConsole(uid)
    hydrate.console = data
    loadedOnce = true
    try {
      window.__DAYU_CONSOLE__ = data
    } catch (_) { /* ignore */ }
    if (data?.ladder?.me?.name) {
      hydrate.nickname = data.ladder.me.name
    }
    await nextTick()
  } catch (e) {
    console.warn('[console] load failed', e?.message || e)
    uni.showToast({
      title: e?.message || '中央电脑数据加载失败',
      icon: 'none',
      duration: 2500,
    })
  } finally {
    loading = false
  }
}

onShow(() => {
  loadConsole({ force: false })
})

loadConsole({ force: true })
</script>
