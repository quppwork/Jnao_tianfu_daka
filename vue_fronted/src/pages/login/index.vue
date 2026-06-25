<template>
  <view class="app">
    <view class="card">
      <view class="logo-row">
        <text class="logo-j">J</text><text class="logo-nao">nao</text><text class="logo-ai">AI</text>
      </view>
      <text class="subtitle">天赋成长平台</text>

      <!-- Input -->
      <view class="form">
        <view class="input-wrap">
          <text class="input-icon">👤</text>
          <input class="login-input" v-model="form.name" placeholder="输入昵称" />
        </view>
        <view class="input-wrap">
          <text class="input-icon">📱</text>
          <input class="login-input" v-model="form.phone" placeholder="手机号（选填）" type="number" />
        </view>

        <!-- Role Select -->
        <view class="role-row">
          <view class="role-item" :class="{ active: form.role === 'student' }" @click="form.role = 'student'">
            <text class="ri-icon">🧑‍🎓</text>
            <text class="ri-label">学生</text>
          </view>
          <view class="role-item" :class="{ active: form.role === 'parent' }" @click="form.role = 'parent'">
            <text class="ri-icon">👨‍👩‍👧</text>
            <text class="ri-label">家长</text>
          </view>
        </view>

        <view class="btn-login" @click="doLogin">
          <text>{{ submitting ? '登录中...' : '进入平台' }}</text>
        </view>
      </view>

      <text class="skip" @click="skipLogin">跳过，直接体验 ›</text>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { loginOrRegisterChildUser } from '@/utils/userApi.js'

const form = ref({ name: '', phone: '', role: 'student' })
const submitting = ref(false)

async function doLogin() {
  if (!form.value.name.trim()) {
    uni.showToast({ title: '请输入昵称', icon: 'none' })
    return
  }
  submitting.value = true
  try {
    localStorage.setItem('jnao_user', JSON.stringify({
      name: form.value.name,
      phone: form.value.phone,
      role: form.value.role,
      loginTime: new Date().toISOString()
    }))
    localStorage.setItem('jnao_logged_in', '1')
    await loginOrRegisterChildUser({
      nickname: form.value.name.trim(),
      phone: form.value.phone.trim(),
    })
  } catch(e) {}
  submitting.value = false
  uni.showToast({ title: '欢迎，' + form.value.name + '！', icon: 'none' })
  setTimeout(() => {
    uni.redirectTo({ url: '/pages/index' })
  }, 500)
}

async function skipLogin() {
  localStorage.setItem('jnao_user', JSON.stringify({ name: '体验用户', role: 'student' }))
  localStorage.setItem('jnao_logged_in', '1')
  try {
    await loginOrRegisterChildUser({ nickname: '体验用户' })
  } catch (e) {}
  uni.redirectTo({ url: '/pages/index' })
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
.role-row { display:flex; gap:10px; margin-bottom:20px; }
.role-item { flex:1; background:var(--bg-card); border-radius:14px; padding:14px; text-align:center; border:2px solid transparent; cursor:pointer; transition:all 0.15s; }
.role-item.active { border-color:var(--accent); background:var(--accent-bg); }
.ri-icon { font-size:24px; display:block; margin-bottom:4px; }
.ri-label { color:var(--text-dim); font-size:13px; font-weight:500; }
.role-item.active .ri-label { color:var(--accent); }
.btn-login { background:linear-gradient(135deg,var(--accent),#3b8bff); border-radius:14px; padding:15px; text-align:center; cursor:pointer; }
.btn-login text { color:#fff; font-size:16px; font-weight:700; }
.btn-login:active { opacity:0.85; }
.skip { color:var(--text-dim); font-size:12px; text-align:center; display:block; margin-top:16px; cursor:pointer; }
</style>
