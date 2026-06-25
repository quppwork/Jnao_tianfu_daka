<template>
  <view class="app">
    <!-- 顶部光晕 -->
    <view class="glow glow-top"></view>

    <view class="card">
      <view class="logo-row">
        <text class="logo-j">J</text><text class="logo-nao">nao</text><text class="logo-ai">AI</text>
      </view>
      <text class="subtitle">天赋成长平台</text>

      <view class="form">
        <view class="input-wrap">
          <svg class="input-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--text-dim)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M20 21a8 8 0 1 0-16 0"/></svg>
          <input class="login-input" v-model="form.name" placeholder="输入昵称" />
        </view>
        <view class="input-wrap">
          <svg class="input-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--text-dim)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12" y2="18.01"/></svg>
          <input class="login-input" v-model="form.phone" placeholder="手机号" type="number" />
        </view>

        <view class="role-row">
          <view class="role-item" :class="{ active: form.role === 'student' }" @click="form.role = 'student'">
            <svg class="ri-icon-svg" :class="{ on: form.role === 'student' }" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M22 10v4M2 10v4"/><path d="M12 2L2 10l10 8 10-8-2-1.5"/><circle cx="12" cy="10" r="3"/><path d="M7 21h10"/></svg>
            <text class="ri-label">学生</text>
          </view>
          <view class="role-item" :class="{ active: form.role === 'parent' }" @click="form.role = 'parent'">
            <svg class="ri-icon-svg" :class="{ on: form.role === 'parent' }" viewBox="0 0 26 24" width="22" height="22" fill="none" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="7" r="2.3"/><path d="M4 21v-5.5a4 4 0 0 1 8 0V21"/><circle cx="18.5" cy="8" r="1.6"/><path d="M16 21v-4.5a2.8 2.8 0 0 1 5.5 0V21"/></svg>
            <text class="ri-label">家长</text>
          </view>
        </view>

        <view class="btn-login" @click="doLogin">
          <text>{{ submitting ? '登录中...' : '进入平台' }}</text>
        </view>

        <view class="btn-register" @click="goRegister">
          <text>注册新账号</text>
        </view>
      </view>
    </view>

    <!-- 底部光晕 -->
    <view class="glow glow-bottom"></view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { loginUser } from '@/utils/userApi.js'

const form = ref({ name: '', phone: '', role: 'student' })
const submitting = ref(false)

async function doLogin() {
  if (form.value.role === 'parent') {
    uni.showToast({ title: '家长模式暂未开放，敬请期待', icon: 'none', duration: 2000 })
    return
  }
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
    const data = await loginUser(form.value.phone.trim(), form.value.name.trim())
    localStorage.setItem('jnao_user', JSON.stringify({
      name: data.nickname,
      phone: data.parent_phone,
      role: form.value.role,
      loginTime: new Date().toISOString()
    }))
    localStorage.setItem('jnao_logged_in', '1')
    uni.showToast({ title: '欢迎，' + data.nickname + '！', icon: 'none' })
    setTimeout(() => { uni.redirectTo({ url: '/pages/index' }) }, 500)
  } catch (e) {
    submitting.value = false
    if (e.status === 404) {
      uni.showToast({ title: '用户不存在，请先注册', icon: 'none', duration: 2000 })
    } else {
      uni.showToast({ title: '登录失败，请稍后重试', icon: 'none' })
    }
  }
}

function goRegister() {
  uni.navigateTo({ url: '/pages/login/register' })
}

</script>

<style scoped>
.app { height:100vh; max-width:480px; margin:0 auto; background:var(--bg); display:flex; align-items:flex-start; justify-content:center; padding:30px; padding-top:18vh; font-family:-apple-system,"PingFang SC",sans-serif; position:relative; overflow:hidden; }

/* 渐变光晕 */
.glow { position:absolute; width:260px; height:260px; border-radius:50%; pointer-events:none; z-index:0; }
.glow-top { top:-80px; right:-60px; background:radial-gradient(circle, rgba(88,166,255,0.18) 0%, transparent 70%); }
.glow-bottom { bottom:-100px; left:-50px; background:radial-gradient(circle, rgba(139,92,246,0.14) 0%, transparent 70%); }

.card { width:100%; position:relative; z-index:1;
  background:rgba(255,255,255,0.03); backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px);
  border:1px solid rgba(255,255,255,0.08); border-radius:20px; padding:36px 22px 28px;
}
.logo-row { display:flex; align-items:baseline; justify-content:center; gap:6px; margin-bottom:4px; }
.logo-j { color:#dc2626; font-size:48px; font-weight:800; text-shadow:0 0 24px rgba(220,38,38,0.3); }
.logo-nao { color:var(--text); font-size:36px; font-weight:700; }
.logo-ai { color:var(--text); font-size:36px; font-weight:300; }
.subtitle { color:var(--text-dim); font-size:12px; text-align:center; display:block; margin-bottom:28px; letter-spacing:0.12em; opacity:0.7; }
.form { }
.input-wrap { display:flex; align-items:center; background:var(--bg-card); border-radius:12px; padding:0 14px; margin-bottom:12px; border:1.5px solid var(--border); transition:border-color 0.2s; }
.input-wrap:focus-within { border-color:var(--accent); box-shadow:0 0 0 3px rgba(88,166,255,0.1); }
.input-icon { flex-shrink:0; margin-right:10px; opacity:0.5; }
.login-input { flex:1; padding:14px 0; font-size:15px; color:var(--text); }
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
.btn-register { border:1.5px solid rgba(255,255,255,0.1); border-radius:14px; padding:13px; text-align:center; cursor:pointer; margin-top:10px; backdrop-filter:blur(4px); transition:all 0.2s; }
.btn-register text { color:var(--text-dim); font-size:14px; font-weight:500; }
.btn-register:active { background:rgba(255,255,255,0.05); border-color:var(--accent); }

/* 白色主题适配 */
[data-theme="white"] .card { background:rgba(255,255,255,0.6); border-color:rgba(0,0,0,0.06); }
[data-theme="white"] .glow-top { background:radial-gradient(circle, rgba(37,99,235,0.12) 0%, transparent 70%); }
[data-theme="white"] .glow-bottom { background:radial-gradient(circle, rgba(124,58,237,0.08) 0%, transparent 70%); }
[data-theme="white"] .input-wrap { background:#fff; border-color:#e5e7eb; }
[data-theme="white"] .input-wrap:focus-within { border-color:#2563eb; box-shadow:0 0 0 3px rgba(37,99,235,0.08); }
[data-theme="white"] .role-item { background:#fff; border-color:#e5e7eb; }
[data-theme="white"] .role-item.active { border-color:#2563eb; background:rgba(37,99,235,0.04); box-shadow:0 0 12px rgba(37,99,235,0.06); }
[data-theme="white"] .role-item.active .ri-label { color:#2563eb; }
[data-theme="white"] .btn-login { background:linear-gradient(135deg, #2563eb, #7c3aed); box-shadow:0 4px 16px rgba(37,99,235,0.2); }
[data-theme="white"] .btn-register { border-color:#e5e7eb; }
[data-theme="white"] .btn-register:active { background:#f9fafb; border-color:#2563eb; }
</style>
