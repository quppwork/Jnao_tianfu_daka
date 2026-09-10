<template>
  <view class="dayu-frame-wrap">
    <!-- #ifdef H5 -->
    <iframe
      ref="iframeRef"
      class="dayu-iframe"
      :src="src"
      frameborder="0"
      allow="autoplay; fullscreen"
      @load="onFrameLoad"
    />
    <!-- #endif -->
    <!-- #ifndef H5 -->
    <web-view :src="src" />
    <!-- #endif -->
  </view>
</template>

<script setup>
import { onMounted, onUnmounted, ref, watch, computed } from 'vue'
import { switchMainTab } from '@/utils/mainTabs.js'
import { goLinkedParentHome, goLinkedStudentHome } from '@/utils/switchLinkedAccount.js'

const props = defineProps({
  page: { type: String, required: true },
  /** 注入 iframe：昵称 / 主题 / 今日状态文案 */
  hydrate: {
    type: Object,
    default: () => ({}),
  },
})

const emit = defineEmits(['parent', 'student', 'account', 'theme'])

const src = computed(() => `/static/dayu/html/${props.page}`)
const iframeRef = ref(null)
let frameReady = false

function postToFrame(payload) {
  // #ifdef H5
  try {
    let win = null
    const el = iframeRef.value
    if (el) {
      win = el.contentWindow || el.$el?.contentWindow || null
    }
    if (!win) {
      const node = document.querySelector('.dayu-iframe')
      win = node?.contentWindow || null
    }
    if (win) win.postMessage(payload, '*')
  } catch (_) { /* ignore */ }
  // #endif
}

function pushHydrate() {
  if (!frameReady) return
  const h = props.hydrate || {}
  postToFrame({
    type: 'dayu-hydrate',
    nickname: h.nickname || '',
    theme: h.theme || '',
    situationLabel: h.situationLabel || '',
    welcome: h.welcome || '',
  })
}

function handleMessage(ev) {
  const data = ev?.data
  if (!data || typeof data !== 'object') return

  if (data.type === 'dayu-parent') {
    emit('parent')
    goLinkedParentHome()
    return
  }
  if (data.type === 'dayu-student') {
    emit('student')
    goLinkedStudentHome()
    return
  }
  if (data.type === 'dayu-toast') {
    uni.showToast({ title: data.title || '功能即将开放', icon: 'none' })
    return
  }
  if (data.type === 'dayu-account') {
    emit('account')
    return
  }
  if (data.type === 'dayu-theme') {
    const light = !!data.light
    try {
      const theme = light ? 'white' : 'dark'
      localStorage.setItem('jnao_theme', theme)
      localStorage.setItem('jn_theme', light ? 'lt' : 'dk')
      document.documentElement.setAttribute('data-theme', theme)
    } catch (_) { /* ignore */ }
    emit('theme', light)
    return
  }
  if (data.type === 'dayu-ready') {
    frameReady = true
    pushHydrate()
    return
  }
  if (data.type === 'dayu-back') {
    const pages = getCurrentPages()
    if (pages.length > 1) uni.navigateBack({ delta: 1 })
    else uni.reLaunch({ url: '/pages/dayu/home' })
    return
  }

  const parentShellPages = new Set([
    'parent.html',
    'pset.html',
    'pdata.html',
    'consult.html',
    'community.html',
    'pcourse.html',
  ])
  const parentShellRoutes = {
    '/pages/parent/dayu': true,
    '/pages/parent/pset': true,
    '/pages/parent/pdata': true,
    '/pages/parent/consult': true,
    '/pages/parent/community': true,
    '/pages/parent/pcourse': true,
  }

  if (data.type !== 'dayu-nav' || !data.path) return
  let path = String(data.path)
  const base = path.split('?')[0]
  // 旧 /pages/index 对话页已废弃 → 大宇首页
  if (base === '/pages/index') {
    switchMainTab('/pages/dayu/home')
    return
  }
  if (base === '/pages/training/index') path = '/pages/training/dayu'
  if (base === '/pages/qa/index' && !path.includes('?')) path = '/pages/qa/dayu'
  // 家长账户登录入口 / 切到关联家长版
  if (path.includes('role=parent')) {
    emit('parent')
    goLinkedParentHome()
    return
  }
  if (parentShellRoutes[base]) {
    // 底栏页用 reLaunch；子页（家长课堂）用 navigateTo，失败再 reLaunch
    const stackOnly = base === '/pages/parent/pcourse'
    if (stackOnly) {
      uni.navigateTo({
        url: path,
        fail: () => uni.reLaunch({ url: path }),
      })
    } else {
      uni.reLaunch({ url: base })
    }
    return
  }
  if (base === '/pages/parent/index') {
    // 学生侧旧映射：改为切家长版；家长壳内「孩子账户管理」进管理中心
    if (parentShellPages.has(props.page)) {
      uni.navigateTo({ url: path })
    } else {
      emit('parent')
      goLinkedParentHome()
    }
    return
  }

  // 家长版壳内：学生业务页尚未对家长开放，留在本页提示，避免鉴权踢登录
  // 天赋测试 hub/index 允许进入（测评页会按角色处理）
  if (parentShellPages.has(props.page)) {
    const studentOnly = [
      '/pages/dayu/home',
      '/pages/training/dayu',
      '/pages/qa/dayu',
      '/pages/hub/academy',
      '/pages/hub/console',
      '/pages/hub/courses',
      '/pages/hub/story',
    ]
    if (studentOnly.includes(base)) {
      uni.showToast({ title: '功能即将开放', icon: 'none' })
      return
    }
  }

  const tabBases = [
    '/pages/dayu/home',
    '/pages/training/dayu',
    '/pages/qa/dayu',
    '/pages/hub/academy',
    '/pages/hub/console',
  ]
  if (tabBases.includes(path.split('?')[0])) {
    switchMainTab(path)
    return
  }
  uni.navigateTo({ url: path })
}

function onFrameLoad() {
  frameReady = true
  pushHydrate()
}

watch(
  () => props.hydrate,
  () => pushHydrate(),
  { deep: true },
)

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
