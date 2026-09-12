<template>
  <view class="app">
    <view v-if="pageLoading" class="page-loading">
      <view class="spinner" />
      <text class="page-loading-text">加载中…</text>
    </view>
    <template v-else>
      <view class="top-fixed">
        <view class="ptop">
          <view class="brand">
            <text class="t1">大宇智能体</text>
            <text class="t2">PARENT · 家长版</text>
          </view>
          <view class="acctbtn" @tap="goStudent">训练账户</view>
        </view>

        <view class="phero">
          <image class="phero-img" src="/static/dayu/assets/parent-team.jpg" mode="aspectFill" />
          <text class="teamtag">天赋导师团</text>
          <view class="cap">
            <text class="cap-t">张宇老师 · 天赋导师团</text>
            <text class="cap-s">不是一个人，是一支教育团队——陪孩子，也陪家长</text>
          </view>
        </view>

        <view class="tri">
          <view class="tri-item" @tap="go('/pages/talent/hub')">
            <image class="tri-ic" src="/static/dayu/assets/ic/dna.png" mode="aspectFit" />
            <text class="tri-n">天赋测试</text>
            <text class="tri-s">孩子·自己都能测</text>
          </view>
          <view class="tri-item" @tap="go('/pages/parent/pcourse')">
            <image class="tri-ic" src="/static/dayu/assets/ic/cap.png" mode="aspectFit" />
            <text class="tri-n">家长课堂</text>
            <text class="tri-s">6门课·72讲</text>
          </view>
          <view class="tri-item" @tap="go('/pages/parent/consult')">
            <image class="tri-ic" src="/static/dayu/assets/ic/bubble.png" mode="aspectFit" />
            <text class="tri-n">一键咨询</text>
            <text class="tri-s live">● 真人导师在线</text>
          </view>
        </view>
      </view>

      <DayuChatPanel
        accent="gold"
        v-model="inputText"
        :messages="messages"
        :loading="loading"
        :thinking-hint="thinkingHint"
        :scroll-into="scrollInto"
        :suggests="suggestChips"
        :show-suggests="showSuggest"
        placeholder="问大宇：孩子训练 / 家长课程 / 报告解读…"
        @send="sendMsg"
        @stop="stopStream"
        @suggest="sendSuggest"
        @navigate="runNavigate"
      >
        <template #intro>
          <view class="intro">
            <view class="msg-row">
              <view class="av sm" />
              <view class="bubble ai">
                <view class="rich" v-html="introHtml1" />
              </view>
            </view>
            <view class="msg-row">
              <view class="av sm" />
              <view class="bubble ai">
                <view class="rich" v-html="introHtml2" />
              </view>
            </view>
          </view>
        </template>
      </DayuChatPanel>

      <view class="foot">
        <view
          v-for="tab in parentTabs"
          :key="tab.key"
          class="foot-item"
          :class="{ on: tab.key === 'dayu' }"
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
import DayuChatPanel from '@/components/dayu-chat-panel/dayu-chat-panel.vue'
import {
  ensureParentUser,
  fetchParentGuideSession,
  fetchParentSuggestPrompts,
  requirePageAuth,
  sendParentGuideMessageStream,
} from '@/utils/userApi.js'
import { isStreamAborted, applyStreamStoppedHint } from '@/utils/chatStream.js'
import {
  alignGuideActionsWithReply,
  GUIDE_NAV_ROUTES,
  trimGuideMessages,
} from '@/utils/guideUi.js'
import { goLinkedStudentHome } from '@/utils/switchLinkedAccount.js'

const FOCUS_KEY = 'jnao_parent_focus_child_id'

const introHtml1 =
  '家长您好！我是张宇老师的智能体——<b>大宇智能体</b>。孩子的天赋报告、训练数据、家长课程，都可以直接问我。'
const introHtml2 =
  '想测天赋点上方<b>「天赋测试」</b>；想学习进<b>「家长课堂」</b>；想找真人老师点<b>「一键咨询」</b>——也可以点下面快捷问法，或直接打字问我。今天想先从哪件事开始？'

const suggestChips = ref([
  { label: '学者天赋是什么', text: '学者天赋是什么' },
  { label: '什么是火箭提分营', text: '什么是火箭提分营' },
  { label: '提分营适合谁', text: '火箭提分营适合什么样的孩子' },
])

const parentTabs = [
  { key: 'dayu', label: '大宇', path: '/pages/parent/dayu', icon: '/static/dayu/assets/ic/robot.png' },
  { key: 'community', label: '天赋社区', path: '/pages/parent/community', icon: '/static/dayu/assets/ic/family.png' },
  { key: 'consult', label: '在线咨询', path: '/pages/parent/consult', icon: '/static/dayu/assets/ic/bubble.png' },
  { key: 'pdata', label: '数据分析', path: '/pages/parent/pdata', icon: '/static/dayu/assets/ic/target.png' },
  { key: 'pset', label: '我的', path: '/pages/parent/pset', icon: '/static/dayu/assets/ic/person.png' },
]

const pageLoading = ref(false)
const messages = ref([])
const inputText = ref('')
const loading = ref(false)
const thinkingHint = ref('agent思考中…')
const guideSessionId = ref(null)
const scrollInto = ref('')

let chatAbort = null
let abortRequested = false

const showSuggest = computed(() => (
  !loading.value && suggestChips.value.length > 0
))

async function loadSuggestChips(uid) {
  try {
    const data = await fetchParentSuggestPrompts(uid, { limit: 3 })
    const items = data?.items
    if (Array.isArray(items) && items.length) suggestChips.value = items.slice(0, 3)
  } catch (_) { /* keep fallback */ }
}

function go(url) {
  if (!url) return
  if (url.startsWith('/pages/parent/') && url !== '/pages/parent/pcourse') {
    uni.reLaunch({ url })
    return
  }
  uni.navigateTo({ url, fail: () => uni.reLaunch({ url }) })
}

function goStudent() {
  goLinkedStudentHome()
}

function onTab(tab) {
  if (!tab?.path || tab.key === 'dayu') return
  uni.reLaunch({ url: tab.path })
}

function scrollChat() {
  nextTick(() => {
    scrollInto.value = ''
    nextTick(() => { scrollInto.value = 'chatEnd' })
  })
}

function readFocusChildId() {
  try {
    const n = parseInt(localStorage.getItem(FOCUS_KEY) || '', 10)
    return n > 0 ? n : null
  } catch (_) {
    return null
  }
}

function writeFocusChildId(id) {
  if (!id) return
  try { localStorage.setItem(FOCUS_KEY, String(id)) } catch (_) { /* ignore */ }
}

function applyGuideMessages(guideData) {
  if (!guideData) {
    guideSessionId.value = null
    messages.value = []
    return
  }
  guideSessionId.value = guideData.session_id
  let rawMsgs = guideData.messages || []
  rawMsgs = trimGuideMessages(rawMsgs)
  const hasUser = rawMsgs.some((m) => m.role === 'user')
  // 引导词不入库：只回放真实对话
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

function runNavigate(act) {
  if (!act) return
  if (act.child_id) writeFocusChildId(act.child_id)
  let url = act.path || GUIDE_NAV_ROUTES[act.target]
  if (!url && act.target === 'talent') url = '/pages/talent/hub'
  if (!url) {
    uni.showToast({ title: act.label || '即将开放', icon: 'none' })
    return
  }
  if (act.child_id && url.indexOf('child_id=') < 0) {
    url += (url.includes('?') ? '&' : '?') + 'child_id=' + encodeURIComponent(act.child_id)
  }
  const base = url.split('?')[0]
  if (base.startsWith('/pages/parent/') && base !== '/pages/parent/pcourse') {
    uni.reLaunch({ url })
    return
  }
  uni.navigateTo({ url, fail: () => uni.reLaunch({ url }) })
}

function sendSuggest(text) {
  if (!text || loading.value) return
  inputText.value = text
  sendMsg()
}

async function sendMsg() {
  const text = inputText.value.trim()
  if (!text || loading.value) return
  messages.value.push({ role: 'user', text })
  inputText.value = ''
  const aiIdx = messages.value.length
  messages.value.push({ role: 'ai', text: '', actions: [] })
  loading.value = true
  thinkingHint.value = 'agent思考中…'
  abortRequested = false
  scrollChat()
  try {
    const uid = await ensureParentUser()
    if (abortRequested) {
      applyStreamStoppedHint(messages, aiIdx)
      return
    }
    const focusChild = readFocusChildId()
    const { promise, abort } = sendParentGuideMessageStream(
      uid,
      text,
      guideSessionId.value,
      {
        onStatus(msg) {
          if (abortRequested || !msg) return
          thinkingHint.value = String(msg)
        },
        onToken(chunk) {
          if (abortRequested) return
          const cur = messages.value[aiIdx]
          messages.value[aiIdx] = { ...cur, text: (cur?.text || '') + chunk }
          scrollChat()
        },
        onDone(data) {
          if (data?.session_id) guideSessionId.value = data.session_id
          if (data?.focus_child_id) writeFocusChildId(data.focus_child_id)
          if (data?.reply) messages.value[aiIdx].text = data.reply
          messages.value[aiIdx].actions = alignGuideActionsWithReply(
            messages.value[aiIdx].text,
            Array.isArray(data?.actions) ? data.actions : [],
          )
        },
      },
      { childId: focusChild },
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
      const tip = e?.message || '说太快了，稍等再问'
      messages.value[aiIdx].text = tip
      try { uni.showToast({ title: tip.slice(0, 40), icon: 'none' }) } catch (_) { /* ignore */ }
    } else if (!messages.value[aiIdx].text) {
      messages.value[aiIdx].text = e?.message || '网络错误，请稍后再试'
    }
  } finally {
    chatAbort = null
    abortRequested = false
    loading.value = false
    thinkingHint.value = 'agent思考中…'
  }
  scrollChat()
}

function stopStream() {
  abortRequested = true
  chatAbort?.()
}

onMounted(async () => {
  // 家长首页 intro 可先出壳；会话后台加载，避免切换账号后整页转圈
  const auth = await requirePageAuth('parent')
  if (!auth.ok) return
  loadSuggestChips(auth.userId)
  try {
    const data = await fetchParentGuideSession(auth.userId)
    applyGuideMessages(data)
    scrollChat()
  } catch (e) {
    console.error('[parent-dayu] session', e)
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
  background: #0d111f;
  color: #edebe4;
  box-sizing: border-box;
  padding-bottom: calc(72px + env(safe-area-inset-bottom, 0px));
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
  width: 28px;
  height: 28px;
  border: 3px solid #2a3040;
  border-top-color: #f5d576;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.page-loading-text { color: #8b93a5; font-size: 14px; }

.top-fixed { flex: none; }
.ptop {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px 6px;
}
.brand .t1 {
  display: block;
  font-size: 19px;
  font-weight: 900;
  color: #f5d9a8;
}
.brand .t2 {
  display: block;
  font-size: 12px;
  color: #8b93a5;
  letter-spacing: 2px;
  font-weight: 700;
  margin-top: 1px;
}
.acctbtn {
  font-size: 14px;
  font-weight: 800;
  color: #9ad9ff;
  background: rgba(46, 107, 230, 0.18);
  border: 1.5px solid #2e6be6;
  border-radius: 99px;
  padding: 5px 12px;
}

.phero {
  margin: 8px 18px 0;
  border-radius: 20px;
  overflow: hidden;
  position: relative;
  border: 1.5px solid #2a3040;
  height: 150px;
}
.phero-img { width: 100%; height: 100%; display: block; }
.teamtag {
  position: absolute;
  top: 12px;
  left: 12px;
  font-size: 14px;
  font-weight: 900;
  color: #0d111f;
  background: linear-gradient(90deg, #f5d576, #c9a869);
  border-radius: 99px;
  padding: 4px 12px;
}
.cap {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 40px 16px 13px;
  background: linear-gradient(180deg, transparent, rgba(8, 11, 22, 0.88));
}
.cap-t { display: block; font-size: 19px; font-weight: 900; color: #fff; }
.cap-s { display: block; font-size: 14px; color: #c9cfdc; margin-top: 3px; }

.tri {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 9px;
  margin: 12px 18px 8px;
}
.tri-item {
  background: #131926;
  border: 1.5px solid #2a3040;
  border-radius: 15px;
  padding: 11px 6px 10px;
  text-align: center;
}
.tri-ic { width: 42px; height: 42px; display: block; margin: 0 auto 5px; }
.tri-n { display: block; font-size: 16px; font-weight: 900; color: #edebe4; }
.tri-s { display: block; font-size: 12px; color: #8b93a5; margin-top: 2px; }
.tri-s.live { color: #3fb950; font-weight: 800; }

/* intro 复用对话气泡视觉（引导词不入库） */
.intro { margin-bottom: 4px; }
.intro .msg-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  margin-bottom: 10px;
}
.intro .av {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: url('/static/dayu/assets/avatar-dayu.jpg') center 12% / 120% auto;
  border: 1.5px solid #edebe4;
  flex: none;
}
.intro .bubble {
  max-width: 82%;
  padding: 10px 14px;
  background: #131926;
  border: 1.5px solid #232b3d;
  color: #d8dce6;
  border-radius: 14px 14px 14px 4px;
  font-size: 14px;
  line-height: 1.55;
}
.intro .rich :deep(b) { color: #f5d9a8; font-weight: 800; }
.suggest {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 2px 0 8px 40px;
}
.chip {
  border: 1.5px solid rgba(201, 162, 39, 0.45);
  background: rgba(201, 162, 39, 0.1);
  color: #f5d9a8;
  font-size: 13px;
  font-weight: 800;
  border-radius: 99px;
  padding: 7px 12px;
}

.foot {
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: var(--app-max-width, 480px);
  background: rgba(13, 17, 31, 0.96);
  backdrop-filter: blur(12px);
  border-top: 1px solid #232b3d;
  padding: 8px 10px calc(8px + env(safe-area-inset-bottom, 0px));
  display: flex;
  justify-content: space-around;
  z-index: 50;
  box-sizing: border-box;
}
.foot-item {
  text-align: center;
  color: #8b93a5;
  font-size: 11px;
  flex: 1;
}
.foot-item.on { color: #f5d9a8; font-weight: 700; }
.fic {
  display: block;
  width: 38px;
  height: 38px;
  margin: 0 auto 1px;
}
</style>
