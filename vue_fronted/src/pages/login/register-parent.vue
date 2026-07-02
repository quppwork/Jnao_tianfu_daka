<template>
  <view class="app">
    <view class="card">
      <view class="logo-row">
        <text class="logo-j">J</text><text class="logo-nao">nao</text><text class="logo-ai">AI</text>
      </view>
      <text class="subtitle">注册家长账户</text>

      <view class="form">
        <view class="input-wrap">
          <text class="input-icon">👤</text>
          <input class="login-input" v-model="form.name" placeholder="输入昵称（必填）" />
        </view>
        <view class="input-wrap">
          <text class="input-icon">📱</text>
          <input class="login-input" v-model="form.phone" placeholder="手机号（必填）" type="number" />
        </view>
        <view class="input-wrap">
          <text class="input-icon">🔒</text>
          <input class="login-input" v-model="form.password" placeholder="设置密码（至少6位）" type="password" />
        </view>
        <view class="input-wrap">
          <text class="input-icon">🔒</text>
          <input class="login-input" v-model="form.confirm" placeholder="再次输入密码" type="password" />
        </view>

        <view class="hint-text">
          <text>注册即代表您同意《用户协议》和《隐私政策》</text>
        </view>

        <view class="btn-login" @click="doRegister">
          <text>{{ submitting ? '注册中...' : '注册并进入家长中心' }}</text>
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
import { registerParent } from '@/utils/userApi.js'

const form = ref({ name: '', phone: '', password: '', confirm: '' })
const submitting = ref(false)

async function doRegister() {
  if (!form.value.name.trim()) { uni.showToast({ title: '请输入昵称', icon: 'none' }); return }
  if (!form.value.phone.trim() || form.value.phone.trim().length < 11) { uni.showToast({ title: '请输入正确的手机号', icon: 'none' }); return }
  if (!form.value.password.trim() || form.value.password.trim().length < 6) { uni.showToast({ title: '密码至少6位', icon: 'none' }); return }
  if (form.value.password.trim() !== form.value.confirm.trim()) { uni.showToast({ title: '两次密码不一致', icon: 'none' }); return }

  submitting.value = true
  try {
    const data = await registerParent(
      form.value.phone.trim(),
      form.value.name.trim(),
      form.value.password.trim(),
    )
    localStorage.setItem('jnao_user', JSON.stringify({
      id: data.child_user_id,
      name: data.nickname,
      phone: data.parent_phone,
      role: 'parent',
      loginTime: new Date().toISOString(),
    }))
    localStorage.setItem('jnao_logged_in', '1')
    uni.showToast({ title: '注册成功！欢迎，' + data.nickname, icon: 'none' })
    setTimeout(() => { uni.redirectTo({ url: '/pages/parent/index' }) }, 600)
  } catch (e) {
    submitting.value = false
    if (e.status === 409) uni.showToast({ title: '该手机号已注册', icon: 'none' })
    else if (!e.status) uni.showToast({ title: '无法连接服务器，请确认后端已启动', icon: 'none', duration: 2500 })
    else uni.showToast({ title: e.message || '注册失败，请稍后重试', icon: 'none' })
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
.input-wrap { display:flex; align-items:center; background:var(--bg-card); border-radius:14px; padding:0 14px; margin-bottom:12px; border:1.5px solid var(--border); }
.input-wrap:focus-within { border-color:#a78bfa; }
.input-icon { font-size:16px; margin-right:10px; }
.login-input { flex:1; padding:14px 0; font-size:15px; color:var(--text); }
.hint-text { text-align:center; margin:4px 0 16px; }
.hint-text text { color:var(--text-dim); font-size:11px; opacity:0.6; }
.btn-login { background:linear-gradient(135deg, #8b5cf6, #7c3aed); border-radius:14px; padding:15px; text-align:center; cursor:pointer; box-shadow:0 4px 20px rgba(139,92,246,0.25); }
.btn-login text { color:#fff; font-size:16px; font-weight:700; }
.btn-login:active { opacity:0.85; }
.btn-back { border:1.5px solid var(--border); border-radius:14px; padding:13px; text-align:center; cursor:pointer; margin-top:10px; }
.btn-back text { color:var(--text-dim); font-size:14px; font-weight:500; }
.btn-back:active { background:var(--bg-card); }
</style>
