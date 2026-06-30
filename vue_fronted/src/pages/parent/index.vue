<template>
  <view class="app">
    <!-- Nav Bar -->
    <view class="nav-bar">
      <view class="nav-spacer"></view>
      <text class="nav-center">家长中心</text>
      <view class="nav-actions">
        <view class="nav-icon-btn" @click="toggleTheme">
          <svg v-if="isLight" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--text-dim)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
          <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--text-dim)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
        </view>
        <view class="nav-icon-btn" @click="showSettings = true">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--text-dim)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        </view>
      </view>
    </view>

    <!-- Hero -->
    <view class="hero">
      <view class="hero-avatar">{{ parentName.charAt(0) }}</view>
      <text class="hero-name">{{ parentName }}</text>
      <text class="hero-sub">已绑定 {{ children.length }} 个孩子</text>
    </view>

    <!-- Children Cards -->
    <view class="children-section">
      <text class="section-title">我的孩子</text>
      <view v-if="children.length === 0" class="empty-state">
        <text class="empty-icon">📋</text>
        <text class="empty-text">暂无绑定孩子</text>
        <text class="empty-hint">请让孩子在注册时填写此手机号</text>
      </view>
      <view v-for="child in children" :key="child.id" class="child-card">
        <view class="child-avatar">{{ (child.nickname || '?').charAt(0) }}</view>
        <view class="child-info">
          <text class="child-name">{{ child.nickname || '未命名' }}</text>
          <text class="child-detail">天赋：{{ child.talent || '未测评' }}</text>
          <text class="child-detail">训练：{{ child.training_days || 0 }} 天 · 打卡 {{ child.checkins || 0 }} 次</text>
        </view>
        <view class="child-arrow">
          <text>→</text>
        </view>
      </view>
    </view>

    <!-- Settings Overlay -->
    <view v-if="showSettings" class="overlay" @tap="showSettings = false">
      <view class="settings-panel" @tap.stop>
        <text class="settings-title">设置</text>
        <view class="settings-item" @tap="doLogout">
          <text class="settings-label">退出登录</text>
        </view>
        <view class="settings-close" @tap="showSettings = false">
          <text>关闭</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const showSettings = ref(false)
const parentName = ref('家长')
const children = ref([])
const isLight = ref(false)

onMounted(async () => {
  try {
    const raw = localStorage.getItem('jnao_user')
    if (raw) {
      const u = JSON.parse(raw)
      parentName.value = u.name || '家长'
    }
  } catch (_) {}
  // 主题
  try {
    isLight.value = localStorage.getItem('jnao_theme') === 'white'
  } catch (_) {}
  // TODO: 后端接口就绪后替换为真实数据
  // const uid = await ensureChildUser()
  // const data = await fetchParentChildren(uid)
  // children.value = data.children || []
  // 当前使用模拟数据展示卡片效果
  children.value = []
})

function toggleTheme() {
  isLight.value = !isLight.value
  try {
    localStorage.setItem('jnao_theme', isLight.value ? 'white' : 'dark')
  } catch (_) {}
  const html = document.documentElement
  if (isLight.value) html.setAttribute('data-theme', 'white')
  else html.removeAttribute('data-theme')
}

function doLogout() {
  showSettings.value = false
  try {
    localStorage.removeItem('jnao_child_user_id')
    localStorage.removeItem('jnao_user')
    localStorage.removeItem('jnao_logged_in')
  } catch (_) {}
  uni.redirectTo({ url: '/pages/login/index' })
}
</script>

<style scoped>
.app {
  min-height: 100vh; max-width: 480px; margin: 0 auto;
  background: var(--bg); font-family: -apple-system, "PingFang SC", sans-serif;
  display: flex; flex-direction: column; padding: 0 0 40px;
}

/* ── Nav ── */
.nav-bar { display:flex; align-items:center; padding:14px 14px 10px; }
.nav-spacer { width:36px; }
.nav-center { flex:1; text-align:center; color:var(--text); font-size:16px; font-weight:600; }
.nav-actions { display:flex; gap:8px; }
.nav-icon-btn { width:34px; height:34px; border-radius:50%; background:var(--bg-card); border:1px solid var(--border); display:flex; align-items:center; justify-content:center; cursor:pointer; }

/* ── Hero ── */
.hero { text-align:center; padding:24px 20px 20px; }
.hero-avatar { width:64px; height:64px; border-radius:50%; background:linear-gradient(135deg,var(--accent),#7c3aed); display:flex; align-items:center; justify-content:center; margin:0 auto 10px; color:#fff; font-size:28px; font-weight:700; }
.hero-name { color:var(--text); font-size:20px; font-weight:700; display:block; }
.hero-sub { color:var(--text-dim); font-size:13px; margin-top:4px; display:block; }

/* ── Children ── */
.children-section { padding:0 16px; }
.section-title { color:var(--text); font-size:15px; font-weight:700; display:block; margin-bottom:12px; }
.child-card { display:flex; align-items:center; background:var(--bg-card); border-radius:14px; padding:14px; margin-bottom:10px; border:1px solid var(--border); cursor:pointer; }
.child-avatar { width:44px; height:44px; border-radius:50%; background:var(--accent-bg); display:flex; align-items:center; justify-content:center; margin-right:12px; flex-shrink:0; color:var(--accent); font-size:18px; font-weight:700; }
.child-info { flex:1; min-width:0; }
.child-name { color:var(--text); font-size:15px; font-weight:600; display:block; }
.child-detail { color:var(--text-dim); font-size:11px; margin-top:2px; display:block; }
.child-arrow { color:var(--text-dim); font-size:16px; flex-shrink:0; margin-left:8px; }

/* ── Empty ── */
.empty-state { text-align:center; padding:40px 20px; }
.empty-icon { font-size:40px; display:block; margin-bottom:10px; }
.empty-text { color:var(--text); font-size:15px; font-weight:600; display:block; }
.empty-hint { color:var(--text-dim); font-size:12px; margin-top:6px; display:block; }

/* ── Settings Overlay ── */
.overlay { position:fixed; inset:0; z-index:500; background:rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center; padding:40px; }
.settings-panel { width:100%; max-width:300px; background:var(--bg-card); border-radius:16px; padding:24px 20px 20px; }
.settings-title { color:var(--text); font-size:17px; font-weight:700; text-align:center; display:block; margin-bottom:16px; }
.settings-item { padding:14px; border-radius:12px; background:rgba(220,38,38,0.08); text-align:center; cursor:pointer; margin-bottom:12px; }
.settings-label { color:#dc2626; font-size:15px; font-weight:500; }
.settings-close { text-align:center; padding:10px; cursor:pointer; }
.settings-close text { color:var(--text-dim); font-size:13px; }
</style>
