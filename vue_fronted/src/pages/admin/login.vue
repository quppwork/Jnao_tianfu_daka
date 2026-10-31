<template>
  <view class="app">
    <view class="card">
      <text class="badge">仅限工作人员</text>
      <text class="title">管理后台登录</text>
      <view class="input-wrap">
        <input class="input" v-model="form.loginName" placeholder="管理员账号" />
      </view>
      <view class="input-wrap">
        <input class="input" v-model="form.password" placeholder="管理员密码" type="password" />
      </view>
      <view class="btn" @click="doLogin">
        <text>{{ submitting ? '登录中...' : '进入管理后台' }}</text>
      </view>
      <view class="footer">
        <text class="footer-link" @click="goBack">← 返回用户登录</text>
        <text class="footer-dot">·</text>
        <text class="footer-link" @click="confirmClearCache">清除登录状态</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { loginAdmin, resetLocalAuthCache } from '@/utils/userApi.js'
import { sanitizeAuthForLoginEntry } from '@/utils/appSession.js'

const form = ref({ loginName: '', password: '' })
const submitting = ref(false)

onMounted(() => {
  sanitizeAuthForLoginEntry('/pages/admin/login')
})

async function doLogin() {
  if (!form.value.loginName.trim() || !form.value.password.trim()) {
    uni.showToast({ title: '请输入账号和密码', icon: 'none' }); return
  }
  submitting.value = true
  try {
    await loginAdmin(form.value.loginName.trim(), form.value.password.trim())
    uni.redirectTo({ url: '/pages/admin/index' })
  } catch (e) {
    uni.showToast({ title: e.status === 401 ? '账号或密码错误' : '登录失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

function goBack() {
  uni.redirectTo({ url: '/pages/login/index' })
}

function confirmClearCache() {
  uni.showModal({
    title: '清除登录状态',
    content: '清除本网站全部登录信息，确定？',
    success: (r) => {
      if (!r.confirm) return
      resetLocalAuthCache()
      uni.showToast({ title: '已清除', icon: 'none' })
    },
  })
}
</script>

<style scoped>
.app { min-height:100vh; display:flex; align-items:center; justify-content:center; padding:24px; background:var(--bg); }
.card { width:100%; max-width:360px; background:var(--bg-card); border:1px solid var(--border); border-radius:16px; padding:24px; }
.badge { display:block; text-align:center; color:#f59e0b; font-size:11px; font-weight:600; margin-bottom:8px; letter-spacing:0.05em; }
.title { display:block; text-align:center; color:var(--text); font-size:18px; font-weight:700; margin-bottom:20px; }
.input-wrap { background:var(--bg); border:1px solid var(--border); border-radius:10px; padding:0 12px; margin-bottom:12px; }
.input { padding:12px 0; font-size:15px; color:var(--text); width:100%; }
.btn { background:linear-gradient(135deg,#f59e0b,#d97706); border-radius:12px; padding:14px; text-align:center; margin-top:8px; }
.btn text { color:#fff; font-weight:600; }
.footer { display:flex; align-items:center; justify-content:center; gap:8px; margin-top:20px; padding-top:14px; border-top:1px solid var(--border); }
.footer-link { color:var(--text-dim); font-size:12px; }
.footer-dot { color:var(--text-dim); font-size:12px; opacity:0.5; }
</style>
