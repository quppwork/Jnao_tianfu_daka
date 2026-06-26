<template>
  <view class="app">
    <!-- Nav Bar -->
    <view class="nav-bar">
      <view class="nav-spacer"></view>
      <text class="nav-center" @click="onNavTap">张宇老师</text>
      <view class="nav-actions">
        <!-- 设置 -->
        <view class="nav-icon-btn" @click="showSettings = true; settingsTab = 'profile'">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--text-dim)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        </view>
        <!-- 主题 -->
        <view class="nav-icon-btn" @click="toggleTheme">
          <svg v-if="isLight" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--text-dim)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
          <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--text-dim)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
        </view>
      </view>
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
        <view class="chat-av ai" v-else><image class="ai-avatar-img" src="/static/teacher-avatar.png" mode="aspectFill"></image></view>
        <view class="chat-bbl" :class="{ me: m.role==='user', ai: m.role!=='user' }">{{ m.text }}</view>
      </view>
      <view v-if="loading" class="chat-row">
        <view class="chat-av ai"><image class="ai-avatar-img" src="/static/teacher-avatar.png" mode="aspectFill"></image></view>
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

    <!-- Settings Modal -->
    <view v-if="showSettings" class="picker-overlay" @click="showSettings = false">
      <view class="picker-card settings-card" @click.stop>
        <text class="picker-title">⚙ 设置</text>

        <!-- Tab 1: 个人信息 -->
        <view class="set-block">
          <view class="set-block-head" @click="settingsTab = 'profile'">
            <text class="set-block-title">📋 个人信息</text>
            <text class="set-block-arrow" :class="{ open: settingsTab === 'profile' }">▾</text>
          </view>
          <view v-if="settingsTab === 'profile'" class="set-block-body">
            <view class="form-row">
              <text class="form-label">孩子姓名</text>
              <input class="form-input" v-model="profile.name" placeholder="孩子真实姓名" />
            </view>
            <view class="form-row">
              <text class="form-label">年级</text>
              <picker class="form-picker" mode="selector" :range="gradeOptions" :value="gradeIndex" @change="onGradeChange">
                <view class="form-input form-picker-val">{{ profile.grade || '请选择年级' }}</view>
              </picker>
            </view>
            <view v-if="profile.talent" class="form-row">
              <text class="form-label">天赋</text>
              <view class="form-input talent-readonly">{{ profile.talent }}</view>
            </view>
            <view class="form-row">
              <text class="form-label">家长手机</text>
              <view class="form-input form-input-dim">{{ profile.phone || '暂无' }}</view>
            </view>
            <view class="form-row">
              <text class="form-label">家长姓名</text>
              <input class="form-input" v-model="profile.parentName" placeholder="家长姓名（选填）" />
            </view>
            <view class="btn-checkin" @click="saveProfile"><text>保存信息</text></view>
          </view>
        </view>

        <!-- Tab 2: 天赋测评历史 -->
        <view class="set-block">
          <view class="set-block-head" @click="settingsTab = 'history'">
            <text class="set-block-title">📊 天赋测评历史</text>
            <text class="set-block-arrow" :class="{ open: settingsTab === 'history' }">▾</text>
          </view>
          <view v-if="settingsTab === 'history'" class="set-block-body">
            <view v-if="historyList.length" class="history-mini">
              <view v-for="(h, i) in historyList" :key="h.id || i" class="hm-item">
                <view class="hm-left" @click="viewHistory(h)">
                  <text class="hm-talent">{{ h.talent_primary || h.talent || '--' }}</text>
                  <text class="hm-time">{{ h.create_time || h.assessed_at }}</text>
                </view>
                <text class="hm-del" @click.stop="confirmDeleteHistory(h)">✕</text>
                <text class="hm-arrow">›</text>
              </view>
            </view>
            <text v-else class="history-empty">暂无历史测评记录</text>
            <view class="btn-clear-chat" @click="clearGuideChat"><text>清空首页对话</text></view>
          </view>
        </view>

        <view class="btn-logout" @click="doLogout"><text>登出账号</text></view>
        <view class="picker-close" @click="showSettings = false"><text>关闭</text></view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import {
  clearChildUserId,
  ensureChildUser,
  getChildUserId,
  markChildUserSessionValid,
  invalidateChildUserSession,
  fetchGuideSession,
  sendGuideMessage,
  clearGuideSession,
  fetchProfile,
  saveProfile as saveProfileToDb,
  fetchAssessmentHistory,
  fetchLatestAssessment,
  deleteAssessmentReport,
  updateLearnerProfile,
  gradeToSchoolStage,
} from '@/utils/userApi.js'

const isLight = ref(false)
const inputText = ref('')
const loading = ref(false)
const guideSessionId = ref(null)
const messages = ref([])
const showSettings = ref(false)
const settingsTab = ref('profile')
const profile = ref({ name: '', grade: '', talent: '', phone: '', parentName: '' })
const gradeOptions = ['一年级','二年级','三年级','四年级','五年级','六年级','初一','初二','初三','高一','高二','高三']
const gradeIndex = ref(0)
const historyList = ref([])

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

function applyProfileData(data, uid, { fetchLatest = true } = {}) {
  if (data.nickname && data.nickname !== '学员') profile.value.name = data.nickname
  if (data.parent_phone) profile.value.phone = data.parent_phone
  let hasTalent = false
  if (data.profile_json) {
    if (data.profile_json.grade) profile.value.grade = data.profile_json.grade
    if (data.profile_json.parentName) profile.value.parentName = data.profile_json.parentName
    const tp = data.profile_json.talent_primary || data.profile_json.talent
    const tt = data.profile_json.talent_tag
    if (tp) {
      hasTalent = true
      profile.value.talent = tt ? `${tp}偏${tt}` : tp
    }
  }
  const idx = gradeOptions.indexOf(profile.value.grade)
  if (idx >= 0) gradeIndex.value = idx
  if (fetchLatest && !hasTalent && uid) {
    return fetchLatestAssessment(uid).then((latest) => {
      if (latest?.talent_primary) {
        profile.value.talent = latest.talent_tag
          ? `${latest.talent_primary}偏${latest.talent_tag}`
          : latest.talent_primary
      }
    }).catch(() => {})
  }
  return Promise.resolve()
}

async function initHome() {
  try {
    let uid = getChildUserId()
    if (!uid) uid = await ensureChildUser()
    let profileData
    let history
    let guideData
    try {
      ;[profileData, history, guideData] = await Promise.all([
        fetchProfile(uid),
        fetchAssessmentHistory(uid),
        fetchGuideSession(uid),
      ])
      markChildUserSessionValid(uid)
    } catch (e) {
      if (e.status === 404 && getChildUserId()) {
        invalidateChildUserSession()
        clearChildUserId()
        uid = await ensureChildUser()
        ;[profileData, history, guideData] = await Promise.all([
          fetchProfile(uid),
          fetchAssessmentHistory(uid),
          fetchGuideSession(uid),
        ])
        markChildUserSessionValid(uid)
      } else {
        throw e
      }
    }
    historyList.value = history
    guideSessionId.value = guideData.session_id
    messages.value = (guideData.messages || []).map(m => ({
      role: m.role === 'assistant' ? 'ai' : 'user',
      text: m.content,
    }))
    if (!messages.value.length) {
      messages.value = [{ role: 'ai', text: '你好！我是张宇老师 👋 想了解平台怎么用都可以问我～比如：天赋测试怎么做？知识答题在哪里？' }]
    }
    await applyProfileData(profileData, uid)
  } catch (_) {}
}

async function loadProfile() {
  try {
    const uid = await ensureChildUser()
    const data = await fetchProfile(uid)
    await applyProfileData(data, uid)
  } catch (_) {}
}

function onGradeChange(e) {
  gradeIndex.value = e.detail.value
  profile.value.grade = gradeOptions[e.detail.value]
}

async function saveProfile() {
  try {
    const uid = await ensureChildUser()
    const existing = await fetchProfile(uid)
    const pj = { ...(existing.profile_json || {}), grade: profile.value.grade, parentName: profile.value.parentName }
    await saveProfileToDb(uid, {
      nickname: profile.value.name,
      profile_json: pj,
    })
    if (profile.value.grade) {
      await updateLearnerProfile(uid, {
        grade: profile.value.grade,
        school_stage: gradeToSchoolStage(profile.value.grade),
      })
    }
    uni.showToast({ title: '已保存', icon: 'none' })
  } catch (_) { uni.showToast({ title: '保存失败', icon: 'none' }) }
}

async function deleteHistory(assessmentId) {
  try {
    const uid = await ensureChildUser()
    await deleteAssessmentReport(uid, assessmentId)
    historyList.value = historyList.value.filter(h => h.id !== assessmentId)
    await loadProfile()
    uni.showToast({ title: '已删除', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '删除失败', icon: 'none' })
  }
}

async function clearGuideChat() {
  try {
    const uid = await ensureChildUser()
    await clearGuideSession(uid)
    guideSessionId.value = null
    messages.value = [{ role: 'ai', text: '你好！我是张宇老师 👋 想了解平台怎么用都可以问我～比如：天赋测试怎么做？知识答题在哪里？' }]
    uni.showToast({ title: '对话已清空', icon: 'none' })
  } catch (_) {
    uni.showToast({ title: '清空失败', icon: 'none' })
  }
}

function viewHistory(h) {
  if (h.id) {
    showSettings.value = false
    uni.navigateTo({ url: `/pages/report/index?assessment_id=${h.id}` })
  }
}

function confirmDeleteHistory(h) {
  if (!h?.id) return
  uni.showModal({
    title: '删除报告',
    content: `确定删除「${h.talent_primary || h.talent || '测评'}」报告？`,
    confirmText: '删除',
    confirmColor: '#ef4444',
    success: (res) => { if (res.confirm) deleteHistory(h.id) },
  })
}

function doLogout() {
  try {
    clearChildUserId()
    localStorage.removeItem('jnao_logged_in')
    localStorage.removeItem('jnao_user')
  } catch (_) {}
  showSettings.value = false
  uni.redirectTo({ url: '/pages/login/index' })
}

onMounted(() => {
  try {
    if (localStorage.getItem('jnao_logged_in') !== '1') {
      uni.redirectTo({ url: '/pages/login/index' })
      return
    }
  } catch (_) {}
  initHome()
})

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
  const routes = {
    talent: '/pages/talent/index',
    train: '/pages/training/index',
    qa: '/pages/qa/index',
    growth: '/pages/growth/index',
  }
  const url = routes[name]
  if (url) uni.navigateTo({ url })
  else uni.showToast({ title: '进入: ' + name, icon: 'none' })
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

.nav-bar { display:flex; align-items:center; justify-content:space-between; padding:10px 16px 8px; }
.nav-spacer { width:78px; flex-shrink:0; }
.nav-center { color:var(--text); font-size:15px; font-weight:500; text-align:center; }
.nav-actions { display:flex; align-items:center; gap:6px; flex-shrink:0; }
.nav-icon-btn { width:32px; height:32px; display:flex; align-items:center; justify-content:center; border-radius:8px; cursor:pointer; opacity:0.55; transition:opacity 0.15s; }
.nav-icon-btn:active { opacity:1; background:rgba(255,255,255,0.06); }
.nav-icon-btn svg { display:block; }

.hero-img { width:calc(100% - 28px); margin:0 14px; border-radius:16px; display:block; }

.func-grid { display:flex; gap:8px; padding:12px 14px; }
.func-card { flex:1; background:var(--bg-card); border-radius:12px; padding:12px 6px 10px; display:flex; flex-direction:column; align-items:center; gap:6px; border:1.5px solid transparent; transition:all 0.15s; }
.func-card:active { background:var(--accent-bg); border-color:var(--accent); transform:scale(0.95); }
.func-icon { width:34px; height:34px; border-radius:8px; display:flex; align-items:center; justify-content:center; background:var(--accent-bg); }
.func-label { color:var(--text-sub); font-size:11px; font-weight:500; }

.chat-section { flex:1; overflow-y:auto; padding:8px 14px 0; scrollbar-width:none; -ms-overflow-style:none; }
.chat-section::-webkit-scrollbar { display:none; }
.chat-row { display:flex; gap:8px; margin-bottom:12px; align-items:flex-end; }
.chat-row.user { flex-direction:row-reverse; }
.chat-av { width:32px; height:32px; border-radius:8px; flex-shrink:0; display:flex; align-items:center; justify-content:center; overflow:hidden; }
.chat-av.ai { background:var(--chat-ai-bg); border:1px solid var(--border); }
.chat-av.me { background:var(--chat-me-bg); border-radius:50%; color:var(--text-dim); font-size:12px; }
.ai-avatar-img { width:100%; height:100%; border-radius:8px; object-fit:cover; }
.chat-bbl { max-width:76%; padding:9px 13px; border-radius:14px; font-size:13px; line-height:1.55; word-break:break-word; white-space:pre-wrap; }
.chat-bbl.ai { background:var(--chat-ai-bg); color:var(--text); border-bottom-left-radius:4px; }
.chat-bbl.me { background:var(--chat-me-bg); color:var(--text-sub); border-bottom-right-radius:4px; }
[data-theme="white"] .chat-bbl.me { background:#eef2ff; color:#1e293b; border:1px solid #e0e7ff; }

.input-panel { margin:8px 14px 14px; background:var(--bg-card); border-radius:18px; padding:8px 10px; display:flex; align-items:center; gap:8px; border:1px solid var(--border); }
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

/* Settings modal */
.picker-overlay { position:fixed; inset:0; z-index:500; background:rgba(0,0,0,0.75); display:flex; align-items:center; justify-content:center; padding:20px; }
.picker-card { background:var(--bg-card); border:1px solid var(--border); border-radius:14px; padding:24px 20px; width:100%; max-width:340px; max-height:85vh; overflow-y:auto; }
.settings-card { animation:settingsIn 0.3s cubic-bezier(0.22,0.61,0.36,1); }
@keyframes settingsIn { from { opacity:0; transform:translateY(30px); } to { opacity:1; transform:translateY(0); } }
.picker-title { color:var(--text); font-size:16px; font-weight:700; text-align:center; display:block; margin-bottom:16px; }
.set-block { margin-bottom:4px; border:1px solid var(--border); border-radius:10px; overflow:hidden; }
.set-block-head { display:flex; align-items:center; justify-content:space-between; padding:12px 14px; cursor:pointer; background:rgba(255,255,255,0.02); }
.set-block-title { color:var(--text); font-size:13px; font-weight:600; }
.set-block-arrow { color:var(--text-dim); font-size:12px; transition:transform 0.2s; }
.set-block-arrow.open { transform:rotate(180deg); }
.set-block-body { padding:4px 14px 14px; }
.talent-readonly { color:var(--accent); font-weight:600; }
.form-input-dim { color:var(--text-dim); }
.picker-close { text-align:center; margin-top:10px; cursor:pointer; }
.picker-close text { color:var(--text-dim); font-size:14px; }
.form-row { display:flex; align-items:center; gap:10px; margin-bottom:10px; }
.form-row:last-child { margin-bottom:0; }
.form-label { color:var(--text-dim); font-size:13px; width:56px; flex-shrink:0; }
.form-input { flex:1; background:var(--bg-input); border:1px solid var(--border); border-radius:10px; padding:10px 12px; font-size:13px; color:var(--text); }
.form-picker { flex:1; }
.form-picker-val { color:var(--text); }
.btn-checkin { background:linear-gradient(135deg,var(--accent),#3b8bff); border-radius:10px; padding:12px; text-align:center; cursor:pointer; margin-top:4px; }
.btn-checkin text { color:#fff; font-size:15px; font-weight:600; }
.btn-checkin:active { opacity:0.85; }
.btn-logout { background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.25); border-radius:10px; padding:10px; text-align:center; cursor:pointer; margin-top:8px; }
.btn-logout text { color:rgba(239,68,68,0.8); font-size:14px; font-weight:500; }
.btn-logout:active { background:rgba(239,68,68,0.2); }
.history-mini { max-height:160px; overflow-y:auto; }
.hm-item { display:flex; align-items:center; gap:8px; padding:8px 0; border-bottom:1px solid var(--border); cursor:pointer; }
.hm-del { color:#f85149; font-size:14px; padding:0 4px; cursor:pointer; flex-shrink:0; }
.btn-clear-chat { margin-top:10px; padding:10px; text-align:center; border:1px dashed var(--border); border-radius:10px; cursor:pointer; }
.btn-clear-chat text { color:var(--text-dim); font-size:12px; }
.hm-item:last-child { border-bottom:none; }
.hm-talent { flex:1; color:var(--text); font-size:12px; font-weight:600; }
.hm-time { color:var(--text-dim); font-size:10px; }
.hm-arrow { color:var(--text-dim); font-size:16px; }
.hm-del { color:var(--text-dim); font-size:14px; padding:4px; cursor:pointer; }
.hm-del:active { color:#ef4444; }
.history-empty { color:var(--text-dim); font-size:12px; text-align:center; padding:8px 0; }
</style>
