<template>
  <view class="app" :class="{ lt: isLight }">
    <view v-if="pageLoading" class="page-loading">
      <view class="spinner" />
      <text class="page-loading-text">加载中…</text>
    </view>
    <template v-else>
      <!-- 固定顶区：顶栏 + 头图 + 三入口 -->
      <view class="top-fixed">
        <view class="hometop">
          <view class="sp left">
            <view class="acctbtn" @tap="goParentLogin">家长账户</view>
          </view>
          <view class="user" @tap="toggleAccountSwitcher">
            <text>{{ currentUserDisplay }}</text>
            <text class="caret"> ▾</text>
          </view>
          <view class="icons">
            <view class="themebtn" @tap="toggleTheme">{{ isLight ? '☀️' : '🌙' }}</view>
          </view>
        </view>

        <view class="hero">
          <view class="hero-sh ct-sh" />
          <image class="hero-p zy" src="/static/dayu/assets/_zy-cut.png" mode="heightFix" />
          <image class="hero-p ct" src="/static/dayu/assets/_cartoon-cut.png" mode="heightFix" />
          <view class="hero-fuse" />
        </view>

        <view class="nav4">
          <view class="nav4-item" @tap="openChip('talent')">
            <image class="nav4-ic" src="/static/dayu/assets/ic/dna.png" mode="aspectFit" />
            <text class="nav4-n">天赋测试</text>
          </view>
          <view class="nav4-item" @tap="openChip('story')">
            <image class="nav4-ic" src="/static/dayu/assets/ic/clapper.png" mode="aspectFit" />
            <text class="nav4-n">历史剧情</text>
          </view>
          <view class="nav4-item" @tap="openChip('course')">
            <image class="nav4-ic" src="/static/dayu/assets/ic/books.png" mode="aspectFit" />
            <text class="nav4-n">天赋课程</text>
          </view>
        </view>
      </view>

      <view v-if="showAccountSwitcher" class="asd-mask" @tap="showAccountSwitcher = false" />
      <view v-if="showAccountSwitcher" class="account-switcher-drop">
        <view class="asd-current">
          <text class="asd-label">当前账户</text>
          <text class="asd-name">{{ currentUserDisplay }}</text>
        </view>
        <view v-if="siblings.length" class="asd-list">
          <text class="asd-label" style="margin-top:8px;">切换至</text>
          <view
            v-for="sib in siblings"
            :key="sib.id"
            class="asd-item"
            @tap="switchToChild(sib.id)"
          >
            <text class="asd-name">{{ sib.nickname }}</text>
            <text v-if="sib.talent" class="asd-talent">{{ sib.talent }}</text>
          </view>
        </view>
        <view v-else class="asd-empty"><text>暂无其他账户</text></view>
      </view>

      <!-- 对话独立滚动框 -->
      <view class="chat-panel">
        <scroll-view
          class="chat-scroll"
          scroll-y
          :scroll-into-view="scrollInto"
          scroll-with-animation
          :enable-flex="true"
          :show-scrollbar="false"
          :enhanced="true"
        >
          <view class="chat-stack">
            <view v-if="showBootstrapCard" class="chat-card">
              <view class="chat-head">
                <view class="av" />
                <view v-if="situationLabel" class="tag">今日：{{ situationLabel }}</view>
              </view>
              <text class="welcome">{{ welcomeText }}</text>
              <view class="warn">⚠️ 训练为「{{ currentUserDisplay }}」准备。不是本人？点顶部「{{ currentUserDisplay }} ▾」切换账号，别混了数据。</view>
              <view
                v-for="(act, ai) in welcomeActions"
                :key="'w' + ai"
                class="go"
                @tap="runNavigateAction(act)"
              >
                <text>{{ act.label || actionLabel(act.target) }}</text>
              </view>
            </view>

            <view
              v-for="(m, i) in messages"
              :id="'msg' + i"
              :key="i"
              class="msg-row"
              :class="{ user: m.role === 'user' }"
            >
              <view v-if="m.role !== 'user'" class="av sm" />
              <view class="bubble" :class="m.role === 'user' ? 'me' : 'ai'">
                <view
                  v-if="m.role === 'ai' && loading && i === messages.length - 1 && !m.text"
                  class="thinking"
                >
                  <text>agent思考中…</text>
                </view>
                <view
                  v-else-if="m.role === 'ai' && m.text"
                  class="rich"
                  v-html="formatGuideRichHtml(m.text)"
                />
                <text v-else-if="m.text">{{ m.text }}</text>
                <view v-if="m.role === 'ai' && m.actions?.length" class="act-row">
                  <template v-for="(act, ai) in m.actions" :key="ai">
                    <view
                      v-if="act.type === 'navigate'"
                      class="go sm"
                      @tap="runNavigateAction(act)"
                    >
                      <text>{{ act.label || actionLabel(act.target) }}</text>
                    </view>
                    <view v-else-if="act.type === 'confirm'" class="confirm-wrap">
                      <text v-if="act.preview" class="preview">{{ act.preview }}</text>
                      <view class="act-row">
                        <view
                          class="go sm"
                          :class="{ muted: act._done || act._dismissed }"
                          @tap="runConfirmAction(m, ai, act)"
                        >
                          <text>{{ act._done ? '已记下 ✓' : (act.label || '确认记下') }}</text>
                        </view>
                        <view
                          v-if="!act._done && !act._dismissed"
                          class="go sm ghost"
                          @tap="dismissConfirmAction(m, ai)"
                        >
                          <text>{{ act.cancel_label || '暂不' }}</text>
                        </view>
                      </view>
                    </view>
                  </template>
                </view>
              </view>
            </view>
            <view id="chatEnd" class="chat-end" />
          </view>
        </scroll-view>

        <!-- 提问条：贴在对话框底部，与后端 guide chat 同步 -->
        <view class="chat-ask">
          <input
            class="box"
            v-model="inputText"
            type="text"
            placeholder="输入问题…"
            :disabled="loading"
            confirm-type="send"
            :adjust-position="true"
            :hold-keyboard="true"
            maxlength="2000"
            @confirm="sendMsg"
          />
          <view
            class="send"
            :class="{ stop: loading, disabled: !canSend && !loading }"
            @tap="loading ? stopStream() : sendMsg()"
          >
            <text>{{ loading ? '■' : '➤' }}</text>
          </view>
        </view>
      </view>

      <!-- 底栏 -->
      <view class="foot">
        <view
          v-for="tab in tabs"
          :key="tab.key"
          class="foot-item"
          :class="{ on: tab.key === 'guide' }"
          @tap="onTab(tab)"
        >
          <image class="fic" :src="tab.icon" mode="aspectFit" />
          <text>{{ tab.label }}</text>
        </view>
      </view>
    </template>
  </view>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import {
  apiJson,
  applySwitchChildSession,
  confirmGuideWrite,
  ensureChildUser,
  fetchGuideBootstrap,
  fetchGuideSession,
  fetchLatestAssessment,
  fetchProfile,
  fetchSiblings,
  getChildUserId,
  invalidatePageAuthCache,
  markChildUserSessionValid,
  requirePageAuth,
  sendGuideMessageStream,
  switchChildAccount,
  withUser,
} from '@/utils/userApi.js'
import { prepareRoleLoginEntry } from '@/utils/appSession.js'
import { formatGuideRichHtml } from '@/utils/chatRichText.js'
import { isStreamAborted, applyStreamStoppedHint } from '@/utils/chatStream.js'
import { MAIN_TABS, HOME_CHIPS, switchMainTab } from '@/utils/mainTabs.js'
import {
  ACTION_LABEL_FALLBACK,
  GUIDE_NAV_ROUTES,
  actionLabel,
  alignGuideActionsWithReply,
  normalizeNavigateActions,
  trimGuideMessages,
} from '@/utils/guideUi.js'
import 'katex/dist/katex.min.css'

const FALLBACK_WELCOME = '你好！我是张宇老师的智能体——大宇智能体，你的专属 AI 教练。点上方入口开始，或直接问我。'

const tabs = MAIN_TABS
const pageLoading = ref(true)
const isLight = ref(true)
const currentUserDisplay = ref('学员')
const showAccountSwitcher = ref(false)
const siblings = ref([])
const situationLabel = ref('')
const welcomeText = ref('正在了解你的训练状态…')
const welcomeActions = ref([])
const messages = ref([])
const inputText = ref('')
const loading = ref(false)
const guideSessionId = ref(null)
const scrollInto = ref('')
const assessmentId = ref(null)

let chatAbort = null
let abortRequested = false

try {
  const saved = localStorage.getItem('jnao_theme')
  isLight.value = saved !== 'dark'
  document.documentElement.setAttribute('data-theme', isLight.value ? 'white' : 'dark')
  try {
    localStorage.setItem('jn_theme', isLight.value ? 'lt' : 'dk')
  } catch (_) { /* ignore */ }
} catch (_) { /* ignore */ }

const showBootstrapCard = computed(() => {
  const hasUser = messages.value.some((m) => m.role === 'user')
  return !hasUser
})

const canSend = computed(() => !!inputText.value.trim() && !loading.value)

function toggleTheme() {
  isLight.value = !isLight.value
  const theme = isLight.value ? 'white' : 'dark'
  document.documentElement.setAttribute('data-theme', theme)
  try {
    localStorage.setItem('jnao_theme', theme)
    localStorage.setItem('jn_theme', isLight.value ? 'lt' : 'dk')
  } catch (_) { /* ignore */ }
}

function goParentLogin() {
  prepareRoleLoginEntry('parent')
  invalidatePageAuthCache()
  uni.reLaunch({ url: '/pages/login/index?role=parent' })
}

function toggleAccountSwitcher() {
  showAccountSwitcher.value = !showAccountSwitcher.value
  if (showAccountSwitcher.value) loadSiblings()
}

async function loadSiblings() {
  try {
    const uid = getChildUserId()
    if (!uid) return
    const data = await fetchSiblings(uid)
    siblings.value = (data.siblings || []).filter((s) => {
      const st = s.account_status
      return !st || st === 'active'
    })
    if (data.current?.nickname) currentUserDisplay.value = data.current.nickname
  } catch (_) { /* ignore */ }
}

async function switchToChild(targetId) {
  try {
    const uid = getChildUserId()
    if (!uid) return
    try {
      await apiJson(withUser('/api/user/profile', uid))
    } catch (e) {
      uni.showToast({
        title: e.status === 401 ? '登录已过期，请重新登录后再切换' : '网络异常，请稍后重试',
        icon: 'none',
      })
      showAccountSwitcher.value = false
      return
    }
    const data = await switchChildAccount(uid, targetId)
    showAccountSwitcher.value = false
    applySwitchChildSession(data)
    setTimeout(() => { location.reload() }, 400)
  } catch (e) {
    uni.showToast({ title: e.message || '切换失败', icon: 'none' })
  }
}

function openChip(key) {
  const chip = HOME_CHIPS.find((c) => c.key === key)
  if (!chip?.path) return
  if (chip.key === 'course') {
    switchMainTab(chip.path)
    return
  }
  uni.navigateTo({ url: chip.path })
}

function onTab(tab) {
  if (tab.key === 'guide') return
  switchMainTab(tab.path)
}

async function openPage(name, query) {
  if (name === 'report') {
    try {
      const uid = await ensureChildUser()
      let aid = assessmentId.value
      if (!aid || Number(aid) <= 0) {
        const latest = await fetchLatestAssessment(uid)
        aid = latest?.id
        if (aid && Number(aid) > 0) assessmentId.value = Number(aid)
      }
      if (aid && Number(aid) > 0) {
        uni.navigateTo({ url: `/pages/report/index?assessment_id=${aid}` })
        return
      }
      uni.showToast({ title: '暂无正式报告，请先测评', icon: 'none' })
      uni.navigateTo({ url: '/pages/talent/hub' })
    } catch (e) {
      uni.showToast({ title: e?.message || '无法打开报告', icon: 'none' })
    }
    return
  }
  const url = GUIDE_NAV_ROUTES[name]
  if (!url) {
    uni.showToast({ title: '进入: ' + name, icon: 'none' })
    return
  }
  const tabKeys = ['train', 'qa', 'academy', 'console', 'growth']
  let full = url
  if (query && typeof query === 'object') {
    const qs = Object.entries(query)
      .filter(([, v]) => v != null && String(v).trim())
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v).trim())}`)
      .join('&')
    if (qs) full = `${url}?${qs}`
  }
  if (tabKeys.includes(name)) {
    switchMainTab(full)
    return
  }
  uni.navigateTo({ url: full })
}

function runNavigateAction(act) {
  if (act?.type === 'confirm') return
  if (act?.target) openPage(act.target, act?.query)
}

async function runConfirmAction(msg, actIndex, act) {
  if (!act || act.type !== 'confirm' || act._done || act._dismissed || act._busy) return
  act._busy = true
  try {
    const uid = await ensureChildUser()
    await confirmGuideWrite(uid, act.write_op, act.args || {})
    act._done = true
    uni.showToast({ title: '已记下', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e?.message || '记下失败', icon: 'none' })
  } finally {
    act._busy = false
  }
}

function dismissConfirmAction(msg, actIndex) {
  const act = msg?.actions?.[actIndex]
  if (!act || act.type !== 'confirm') return
  act._dismissed = true
}

function applyBootstrap(data) {
  if (!data || data.error) {
    welcomeText.value = FALLBACK_WELCOME
    welcomeActions.value = []
    situationLabel.value = ''
    return
  }
  welcomeText.value = data.welcome || FALLBACK_WELCOME
  const fromActions = normalizeNavigateActions(data.actions)
  if (fromActions.length) {
    welcomeActions.value = fromActions
  } else if (ACTION_LABEL_FALLBACK[data.next_action]) {
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

function applyGuideMessages(guideData, { trim = true } = {}) {
  if (!guideData) {
    guideSessionId.value = null
    messages.value = []
    return
  }
  guideSessionId.value = guideData.session_id
  let rawMsgs = guideData.messages || []
  if (trim) rawMsgs = trimGuideMessages(rawMsgs)
  const hasUser = rawMsgs.some((m) => m.role === 'user')
  messages.value = (hasUser ? rawMsgs : [])
    .map((m) => {
      const isAi = m.role === 'assistant' || m.role === 'ai'
      return {
        role: isAi ? 'ai' : 'user',
        text: m.content || m.text || '',
        actions: isAi ? alignGuideActionsWithReply(m.content || m.text || '', m.actions) : [],
      }
    })
}

function scrollChat() {
  nextTick(() => {
    scrollInto.value = ''
    nextTick(() => { scrollInto.value = 'chatEnd' })
  })
}

async function sendMsg() {
  const text = inputText.value.trim()
  if (!text || loading.value) return
  messages.value.push({ role: 'user', text })
  inputText.value = ''
  const aiIdx = messages.value.length
  messages.value.push({ role: 'ai', text: '', actions: [] })
  loading.value = true
  abortRequested = false
  scrollChat()
  try {
    const uid = await ensureChildUser()
    if (abortRequested) {
      applyStreamStoppedHint(messages, aiIdx)
      return
    }
    const { promise, abort } = sendGuideMessageStream(
      uid,
      text,
      guideSessionId.value,
      {
        onToken(chunk) {
          if (abortRequested) return
          messages.value[aiIdx].text += chunk
          scrollChat()
        },
        onDone(data) {
          if (data?.session_id) guideSessionId.value = data.session_id
          if (data?.reply) messages.value[aiIdx].text = data.reply
          messages.value[aiIdx].actions = alignGuideActionsWithReply(
            messages.value[aiIdx].text,
            Array.isArray(data?.actions) ? data.actions : [],
          )
          if (data?.situation_label) situationLabel.value = data.situation_label
        },
      },
    )
    chatAbort = abort
    await promise
    if (messages.value.length > 20) {
      messages.value = trimGuideMessages(messages.value)
    }
  } catch (e) {
    if (isStreamAborted(e)) {
      applyStreamStoppedHint(messages, aiIdx)
    } else if (e?.status === 429) {
      const tip = e?.message || '说太快了，稍等再问老师'
      messages.value[aiIdx].text = tip
      try { uni.showToast({ title: tip.slice(0, 40), icon: 'none' }) } catch (_) { /* ignore */ }
    } else if (!messages.value[aiIdx].text) {
      messages.value[aiIdx].text = e?.message || '网络错误，请稍后再试'
    }
  } finally {
    chatAbort = null
    abortRequested = false
    loading.value = false
  }
  scrollChat()
}

function stopStream() {
  abortRequested = true
  chatAbort?.()
}

function hydrateFromLocal() {
  try {
    const raw = localStorage.getItem('jnao_user')
    if (!raw) return
    const u = JSON.parse(raw)
    if (u?.name) currentUserDisplay.value = u.name
  } catch (_) { /* ignore */ }
}

async function initHome(uid) {
  const [profileData, guideData, bootstrapData] = await Promise.all([
    fetchProfile(uid),
    fetchGuideSession(uid).catch(() => null),
    fetchGuideBootstrap(uid).catch(() => null),
  ])
  markChildUserSessionValid(uid)
  if (profileData?.nickname) currentUserDisplay.value = String(profileData.nickname).trim()
  const aid = profileData?.profile_json?.latest_assessment_id
  if (aid && Number(aid) > 0) assessmentId.value = Number(aid)
  applyGuideMessages(guideData)
  applyBootstrap(bootstrapData)
  scrollChat()
}

onMounted(async () => {
  hydrateFromLocal()
  const auth = await requirePageAuth('student')
  if (!auth.ok) {
    pageLoading.value = false
    return
  }
  try {
    await initHome(auth.userId)
  } catch (e) {
    console.error('[dayu-home] init failed', e)
    welcomeText.value = FALLBACK_WELCOME
  } finally {
    pageLoading.value = false
  }
})
</script>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh;
  max-width: var(--app-max-width, 480px);
  margin: 0 auto;
  background: linear-gradient(180deg, #101623 0%, #0b0e14 30%);
  position: relative;
  overflow: hidden;
  box-sizing: border-box;
  padding-bottom: calc(56px + env(safe-area-inset-bottom, 0px));
}
.app.lt {
  background: linear-gradient(180deg, #dce2ef 0%, #ebeef4 30%);
}
.page-loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
}
.spinner {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 3px solid rgba(255, 255, 255, 0.2);
  border-top-color: #58a6ff;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.page-loading-text { color: #8b93a5; font-size: 14px; }

/* 固定顶区：不随对话滚动 */
.top-fixed {
  flex-shrink: 0;
  z-index: 20;
  background: inherit;
  padding-bottom: 2px;
}

.hometop {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px 6px;
  gap: 8px;
}
.hometop .sp { flex: 1; min-width: 0; display: flex; align-items: center; }
.hometop .sp.left { justify-content: flex-start; }
.hometop .user {
  flex: 1;
  min-width: 0;
  text-align: center;
  font-size: 17px;
  font-weight: 900;
  color: #edebe4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.app.lt .hometop .user { color: #1b1912; }
.hometop .caret { font-size: 11px; color: #5a6274; }
.hometop .icons {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
}
.themebtn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
}
.acctbtn {
  font-size: 11.5px;
  font-weight: 800;
  color: #f5d9a8;
  background: linear-gradient(135deg, rgba(201, 162, 39, 0.3), rgba(201, 162, 39, 0.12));
  border: 1.5px solid #c9a227;
  border-radius: 99px;
  padding: 5px 12px;
  white-space: nowrap;
}
.app.lt .acctbtn {
  color: #967536;
  background: rgba(150, 117, 54, 0.12);
  border-color: #967536;
}

.asd-mask { position: fixed; inset: 0; z-index: 400; }
.account-switcher-drop {
  position: fixed;
  top: 52px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 500;
  background: #161b22;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 14px;
  width: 220px;
  max-width: calc(100vw - 32px);
}
.app.lt .account-switcher-drop {
  background: #fff;
  border-color: #e5e7eb;
}
.asd-label { color: #8b949e; font-size: 11px; display: block; margin-bottom: 4px; }
.asd-name { color: #e6edf3; font-size: 14px; font-weight: 600; display: block; }
.app.lt .asd-name { color: #1a1a2e; }
.asd-talent { color: #58a6ff; font-size: 11px; }
.asd-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 8px;
  border-radius: 8px;
  margin-top: 4px;
}
.asd-empty { padding: 12px 0; text-align: center; color: #8b949e; font-size: 12px; }

.hero {
  position: relative;
  margin: 6px 18px 0;
  width: auto;
  aspect-ratio: 1125 / 480;
  border-radius: 18px;
  border: 1.5px solid #232b3d;
  background: url('/static/dayu/assets/hero_bg.jpg') center / cover;
  overflow: hidden;
  box-sizing: border-box;
}
.app.lt .hero { border-color: #c2cadc; }
.hero-p { position: absolute; bottom: 0; }
.hero-p.zy { left: 4.3%; height: 93%; }
.hero-p.ct {
  left: 22.2%;
  height: 82%;
  bottom: 1.2%;
  animation: heroFloat 3.6s ease-in-out infinite;
  animation-delay: -1.8s;
}
.hero-sh {
  position: absolute;
  border-radius: 50%;
  background: radial-gradient(ellipse at center, rgba(4, 6, 16, 0.85), rgba(4, 6, 16, 0.35) 55%, transparent 72%);
  filter: blur(1.5px);
}
.ct-sh {
  left: 23.5%;
  bottom: 0.6%;
  width: 24%;
  height: 6.5%;
  animation: heroShadow 3.6s ease-in-out infinite;
  animation-delay: -1.8s;
}
.hero-fuse {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 16%;
  background: linear-gradient(180deg, transparent, rgba(64, 86, 176, 0.5) 78%, rgba(62, 84, 180, 0.72));
  pointer-events: none;
}
@keyframes heroFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-2.4%); }
}
@keyframes heroShadow {
  0%, 100% { transform: scaleX(1); opacity: 0.9; }
  50% { transform: scaleX(0.86); opacity: 0.55; }
}

.nav4 {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin: 12px 18px 8px;
}
.nav4-item {
  background: #131926;
  border: 1.5px solid #232b3d;
  border-radius: 14px;
  padding: 12px 2px;
  text-align: center;
}
.app.lt .nav4-item {
  background: #d9dfec;
  border-color: #c2cadc;
}
.nav4-ic { width: 60px; height: 60px; display: block; margin: 0 auto; }
.nav4-n {
  display: block;
  font-size: 12.5px;
  font-weight: 800;
  color: #edebe4;
  margin-top: 4px;
}
.app.lt .nav4-n { color: #1b1912; }

/* 对话独立框：仅此处上下滑 */
.chat-panel {
  flex: 1;
  min-height: 0;
  margin: 0 14px 8px;
  display: flex;
  flex-direction: column;
  background: rgba(19, 25, 38, 0.55);
  border: 1.5px solid #232b3d;
  border-radius: 18px;
  overflow: hidden;
  box-sizing: border-box;
}
.app.lt .chat-panel {
  background: rgba(217, 223, 236, 0.72);
  border-color: #c2cadc;
}
.chat-scroll {
  flex: 1;
  height: 0;
  min-height: 0;
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.chat-scroll::-webkit-scrollbar,
:deep(uni-scroll-view)::-webkit-scrollbar,
:deep(.uni-scroll-view)::-webkit-scrollbar,
:deep(.uni-scroll-view-content)::-webkit-scrollbar {
  display: none;
  width: 0;
  height: 0;
}
.chat-stack { padding: 12px 12px 10px; }
.chat-end { height: 8px; }

.chat-ask {
  flex-shrink: 0;
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 8px 10px 10px;
  border-top: 1px solid #232b3d;
  background: rgba(11, 14, 20, 0.72);
  box-sizing: border-box;
}
.app.lt .chat-ask {
  border-top-color: #c2cadc;
  background: rgba(235, 238, 244, 0.88);
}
.chat-ask .box {
  flex: 1;
  min-width: 0;
  height: 42px;
  line-height: 42px;
  background: #161d2b;
  border: 1.5px solid #2a3040;
  border-radius: 999px;
  padding: 0 16px;
  font-size: 14px;
  color: #edebe4;
  box-sizing: border-box;
}
.app.lt .chat-ask .box {
  background: #d4dbe9;
  border-color: #bfc5d5;
  color: #1b1912;
}
.chat-ask .send {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: #6fcf8e;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex: none;
  color: #0b0e14;
  font-weight: 900;
}
.chat-ask .send.stop { background: #e05252; color: #fff; }
.chat-ask .send.disabled { opacity: 0.45; }
.app.lt .chat-ask .send { background: #30904f; color: #fff; }
.chat-card {
  background: #131926;
  border: 1.5px solid #232b3d;
  border-radius: 18px;
  padding: 14px;
  margin-bottom: 10px;
}
.app.lt .chat-card {
  background: #d9dfec;
  border-color: #c2cadc;
}
.chat-head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.av {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: url('/static/dayu/assets/avatar-dayu.jpg') center 12% / 120% auto;
  border: 2px solid #edebe4;
  flex: none;
}
.av.sm { width: 32px; height: 32px; border-width: 1.5px; }
.app.lt .av { border-color: #1956d1; }
.tag {
  background: rgba(46, 107, 230, 0.14);
  border: 1px solid #2e6be6;
  color: #7fa7ef;
  font-size: 12.5px;
  font-weight: 800;
  padding: 4px 12px;
  border-radius: 99px;
}
.app.lt .tag {
  background: rgba(25, 86, 209, 0.14);
  border-color: #1956d1;
  color: #103880;
}
.welcome {
  display: block;
  font-size: 14.5px;
  color: #d8dce6;
  line-height: 1.65;
  white-space: pre-wrap;
}
.app.lt .welcome { color: #191d27; }
.warn {
  margin-top: 10px;
  font-size: 12.5px;
  color: #c9a869;
  line-height: 1.55;
  background: rgba(201, 168, 105, 0.08);
  border-radius: 10px;
  padding: 8px 10px;
}
.app.lt .warn {
  color: #967536;
  background: rgba(150, 117, 54, 0.08);
}
.go {
  display: inline-flex;
  margin-top: 12px;
  background: #2e6be6;
  color: #fff;
  font-size: 15px;
  font-weight: 900;
  padding: 12px 22px;
  border-radius: 99px;
}
.go.sm { margin-top: 8px; padding: 8px 16px; font-size: 13px; margin-right: 8px; }
.go.ghost {
  background: transparent;
  border: 1.5px solid #2a3040;
  color: #8b93a5;
}
.go.muted { opacity: 0.55; }
.app.lt .go { background: #1956d1; color: #141414; }

.msg-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  margin-bottom: 10px;
}
.msg-row.user { justify-content: flex-end; }
.bubble {
  max-width: 82%;
  padding: 10px 14px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.55;
  word-break: break-word;
}
.bubble.ai {
  background: #131926;
  border: 1.5px solid #232b3d;
  color: #d8dce6;
  border-radius: 14px 14px 14px 4px;
}
.bubble.me {
  background: rgba(46, 107, 230, 0.22);
  border: 1.5px solid #2e6be6;
  color: #edebe4;
  border-radius: 14px 14px 4px 14px;
}
.app.lt .bubble.ai {
  background: #d9dfec;
  border-color: #c2cadc;
  color: #191d27;
}
.app.lt .bubble.me {
  background: rgba(25, 86, 209, 0.14);
  border-color: #1956d1;
  color: #103880;
}
.thinking { color: #8b93a5; font-size: 13px; }
.act-row { display: flex; flex-wrap: wrap; align-items: center; }
.confirm-wrap { width: 100%; }
.preview {
  display: block;
  font-size: 12px;
  color: #8b93a5;
  margin: 6px 0 2px;
}

.foot {
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: var(--app-max-width, 480px);
  background: rgba(11, 14, 20, 0.94);
  backdrop-filter: blur(12px);
  border-top: 1px solid #232b3d;
  padding: 8px 10px calc(8px + env(safe-area-inset-bottom, 0px));
  display: flex;
  justify-content: space-around;
  z-index: 50;
  box-sizing: border-box;
}
.app.lt .foot {
  background: rgba(235, 238, 244, 0.94);
  border-top-color: #c2cadc;
}
.foot-item {
  text-align: center;
  color: #5a6274;
  font-size: 11px;
  flex: 1;
}
.foot-item.on { color: #6fcf8e; font-weight: 700; }
.app.lt .foot-item.on { color: #30904f; }
.fic {
  display: block;
  width: 38px;
  height: 38px;
  margin: 0 auto 1px;
}
</style>
