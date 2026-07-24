<template>
  <view class="app">
    <!-- Nav Bar -->
    <view class="nav-bar">
      <view class="nav-spacer"></view>
      <text class="nav-center" @click="onNavTap">张宇老师</text>
      <view class="nav-actions">
        <!-- 设置 -->
        <view class="nav-icon-btn" @click="openSettings">
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
    <image class="hero-img" src="/static/teacher.png" mode="widthFix" lazy-load />

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

    <!-- 今日轻状态（bootstrap.situation_label） -->
    <view v-if="situationLabel" class="home-status-bar">
      <text class="home-status-text">{{ situationLabel }}</text>
    </view>

    <!-- Chat Area -->
    <view class="chat-section" id="chatScroll">
      <!-- 开场欢迎（bootstrap；对话开始后仍保留，避免割裂） -->
      <view v-if="welcomeText" class="chat-welcome">
        <view class="chat-av ai"><image class="ai-avatar-img" src="/static/teacher-avatar.png" mode="aspectFill"></image></view>
        <view class="welcome-card">
          <text class="welcome-sub">{{ welcomeText }}</text>
          <view v-if="welcomeActions.length" class="chat-actions welcome-actions">
            <view
              v-for="(act, ai) in welcomeActions"
              :key="ai"
              class="welcome-action"
              @click="runNavigateAction(act)"
            >
              <text>{{ act.label || actionLabel(act.target) }}</text>
            </view>
          </view>
        </view>
      </view>
      <!-- 聊天记录 -->
      <view v-for="(m,i) in messages" :key="i" class="chat-row" :class="{ user: m.role === 'user' }">
        <view class="chat-av me" v-if="m.role==='user'">
          <image v-if="userTalentAvatar" class="user-avatar-img" :src="userTalentAvatar" mode="aspectFill"></image>
          <text v-else>我</text>
        </view>
        <view class="chat-av ai" v-else><image class="ai-avatar-img" src="/static/teacher-avatar.png" mode="aspectFill"></image></view>
        <view class="chat-bbl-wrap" :class="{ me: m.role==='user' }">
          <view
            v-if="m.role==='ai' && loading && i === messages.length - 1 && !m.text"
            class="chat-bbl ai thinking-bbl"
          >
            <view class="thinking-dots" aria-hidden="true">
              <view class="thinking-dot"></view>
              <view class="thinking-dot"></view>
              <view class="thinking-dot"></view>
            </view>
            <text class="thinking-label">agent思考中</text>
          </view>
          <view
            v-else-if="m.text"
            class="chat-bbl"
            :class="{ me: m.role==='user', ai: m.role!=='user' }"
          >{{ m.text }}</view>
          <view
            v-if="m.role==='ai' && m.actions?.length"
            class="chat-actions"
          >
            <view
              v-for="(act, ai) in m.actions"
              :key="ai"
              class="welcome-action"
              @click="runNavigateAction(act)"
            >
              <text>{{ act.label || actionLabel(act.target) }}</text>
            </view>
          </view>
          <view
            v-if="guideDebugTools && m.role==='ai' && m.tools_used?.length"
            class="tools-debug"
          >
            <text class="tools-debug-label">tools</text>
            <view
              v-for="(t, ti) in m.tools_used"
              :key="ti"
              class="tools-debug-chip"
              :class="{ fail: t.ok === false }"
            >
              <text>{{ t.name || 'tool' }}{{ t.ok === false ? ' ✕' : '' }}</text>
            </view>
          </view>
        </view>
      </view>
    </view>

    <!-- Bottom Input -->
    <view class="input-panel">
      <view class="input-wrap">
        <textarea class="chat-input" v-model="inputText" placeholder="输入问题..." :disabled="loading" @keydown="onKeyDown" :rows="1" />
        <view class="input-btns">
          <view class="btn-send" :class="{ 'btn-stop': loading }" @click="loading ? stopStream() : sendMsg()">
            <text v-if="loading" style="color:#fff;font-size:12px;font-weight:700;">■</text>
            <text v-else style="color:#fff;font-size:14px;">➤</text>
          </view>
        </view>
      </view>
    </view>

    <!-- Settings Modal -->
    <view v-if="showSettings" class="picker-overlay" @click="showSettings = false">
      <view class="picker-card settings-card" @click.stop>
        <view class="settings-header">
          <text class="picker-title">设置</text>
          <view class="settings-close-x" @click="showSettings = false"><text>×</text></view>
        </view>

        <view class="settings-sections">
          <!-- 个人信息 -->
          <view class="acc-item" :class="{ open: settingsOpen.profile }">
            <view class="acc-head" @click="toggleSettingsSection('profile')">
              <view class="acc-head-left">
                <view class="acc-icon">👤</view>
                <text class="acc-title">个人信息</text>
              </view>
              <text class="acc-chevron" :class="{ open: settingsOpen.profile }">›</text>
            </view>
            <view v-if="settingsOpen.profile" class="acc-body">
              <view class="field">
                <text class="field-label">孩子姓名</text>
                <input
                  class="field-input"
                  type="text"
                  :value="profile.name"
                  placeholder="孩子真实姓名"
                  placeholder-class="field-ph"
                  @input="onProfileNameInput"
                />
              </view>
              <view class="field">
                <text class="field-label">年级</text>
                <picker class="field-picker" mode="selector" :range="gradeOptions" :value="gradeIndex" @change="onGradeChange">
                  <view class="field-input field-select">{{ profile.grade || '请选择年级' }}</view>
                </picker>
              </view>
              <view v-if="profile.talent" class="field">
                <text class="field-label">天赋</text>
                <view class="field-input field-readonly">{{ profile.talent }}</view>
              </view>
              <view class="field">
                <text class="field-label">家长手机</text>
                <view class="field-input field-readonly dim">{{ profile.phone || '暂无' }}</view>
              </view>
              <view class="field">
                <text class="field-label">家长姓名</text>
                <input
                  class="field-input"
                  type="text"
                  :value="profile.parentName"
                  placeholder="家长姓名（选填）"
                  placeholder-class="field-ph"
                  @input="onParentNameInput"
                />
              </view>
              <view class="btn-primary" @click="saveProfile"><text>保存信息</text></view>
            </view>
          </view>

          <!-- 首页对话 -->
          <view class="acc-item" :class="{ open: settingsOpen.chat }">
            <view class="acc-head" @click="toggleSettingsSection('chat')">
              <view class="acc-head-left">
                <view class="acc-icon">💬</view>
                <text class="acc-title">首页对话</text>
              </view>
              <text class="acc-chevron" :class="{ open: settingsOpen.chat }">›</text>
            </view>
            <view v-if="settingsOpen.chat" class="acc-body">
              <view class="btn-secondary" @click="startNewGuideChat">
                <text>＋ 新建对话</text>
              </view>
              <text class="btn-hint">不删除当前内容，会留在下方历史里；下一句起新会话</text>

              <view class="chat-actions-row">
                <view class="btn-text-action" @click="clearCurrentGuideChat">
                  <text>删除当前对话</text>
                </view>
              </view>

              <view class="list-section">
                <view class="list-section-head">
                  <text class="list-section-title">历史对话</text>
                  <text
                    v-if="guideSessionList.length"
                    class="list-section-action"
                    @click="confirmClearAllGuideSessions"
                  >清空全部</text>
                </view>
                <view v-if="guideSessionsLoading" class="list-empty"><text>加载中…</text></view>
                <view v-else-if="guideSessionList.length" class="session-list">
                  <view
                    v-for="s in guideSessionList"
                    :key="s.id"
                    class="session-item"
                    :class="{ active: s.id === guideSessionId }"
                  >
                    <view class="session-main" @click="switchGuideSession(s.id)">
                      <text class="session-title">{{ s.title || '首页对话' }}</text>
                      <text class="session-time">{{ formatGuideSessionTime(s.updated_at || s.created_at) }}</text>
                    </view>
                    <view class="session-del" @click.stop="confirmDeleteGuideSession(s)">
                      <text>×</text>
                    </view>
                  </view>
                </view>
                <view v-else class="list-empty"><text>暂无历史对话</text></view>
              </view>

              <view class="debug-row" @click="toggleGuideDebugTools">
                <text class="debug-row-label">调试：显示工具调用</text>
                <view class="debug-switch" :class="{ on: guideDebugTools }">
                  <view class="debug-switch-knob"></view>
                </view>
              </view>
            </view>
          </view>
        </view>

        <view class="settings-footer">
          <view class="btn-danger" @click="doLogout"><text>登出账号</text></view>
          <view class="btn-text" @click="showSettings = false"><text>关闭</text></view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
import {
  clearChildUserId,
  ensureChildUser,
  requirePageAuth,
  logoutAndGoLogin,
  getChildUserId,
  markChildUserSessionValid,
  invalidateChildUserSession,
  fetchGuideSession,
  fetchGuideSessions,
  fetchGuideSessionById,
  deleteGuideSession,
  fetchGuideBootstrap,
  sendGuideMessageStream,
  clearGuideSession,
  fetchProfile,
  saveProfile as saveProfileToDb,
  fetchLatestAssessment,
  updateLearnerProfile,
  gradeToSchoolStage,
} from '@/utils/userApi.js'
import { refreshTalentState } from '@/utils/talentState.js'
import { isStreamAborted, applyStreamStoppedHint } from '@/utils/chatStream.js'

const isLight = ref(true)
const inputText = ref('')
const loading = ref(false)
let streamAbort = null
let abortRequested = false
const guideSessionId = ref(null)
const messages = ref([])
const showSettings = ref(false)
const settingsOpen = ref({ profile: true, chat: true })
const guideSessionList = ref([])
const guideSessionsLoading = ref(false)
const GUIDE_DEBUG_KEY = 'jnao_guide_debug_tools'
const guideDebugTools = ref(false)
try {
  guideDebugTools.value = localStorage.getItem(GUIDE_DEBUG_KEY) === '1'
} catch (_) {}

function toggleGuideDebugTools() {
  guideDebugTools.value = !guideDebugTools.value
  try {
    localStorage.setItem(GUIDE_DEBUG_KEY, guideDebugTools.value ? '1' : '0')
  } catch (_) {}
  uni.showToast({
    title: guideDebugTools.value ? '已开启工具调试' : '已关闭工具调试',
    icon: 'none',
  })
}
const profile = ref({ name: '', grade: '', talent: '', phone: '', parentName: '', assessmentId: null })
const gradeOptions = ['一年级','二年级','三年级','四年级','五年级','六年级','初一','初二','初三','高一','高二','高三']
const gradeIndex = ref(0)
const welcomeText = ref('正在了解你的训练状态…')
const welcomeActions = ref([])
const situationLabel = ref('')

/** 与 backend handoff.ACTION_LABELS 对齐；优先用 API 返回的 act.label */
const ACTION_LABEL_FALLBACK = {
  talent: '去天赋测试 ›',
  report: '去天赋报告 ›',
  train: '去今日训练 ›',
  qa: '去学科答疑 ›',
  growth: '去成长里程碑 ›',
}

/** 与报告页 TALENT_LOGOS 一致 */
const TALENT_LOGOS = {
  学者: '/static/xue.jpg',
  思者: '/static/si.jpg',
  赢者: '/static/ying.jpg',
  德者: '/static/de.jpg',
  行者: '/static/xing.jpg',
}

function resolveTalentLogoKey(raw) {
  if (!raw) return ''
  const s = String(raw).trim()
  for (const name of Object.keys(TALENT_LOGOS)) {
    if (s === name || s.includes(name)) return name
  }
  const tagMap = { 学: '学者', 思: '思者', 赢: '赢者', 德: '德者', 行: '行者' }
  return tagMap[s[0]] || ''
}

const userTalentAvatar = computed(() => {
  const key = resolveTalentLogoKey(profile.value.talent)
  return key ? TALENT_LOGOS[key] : ''
})

function actionLabel(target) {
  return ACTION_LABEL_FALLBACK[target] || '前往 ›'
}

function normalizeNavigateActions(raw) {
  if (!Array.isArray(raw)) return []
  return raw
    .filter(a => a && a.type === 'navigate' && ACTION_LABEL_FALLBACK[a.target])
    .map(a => ({
      type: 'navigate',
      target: a.target,
      label: a.label || actionLabel(a.target),
    }))
}

function runNavigateAction(act) {
  const target = act?.target
  if (target) openPage(target)
}

try {
  const saved = localStorage.getItem('jnao_theme')
  // 默认白色主题，仅当明确存了 dark 时才用暗色
  isLight.value = saved !== 'dark'
} catch (e) {}
// 初始应用主题
document.documentElement.setAttribute('data-theme', isLight.value ? 'white' : 'dark')

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
  const text = inputText.value.trim()
  if (!text || loading.value) return
  messages.value.push({ role: 'user', text })
  inputText.value = ''
  const aiIdx = messages.value.length
  messages.value.push({ role: 'ai', text: '', actions: [], tools_used: [] })
  loading.value = true
  abortRequested = false
  await nextTick()
  scrollChat()
  try {
    const uid = await ensureChildUser()
    if (abortRequested) {
      applyStreamStoppedHint(messages, aiIdx)
      return
    }
    const { promise, abort } = sendGuideMessageStream(uid, text, guideSessionId.value, {
      onToken(chunk) {
        messages.value[aiIdx].text += chunk
        scrollChat()
      },
      onDone(data) {
        guideSessionId.value = data.session_id
        if (data.reply) messages.value[aiIdx].text = data.reply
        if (Array.isArray(data.actions)) {
          messages.value[aiIdx].actions = normalizeNavigateActions(data.actions)
        }
        if (Array.isArray(data.tools_used)) {
          messages.value[aiIdx].tools_used = data.tools_used
        }
        if (data.situation_label) situationLabel.value = data.situation_label
      },
    })
    streamAbort = abort
    await promise
  } catch (e) {
    if (isStreamAborted(e)) {
      applyStreamStoppedHint(messages, aiIdx)
    } else if (!messages.value[aiIdx].text) {
      messages.value[aiIdx].text = e?.message || '网络错误，请稍后再试'
    }
  } finally {
    streamAbort = null
    abortRequested = false
    loading.value = false
  }
  await nextTick()
  scrollChat()
}

function stopStream() {
  abortRequested = true
  streamAbort?.()
}

function applyProfileData(data, uid, { fetchLatest = true } = {}) {
  if (data.nickname != null && String(data.nickname).trim()) {
    profile.value.name = String(data.nickname).trim()
  }
  if (data.parent_phone) profile.value.phone = data.parent_phone
  if (data.parent_name != null && String(data.parent_name).trim()) {
    profile.value.parentName = String(data.parent_name).trim()
  }
  let hasTalent = false
  if (data.profile_json) {
    const grade = data.profile_json.grade || data.profile_json.learner?.grade
    if (grade) profile.value.grade = grade
    if (!profile.value.parentName && data.profile_json.parentName) {
      profile.value.parentName = String(data.profile_json.parentName).trim()
    }
    const aid = data.profile_json.latest_assessment_id
    if (aid && Number(aid) > 0) profile.value.assessmentId = Number(aid)
    const td = data.profile_json.talent_display
    const tp = data.profile_json.talent_primary || data.profile_json.talent
    const obName = data.profile_json.onboarding?.self_reported_talent
    if (td) {
      hasTalent = true
      profile.value.talent = td
    } else if (tp) {
      hasTalent = true
      profile.value.talent = tp
    } else if (data.talent_primary) {
      hasTalent = true
      profile.value.talent = data.talent_primary
    } else if (obName) {
      hasTalent = true
      profile.value.talent = obName
    } else if (data.training_level && data.training_level !== '学员') {
      hasTalent = true
      profile.value.talent = data.training_level
    }
  }
  const idx = gradeOptions.indexOf(profile.value.grade)
  if (idx >= 0) gradeIndex.value = idx
  if (fetchLatest && uid) {
    return fetchLatestAssessment(uid).then((latest) => {
      if (latest?.id && Number(latest.id) > 0) {
        profile.value.assessmentId = Number(latest.id)
      }
      if (!hasTalent && latest?.talent_primary) {
        profile.value.talent = latest.talent_primary
      }
    }).catch(() => {})
  }
  return Promise.resolve()
}

function _inputValue(e) {
  if (e?.detail != null && e.detail.value != null) return String(e.detail.value)
  if (e?.target != null && e.target.value != null) return String(e.target.value)
  return ''
}

function onProfileNameInput(e) {
  profile.value.name = _inputValue(e)
}

function onParentNameInput(e) {
  profile.value.parentName = _inputValue(e)
}

async function initHome() {
  try {
    let uid = getChildUserId()
    if (!uid) uid = await ensureChildUser()
    let profileData
    let guideData
    let bootstrapData
    try {
      const talentWarm = refreshTalentState(uid).catch(() => null)
      ;[profileData, guideData, bootstrapData] = await Promise.all([
        fetchProfile(uid),
        fetchGuideSession(uid),
        fetchGuideBootstrap(uid).catch(() => null),
      ])
      await talentWarm
      markChildUserSessionValid(uid)
    } catch (e) {
      if (e.status === 404 && getChildUserId()) {
        invalidateChildUserSession()
        clearChildUserId()
        uid = await ensureChildUser()
        ;[profileData, guideData, bootstrapData] = await Promise.all([
          fetchProfile(uid),
          fetchGuideSession(uid),
          fetchGuideBootstrap(uid).catch(() => null),
        ])
        markChildUserSessionValid(uid)
      } else {
        throw e
      }
    }
    applyGuideMessages(guideData)
    applyBootstrap(bootstrapData)
    await applyProfileData(profileData, uid)
  } catch (e) {
    console.error('[home] initHome 失败:', e?.message || e, e?.status)
    welcomeText.value = '你好！我是张宇老师。有问题随时问我，也可以从上方入口进入各功能。'
  }
}

function applyGuideMessages(guideData) {
  if (!guideData) {
    guideSessionId.value = null
    messages.value = []
    return
  }
  guideSessionId.value = guideData.session_id
  const rawMsgs = guideData.messages || []
  const hasUser = rawMsgs.some(m => m.role === 'user')
  messages.value = (hasUser ? rawMsgs : [])
    .map(m => {
      const isAi = m.role === 'assistant' || m.role === 'ai'
      return {
        role: isAi ? 'ai' : 'user',
        text: m.content || m.text || '',
        actions: isAi ? normalizeNavigateActions(m.actions) : [],
        tools_used: isAi && Array.isArray(m.tools_used) ? m.tools_used : [],
      }
    })
}

function applyBootstrap(data) {
  if (!data || data.error) {
    welcomeText.value = '你好！我是张宇老师。有问题随时问我，也可以从上方入口进入各功能。'
    welcomeActions.value = []
    situationLabel.value = ''
    return
  }
  welcomeText.value = data.welcome || '你好！我是张宇老师。今天可以从上方入口开始训练或提问。'
  const fromActions = normalizeNavigateActions(data.actions)
  if (fromActions.length) {
    welcomeActions.value = fromActions
  } else if (ACTION_LABEL_FALLBACK[data.next_action]) {
    // 兼容旧缓存仅有 next_action、无 actions 的情况
    welcomeActions.value = [{
      type: 'navigate',
      target: data.next_action,
      label: actionLabel(data.next_action),
    }]
  } else {
    welcomeActions.value = []
  }
  situationLabel.value = data.situation_label || ''
}

async function loadProfile() {
  try {
    const uid = await ensureChildUser()
    const data = await fetchProfile(uid)
    await applyProfileData(data, uid)
  } catch (e) {
    console.error('[home] loadProfile 失败:', e?.message || e, e?.status)
  }
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

async function openSettings() {
  settingsOpen.value = { profile: true, chat: true }
  showSettings.value = true
  await Promise.all([loadProfile(), loadGuideSessionList()])
}

function toggleSettingsSection(key) {
  settingsOpen.value = {
    ...settingsOpen.value,
    [key]: !settingsOpen.value[key],
  }
  if (key === 'chat' && settingsOpen.value.chat) {
    loadGuideSessionList()
  }
  if (key === 'profile' && settingsOpen.value.profile) {
    loadProfile()
  }
}

async function loadGuideSessionList() {
  guideSessionsLoading.value = true
  try {
    const uid = await ensureChildUser()
    guideSessionList.value = await fetchGuideSessions(uid)
  } catch (e) {
    console.error('[home] loadGuideSessionList 失败:', e?.message || e)
    guideSessionList.value = []
  } finally {
    guideSessionsLoading.value = false
  }
}

function formatGuideSessionTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return String(iso).slice(0, 16)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function startNewGuideChat() {
  if (loading.value) {
    uni.showToast({ title: '请先停止当前回复', icon: 'none' })
    return
  }
  try {
    const uid = await ensureChildUser()
    // 不删除当前会话：保留进历史，下一句消息会新建 session
    guideSessionId.value = null
    messages.value = []
    const bootstrapData = await fetchGuideBootstrap(uid, { force: false }).catch(() => null)
    applyBootstrap(bootstrapData)
    await loadGuideSessionList()
    showSettings.value = false
    await nextTick()
    scrollChat()
    uni.showToast({ title: '已开新对话', icon: 'none' })
  } catch (_) {
    uni.showToast({ title: '新建失败', icon: 'none' })
  }
}

async function clearCurrentGuideChat() {
  if (loading.value) {
    uni.showToast({ title: '请先停止当前回复', icon: 'none' })
    return
  }
  try {
    const uid = await ensureChildUser()
    if (guideSessionId.value) {
      await deleteGuideSession(uid, guideSessionId.value)
    }
    guideSessionId.value = null
    messages.value = []
    const bootstrapData = await fetchGuideBootstrap(uid, { force: true }).catch(() => null)
    applyBootstrap(bootstrapData)
    await loadGuideSessionList()
    uni.showToast({ title: '当前对话已删除', icon: 'none' })
  } catch (_) {
    uni.showToast({ title: '删除失败', icon: 'none' })
  }
}

async function switchGuideSession(sessionId) {
  if (!sessionId || loading.value) return
  try {
    const uid = await ensureChildUser()
    const data = await fetchGuideSessionById(uid, sessionId)
    applyGuideMessages(data)
    showSettings.value = false
    await nextTick()
    scrollChat()
  } catch (e) {
    uni.showToast({ title: e?.message || '加载失败', icon: 'none' })
  }
}

function confirmDeleteGuideSession(s) {
  if (!s?.id) return
  uni.showModal({
    title: '删除对话',
    content: `确定删除「${s.title || '首页对话'}」？删除后无法恢复。`,
    confirmText: '删除',
    confirmColor: '#ef4444',
    success: async (res) => {
      if (!res.confirm) return
      try {
        const uid = await ensureChildUser()
        await deleteGuideSession(uid, s.id)
        if (guideSessionId.value === s.id) {
          guideSessionId.value = null
          messages.value = []
          const bootstrapData = await fetchGuideBootstrap(uid, { force: true }).catch(() => null)
          applyBootstrap(bootstrapData)
        }
        await loadGuideSessionList()
        uni.showToast({ title: '已删除', icon: 'none' })
      } catch (e) {
        uni.showToast({ title: e?.message || '删除失败', icon: 'none' })
      }
    },
  })
}

function confirmClearAllGuideSessions() {
  uni.showModal({
    title: '清空全部历史',
    content: '将删除所有首页对话记录（含当前），且无法恢复。确定继续？',
    confirmText: '全部清空',
    confirmColor: '#ef4444',
    success: async (res) => {
      if (!res.confirm) return
      try {
        const uid = await ensureChildUser()
        await clearGuideSession(uid)
        guideSessionId.value = null
        messages.value = []
        guideSessionList.value = []
        const bootstrapData = await fetchGuideBootstrap(uid, { force: true }).catch(() => null)
        applyBootstrap(bootstrapData)
        uni.showToast({ title: '历史已清空', icon: 'none' })
      } catch (_) {
        uni.showToast({ title: '清空失败', icon: 'none' })
      }
    },
  })
}

function doLogout() {
  logoutAndGoLogin()
  showSettings.value = false
}

onMounted(async () => {
  const auth = await requirePageAuth('student')
  if (!auth.ok) return
  initHome()
})

function scrollChat() {
  const el = document.getElementById('chatScroll')
  if (el) el.scrollTop = el.scrollHeight
}



async function openPage(name) {
  const routes = {
    talent: '/pages/talent/index',
    train: '/pages/training/index',
    qa: '/pages/qa/index',
    growth: '/pages/growth/index',
  }
  if (name === 'report') {
    try {
      const uid = await ensureChildUser()
      let aid = profile.value.assessmentId
      if (!aid || Number(aid) <= 0) {
        const latest = await fetchLatestAssessment(uid)
        aid = latest?.id
        if (aid && Number(aid) > 0) profile.value.assessmentId = Number(aid)
      }
      if (aid && Number(aid) > 0) {
        uni.navigateTo({ url: `/pages/report/index?assessment_id=${aid}` })
        return
      }
      uni.showToast({ title: '暂无正式报告，请先测评', icon: 'none' })
      uni.navigateTo({ url: '/pages/talent/index' })
    } catch (e) {
      uni.showToast({ title: e?.message || '无法打开报告', icon: 'none' })
    }
    return
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
  display:flex; flex-direction:column; height:100vh;height:100dvh; max-width:var(--app-max-width, 480px); margin:0 auto;
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

.home-status-bar {
  margin: 8px 14px 0; padding: 8px 12px; border-radius: 10px;
  background: var(--accent-bg); border: 1px solid var(--border);
}
.home-status-text { color: var(--accent); font-size: 12px; font-weight: 600; }

.func-grid { display:flex; gap:8px; padding:12px 14px; }
.func-card { flex:1; background:var(--bg-card); border-radius:12px; padding:12px 6px 10px; display:flex; flex-direction:column; align-items:center; gap:6px; border:1.5px solid transparent; transition:all 0.15s; }
.func-card:active { background:var(--accent-bg); border-color:var(--accent); transform:scale(0.95); }
.func-icon { width:34px; height:34px; border-radius:8px; display:flex; align-items:center; justify-content:center; background:var(--accent-bg); }
.func-label { color:var(--text-sub); font-size:11px; font-weight:500; }

.chat-section { flex:1; overflow-y:auto; padding:8px 14px 0; scrollbar-width:none; -ms-overflow-style:none; }
.chat-welcome { display:flex; gap:8px; align-items:flex-start; margin-bottom:12px; }
.welcome-card {
  flex:1; background:var(--chat-ai-bg); border-radius:14px;
  border-bottom-left-radius:4px; padding:14px 16px;
}
.welcome-text { display:block; color:var(--text); font-size:14px; font-weight:600; margin-bottom:4px; }
.welcome-sub { display:block; color:var(--text-sub); font-size:12px; line-height:1.5; white-space:pre-wrap; }
.welcome-actions { margin-top:10px; }
.welcome-action {
  display:inline-flex; padding:6px 12px; border-radius:8px;
  background:var(--accent-bg); border:1px solid var(--accent); cursor:pointer;
}
.welcome-action text { color:var(--accent); font-size:12px; font-weight:600; }
.welcome-action:active { opacity:0.85; }
.chat-section::-webkit-scrollbar { display:none; }
.chat-row { display:flex; gap:8px; margin-bottom:12px; align-items:flex-start; }
.chat-row.user { flex-direction:row-reverse; }
.chat-av { width:32px; height:32px; border-radius:8px; flex-shrink:0; display:flex; align-items:center; justify-content:center; overflow:hidden; }
.chat-av.ai { background:var(--chat-ai-bg); border:1px solid var(--border); }
.chat-av.me { background:var(--chat-me-bg); border-radius:50%; color:var(--text-dim); font-size:12px; }
.ai-avatar-img { width:100%; height:100%; border-radius:8px; object-fit:cover; }
.user-avatar-img { width:100%; height:100%; border-radius:50%; object-fit:cover; }
.chat-bbl { max-width:76%; padding:9px 13px; border-radius:14px; font-size:13px; line-height:1.55; word-break:break-word; white-space:pre-wrap; }
.chat-bbl-wrap { max-width:76%; display:flex; flex-direction:column; gap:6px; }
.chat-bbl-wrap .chat-bbl { max-width:100%; }
.chat-bbl-wrap.me { align-items:flex-end; }
.chat-actions { display:flex; flex-wrap:wrap; gap:6px; }
.tools-debug {
  display:flex; flex-wrap:wrap; align-items:center; gap:4px; margin-top:2px;
}
.tools-debug-label {
  color:var(--text-dim); font-size:10px; font-weight:600; margin-right:2px;
}
.tools-debug-chip {
  padding:2px 7px; border-radius:999px;
  background:rgba(88,166,255,0.12); border:1px solid rgba(88,166,255,0.35);
}
.tools-debug-chip text { color:var(--accent); font-size:10px; font-weight:600; }
.tools-debug-chip.fail {
  background:rgba(239,68,68,0.1); border-color:rgba(239,68,68,0.35);
}
.tools-debug-chip.fail text { color:#ef4444; }
.chat-bbl.ai { background:var(--chat-ai-bg); color:var(--text); border-bottom-left-radius:4px; }
.chat-bbl.me { background:var(--chat-me-bg); color:var(--text-sub); border-bottom-right-radius:4px; }
[data-theme="white"] .chat-bbl.me { background:#eef2ff; color:#1e293b; border:1px solid #e0e7ff; }

.thinking-bbl {
  display:flex; align-items:center; gap:8px; min-height:20px;
}
.thinking-dots { display:flex; align-items:center; gap:4px; }
.thinking-dot {
  width:6px; height:6px; border-radius:50%;
  background:var(--accent); opacity:0.35;
  animation:thinkingBounce 1.2s ease-in-out infinite;
}
.thinking-dot:nth-child(2) { animation-delay:0.15s; }
.thinking-dot:nth-child(3) { animation-delay:0.3s; }
.thinking-label {
  color:var(--text-dim); font-size:11px; font-weight:500;
  animation:thinkingPulse 1.4s ease-in-out infinite;
}
@keyframes thinkingBounce {
  0%, 80%, 100% { transform:translateY(0); opacity:0.3; }
  40% { transform:translateY(-3px); opacity:1; }
}
@keyframes thinkingPulse {
  0%, 100% { opacity:0.45; }
  50% { opacity:0.9; }
}

.input-panel { margin:8px 14px 14px; }
.input-wrap { position:relative; display:flex; align-items:center; background:rgba(255,255,255,0.1); border-radius:24px; padding:4px; border:1px solid rgba(255,255,255,0.15); }
[data-theme="white"] .input-wrap { background:#f3f4f6; border-color:#d1d5db; }
.chat-input { flex:1; background:transparent; border-radius:20px; padding:8px 8px 8px 14px; font-size:13px; color:var(--text); border:none; outline:none; resize:none; height:36px; line-height:20px; overflow-y:auto; }
.input-btns { display:flex; align-items:center; gap:6px; flex-shrink:0; padding-right:4px; }
.loading-dots { animation:dotPulse 1.4s infinite; }
@keyframes dotPulse { 0%,80%,100% { opacity:0.2 } 40% { opacity:1 } }
.btn-send { width:32px; height:32px; border-radius:50%; background:var(--accent); display:flex !important; align-items:center; justify-content:center; cursor:pointer; flex-shrink:0; }
.btn-send.btn-stop { background:#ef4444; }
.btn-send:active { opacity:0.8; }
.btn-disabled { opacity:0.45; pointer-events:none; }

/* Settings modal */
.picker-overlay {
  position:fixed; inset:0; z-index:500;
  background:rgba(15,23,42,0.55); backdrop-filter:blur(6px);
  display:flex; align-items:center; justify-content:center; padding:20px;
}
.picker-card {
  background:var(--bg-card); border:1px solid var(--border);
  border-radius:20px; padding:0; width:100%; max-width:360px;
  max-height:85vh; max-height:85dvh; overflow-y:auto;
  box-shadow:0 20px 50px rgba(0,0,0,0.22);
  scrollbar-width:none; -ms-overflow-style:none;
}
.picker-card::-webkit-scrollbar { display:none; }
.settings-card { animation:settingsIn 0.28s cubic-bezier(0.22,0.61,0.36,1); }
@keyframes settingsIn { from { opacity:0; transform:translateY(18px) scale(0.98); } to { opacity:1; transform:translateY(0) scale(1); } }

.settings-header {
  display:flex; align-items:center; justify-content:center;
  position:relative; padding:18px 20px 12px;
  border-bottom:1px solid var(--border);
}
.picker-title { color:var(--text); font-size:16px; font-weight:700; text-align:center; display:block; margin:0; }
.settings-close-x {
  position:absolute; right:14px; top:50%; transform:translateY(-50%);
  width:28px; height:28px; border-radius:50%;
  display:flex; align-items:center; justify-content:center;
  background:var(--bg-input); cursor:pointer;
}
.settings-close-x text { color:var(--text-dim); font-size:18px; line-height:1; }
.settings-close-x:active { opacity:0.7; }

.settings-sections { padding:14px 16px; display:flex; flex-direction:column; gap:10px; }

.acc-item {
  border:1px solid var(--border); border-radius:14px;
  background:var(--bg); overflow:hidden;
  transition:border-color 0.15s, box-shadow 0.15s;
}
.acc-item.open { border-color:var(--accent); }
.acc-head {
  display:flex; align-items:center; justify-content:space-between;
  padding:13px 14px; cursor:pointer; user-select:none;
}
.acc-head:active { background:rgba(127,127,127,0.06); }
.acc-head-left { display:flex; align-items:center; gap:10px; }
.acc-icon {
  width:28px; height:28px; border-radius:8px;
  display:flex; align-items:center; justify-content:center;
  background:var(--accent-bg); font-size:14px;
}
.acc-title { color:var(--text); font-size:14px; font-weight:600; }
.acc-chevron {
  color:var(--text-dim); font-size:18px; font-weight:400;
  transform:rotate(90deg); transition:transform 0.2s ease; line-height:1;
}
.acc-chevron.open { transform:rotate(-90deg); }
.acc-body {
  padding:4px 14px 14px;
  border-top:1px solid var(--border);
}

.field { margin-bottom:10px; }
.field:last-of-type { margin-bottom:12px; }
.field-label {
  display:block; color:var(--text-dim); font-size:11px; font-weight:600;
  letter-spacing:0.02em; margin-bottom:5px;
}
.field-input {
  display:block; width:100%; box-sizing:border-box;
  min-height:40px; line-height:20px;
  background:var(--bg-input, #f3f4f6); border:1px solid var(--border);
  border-radius:10px; padding:10px 12px; font-size:13px;
  color:var(--text); -webkit-text-fill-color:var(--text);
}
.field-ph { color:var(--text-dim); }
.field-picker { display:block; width:100%; }
.field-select { color:var(--text); -webkit-text-fill-color:var(--text); }
.field-readonly { color:var(--accent); -webkit-text-fill-color:var(--accent); font-weight:600; }
.field-readonly.dim { color:var(--text-dim); -webkit-text-fill-color:var(--text-dim); font-weight:500; }
[data-theme="white"] .field-input {
  background:#f3f4f6; border-color:#e5e7eb; color:#1f2937; -webkit-text-fill-color:#1f2937;
}
[data-theme="dark"] .field-input {
  background:rgba(255,255,255,0.06); color:#e5e7eb; -webkit-text-fill-color:#e5e7eb;
}

.btn-primary {
  background:var(--accent); border-radius:10px; padding:11px;
  text-align:center; cursor:pointer; margin-top:2px;
}
.btn-primary text { color:#fff; font-size:14px; font-weight:600; }
.btn-primary:active { opacity:0.88; }

.btn-secondary {
  background:var(--bg-card); border:1px solid var(--border);
  border-radius:10px; padding:10px; text-align:center; cursor:pointer;
}
.btn-secondary text { color:var(--text); font-size:13px; font-weight:500; }
.btn-secondary:active { background:var(--accent-bg); }
.btn-hint {
  display:block; margin-top:6px; color:var(--text-dim);
  font-size:11px; line-height:1.4; text-align:center;
}
.chat-actions-row {
  display:flex; justify-content:center; margin-top:8px;
}
.btn-text-action { padding:4px 8px; cursor:pointer; }
.btn-text-action text {
  color:var(--text-dim); font-size:11px;
  text-decoration:underline; text-underline-offset:2px;
}
.btn-text-action:active text { color:#ef4444; }

.debug-row {
  margin-top:14px; padding:10px 12px; border-radius:10px;
  border:1px dashed var(--border);
  display:flex; align-items:center; justify-content:space-between; gap:10px;
  cursor:pointer;
}
.debug-row-label { color:var(--text-dim); font-size:12px; font-weight:500; }
.debug-switch {
  width:40px; height:22px; border-radius:999px; flex-shrink:0;
  background:rgba(127,127,127,0.25); position:relative;
  transition:background 0.2s;
}
.debug-switch.on { background:var(--accent); }
.debug-switch-knob {
  position:absolute; top:2px; left:2px;
  width:18px; height:18px; border-radius:50%; background:#fff;
  transition:transform 0.2s; box-shadow:0 1px 3px rgba(0,0,0,0.2);
}
.debug-switch.on .debug-switch-knob { transform:translateX(18px); }

.list-section { margin-top:14px; }
.list-section-head {
  display:flex; align-items:center; justify-content:space-between;
  margin-bottom:8px; gap:8px;
}
.list-section-title {
  color:var(--text-dim); font-size:11px; font-weight:600;
  letter-spacing:0.02em;
}
.list-section-action {
  color:var(--text-dim); font-size:11px; cursor:pointer;
  text-decoration:underline; text-underline-offset:2px;
}
.list-section-action:active { color:#ef4444; }
.session-list {
  display:flex; flex-direction:column; gap:6px;
  max-height:168px; overflow-y:auto;
  scrollbar-width:none; -ms-overflow-style:none;
}
.session-list::-webkit-scrollbar { display:none; }
.session-item {
  display:flex; align-items:center; gap:8px;
  padding:10px 10px; border-radius:10px;
  background:var(--bg-card); border:1px solid var(--border);
  cursor:pointer; transition:border-color 0.15s, background 0.15s;
}
.session-item.active {
  border-color:var(--accent); background:var(--accent-bg);
}
.session-item:active { opacity:0.9; }
.session-main { flex:1; min-width:0; display:flex; flex-direction:column; gap:2px; }
.session-title {
  color:var(--text); font-size:13px; font-weight:600;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}
.session-time { color:var(--text-dim); font-size:10px; }
.session-del {
  width:26px; height:26px; border-radius:8px; flex-shrink:0;
  display:flex; align-items:center; justify-content:center;
  background:rgba(127,127,127,0.08); cursor:pointer;
}
.session-del text { color:var(--text-dim); font-size:15px; line-height:1; }
.session-del:active { background:rgba(239,68,68,0.12); }
.session-del:active text { color:#ef4444; }
.list-empty {
  padding:16px 8px; text-align:center; border-radius:10px;
  background:var(--bg-card); border:1px dashed var(--border);
}
.list-empty text { color:var(--text-dim); font-size:12px; }

.settings-footer {
  padding:8px 16px 16px; display:flex; flex-direction:column; gap:8px;
  border-top:1px solid var(--border);
}
.btn-danger {
  background:rgba(239,68,68,0.08); border:1px solid rgba(239,68,68,0.2);
  border-radius:10px; padding:11px; text-align:center; cursor:pointer;
}
.btn-danger text { color:#ef4444; font-size:14px; font-weight:600; }
.btn-danger:active { background:rgba(239,68,68,0.14); }
.btn-text { text-align:center; padding:8px; cursor:pointer; }
.btn-text text { color:var(--text-dim); font-size:13px; }
.btn-text:active { opacity:0.7; }
</style>
