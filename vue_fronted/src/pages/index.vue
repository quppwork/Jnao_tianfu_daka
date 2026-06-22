<template>
  <view class="app">
    <!-- Nav Bar -->
    <view class="nav-bar">
      <text class="nav-center">张宇老师</text>
      <text class="theme-btn" @click="toggleTheme">{{ isLight ? '☀️' : '🌙' }}</text>
    </view>

    <!-- Hero Banner -->
    <image class="hero-img" src="/static/teacher.png" mode="widthFix"></image>

    <!-- 1x4 Function Grid -->
    <view class="func-grid">
      <view class="func-card" @tap="openPage('talent')">
        <view class="func-icon icon-card">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#58a6ff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/></svg>
        </view>
        <text class="func-label">天赋测试</text>
      </view>
      <view class="func-card" @tap="openPage('train')">
        <view class="func-icon icon-card">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#58a6ff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><polyline points="8 14 11.5 17 16 14"/></svg>
        </view>
        <text class="func-label">今日训练</text>
      </view>
      <view class="func-card" @tap="openPage('qa')">
        <view class="func-icon icon-card">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#58a6ff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        </view>
        <text class="func-label">学科答疑</text>
      </view>
      <view class="func-card" @tap="openPage('growth')">
        <view class="func-icon icon-card">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#58a6ff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="7"/><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/></svg>
        </view>
        <text class="func-label">成长里程碑</text>
      </view>
    </view>

    <!-- Chat Area -->
    <view class="chat-section">
      <view class="chat-row user">
        <view class="chat-av me"><text>我</text></view>
        <view class="chat-bbl me">老师，我想了解一下天赋测试怎么做？</view>
      </view>
      <view class="chat-row">
        <view class="chat-av ai"><view class="ai-avatar-inner"></view></view>
        <view class="chat-bbl ai">天赋测试是我们核心功能，你只需回答 35 道选择题，AI 就会自动分析生成专属报告 ✨</view>
      </view>
      <view class="chat-row">
        <view class="chat-av ai"><view class="ai-avatar-inner"></view></view>
        <view class="chat-bbl ai">报告包含雷达图 📊、情绪分析 🧠、五大天赋维度的详细解读，以及针对性的发展建议。要不要现在就试试？</view>
      </view>
    </view>

    <!-- Bottom Input -->
    <view class="input-panel">
      <view class="input-area">
        <text class="input-hint">点击输入你想问的问题...</text>
        <text class="input-chevron">⌄</text>
      </view>
      <view class="input-actions">
        <view class="btn-speaker" @click="showToast('语音播报')">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#8b949e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
        </view>
        <view class="btn-mic" @click="showToast('语音输入')">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'

const isLight = ref(false)

// 初始化主题
try {
  const saved = localStorage.getItem('jnao_theme')
  isLight.value = saved === 'white'
} catch (e) {}

function toggleTheme() {
  isLight.value = !isLight.value
  const theme = isLight.value ? 'white' : 'dark'
  document.documentElement.setAttribute('data-theme', theme)
  try { localStorage.setItem('jnao_theme', theme) } catch (e) {}
}

function openPage(name) {
  if (name === 'talent') {
    uni.navigateTo({ url: '/pages/talent/index' })
  } else {
    uni.showToast({ title: '进入: ' + name, icon: 'none' })
  }
}
function showToast(msg) {
  uni.showToast({ title: msg, icon: 'none' })
}
</script>

<style scoped>
.app {
  display:flex; flex-direction:column; height:100vh; max-width:480px; margin:0 auto;
  background:var(--bg); font-family:-apple-system,"PingFang SC",sans-serif; position:relative; overflow:hidden;
}

.nav-bar { display:flex; align-items:center; justify-content:center; padding:10px 16px 8px; position:relative; }
.nav-center { color:var(--text); font-size:15px; font-weight:500; }
.theme-btn { position:absolute; right:16px; font-size:20px; cursor:pointer; }

.hero-img { width:calc(100% - 28px); margin:0 14px; border-radius:16px; display:block; }

.func-grid { display:flex; gap:8px; padding:12px 14px; }
.func-card { flex:1; background:var(--bg-card); border-radius:12px; padding:12px 6px 10px; display:flex; flex-direction:column; align-items:center; gap:6px; border:1.5px solid transparent; transition:all 0.15s; }
.func-card:active { background:var(--accent-bg); border-color:var(--accent); transform:scale(0.95); }
.func-card.active { border-color:var(--accent); }
.func-icon { width:34px; height:34px; border-radius:8px; display:flex; align-items:center; justify-content:center; background:var(--accent-bg); }
.func-label { color:var(--text-sub); font-size:11px; font-weight:500; }

.chat-section { flex:1; overflow-y:auto; padding:8px 14px 0; }
.chat-row { display:flex; gap:8px; margin-bottom:14px; align-items:flex-start; }
.chat-row.user { flex-direction:row-reverse; }
.chat-av { width:36px; height:36px; border-radius:8px; flex-shrink:0; display:flex; align-items:center; justify-content:center; }
.chat-av.ai { background:var(--chat-ai-bg); border:1.5px solid rgba(88,166,255,0.3); overflow:hidden; }
.chat-av.me { background:var(--chat-me-bg); border-radius:50%; color:var(--text-dim); font-size:13px; }
.ai-avatar-inner { width:22px; height:26px; background:#2a5a8e; border-radius:5px 5px 0 0; margin-top:8px; }
.chat-bbl { max-width:72%; padding:10px 14px; border-radius:16px; font-size:13px; line-height:1.5; }
.chat-bbl.ai { background:var(--chat-ai-bg); color:var(--text); border-bottom-left-radius:4px; }
.chat-bbl.me { background:var(--chat-me-bg); color:var(--text-sub); border-bottom-right-radius:4px; }

.input-panel { margin:8px 14px 14px; background:var(--bg-card); border-radius:18px; padding:12px 14px; display:flex; align-items:center; gap:10px; }
.input-area { flex:1; background:var(--bg-input); border-radius:12px; padding:10px 14px; display:flex; align-items:center; justify-content:space-between; }
.input-hint { color:var(--text-hint); font-size:13px; }
.input-chevron { color:var(--border); }
.input-actions { display:flex; align-items:center; gap:8px; flex-shrink:0; }
.btn-speaker { width:36px; height:36px; border-radius:50%; border:1.5px solid rgba(139,148,158,0.3); display:flex; align-items:center; justify-content:center; }
.btn-mic { width:42px; height:42px; border-radius:50%; background:linear-gradient(135deg,var(--accent),#3b8bff); display:flex; align-items:center; justify-content:center; box-shadow:0 4px 16px var(--mic-shadow); }
</style>
