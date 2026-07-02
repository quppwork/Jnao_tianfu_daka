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
import { ref } from 'vue'
import { onLaunch } from '@dcloudio/uni-app'

const showSplash = ref(false)

onLaunch(() => {
  // 冷启动才显示，热启动（后台切回）跳过
  const shown = sessionStorage.getItem('jnao_splash_shown')
  if (!shown) {
    sessionStorage.setItem('jnao_splash_shown', '1')
    showSplash.value = true
    setTimeout(() => { showSplash.value = false }, 2000)
  }
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
