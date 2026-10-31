<template>
  <view class="app">
    <text class="hint">正在跳转到注册页…</text>
  </view>
</template>

<script setup>
import { onLoad } from '@dcloudio/uni-app'

function redirectToRegister(bindTicket = '', phone = '') {
  const params = new URLSearchParams()
  params.set('from', 'wechat')
  if (bindTicket) params.set('bind_ticket', bindTicket)
  if (phone) params.set('phone', phone)
  const q = params.toString()
  uni.reLaunch({ url: `/pages/login/register-parent${q ? `?${q}` : ''}` })
}

onLoad((opts) => {
  let bindTicket = opts?.bind_ticket ? String(opts.bind_ticket) : ''
  let phone = opts?.phone ? String(opts.phone) : ''
  if (!bindTicket || !phone) {
    try {
      const q = new URLSearchParams(window.location.search)
      if (!bindTicket) bindTicket = q.get('bind_ticket') || ''
      if (!phone) phone = q.get('phone') || ''
    } catch (_) { /* ignore */ }
  }
  redirectToRegister(bindTicket, phone)
})
</script>

<style scoped>
.app {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg);
}
.hint { color: var(--text-dim); font-size: 14px; }
</style>
