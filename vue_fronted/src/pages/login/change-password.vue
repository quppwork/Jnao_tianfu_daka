<template>
  <view class="app">
    <view class="card">
      <text class="title">请修改密码</text>
      <text class="hint">当前密码强度不足，请设置新密码后继续使用</text>
      <text class="rule">要求：8-32 位，同时包含大写字母、小写字母和数字（可不含特殊字符）</text>

      <view class="form">
        <view class="input-wrap">
          <input v-model="form.oldPassword" class="inp" placeholder="当前密码" type="password" :disabled="busy" />
        </view>
        <view class="input-wrap">
          <input v-model="form.newPassword" class="inp" placeholder="新密码" type="password" :disabled="busy" />
        </view>
        <view class="input-wrap">
          <input v-model="form.confirm" class="inp" placeholder="确认新密码" type="password" :disabled="busy" />
        </view>
        <view class="btn-primary" :class="{ off: busy }" @click="submit">
          <text>{{ busy ? '提交中…' : '确认修改' }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { changePassword, requirePageAuth } from '@/utils/userApi.js'

const form = ref({ oldPassword: '', newPassword: '', confirm: '' })
const busy = ref(false)
let authKind = 'student'

onLoad(async () => {
  const snap = await requirePageAuth('student')
  if (snap.ok) {
    authKind = 'student'
    return
  }
  const parent = await requirePageAuth('parent')
  if (parent.ok) authKind = 'parent'
})

async function submit() {
  if (busy.value) return
  const { oldPassword, newPassword, confirm } = form.value
  if (!oldPassword || !newPassword) {
    uni.showToast({ title: '请填写完整', icon: 'none' })
    return
  }
  if (newPassword !== confirm) {
    uni.showToast({ title: '两次新密码不一致', icon: 'none' })
    return
  }
  busy.value = true
  try {
    const data = await changePassword(oldPassword, newPassword)
    uni.showToast({ title: '密码已更新', icon: 'none' })
    const home = data.role === 'parent' ? '/pages/parent/index' : '/pages/index'
    setTimeout(() => uni.reLaunch({ url: home }), 400)
  } catch (e) {
    uni.showToast({ title: e.message || '修改失败', icon: 'none' })
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.app { min-height: 100vh; padding: 48rpx 32rpx; background: var(--bg, #f5f6f8); }
.card { background: #fff; border-radius: 24rpx; padding: 40rpx 32rpx; box-shadow: 0 8rpx 32rpx rgba(0,0,0,.06); }
.title { display: block; font-size: 36rpx; font-weight: 600; margin-bottom: 16rpx; }
.hint { display: block; font-size: 28rpx; color: #666; margin-bottom: 12rpx; }
.rule { display: block; font-size: 24rpx; color: #999; margin-bottom: 32rpx; line-height: 1.5; }
.input-wrap { margin-bottom: 24rpx; }
.inp { width: 100%; height: 88rpx; padding: 0 24rpx; border: 1px solid #e5e7eb; border-radius: 12rpx; font-size: 28rpx; box-sizing: border-box; }
.btn-primary { margin-top: 16rpx; height: 88rpx; line-height: 88rpx; text-align: center; background: #2563eb; color: #fff; border-radius: 12rpx; font-size: 30rpx; }
.btn-primary.off { opacity: .6; }
</style>
