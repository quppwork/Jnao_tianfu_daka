<template>
  <view class="dayu-frame-wrap">
    <!-- #ifdef H5 -->
    <iframe
      ref="iframeRef"
      class="dayu-iframe"
      :src="src"
      frameborder="0"
      scrolling="no"
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
import { fetchUsageSummary, formatTokenCount } from '@/utils/api/usage.js'

const USAGE_PILL_PAGES = new Set(['parent.html', 'pset.html'])

const props = defineProps({
  page: { type: String, required: true },
  /** 注入 iframe：昵称 / 主题 / 今日状态文案 */
  hydrate: {
    type: Object,
    default: () => ({}),
  },
  /** 有值时 dayu-back 直达该页（做什么报告回什么页） */
  backPath: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['parent', 'student', 'account', 'theme'])

const src = computed(() => `/static/dayu/html/${props.page}`)
const iframeRef = ref(null)
let frameReady = false

function postToFrame(payload) {
  // #ifdef H5
  try {
    if (payload && payload.type === 'dayu-console' && payload.console) {
      window.__DAYU_CONSOLE__ = payload.console
    }
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

function syncFrameLayoutVars() {
  // #ifdef H5
  try {
    let win = null
    const el = iframeRef.value
    if (el) win = el.contentWindow || el.$el?.contentWindow || null
    if (!win) {
      const node = document.querySelector('.dayu-iframe')
      win = node?.contentWindow || null
    }
    if (!win?.document?.documentElement) return
    const maxW =
      getComputedStyle(document.documentElement).getPropertyValue('--app-max-width').trim() ||
      '480px'
    win.document.documentElement.style.setProperty('--app-max-width', maxW)

    // iframe 内 env(safe-area-*) 常为 0，用父页实测值对齐底栏高度
    let sab = '0px'
    try {
      const probe = document.createElement('div')
      probe.style.cssText =
        'position:fixed;visibility:hidden;pointer-events:none;padding-bottom:env(safe-area-inset-bottom,0px)'
      document.body.appendChild(probe)
      sab = getComputedStyle(probe).paddingBottom || '0px'
      probe.remove()
    } catch (_) { /* ignore */ }

    const parentPages = new Set([
      'parent.html',
      'pset.html',
      'pdata.html',
      'consult.html',
      'community.html',
      'pcourse.html',
    ])
    const isParent = parentPages.has(String(props.page || ''))
    const mute = isParent ? '#8B93A5' : '#5A6274'
    const on = isParent ? '#F5D9A8' : '#6FCF8E'
    const ltMute = '#8b93a5'
    const ltOn = isParent ? '#967536' : '#30904f'

    const style = win.document.getElementById('dayu-foot-sync') || win.document.createElement('style')
    style.id = 'dayu-foot-sync'
    style.textContent = [
      `.foot{left:0!important;right:0!important;transform:none!important;`,
      `width:100%!important;max-width:none!important;margin:0!important;`,
      `padding:8px 10px calc(8px + ${sab})!important;`,
      `box-sizing:border-box!important}`,
      `.foot a{padding:0!important;gap:0!important;font-size:11px!important;font-weight:400!important;`,
      `color:${mute}!important;display:block!important;min-width:0!important}`,
      `.foot a.on{color:${on}!important;font-weight:700!important}`,
      `html.lt .foot a{color:${ltMute}!important}`,
      `html.lt .foot a.on{color:${ltOn}!important}`,
      `.foot a img,.foot .fic,.foot a .fic,.fic{width:38px!important;height:38px!important;`,
      `display:block!important;margin:0 auto 1px!important;object-fit:contain!important}`,
      `.askbar{left:0!important;right:0!important;transform:none!important;`,
      `width:100%!important;max-width:none!important;margin:0 auto!important;`,
      `bottom:calc(72px + ${sab})!important;box-sizing:border-box!important}`,
      `html,body{height:100%!important;overflow:hidden!important;overflow-x:hidden!important;`,
      `scrollbar-width:none!important;-ms-overflow-style:none!important}`,
      `html::-webkit-scrollbar,body::-webkit-scrollbar,*::-webkit-scrollbar{display:none!important;width:0!important;height:0!important}`,
      `*{scrollbar-width:none!important;-ms-overflow-style:none!important}`,
      `.phone,.wrap{overflow-x:hidden!important;overflow-y:auto!important;`,
      `height:100%!important;max-height:100%!important;box-sizing:border-box!important;`,
      `scrollbar-width:none!important;-ms-overflow-style:none!important}`,
      `.phone::-webkit-scrollbar,.wrap::-webkit-scrollbar{display:none!important;width:0!important;height:0!important}`,
    ].join('')
    if (!style.parentNode) win.document.head.appendChild(style)
  } catch (_) { /* ignore */ }
  // #endif
}

function pushHydrate() {
  if (!frameReady) return
  syncFrameLayoutVars()
  const h = props.hydrate || {}
  postToFrame({
    type: 'dayu-hydrate',
    nickname: h.nickname || '',
    theme: h.theme || '',
    situationLabel: h.situationLabel || '',
    welcome: h.welcome || '',
  })
  if (h.console) {
    postToFrame({ type: 'dayu-console', console: h.console })
  }
  pushUsage()
}

async function pushUsage() {
  if (!frameReady) return
  if (!USAGE_PILL_PAGES.has(String(props.page || ''))) return
  try {
    const data = await fetchUsageSummary()
    const total = Number(data?.display_total_tokens) || 0
    postToFrame({
      type: 'dayu-usage',
      display_total_tokens: total,
      label: formatTokenCount(total),
      role: data?.role || '',
      me: data?.me || null,
      billing: data?.billing || null,
    })
  } catch (_) {
    /* 未登录或暂无用量时保持占位 */
  }
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
  if (data.type === 'dayu-usage-request') {
    pushUsage()
    return
  }
  if (data.type === 'dayu-console-request') {
    frameReady = true
    pushHydrate()
    return
  }
  if (data.type === 'dayu-back') {
    const target = String(props.backPath || '').trim()
    if (target) {
      uni.reLaunch({ url: target })
      return
    }
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
  syncFrameLayoutVars()
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
/* 与 Vue 页 fixed 底栏同一视口盒，避免切换时底栏上下/宽窄跳动 */
.dayu-frame-wrap {
  position: fixed;
  top: 0;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: var(--app-max-width, 480px);
  background: #07090e;
  overflow: hidden;
  z-index: 1;
  box-sizing: border-box;
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.dayu-iframe {
  width: 100%;
  height: 100%;
  border: 0;
  display: block;
  background: #07090e;
  overflow: hidden;
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.dayu-iframe::-webkit-scrollbar {
  display: none;
  width: 0;
  height: 0;
}
</style>
