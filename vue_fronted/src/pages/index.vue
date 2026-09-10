<template>
  <view class="redirect">
    <text>正在进入大宇首页…</text>
  </view>
</template>

<script setup>
import { onLoad } from '@dcloudio/uni-app'

/** 旧引导对话页已废弃，统一进入图二大宇首页 */
onLoad(() => {
  uni.reLaunch({ url: '/pages/dayu/home' })
})
</script>

<style scoped>
.redirect {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #8b93a5;
  font-size: 14px;
  background: #0b0e14;
}
</style>
