<template>
  <view class="app">
    <!-- Nav Bar -->
    <view class="nav-bar">
      <text class="nav-center" @click="onNavTap">张宇老师</text>
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
    <view class="chat-section" id="chatScroll">
      <view v-for="(m,i) in messages" :key="i" class="chat-row" :class="{ user: m.role === 'user' }">
        <view class="chat-av me" v-if="m.role==='user'"><text>我</text></view>
        <view class="chat-av ai" v-else><view class="ai-avatar-inner"></view></view>
        <view class="chat-bbl" :class="{ me: m.role==='user', ai: m.role!=='user' }">{{ m.text }}</view>
      </view>
      <view v-if="loading" class="chat-row">
        <view class="chat-av ai"><view class="ai-avatar-inner"></view></view>
        <view class="chat-bbl ai"><text class="loading-dots">...</text></view>
      </view>
    </view>

    <!-- Bottom Input -->
    <view class="input-panel">
      <textarea class="chat-input" v-model="inputText" placeholder="输入问题... Shift+Enter 换行" :disabled="loading" @keydown="onKeyDown" :rows="1" />
      <view class="btn-send" @click="sendMsg">
        <text style="color:#fff;font-size:18px;">➤</text>
      </view>
      <view class="input-actions">
        <view class="btn-speaker" @click="speakLast">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#8b949e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
        </view>
        <view class="btn-mic" :class="{ 'mic-recording': recording }" @click="voicePlaceholder">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import {
  clearChildUserId,
  ensureChildUser,
  fetchGuideSession,
  sendGuideMessage,
} from '@/utils/userApi.js'

const isLight = ref(false)
const inputText = ref('')
const loading = ref(false)
const guideSessionId = ref(null)
const messages = ref([])

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

function onKeyDown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMsg()
  }
}

async function sendMsg() {
  stopRecord()
  const text = inputText.value.trim()
  if (!text || loading.value) return
  messages.value.push({ role: 'user', text })
  inputText.value = ''
  loading.value = true
  await nextTick()
  scrollChat()
  try {
    const uid = await ensureChildUser()
    const data = await sendGuideMessage(uid, text, guideSessionId.value)
    guideSessionId.value = data.session_id
    messages.value.push({ role: 'ai', text: data.reply || '抱歉，AI 暂时无法响应' })
  } catch (e) {
    messages.value.push({ role: 'ai', text: '网络错误，请稍后再试' })
  }
  loading.value = false
  await nextTick()
  scrollChat()
}

async function loadGuideSession() {
  try {
    const uid = await ensureChildUser()
    const data = await fetchGuideSession(uid)
    guideSessionId.value = data.session_id
    messages.value = (data.messages || []).map(m => ({
      role: m.role === 'assistant' ? 'ai' : 'user',
      text: m.content,
    }))
    if (!messages.value.length) {
      messages.value = [{ role: 'ai', text: '你好！我是 JNAO 智能助手 👋 有什么想问的吗？比如：天赋测试怎么做？' }]
    }
  } catch (e) {
    messages.value = [{ role: 'ai', text: '你好！我是 JNAO 智能助手 👋 有什么想问的吗？比如：天赋测试怎么做？' }]
  }
}

onMounted(loadGuideSession)

function scrollChat() {
  const el = document.getElementById('chatScroll')
  if (el) el.scrollTop = el.scrollHeight
}

function speakLast() {
  const aiMsgs = messages.value.filter(m => m.role === 'ai')
  if (!aiMsgs.length) return
  const text = aiMsgs[aiMsgs.length - 1].text
  if (window.speechSynthesis) {
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'zh-CN'
    u.rate = 1.1
    speechSynthesis.cancel()
    speechSynthesis.speak(u)
  } else {
    uni.showToast({ title: '当前浏览器不支持语音播报', icon: 'none' })
  }
}
const recording = ref(false)
let recognition = null

function initRecognition() {
  if (recognition) return true
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SpeechRecognition) { console.log('SpeechRecognition not available'); return false }
  recognition = new SpeechRecognition()
  recognition.lang = 'zh-CN'
  recognition.interimResults = true
  recognition.continuous = true
  recognition.onresult = (e) => {
    let text = ''
    for (let i = e.resultIndex; i < e.results.length; i++) {
      text += e.results[i][0].transcript
    }
    inputText.value = text
    console.log('recognized:', text)
  }
  recognition.onerror = (e) => {
    console.log('recognition error:', e.error)
    recording.value = false
  }
  recognition.onend = () => {
    console.log('recognition ended')
    recording.value = false
    if (inputText.value.trim()) sendMsg()
  }
  console.log('SpeechRecognition ready')
  return true
}

function voicePlaceholder() {
  if (recording.value) { stopRecord(); return }
  if (!initRecognition()) {
    uni.showToast({ title: '当前浏览器不支持语音识别', icon: 'none' })
    return
  }
  recording.value = true
  try { recognition.start() } catch(e) {
    recording.value = false
    uni.showToast({ title: '麦克风权限被拒', icon: 'none', duration: 3000 })
  }
}

function stopRecord() {
  if (recognition) {
    try { recognition.stop() } catch(e) {}
    recording.value = false
  }
}

function openPage(name) {
  if (name === 'talent') {
    uni.navigateTo({ url: '/pages/talent/index' })
  } else if (name === 'train') {
    uni.navigateTo({ url: '/pages/training/index' })
  } else if (name === 'qa') {
    uni.navigateTo({ url: '/pages/qa/index' })
  } else if (name === 'growth') {
    uni.navigateTo({ url: '/pages/growth/index' })
  } else {
    uni.showToast({ title: '进入: ' + name, icon: 'none' })
  }
}

let navTapCount = 0
let navTapTimer = null

function onNavTap() {
  navTapCount += 1
  if (navTapTimer) clearTimeout(navTapTimer)
  navTapTimer = setTimeout(() => { navTapCount = 0 }, 1500)
  if (navTapCount < 3) return
  navTapCount = 0
  const ok = window.confirm(
    '清空本地登录状态？\n（将清除本机用户标识；服务器上的测评/训练数据需运行 reset.bat 清库）'
  )
  if (!ok) return
  clearChildUserId()
  location.reload()
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

.chat-section { flex:1; overflow-y:auto; padding:8px 14px 0; scrollbar-width:none; -ms-overflow-style:none; }
.chat-section::-webkit-scrollbar { display:none; }
.chat-row { display:flex; gap:8px; margin-bottom:14px; align-items:flex-start; }
.chat-row.user { flex-direction:row-reverse; }
.chat-av { width:36px; height:36px; border-radius:8px; flex-shrink:0; display:flex; align-items:center; justify-content:center; }
.chat-av.ai { background:var(--chat-ai-bg); border:1.5px solid rgba(88,166,255,0.3); overflow:hidden; }
.chat-av.me { background:var(--chat-me-bg); border-radius:50%; color:var(--text-dim); font-size:13px; }
.ai-avatar-inner { width:22px; height:26px; background:#2a5a8e; border-radius:5px 5px 0 0; margin-top:8px; }
.chat-bbl { max-width:75%; padding:10px 14px; border-radius:16px; font-size:13px; line-height:1.6; word-break:break-word; white-space:pre-wrap; }
.chat-bbl.ai { background:var(--chat-ai-bg); color:var(--text); border-bottom-left-radius:4px; }
.chat-bbl.me { background:var(--chat-me-bg); color:var(--text-sub); border-bottom-right-radius:4px; }

.input-panel { margin:8px 14px 14px; background:var(--bg-card); border-radius:18px; padding:8px 10px; display:flex; align-items:center; gap:8px; }
.chat-input { flex:1; background:var(--bg-input); border-radius:12px; padding:10px 14px; font-size:13px; color:var(--text); border:none; outline:none; resize:none; height:38px; line-height:18px; overflow-y:auto; }
.loading-dots { animation:dotPulse 1.4s infinite; }
@keyframes dotPulse { 0%,80%,100% { opacity:0.2 } 40% { opacity:1 } }
.input-actions { display:flex; align-items:center; gap:8px; flex-shrink:0; }
.btn-speaker { width:36px; height:36px; border-radius:50%; border:1.5px solid rgba(139,148,158,0.3); display:flex; align-items:center; justify-content:center; }
.btn-send { width:36px; height:36px; border-radius:50%; background:var(--accent); display:flex !important; align-items:center; justify-content:center; cursor:pointer; flex-shrink:0; }
.btn-send:active { opacity:0.8; }
.btn-mic { width:42px; height:42px; border-radius:50%; background:linear-gradient(135deg,var(--accent),#3b8bff); display:flex; align-items:center; justify-content:center; box-shadow:0 4px 16px var(--mic-shadow); transition:all 0.2s; }
.btn-mic.mic-recording { background:#ff4444 !important; box-shadow:0 0 0 6px rgba(255,68,68,0.3); animation:micPulse 1s infinite; }
@keyframes micPulse { 0%,100% { box-shadow:0 0 0 6px rgba(255,68,68,0.3) } 50% { box-shadow:0 0 0 14px rgba(255,68,68,0) } }
</style>
