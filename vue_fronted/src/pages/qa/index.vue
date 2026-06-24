<template>
  <view class="app">
    <view class="nav">
      <view class="nav-back" @click="goBack">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#8b949e" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      </view>
      <text class="nav-title">学科答疑</text>
      <view class="nav-spacer"></view>
    </view>

    <view class="top-area">
      <view class="avatar-wrap">
        <view class="avatar-ring">
          <view class="avatar-inner">🧑‍🏫</view>
        </view>
      </view>
      <text class="greet-text">有什么不会的？告诉我吧～</text>
    </view>

    <view class="chat-section" id="chatScroll">
      <view v-for="(m,i) in messages" :key="i" class="chat-row" :class="{ user: m.role === 'user' }">
        <view class="chat-av" :class="m.role">
          <text>{{ m.role === 'user' ? '我' : 'AI' }}</text>
        </view>
        <view class="chat-bbl" :class="m.role">{{ m.text }}</view>
      </view>
      <view v-if="loading" class="chat-row">
        <view class="chat-av assistant"><text>AI</text></view>
        <view class="chat-bbl assistant"><text class="typing">...</text></view>
      </view>
    </view>

    <view class="input-panel">
      <input class="chat-input" v-model="inputText" placeholder="输入问题... Enter 发送" confirm-type="send" @confirm="sendMsg" :disabled="loading" />
      <view class="btn-send" @click="sendMsg"><text style="color:#fff;">➤</text></view>
      <view class="btn-mic" @click="voiceInput"><text style="font-size:16px;">🎤</text></view>
    </view>
  </view>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { ensureChildUser, fetchQaSession, sendQaMessage } from '@/utils/userApi.js'

const inputText = ref('')
const loading = ref(false)
const qaSessionId = ref(null)
const messages = ref([
  { role: 'assistant', text: '你好！我是张宇老师 ✨ 有任何学科问题都可以问我～' },
])

function goBack() { uni.navigateBack({ delta: 1 }) }

async function loadSession() {
  try {
    const uid = await ensureChildUser()
    const sessions = await fetch(`/api/qa/sessions?user_id=${uid}`).then(r => r.json())
    const latest = sessions.items?.[0]
    if (!latest) return
    qaSessionId.value = latest.id
    const data = await fetchQaSession(uid, latest.id)
    if (data.messages?.length) {
      messages.value = data.messages.map(m => ({
        role: m.role === 'user' ? 'user' : 'assistant',
        text: m.content,
      }))
    }
  } catch (e) { /* 新用户无历史会话 */ }
}

async function sendMsg() {
  const text = inputText.value.trim()
  if (!text || loading.value) return
  messages.value.push({ role: 'user', text })
  inputText.value = ''
  loading.value = true
  await nextTick()
  scrollChat()
  try {
    const uid = await ensureChildUser()
    const data = await sendQaMessage(uid, text, qaSessionId.value)
    qaSessionId.value = data.session_id
    messages.value.push({ role: 'assistant', text: data.reply || '抱歉，AI 暂时无法响应' })
  } catch (e) {
    messages.value.push({ role: 'assistant', text: '网络错误，请稍后再试' })
  }
  loading.value = false
  await nextTick()
  scrollChat()
}

function scrollChat() {
  const el = document.getElementById('chatScroll')
  if (el) el.scrollTop = el.scrollHeight
}

function voiceInput() {
  uni.showToast({ title: '语音输入功能开发中', icon: 'none' })
}

onMounted(loadSession)
</script>

<style scoped>
.app { height:100vh; max-width:480px; margin:0 auto; background:var(--bg); font-family:-apple-system,"PingFang SC",sans-serif; display:flex; flex-direction:column; position:relative; overflow:hidden; }
.nav { display:flex; align-items:center; padding:14px 14px 0; }
.nav-back { width:36px; height:36px; border-radius:50%; background:var(--bg-card); display:flex; align-items:center; justify-content:center; cursor:pointer; }
.nav-title { flex:1; text-align:center; color:var(--text); font-size:16px; font-weight:600; }
.nav-spacer { width:36px; }

.top-area { text-align:center; padding:12px 0 8px; }
.avatar-wrap { display:flex; justify-content:center; margin-bottom:8px; }
.avatar-ring { width:64px; height:64px; border-radius:50%; background:var(--accent-bg); border:2px solid var(--accent); display:flex; align-items:center; justify-content:center; animation:avatarPulse 2.5s ease-in-out infinite; }
.avatar-inner { font-size:32px; }
.greet-text { color:var(--text-dim); font-size:13px; }
@keyframes avatarPulse { 0%,100% { box-shadow:0 0 0 0 rgba(88,166,255,0.3); } 50% { box-shadow:0 0 0 10px rgba(88,166,255,0); } }

.chat-section { flex:1; overflow-y:auto; padding:8px 16px 0; scrollbar-width:none; }
.chat-section::-webkit-scrollbar { display:none; }
.chat-row { display:flex; gap:8px; margin-bottom:14px; align-items:flex-start; }
.chat-row.user { flex-direction:row-reverse; }
.chat-av { width:32px; height:32px; border-radius:50%; flex-shrink:0; display:flex; align-items:center; justify-content:center; font-size:11px; }
.chat-av.user { background:var(--chat-me-bg); color:var(--text-dim); }
.chat-av.assistant { background:var(--chat-ai-bg); color:var(--accent); }
.chat-bbl { max-width:75%; padding:10px 14px; border-radius:16px; font-size:13px; line-height:1.6; word-break:break-word; }
.chat-bbl.user { background:var(--chat-me-bg); color:var(--text-sub); border-bottom-right-radius:4px; }
.chat-bbl.assistant { background:var(--chat-ai-bg); color:var(--text); border-bottom-left-radius:4px; }
.typing { animation:dotPulse 1.4s infinite; }
@keyframes dotPulse { 0%,80%,100% { opacity:0.2; } 40% { opacity:1; } }

.input-panel { margin:8px 14px 14px; background:var(--bg-card); border-radius:18px; padding:8px 10px; display:flex; align-items:center; gap:8px; }
.chat-input { flex:1; background:var(--bg-input); border-radius:12px; padding:10px 14px; font-size:13px; color:var(--text); border:none; outline:none; }
.btn-send { width:36px; height:36px; border-radius:50%; background:var(--accent); display:flex; align-items:center; justify-content:center; cursor:pointer; flex-shrink:0; }
.btn-send:active { opacity:0.8; }
.btn-mic { width:36px; height:36px; border-radius:50%; background:var(--accent-bg); display:flex; align-items:center; justify-content:center; cursor:pointer; flex-shrink:0; }
</style>
