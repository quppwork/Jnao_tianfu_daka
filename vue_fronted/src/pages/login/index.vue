<template>
  <view class="app">
    <view class="glow glow-top"></view>

    <view class="card">
      <view class="logo-row">
        <text class="logo-j">J</text><text class="logo-nao">nao</text><text class="logo-ai">AI</text>
      </view>
      <text class="subtitle">天赋成长平台</text>

      <view class="form">
        <!-- 学生密码登录：账号 -->
        <view class="input-wrap" v-if="loginMode === 'password' && form.role === 'student'">
          <svg class="input-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--text-dim)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M20 21a8 8 0 1 0-16 0"/></svg>
          <input class="login-input" v-model="form.loginName" placeholder="孩子账号" />
        </view>
        <!-- 手机号登录（学生）或家长密码登录 -->
        <view class="input-wrap" v-if="loginMode === 'phone' || (loginMode === 'password' && form.role === 'parent')">
          <svg class="input-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--text-dim)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12" y2="18.01"/></svg>
          <input class="login-input" v-model="form.phone" placeholder="手机号" type="number" />
        </view>
        <!-- 手机号登录：昵称 -->
        <view class="input-wrap" v-if="loginMode === 'phone'">
          <svg class="input-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--text-dim)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M20 21a8 8 0 1 0-16 0"/></svg>
          <input class="login-input" v-model="form.name" placeholder="输入昵称" />
        </view>
        <!-- 密码 -->
        <view class="input-wrap" v-if="loginMode === 'password'">
          <svg class="input-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--text-dim)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
          <input class="login-input" v-model="form.password" placeholder="密码" type="password" />
        </view>

        <view class="mode-switch" @click="toggleLoginMode" v-if="form.role === 'student'">
          <text>{{ loginMode === 'phone' ? '🔒 使用账号密码登录' : '📱 使用手机号登录（旧）' }}</text>
        </view>

        <view class="role-row">
          <view class="role-item" :class="{ active: form.role === 'student' }" @click="form.role = 'student'">
            <svg class="ri-icon-svg" :class="{ on: form.role === 'student' }" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M22 10v4M2 10v4"/><path d="M12 2L2 10l10 8 10-8-2-1.5"/><circle cx="12" cy="10" r="3"/><path d="M7 21h10"/></svg>
            <text class="ri-label">学生</text>
          </view>
          <view class="role-item" :class="{ active: form.role === 'parent' }" @click="onParentRole">
            <svg class="ri-icon-svg" :class="{ on: form.role === 'parent' }" viewBox="0 0 26 24" width="22" height="22" fill="none" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="7" r="2.3"/><path d="M4 21v-5.5a4 4 0 0 1 8 0V21"/><circle cx="18.5" cy="8" r="1.6"/><path d="M16 21v-4.5a2.8 2.8 0 0 1 5.5 0V21"/></svg>
            <text class="ri-label">家长</text>
          </view>
        </view>

        <view class="btn-login" @click="doLogin">
          <text>{{ submitting ? '登录中...' : '进入平台' }}</text>
        </view>

        <view v-if="form.role === 'student'" class="hint-register">
          <text>孩子账号由家长在家长中心分配</text>
        </view>
        <view v-else class="btn-register" style="border-color:rgba(139,92,246,0.3); background:rgba(139,92,246,0.04)" @click="goParentRegister">
          <text style="color:#a78bfa">注册家长账户</text>
        </view>
      </view>
    </view>

    <view class="glow glow-bottom"></view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { loginUser, loginParent, loginStudent, studentNeedsOnboarding } from '@/utils/userApi.js'

const form = ref({ name: '', phone: '', loginName: '', password: '', role: 'student' })
const loginMode = ref('password')
const submitting = ref(false)

function toggleLoginMode() {
  loginMode.value = loginMode.value === 'phone' ? 'password' : 'phone'
}

function onParentRole() {
  form.value.role = 'parent'
  loginMode.value = 'password'
}

function saveSession(data) {
  localStorage.setItem('jnao_user', JSON.stringify({
    id: data.child_user_id,
    name: data.nickname,
    phone: data.parent_phone,
    loginName: data.login_name || form.value.loginName.trim(),
    role: data.role || form.value.role,
    loginTime: new Date().toISOString(),
  }))
  localStorage.setItem('jnao_logged_in', '1')
}

async function routeStudentHome(data) {
  saveSession(data)
  uni.showToast({ title: '欢迎，' + data.nickname + '！', icon: 'none' })
  let target = '/pages/index'
  try {
    if (await studentNeedsOnboarding(data.child_user_id)) {
      target = '/pages/login/onboarding/index'
    }
  } catch (_) {
    target = '/pages/login/onboarding/index'
  }
  setTimeout(() => { uni.redirectTo({ url: target }) }, 500)
}

async function doLogin() {
  submitting.value = true
  try {
  if (loginMode.value === 'password') {
    if (!form.value.password.trim() || form.value.password.trim().length < 6) {
      uni.showToast({ title: '密码至少6位', icon: 'none' }); submitting.value = false; return
    }
    if (form.value.role === 'parent') {
      if (!form.value.phone.trim() || form.value.phone.trim().length < 11) {
        uni.showToast({ title: '请输入正确的手机号', icon: 'none' }); submitting.value = false; return
      }
      const data = await loginParent(form.value.phone.trim(), form.value.password.trim())
      saveSession(data)
      uni.showToast({ title: '欢迎，' + data.nickname + '！', icon: 'none' })
      setTimeout(() => { uni.redirectTo({ url: '/pages/parent/index' }) }, 500)
      return
    }
    if (!form.value.loginName.trim()) {
      uni.showToast({ title: '请输入孩子账号', icon: 'none' }); submitting.value = false; return
    }
    const data = await loginStudent(form.value.loginName.trim(), form.value.password.trim())
    await routeStudentHome(data)
    return
  }

  // 旧流程：手机号 + 昵称
  if (!form.value.name.trim()) { uni.showToast({ title: '请输入昵称', icon: 'none' }); submitting.value = false; return }
  if (!form.value.phone.trim() || form.value.phone.trim().length < 11) { uni.showToast({ title: '请输入正确的手机号', icon: 'none' }); submitting.value = false; return }
  const data = await loginUser(form.value.phone.trim(), form.value.name.trim())
  if (form.value.role === 'parent') {
    saveSession(data)
    uni.showToast({ title: '欢迎，' + data.nickname + '！', icon: 'none' })
    setTimeout(() => { uni.redirectTo({ url: '/pages/parent/index' }) }, 500)
  } else {
    await routeStudentHome(data)
  }
  } catch (e) {
    submitting.value = false
    if (e.status === 404) uni.showToast({ title: '用户不存在，请联系家长创建账号', icon: 'none', duration: 2000 })
    else if (e.status === 401) uni.showToast({ title: '账号或密码错误', icon: 'none' })
    else uni.showToast({ title: '登录失败，请稍后重试', icon: 'none' })
  }
}

function goParentRegister() {
  uni.navigateTo({ url: '/pages/login/register-parent' })
}
</script>

<style scoped>
.app { height:100vh; max-width:480px; margin:0 auto; background:var(--bg); display:flex; align-items:flex-start; justify-content:center; padding:30px; padding-top:18vh; font-family:-apple-system,"PingFang SC",sans-serif; position:relative; overflow:hidden; }
.glow { position:absolute; width:260px; height:260px; border-radius:50%; pointer-events:none; z-index:0; }
.glow-top { top:-80px; right:-60px; background:radial-gradient(circle, rgba(88,166,255,0.18) 0%, transparent 70%); }
.glow-bottom { bottom:-100px; left:-50px; background:radial-gradient(circle, rgba(139,92,246,0.14) 0%, transparent 70%); }
.card { width:100%; position:relative; z-index:1; background:rgba(255,255,255,0.03); backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px); border:1px solid rgba(255,255,255,0.08); border-radius:20px; padding:36px 22px 28px; }
.logo-row { display:flex; align-items:baseline; justify-content:center; gap:6px; margin-bottom:4px; }
.logo-j { color:#dc2626; font-size:48px; font-weight:800; text-shadow:0 0 24px rgba(220,38,38,0.3); }
.logo-nao { color:var(--text); font-size:36px; font-weight:700; }
.logo-ai { color:var(--text); font-size:36px; font-weight:300; }
.subtitle { color:var(--text-dim); font-size:12px; text-align:center; display:block; margin-bottom:28px; letter-spacing:0.12em; opacity:0.7; }
.input-wrap { display:flex; align-items:center; background:var(--bg-card); border-radius:12px; padding:0 14px; margin-bottom:12px; border:1.5px solid var(--border); transition:border-color 0.2s; }
.input-wrap:focus-within { border-color:var(--accent); box-shadow:0 0 0 3px rgba(88,166,255,0.1); }
.input-icon { flex-shrink:0; margin-right:10px; opacity:0.5; }
.login-input { flex:1; padding:14px 0; font-size:15px; color:var(--text); }
.mode-switch { text-align:center; margin-bottom:8px; cursor:pointer; }
.mode-switch text { color:var(--text-dim); font-size:12px; opacity:0.6; }
.role-row { display:flex; gap:10px; margin-bottom:22px; }
.role-item { flex:1; background:rgba(255,255,255,0.03); border-radius:12px; padding:14px; text-align:center; border:1.5px solid rgba(255,255,255,0.06); cursor:pointer; transition:all 0.2s; }
.role-item.active { border-color:var(--accent); background:var(--accent-bg); box-shadow:0 0 16px rgba(88,166,255,0.1); }
.ri-icon-svg { display:block; margin:0 auto 4px; stroke:var(--text-dim); transition:stroke 0.2s; overflow:visible; }
.ri-icon-svg.on { stroke:var(--accent); }
.ri-label { color:var(--text-dim); font-size:13px; font-weight:500; }
.role-item.active .ri-label { color:var(--accent); }
.btn-login { background:linear-gradient(135deg, #58a6ff, #7c3aed); border-radius:14px; padding:15px; text-align:center; cursor:pointer; box-shadow:0 4px 20px rgba(88,166,255,0.25); transition:all 0.2s; }
.btn-login text { color:#fff; font-size:16px; font-weight:700; letter-spacing:0.04em; }
.btn-login:active { opacity:0.85; transform:scale(0.98); }
.hint-register { text-align:center; margin-top:12px; }
.hint-register text { color:var(--text-dim); font-size:12px; opacity:0.7; }
.btn-register { border:1.5px solid rgba(255,255,255,0.1); border-radius:14px; padding:13px; text-align:center; cursor:pointer; margin-top:10px; backdrop-filter:blur(4px); transition:all 0.2s; }
.btn-register text { color:var(--text-dim); font-size:14px; font-weight:500; }
.btn-register:active { background:rgba(255,255,255,0.05); border-color:var(--accent); }
[data-theme="white"] .card { background:rgba(255,255,255,0.6); border-color:rgba(0,0,0,0.06); }
[data-theme="white"] .input-wrap { background:#fff; border-color:#e5e7eb; }
[data-theme="white"] .role-item { background:#fff; border-color:#e5e7eb; }
[data-theme="white"] .btn-login { background:linear-gradient(135deg, #2563eb, #7c3aed); }
</style>
