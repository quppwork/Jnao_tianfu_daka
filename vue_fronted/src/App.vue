<template>
  <view v-if="showSplash" class="splash">
    <view class="splash-inner">
      <text class="splash-logo-j">J</text>
      <view class="splash-logo-row">
        <text class="splash-logo-nao">nao</text>
        <text class="splash-logo-ai">AI</text>
      </view>
      <text class="splash-sub">天赋成长平台</text>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { onLaunch, onShow } from '@dcloudio/uni-app'
import { bootstrapAppSession } from '@/utils/userApi.js'
import { rememberCurrentRoute } from '@/utils/appSession.js'
import { startAppUpdateWatcher } from '@/utils/appUpdate.js'

const showSplash = ref(false)

onLaunch(() => {
  bootstrapAppSession().catch(() => {})
  startAppUpdateWatcher()
  // Splash：同浏览器会话只展示一次；2分钟内回来走 bfcache 不展示
  const SESSION_KEY = 'jnao_splash_session'
  const ACTIVE_KEY = 'jnao_last_active'
  const SHORT_TTL = 2 * 60 * 1000  // 2 分钟：覆盖切微信/接电话等短暂离开

  if (sessionStorage.getItem(SESSION_KEY)) return  // 同会话已展示过

  const now = Date.now()
  let last = 0
  try { last = parseInt(localStorage.getItem(ACTIVE_KEY) || '0', 10) } catch (_) {}
  try { localStorage.setItem(ACTIVE_KEY, String(now)) } catch (_) {}

  if (!last || (now - last) > SHORT_TTL) {
    showSplash.value = true
    sessionStorage.setItem(SESSION_KEY, '1')
    setTimeout(() => { showSplash.value = false }, 2000)
  }

  // 动画降级：系统偏好 + 极端低端硬件（其余靠页面级 FPS 实测）
  try {
    const reduce =
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ||
      (navigator.hardwareConcurrency || 8) <= 2 ||
      (navigator.deviceMemory || 8) <= 2
    if (reduce) document.documentElement.setAttribute('data-reduced-motion', '')
  } catch (_) {}
})

onShow(() => {
  rememberCurrentRoute()
})
</script>

<style>
.splash {
  position: fixed; inset: 0; z-index: 9999;
  background: linear-gradient(135deg, #0b111e 0%, #1a1040 100%);
  display: flex; align-items: center; justify-content: center;
  animation: splashOut 0.4s ease-in 1.8s forwards;
}
.splash-inner { text-align: center; animation: splashIn 0.5s ease-out; }
@keyframes splashIn { from { opacity:0; transform:scale(0.9); } to { opacity:1; transform:scale(1); } }
@keyframes splashOut { to { opacity:0; pointer-events:none; } }

.splash-logo-j {
  color: #dc2626; font-size: 72px; font-weight: 800;
  text-shadow: 0 0 40px rgba(220,38,38,0.4);
  display: block; line-height: 1;
}
.splash-logo-row { display: flex; align-items: baseline; justify-content: center; gap: 4px; margin-top: 4px; }
.splash-logo-nao { color: #fff; font-size: 48px; font-weight: 700; }
.splash-logo-ai { color: #fff; font-size: 48px; font-weight: 300; }
.splash-sub {
  color: rgba(255,255,255,0.5); font-size: 14px;
  display: block; margin-top: 12px; letter-spacing: 0.2em;
}
</style>

<!-- 全局容器：手机自然宽度，不做额外断点变动 -->
<style>
:root {
  --app-max-width: 480px;  /* 仅对平板做上限，手机 360-430 不受影响 */
}

/* 横屏手机：宽高比翻转，不限宽度 */
@media (orientation: landscape) and (max-height: 500px) {
  :root {
    --app-max-width: 100%;
  }
}

/* 全面屏 / 刘海屏 / 底部 Home Indicator 安全区 */
body {
  padding-bottom: env(safe-area-inset-bottom, 0px);
  padding-top: env(safe-area-inset-top, 0px);
}

/* ── 全局动画降级：系统偏好 或 低端设备 ── */
/* 规则1: 系统设置"减少动态效果" */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
  [class*="backdrop"],
  [style*="backdrop"] {
    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
  }
}
/* 规则2: JS 检测到低端设备 */
[data-reduced-motion] *,
[data-reduced-motion] *::before,
[data-reduced-motion] *::after {
  animation-duration: 0.01ms !important;
  animation-iteration-count: 1 !important;
  transition-duration: 0.01ms !important;
}
/* 关闭 blur——移动端 GPU 最大消耗源 */
[data-reduced-motion] .card,
[data-reduced-motion] [class*="blur"],
[data-reduced-motion] .bbar {
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
}
/* 关闭无限旋转/脉冲（loading spinner 保留基础显示） */
[data-reduced-motion] .loading-spinner,
[data-reduced-motion] [class*="spin"],
[data-reduced-motion] [class*="pulse"] {
  animation: none !important;
}
</style>
