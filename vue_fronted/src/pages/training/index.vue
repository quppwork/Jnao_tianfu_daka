<template>
  <view class="redirect">
    <text>正在进入今日修炼…</text>
  </view>
</template>
<script setup>
/**
 * 旧版今日训练页已下线，统一进入大宇新版 /pages/training/dayu
 * 保留本路由仅作深链兼容。
 */
import { onLoad } from '@dcloudio/uni-app'

onLoad(() => {
  uni.reLaunch({ url: '/pages/training/dayu' })
})
</script>
<style scoped>
.redirect {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0b0e14;
  color: #8b93a5;
  font-size: 14px;
}
</style>
