<template>
  <view class="app">
    <view class="card">
      <view class="logo-row">
        <text class="logo-j">J</text><text class="logo-nao">nao</text><text class="logo-ai">AI</text>
      </view>
      <text class="subtitle">注册新账号</text>

      <view class="form">
        <view class="input-wrap">
          <text class="input-icon">📱</text>
          <input class="login-input" v-model="form.phone" placeholder="手机号" type="number" />
        </view>
        <view class="input-wrap">
          <text class="input-icon">👤</text>
          <input class="login-input" v-model="form.name" placeholder="输入昵称（必填）" />
        </view>

        <view class="btn-login" @click="doRegister">
          <text>{{ submitting ? '注册中...' : '注册并登录' }}</text>
        </view>

        <view class="btn-back" @click="goBack">
          <text>← 返回登录</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { registerChild, saveProfile, fetchProfile } from '@/utils/userApi.js'

const form = ref({ name: '', phone: '' })
const submitting = ref(false)

async function doRegister() {
  if (!form.value.name.trim()) {
    uni.showToast({ title: '请输入昵称', icon: 'none' })
    return
  }
  if (!form.value.phone.trim() || form.value.phone.trim().length < 11) {
    uni.showToast({ title: '请输入正确的手机号', icon: 'none' })
    return
  }
  submitting.value = true
  try {
    const data = await registerChild(form.value.phone.trim(), form.value.name.trim())
    try {
      const p = await fetchProfile(data.child_user_id)
      await saveProfile(data.child_user_id, {
        profile_json: { ...(p.profile_json || {}), role: 'student' },
      })
    } catch (_) { /* ignore */ }
    localStorage.setItem('jnao_user', JSON.stringify({
      name: data.nickname,
      phone: data.parent_phone,
      role: 'student',
      loginTime: new Date().toISOString()
    }))
    localStorage.setItem('jnao_logged_in', '1')
    uni.showToast({ title: '注册成功，' + data.nickname + '！', icon: 'none' })
    setTimeout(() => { uni.redirectTo({ url: '/pages/login/onboarding' }) }, 500)
  } catch (e) {
    submitting.value = false
    uni.showToast({ title: '注册失败，请稍后重试', icon: 'none' })
  }
}

function goBack() {
  uni.navigateBack()
}
</script>

<style scoped>
.app { height:100vh; max-width:480px; margin:0 auto; background:var(--bg); display:flex; align-items:center; justify-content:center; padding:30px; font-family:-apple-system,"PingFang SC",sans-serif; }
.card { width:100%; }
.logo-row { display:flex; align-items:baseline; justify-content:center; gap:6px; margin-bottom:6px; }
.logo-j { color:#dc2626; font-size:44px; font-weight:800; }
.logo-nao { color:var(--text); font-size:34px; font-weight:700; }
.logo-ai { color:var(--text); font-size:34px; font-weight:300; }
.subtitle { color:var(--text-dim); font-size:13px; text-align:center; display:block; margin-bottom:28px; letter-spacing:0.06em; }
.form { }
.input-wrap { display:flex; align-items:center; background:var(--bg-card); border-radius:14px; padding:0 14px; margin-bottom:12px; border:1.5px solid var(--border); }
.input-icon { font-size:16px; margin-right:10px; }
.login-input { flex:1; padding:14px 0; font-size:15px; color:var(--text); }
.btn-login { background:linear-gradient(135deg,var(--accent),#3b8bff); border-radius:14px; padding:15px; text-align:center; cursor:pointer; }
.btn-login text { color:#fff; font-size:16px; font-weight:700; }
.btn-login:active { opacity:0.85; }
.btn-back { border:1.5px solid var(--border); border-radius:14px; padding:13px; text-align:center; cursor:pointer; margin-top:10px; }
.btn-back text { color:var(--text-dim); font-size:14px; font-weight:500; }
.btn-back:active { background:var(--bg-card); }
</style>
