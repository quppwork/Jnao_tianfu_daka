<template>
  <view class="app" :class="{ lt: isLight, simple: simpleMode }">
    <view class="topbar">
      <view class="brand">
        <view class="logo" />
        <view>
          <text class="t1">学科答疑</text>
          <text class="t2">ASK DAYU · 天赋导师在线</text>
        </view>
      </view>
      <view class="top-actions">
        <view class="gear" @tap="showSettings = true">⚙</view>
        <view class="chip-g" @tap="openHistory">历史</view>
      </view>
    </view>

    <view class="mstage">
      <image class="mstage-img" :src="stageImageSrc" mode="aspectFill" />
      <view class="mgrad" />
      <view v-if="loading" class="mlive">
        <view class="dot" />
        <text class="mlive-t">正在回复你</text>
        <text class="mlive-dots" aria-hidden="true">
          <text class="mlive-dot">.</text><text class="mlive-dot">.</text><text class="mlive-dot">.</text>
        </text>
      </view>
      <view class="mwho">
        <text class="mwho-name">{{ displayName }}</text>
        <text v-if="activeMentor.tag" class="mwho-tag">{{ activeMentor.tag }}</text>
      </view>
    </view>

    <view
      ref="subsRef"
      class="subs"
      @mousedown="onSubsMouseDown"
      @wheel.prevent="onSubsWheel"
    >
      <view class="subs-inner">
        <view
          v-for="m in mentors"
          :key="m.key"
          class="sub-chip"
          :class="{ on: subject === m.subject }"
          @tap="onSubjectChipTap(m.subject)"
        >
          <text>{{ m.guide }}</text>
        </view>
      </view>
    </view>

    <view class="mentor">
      <view
        class="mava"
        :class="{ img: !!activeMentor.ava }"
        :style="mavaStyle"
      >
        <text v-if="!activeMentor.ava" class="mava-emoji">{{ activeMentor.emoji || '🎓' }}</text>
        <view
          class="mtb"
          :style="{ borderColor: activeMentor.badgeColor || '#3E8E5A', color: activeMentor.badgeColor || '#3E8E5A' }"
        >{{ activeMentor.badge || '思' }}</view>
      </view>
      <view class="minfo">
        <view class="mn-row">
          <text class="mn">{{ displayName }}</text>
          <text class="mtag" :style="{ color: activeMentor.color || '#6FD3A7', borderColor: activeMentor.color || '#6FD3A7' }">
            {{ subject ? (activeMentor.tag || '大宇智能体') : '大宇智能体' }}
          </text>
        </view>
        <text class="mknow" :style="{ color: activeMentor.color || '#6FD3A7' }">{{ knowLine }}</text>
      </view>
    </view>

    <view v-if="guideHandoffBanner" class="banner">
      <text class="banner-text">来自首页引导：{{ guideHandoffBanner.hint || ('已切换到' + (guideHandoffBanner.subject || subject)) }}</text>
      <text class="banner-x" @tap="guideHandoffBanner = null">×</text>
    </view>
    <view v-if="mismatchSuggest" class="banner mismatch">
      <text class="banner-text">这道题更像「{{ mismatchSuggest }}」，点切换将自动重发上一问</text>
      <text class="banner-act" @tap="applySuggestedSubject">切换并重发</text>
      <text class="banner-x" @tap="dismissMismatch">×</text>
    </view>

    <scroll-view
      class="chat-scroll"
      scroll-y
      :scroll-into-view="scrollInto"
      scroll-with-animation
      :show-scrollbar="false"
      :enhanced="true"
    >
      <view class="chat-stack">
        <view
          v-for="(m, i) in messages"
          :id="'msg' + i"
          :key="i"
          class="msg"
          :class="{ me: m.role === 'user' }"
        >
          <view
            v-if="m.role !== 'user'"
            class="av"
            :style="{ borderColor: activeMentor.color || '#6FD3A7' }"
          >{{ activeMentor.emoji || '🎓' }}</view>
          <view class="bubble-wrap">
            <view v-if="m.role !== 'user'" class="who">
              <text>{{ displayName }}</text>
              <text class="who-i">{{ subject || '导师在线' }}</text>
            </view>
            <view class="tx" :class="{ 'tx-me': m.role === 'user' }">
              <view v-if="m.imageUrl || m.hasImage" class="bubble-img-wrap" @tap="m.imageUrl && previewImg(m.imageUrl)">
                <image
                  v-if="m.imageUrl"
                  :src="m.imageUrl"
                  class="bubble-img"
                  mode="aspectFill"
                />
                <view v-else class="bubble-img-ph"><text>题目图片加载中…</text></view>
              </view>
              <!-- H5：v-html 才能正确挂 KaTeX；rich-text 会丢掉公式 DOM/样式 -->
              <!-- #ifdef H5 -->
              <view
                v-if="m.role !== 'user' && m.text"
                class="tx-rich bubble-rich"
                v-html="formatHtml(m.text)"
              />
              <!-- #endif -->
              <!-- #ifndef H5 -->
              <rich-text
                v-if="m.role !== 'user' && m.text"
                class="tx-rich"
                :nodes="formatHtml(m.text)"
              />
              <!-- #endif -->
              <text
                v-else-if="shouldShowUserBubbleText(m)"
                class="tx-text"
                selectable
                user-select
              >{{ m.text }}</text>
              <view
                v-else-if="loading && i === messages.length - 1 && m.role !== 'user'"
                class="thinking"
              >
                <view class="thinking-dot" />
                <text class="thinking-t">正在回复你</text>
                <text class="thinking-ellipsis" aria-hidden="true">
                  <text class="te">.</text><text class="te">.</text><text class="te">.</text>
                </text>
              </view>
            </view>
          </view>
        </view>
        <view id="chat-end" class="chat-end" />
      </view>
    </scroll-view>

    <!-- DeepSeek 手机版式：圆角功能框 + 右侧固定发送位（有内容/图片时「＋」换成发送） -->
    <view class="composer">
      <view v-if="pendingImage" class="pending-inline">
        <view class="pending-card">
          <image
            class="pending-thumb"
            :src="pendingImage.preview"
            mode="aspectFill"
            @tap="previewImg(pendingImage.preview)"
          />
          <view class="pending-clear" @tap="clearPendingImage"><text>✕</text></view>
        </view>
        <text class="pending-hint">已附上题目图，点右侧发送</text>
      </view>
      <view class="composer-row">
        <view class="tool voice" aria-hidden="true">🎤</view>
        <view class="composer-main">
          <input
            class="box"
            v-model="inputText"
            type="text"
            confirm-type="send"
            :disabled="loading"
            placeholder="输入问题，或粘贴/拍照发题..."
            @confirm="sendMsg"
            @paste="onInputPaste"
          />
          <view class="composer-actions">
            <view class="act cam" :class="{ disabled: loading }" @tap="pickImage">
              <text class="act-ic">📷</text>
            </view>
            <view
              v-if="loading"
              class="act send stop"
              @tap="stopStream()"
            >
              <text class="send-ic">■</text>
            </view>
            <view
              v-else-if="canSend"
              class="act send"
              @tap="sendMsg()"
            >
              <text class="send-ic">↑</text>
            </view>
            <view v-else class="act plus">
              <text class="act-ic">＋</text>
            </view>
          </view>
        </view>
      </view>
    </view>

    <view class="foot">
      <view
        v-for="tab in tabs"
        :key="tab.key"
        class="foot-item"
        :class="{ on: tab.key === 'qa' }"
        @tap="onTab(tab)"
      >
        <image class="fic" :src="tab.icon" mode="aspectFit" />
        <text>{{ tab.label }}</text>
      </view>
    </view>

    <!-- 历史 -->
    <view v-if="showHistory" class="hist" @tap="closeHistory">
      <view class="hbox" @tap.stop>
        <text class="ht">答疑历史</text>
        <view class="hnew" @tap="startNewSession"><text>＋ 新对话</text></view>
        <scroll-view class="hlist" scroll-y :show-scrollbar="false" :enhanced="true">
          <view
            v-for="s in sessionList"
            :key="s.id"
            class="hitem"
            :class="{ active: s.id === qaSessionId }"
            @tap="switchSession(s.id)"
          >
            <view class="hitem-main">
              <text class="hitem-t">{{ s.title || '新对话' }}</text>
              <text class="hitem-s">{{ s.subject || '通用' }} · {{ formatTime(s.created_at) }}</text>
            </view>
            <text class="hitem-del" @tap.stop="askDeleteSession(s.id)">✕</text>
          </view>
          <view v-if="!sessionList.length" class="hempty"><text>暂无历史会话</text></view>
        </scroll-view>
      </view>
    </view>

    <!-- 删除历史确认 -->
    <view v-if="deleteTargetId" class="delm" @tap="cancelDeleteSession">
      <view class="delbox" @tap.stop>
        <text class="delt">删除对话</text>
        <text class="deld">确定删除这条对话记录？删除后无法恢复。</text>
        <view class="delacts">
          <view class="delbtn cancel" @tap="cancelDeleteSession"><text>取消</text></view>
          <view class="delbtn danger" @tap="confirmDeleteSession">
            <text>{{ deleteSubmitting ? '删除中...' : '删除' }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- 设置 -->
    <view v-if="showSettings" class="setm" @tap="showSettings = false">
      <view class="sbox" @tap.stop>
        <text class="stitle">答疑设置</text>
        <text class="ssub">简洁模式会隐藏导师介绍卡</text>
        <view class="srow">
          <view>
            <text>简洁模式</text>
            <text class="srow-s">只保留学科切换与对话</text>
          </view>
          <view class="sw" :class="{ on: simpleMode }" @tap="toggleSimple"><view class="sw-i" /></view>
        </view>
        <view class="srow" @tap="toggleTheme">
          <view>
            <text>主题</text>
            <text class="srow-s">{{ isLight ? '浅色' : '深色' }}</text>
          </view>
          <text>{{ isLight ? '☀️' : '🌙' }}</text>
        </view>
        <view class="sclose" @tap="showSettings = false"><text>关闭</text></view>
      </view>
    </view>

    <!-- 选图：自研中文底栏，避免 H5 ActionSheet 取消键显示 Cancel -->
    <view v-if="showImageSheet" class="img-sheet-mask" @tap="closeImageSheet">
      <view class="img-sheet" @tap.stop>
        <view class="img-sheet-group">
          <view class="img-sheet-item" @tap="onPickSource('camera')">拍照</view>
          <view class="img-sheet-item" @tap="onPickSource('album')">从相册选择</view>
        </view>
        <view class="img-sheet-cancel" @tap="closeImageSheet">取消</view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import {
  ensureChildUser,
  requirePageAuth,
  fetchQaSessions,
  createQaSession,
  deleteQaSession,
  fetchQaSession,
  resolveQaImageUrl,
  sendQaMessageStream,
  uploadQaImage,
  errMessage,
} from '@/utils/userApi.js'
import { formatDateTimeShortShanghai } from '@/utils/datetime.js'
import 'katex/dist/katex.min.css'
import '@/styles/qaBubbleRich.css'
import { formatQaRichHtml, prefetchKatex, getKatexEpoch } from '@/utils/chatRichText.js'
import { isStreamAborted, applyStreamStoppedHint } from '@/utils/chatStream.js'
import {
  chooseQuestionImage,
  compressImage,
  buildPendingImageFromPath,
  extractClipboardImageFile,
  fileToDataUrl,
  isMobileH5,
  needsWebcamCapture,
  pendingFromImageFile,
  pickImageViaNativeInput,
  putQaImageLocal,
} from '@/utils/qaMedia.js'
import { MAIN_TABS, switchMainTab } from '@/utils/mainTabs.js'
import { QA_MENTORS, QA_SUBJECTS, mentorOrStage, normalizeQaSubject } from '@/utils/qaMentors.js'

const tabs = MAIN_TABS
const mentors = QA_MENTORS
const subjects = QA_SUBJECTS

const isLight = ref(false)
const simpleMode = ref(false)
const showSettings = ref(false)
const showHistory = ref(false)
const subject = ref('')
const inputText = ref('')
const guideHandoffBanner = ref(null)
const loading = ref(false)
const qaSessionId = ref(null)
const messages = ref([])
const sessionList = ref([])
const deleteTargetId = ref(null)
const deleteSubmitting = ref(false)
const scrollInto = ref('')
const pendingImage = ref(null)
const showImageSheet = ref(false)
const mismatchSuggest = ref(null)
const mismatchResendText = ref('')
const subsRef = ref(null)
let streamAbort = null
let abortRequested = false

const activeMentor = computed(() => mentorOrStage(subject.value))
/** 先进 JPG 占位，空闲后再换 GIF，避免进页拉 1MB+ 动图 */
const stageGifReady = ref(false)
let stageGifTimer = null
function scheduleStageGif() {
  stageGifReady.value = false
  if (stageGifTimer) {
    clearTimeout(stageGifTimer)
    stageGifTimer = null
  }
  const gif = activeMentor.value?.gif
  if (!gif) return
  const kick = () => { stageGifReady.value = true }
  if (typeof requestIdleCallback === 'function') {
    requestIdleCallback(kick, { timeout: 1800 })
  } else {
    stageGifTimer = setTimeout(kick, 900)
  }
}
watch(activeMentor, () => scheduleStageGif(), { immediate: true })
const stageImageSrc = computed(() => {
  const m = activeMentor.value || {}
  if (stageGifReady.value && m.gif) return m.gif
  return m.ava || m.gif || ''
})
const displayName = computed(() => {
  const m = activeMentor.value
  if (!subject.value) return '张宇老师'
  return m.name?.includes('老师') ? m.name : `${m.name}老师`
})
const knowLine = computed(() => {
  if (!subject.value) {
    return `对大宝说：'${activeMentor.value.know}'`
  }
  return activeMentor.value.know
})
const mavaStyle = computed(() => {
  const m = activeMentor.value || {}
  const border = m.color || '#6FD3A7'
  if (m.ava) {
    return {
      borderColor: border,
      backgroundImage: `url(${m.ava})`,
      backgroundSize: 'cover',
      backgroundPosition: 'center top',
      backgroundRepeat: 'no-repeat',
    }
  }
  return { borderColor: border, background: `${border}22` }
})
const canSend = computed(() => !loading.value && !!(inputText.value.trim() || pendingImage.value))

const katexTick = ref(0)
function formatHtml(text) {
  void katexTick.value
  return formatQaRichHtml(text || '')
}
function formatTime(t) {
  return formatDateTimeShortShanghai(t)
}
function readTheme() {
  try {
    const t = localStorage.getItem('jn_theme') || localStorage.getItem('jnao_theme') || 'dk'
    isLight.value = t === 'lt' || t === 'light'
  } catch (_) {
    isLight.value = false
  }
}
function toggleTheme() {
  isLight.value = !isLight.value
  const v = isLight.value ? 'lt' : 'dk'
  try {
    localStorage.setItem('jn_theme', v)
    localStorage.setItem('jnao_theme', v)
  } catch (_) { /* ignore */ }
}
function toggleSimple() {
  simpleMode.value = !simpleMode.value
  try {
    localStorage.setItem('jn_answer_simple', simpleMode.value ? '1' : '0')
  } catch (_) { /* ignore */ }
}
function readSimple() {
  try {
    simpleMode.value = localStorage.getItem('jn_answer_simple') === '1'
  } catch (_) {
    simpleMode.value = false
  }
}

function onTab(tab) {
  if (tab.key === 'qa') return
  switchMainTab(tab.path)
}

function scrollChat() {
  scrollInto.value = ''
  nextTick(() => {
    scrollInto.value = 'chat-end'
  })
}

function pushWelcome() {
  const name = displayName.value
  messages.value = [{
    role: 'assistant',
    text: subject.value
      ? `你好，我是${name}。把题目发来，我们一步一步来。`
      : '不急着讲题。先选一门学科，让最懂你的导师来陪你；也可以直接提问或拍照发题。',
  }]
}

function onSubjectTap(s) {
  const shouldResend = mismatchSuggest.value === s && !!mismatchResendText.value
  const resend = mismatchResendText.value
  const changed = subject.value !== s
  subject.value = s
  if (changed && !shouldResend) {
    qaSessionId.value = null
    pushWelcome()
  }
  if (!shouldResend || loading.value) return
  mismatchSuggest.value = null
  mismatchResendText.value = ''
  inputText.value = resend
  nextTick(() => sendMsg())
}

/** 学科条：鼠标拖拽横滑（H5 scroll-view 不支持鼠标拖） */
const subsDrag = {
  active: false,
  moved: false,
  startX: 0,
  scrollLeft: 0,
  el: null,
}

function resolveDomEl(raw) {
  if (!raw) return null
  if (raw.nodeType === 1) return raw
  if (raw.$el?.nodeType === 1) return raw.$el
  // uni-app H5：组件实例可能包一层
  if (typeof raw === 'object' && raw.$) {
    const el = raw.$el || raw.$.vnode?.el
    if (el?.nodeType === 1) return el
  }
  return null
}

function getSubsEl() {
  return resolveDomEl(subsRef.value) || document.querySelector('.subs')
}

function clearSubsDocListeners() {
  if (typeof document === 'undefined') return
  document.removeEventListener('mousemove', onSubsDocMove)
  document.removeEventListener('mouseup', onSubsDocUp)
}

function onSubsDocMove(ev) {
  if (!subsDrag.active || !subsDrag.el) return
  const x = ev.pageX || ev.clientX || 0
  const dx = x - subsDrag.startX
  if (Math.abs(dx) > 4) subsDrag.moved = true
  subsDrag.el.scrollLeft = subsDrag.scrollLeft - dx
  ev.preventDefault?.()
}

function onSubsDocUp() {
  if (subsDrag.el) subsDrag.el.classList?.remove('dragging')
  subsDrag.active = false
  subsDrag.el = null
  clearSubsDocListeners()
  if (subsDrag.moved) {
    setTimeout(() => { subsDrag.moved = false }, 80)
  }
}

function onSubsMouseDown(ev) {
  const el = getSubsEl()
  if (!el) return
  if (ev.button != null && ev.button !== 0) return
  subsDrag.active = true
  subsDrag.moved = false
  subsDrag.startX = ev.pageX || ev.clientX || 0
  subsDrag.scrollLeft = el.scrollLeft || 0
  subsDrag.el = el
  el.classList?.add('dragging')
  if (typeof document !== 'undefined') {
    document.addEventListener('mousemove', onSubsDocMove)
    document.addEventListener('mouseup', onSubsDocUp)
  }
}

function onSubsWheel(ev) {
  const el = getSubsEl()
  if (!el) return
  const dx = ev.deltaX || 0
  const dy = ev.deltaY || 0
  const delta = Math.abs(dx) > Math.abs(dy) ? dx : dy
  if (!delta) return
  el.scrollLeft += delta
}

function onSubjectChipTap(s) {
  if (subsDrag.moved) return
  onSubjectTap(s)
}

function dismissMismatch() {
  mismatchSuggest.value = null
  mismatchResendText.value = ''
}

async function applySuggestedSubject() {
  if (!mismatchSuggest.value || !subjects.includes(mismatchSuggest.value)) {
    dismissMismatch()
    return
  }
  const next = mismatchSuggest.value
  const resend = mismatchResendText.value
  subject.value = next
  dismissMismatch()
  if (resend && !loading.value) {
    inputText.value = resend
    await nextTick()
    await sendMsg()
  }
}

async function openHistory() {
  showHistory.value = true
  try {
    const uid = await ensureChildUser()
    sessionList.value = await fetchQaSessions(uid)
  } catch (_) {
    sessionList.value = []
  }
}
function closeHistory() {
  showHistory.value = false
}

function askDeleteSession(sessionId) {
  deleteTargetId.value = sessionId
}

function cancelDeleteSession() {
  if (deleteSubmitting.value) return
  deleteTargetId.value = null
}

async function confirmDeleteSession() {
  const sessionId = deleteTargetId.value
  if (!sessionId || deleteSubmitting.value) return
  deleteSubmitting.value = true
  try {
    const uid = await ensureChildUser()
    await deleteQaSession(uid, sessionId)
    sessionList.value = sessionList.value.filter((s) => s.id !== sessionId)
    if (qaSessionId.value === sessionId) {
      qaSessionId.value = null
      pushWelcome()
    }
    deleteTargetId.value = null
    if (!sessionList.value.length) closeHistory()
    uni.showToast({ title: '已删除', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e?.message || '删除失败', icon: 'none' })
  }
  deleteSubmitting.value = false
}

async function startNewSession() {
  try {
    const uid = await ensureChildUser()
    const data = await createQaSession(uid, subject.value || null)
    qaSessionId.value = data.id
    pushWelcome()
    showHistory.value = false
    scrollChat()
  } catch (e) {
    uni.showToast({ title: e?.message || '创建失败', icon: 'none' })
  }
}

async function switchSession(sessionId) {
  try {
    const uid = await ensureChildUser()
    const meta = sessionList.value.find((s) => s.id === sessionId)
    const sessSubject = normalizeQaSubject(meta?.subject)
    if (sessSubject && subjects.includes(sessSubject)) {
      subject.value = sessSubject
    }
    qaSessionId.value = sessionId
    const data = await fetchQaSession(uid, sessionId)
    const items = data.messages || []
    messages.value = items.length
      ? items.map((x) => ({
          role: x.role === 'user' ? 'user' : 'assistant',
          text: x.content || '',
          imageUrl: x.image_url ? resolveQaImageUrl(x.image_url, uid) : null,
        }))
      : []
    if (!messages.value.length) pushWelcome()
    showHistory.value = false
    await nextTick()
    scrollChat()
  } catch (e) {
    uni.showToast({ title: e?.message || '加载失败', icon: 'none' })
  }
}

async function pickImage() {
  if (loading.value) return
  showImageSheet.value = true
}

function closeImageSheet() {
  showImageSheet.value = false
}

function clearPendingImage() {
  const prev = pendingImage.value?.preview
  pendingImage.value = null
  if (prev && String(prev).startsWith('blob:')) {
    try { URL.revokeObjectURL(prev) } catch (_) { /* ignore */ }
  }
}

function setPendingImage(pending) {
  if (!pending?.file || loading.value) return
  const prev = pendingImage.value?.preview
  pendingImage.value = pending
  if (prev && prev !== pending.preview && String(prev).startsWith('blob:')) {
    try { URL.revokeObjectURL(prev) } catch (_) { /* ignore */ }
  }
}

async function onPickSource(source) {
  if (loading.value) return
  // 先关自定义底栏；手机 H5 立刻用原生 input（同步 click），避免微信二次菜单
  showImageSheet.value = false
  try {
    if (typeof document !== 'undefined' && isMobileH5()) {
      const pending = await pickImageViaNativeInput(source === 'camera' ? 'environment' : '')
      setPendingImage(pending)
      uni.showToast({ title: source === 'camera' ? '已拍摄，点发送提问' : '已选图片，点发送提问', icon: 'none' })
      return
    }
    if (needsWebcamCapture(source)) {
      const pending = await pickImageViaNativeInput('environment')
      setPendingImage(pending)
      uni.showToast({ title: '已选图片，点发送提问', icon: 'none' })
      return
    }
    const path = await chooseQuestionImage(source)
    if (!path) return
    setPendingImage(await buildPendingImageFromPath(path))
    uni.showToast({ title: '已选图片，点发送提问', icon: 'none' })
  } catch (e) {
    if (e?.message === 'cancel') return
    if (e?.code === 'WEBCAM') {
      try {
        const pending = await pickImageViaNativeInput('environment')
        setPendingImage(pending)
        uni.showToast({ title: '已选图片，点发送提问', icon: 'none' })
      } catch (e2) {
        if (e2?.message !== 'cancel') {
          uni.showToast({ title: '无法打开相机，请用相册选图', icon: 'none' })
        }
      }
      return
    }
    uni.showToast({ title: e?.message || '选图失败', icon: 'none' })
  }
}

/** 对话框 Ctrl+V / 粘贴图片：只挂上待发送，不自动发出 */
async function handleClipboardPaste(event) {
  if (loading.value || typeof document === 'undefined') return
  const file = extractClipboardImageFile(event)
  if (!file) return
  event.preventDefault?.()
  event.stopPropagation?.()
  try {
    setPendingImage(pendingFromImageFile(file))
    uni.showToast({ title: '已粘贴图片，点发送提问', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e?.message || '粘贴图片失败', icon: 'none' })
  }
}

function onInputPaste(event) {
  handleClipboardPaste(event)
}

function previewImg(url) {
  if (!url) return
  uni.previewImage({ urls: [url], current: url })
}

function stopStream() {
  abortRequested = true
  streamAbort?.()
}

const IMAGE_ONLY_PLACEHOLDERS = new Set([
  '请帮我看这道题',
  '帮我看这道题',
  '帮我看下',
  '帮我看看',
])

function isImageOnlyPlaceholder(text) {
  return IMAGE_ONLY_PLACEHOLDERS.has(String(text || '').trim())
}

function shouldShowUserBubbleText(m) {
  const t = String(m?.text || '').trim()
  if (!t) return false
  // 有图时的占位句不展示（只显示图片）
  if (m?.imageUrl && isImageOnlyPlaceholder(t)) return false
  return true
}

async function sendMsg() {
  // 纯发图不附带「请帮我看这道题」
  const text = inputText.value.trim()
  const pending = pendingImage.value
  if ((!text && !pending) || loading.value) return
  if (!subject.value) {
    uni.showToast({ title: '先选一门学科频道', icon: 'none' })
    return
  }

  abortRequested = false
  // 先立刻展示 blob 预览，再异步转 dataURL
  let displayImageUrl = pending?.preview || null
  messages.value.push({
    role: 'user',
    text,
    imageUrl: displayImageUrl,
    hasImage: Boolean(pending),
  })
  inputText.value = ''
  pendingImage.value = null
  loading.value = true
  const userMsgIdx = messages.value.length - 1
  if (pending?.file) {
    try {
      const dataUrl = await fileToDataUrl(pending.file)
      if (dataUrl && messages.value[userMsgIdx]) {
        const old = messages.value[userMsgIdx].imageUrl
        messages.value[userMsgIdx].imageUrl = dataUrl
        if (old?.startsWith('blob:') && old !== dataUrl) {
          try { URL.revokeObjectURL(old) } catch (_) { /* ignore */ }
        }
      }
    } catch (_) { /* 保留 blob */ }
  }
  const aiIdx = messages.value.length
  messages.value.push({ role: 'assistant', text: '' })
  await nextTick()
  scrollChat()

  try {
    const uid = await ensureChildUser()
    let imageId = null
    if (pending?.file) {
      const compressed = await compressImage(pending.file)
      const up = await uploadQaImage(uid, compressed)
      imageId = up.image_id
      const local = messages.value[userMsgIdx]?.imageUrl
      if (local?.startsWith('data:')) {
        putQaImageLocal(imageId, local)
      }
    }

    const { promise, abort } = sendQaMessageStream(
      uid,
      text || '',
      qaSessionId.value,
      { subject: subject.value, image_id: imageId },
      {
        onToken(chunk) {
          const cur = messages.value[aiIdx]
          messages.value[aiIdx] = { ...cur, text: (cur?.text || '') + chunk }
          scrollChat()
        },
        onDone(data) {
          qaSessionId.value = data.session_id
          if (data.reply) messages.value[aiIdx].text = data.reply
          if (data.subject_mismatch && data.suggested_subject && subjects.includes(data.suggested_subject)) {
            mismatchSuggest.value = data.suggested_subject
            mismatchResendText.value = text || ''
          } else {
            dismissMismatch()
          }
        },
      },
    )
    streamAbort = abort
    const finalPayload = await promise
    if (!String(messages.value[aiIdx]?.text || '').trim()) {
      const fallback = String(finalPayload?.reply || '').trim()
      messages.value[aiIdx].text = fallback || '老师暂时没有回复，请再发一次试试～'
    }
  } catch (e) {
    if (isStreamAborted(e)) {
      applyStreamStoppedHint(messages, aiIdx)
      return
    }
    const errText = errMessage(e, '请求失败，请稍后再试')
    if (!messages.value[aiIdx]?.text) {
      messages.value[aiIdx].text = `出错了：${errText}`
    } else {
      messages.value.push({ role: 'assistant', text: `出错了：${errText}` })
    }
  } finally {
    streamAbort = null
    abortRequested = false
    loading.value = false
    scrollChat()
  }
}

onLoad((opts) => {
  const from = String(opts?.from || '').trim()
  let rawSubject = String(opts?.subject || '').trim()
  let rawHint = String(opts?.hint || '').trim()
  let rawQuery = String(opts?.query || '').trim()
  try { if (rawSubject) rawSubject = decodeURIComponent(rawSubject) } catch (_) { /* keep */ }
  try { if (rawHint) rawHint = decodeURIComponent(rawHint) } catch (_) { /* keep */ }
  try { if (rawQuery) rawQuery = decodeURIComponent(rawQuery) } catch (_) { /* keep */ }
  const normSubject = normalizeQaSubject(rawSubject)
  if (subjects.includes(normSubject)) subject.value = normSubject
  const prefill = (rawQuery || rawHint).slice(0, 400)
  if (prefill) inputText.value = prefill.slice(0, 200)
  if (from === 'guide' && (normSubject || prefill)) {
    guideHandoffBanner.value = {
      subject: subjects.includes(normSubject) ? normSubject : '',
      hint: (rawHint || prefill).slice(0, 60),
      childId: String(opts?.child_id || '').trim(),
      image: String(opts?.image || '').trim(),
    }
  }
})

onShow(() => {
  readTheme()
  if (messages.value.length > 1) scrollChat()
})

onMounted(async () => {
  readTheme()
  readSimple()
  await prefetchKatex()
  katexTick.value = getKatexEpoch()
  if (typeof document !== 'undefined') {
    document.addEventListener('paste', handleClipboardPaste)
  }
  const auth = await requirePageAuth('student')
  if (!auth?.ok) return
  pushWelcome()
  scrollChat()
})

onBeforeUnmount(() => {
  if (typeof document !== 'undefined') {
    document.removeEventListener('paste', handleClipboardPaste)
  }
  clearPendingImage()
})
</script>

<style scoped>
.app {
  height: 100vh;
  height: 100dvh;
  width: 100%;
  max-width: var(--app-max-width, 480px);
  margin: 0 auto;
  background: #0b0e14;
  color: #edebe4;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  position: relative;
  overflow: hidden;
  padding-bottom: calc(64px + env(safe-area-inset-bottom, 0px));
}
.app.lt { background: linear-gradient(180deg, #dce2ef 0%, #ebeef4 30%); color: #1b1912; }

.topbar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px 4px;
  gap: 8px;
  min-width: 0;
}
.brand { display: flex; align-items: center; gap: 10px; min-width: 0; flex: 1; }
.logo {
  width: 44px; height: 44px; border-radius: 50%;
  background: url('/static/dayu/assets/avatar_sizhe.jpg') center/cover;
  border: 2px solid #30904f;
  box-shadow: 0 0 10px rgba(48, 144, 79, 0.4);
}
.t1 { display: block; font-size: 19px; font-weight: 800; }
.t2 { display: block; font-size: 10px; color: #8b93a5; letter-spacing: 2px; }
.top-actions { display: flex; gap: 8px; align-items: center; }
.gear { font-size: 18px; color: #8b93a5; padding: 4px 7px; }
.chip-g {
  background: rgba(48, 144, 79, 0.12);
  border: 1.5px solid #30904f;
  color: #6fcf8e;
  font-size: 13px;
  font-weight: 700;
  padding: 5px 11px;
  border-radius: 999px;
}
.app.lt .chip-g { color: #30904f; }

.mstage {
  flex-shrink: 0;
  margin: 8px 18px 0;
  border-radius: 18px;
  overflow: hidden;
  position: relative;
  aspect-ratio: 16 / 9;
  max-height: min(28vh, 220px);
  background: linear-gradient(140deg, #141c2e, #0b0e14);
  border: 1.5px solid #2a3040;
}
.app.lt .mstage {
  background: linear-gradient(140deg, #d1d9eb, #ebeef4);
  border-color: #bfc5d5;
}
.mstage-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  /* 合影/人像靠上：避免 cover 裁掉头顶 */
  object-fit: cover;
  object-position: center top;
}
/* H5 uni-image 内部 img */
.mstage-img :deep(img),
.mstage :deep(img) {
  object-fit: cover !important;
  object-position: center top !important;
}
.mgrad {
  position: absolute; inset: 0;
  background: linear-gradient(180deg, transparent 55%, rgba(5, 8, 14, 0.82));
}
.app.lt .mgrad { background: linear-gradient(180deg, transparent 55%, rgba(241, 244, 250, 0.82)); }
.mlive {
  position: absolute; top: 10px; left: 10px;
  font-size: 11px; font-weight: 900; color: #6fcf8e;
  background: rgba(0, 0, 0, 0.55); border-radius: 8px; padding: 5px 10px;
  display: flex; align-items: center; gap: 6px;
  z-index: 2;
  animation: mlivePulse 1.6s ease-in-out infinite;
}
.app.lt .mlive { color: #30904f; background: rgba(247, 247, 247, 0.7); }
.mlive-t { line-height: 1; }
.mlive-dots { display: inline-flex; width: 14px; letter-spacing: 0; }
.mlive-dot {
  display: inline-block;
  animation: mliveDot 1.2s ease-in-out infinite;
  opacity: 0.25;
}
.mlive-dot:nth-child(2) { animation-delay: 0.2s; }
.mlive-dot:nth-child(3) { animation-delay: 0.4s; }
.dot {
  width: 7px; height: 7px; border-radius: 50%; background: currentColor;
  flex: none;
  box-shadow: 0 0 0 0 rgba(111, 207, 142, 0.55);
  animation: mliveBlink 1.2s ease-in-out infinite;
}
@keyframes mliveBlink {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(111, 207, 142, 0.45); }
  50% { opacity: 0.35; box-shadow: 0 0 0 5px rgba(111, 207, 142, 0); }
}
@keyframes mlivePulse {
  0%, 100% { opacity: 0.88; transform: translateY(0); }
  50% { opacity: 1; transform: translateY(-1px); }
}
@keyframes mliveDot {
  0%, 80%, 100% { opacity: 0.2; }
  40% { opacity: 1; }
}
.mwho {
  position: absolute; left: 12px; bottom: 10px;
  display: flex; align-items: baseline; gap: 8px;
}
.mwho-name { font-size: 16px; font-weight: 900; color: #fff; text-shadow: 0 2px 8px rgba(0,0,0,.7); }
.app.lt .mwho-name { color: #141414; text-shadow: none; }
.mwho-tag { font-size: 10.5px; color: rgba(255,255,255,.85); }
.app.lt .mwho-tag { color: rgba(20,20,20,.85); }

.subs {
  flex-shrink: 0;
  width: 100%;
  margin: 10px 0 0;
  box-sizing: border-box;
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior-x: contain;
  cursor: grab;
  scrollbar-width: none;
  -ms-overflow-style: none;
  touch-action: pan-x;
}
.subs.dragging {
  cursor: grabbing;
  user-select: none;
}
.subs::-webkit-scrollbar {
  display: none !important;
  width: 0 !important;
  height: 0 !important;
}
.subs-inner {
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
  align-items: center;
  gap: 8px;
  padding: 0 18px;
  width: max-content;
  min-width: 100%;
  box-sizing: border-box;
}
.sub-chip {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #131926;
  border: 1.5px solid #232b3d;
  border-radius: 14px;
  padding: 7px 14px;
  font-size: 13.5px;
  font-weight: 800;
  color: #8b93a5;
  white-space: nowrap;
  cursor: pointer;
}
.app.lt .sub-chip { background: #d9dfec; border-color: #c2cadc; color: #5a6274; }
.sub-chip.on {
  background: rgba(46, 107, 230, 0.16);
  border-color: #2e6be6;
  color: #7fa7ef;
}
.app.lt .sub-chip.on {
  background: rgba(25, 86, 209, 0.16);
  border-color: #1956d1;
  color: #103880;
}

.mentor {
  flex-shrink: 0;
  margin: 8px 18px 0;
  background: linear-gradient(160deg, #1a2233, #101623 75%);
  border: 1.5px solid #2a3040;
  border-radius: 18px;
  padding: 12px;
  display: flex;
  gap: 12px;
  align-items: flex-start;
  min-width: 0;
  box-sizing: border-box;
}
.minfo {
  flex: 1;
  min-width: 0;
}
.app.lt .mentor {
  background: linear-gradient(160deg, #ccd4e5, #dce2ef 75%);
  border-color: #bfc5d5;
}
.app.simple .mentor { display: none; }
.mava {
  width: 54px; height: 54px; border-radius: 50%; flex: none;
  display: flex; align-items: center; justify-content: center;
  font-size: 26px; border: 2.5px solid; position: relative;
  background: #0d111f;
}
.mava.img {
  width: 88px;
  height: 118px;
  border-radius: 16px;
  font-size: 0;
  align-self: flex-start;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35), 0 0 0 1px rgba(255, 255, 255, 0.12) inset;
}
.mava.img + .minfo .mn { font-size: 20px; letter-spacing: 1px; }
.app.lt .mava.img {
  box-shadow: 0 6px 16px rgba(60, 80, 120, 0.25);
}
.mava-emoji { line-height: 1; }
.mtb {
  position: absolute; right: -4px; bottom: -4px;
  width: 22px; height: 22px; border-radius: 50%;
  background: #0d111f; border: 1.5px solid;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 900;
}
.mn-row { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
.mn { font-size: 17px; font-weight: 900; }
.mtag {
  font-size: 10px; font-weight: 800; border-radius: 6px;
  padding: 2px 8px; border: 1px solid;
}
.mknow {
  display: block; font-size: 11px; margin-top: 5px; line-height: 1.5;
  word-break: break-word; overflow-wrap: anywhere;
}

.banner {
  flex-shrink: 0;
  margin: 8px 18px 0;
  padding: 8px 10px;
  border-radius: 12px;
  background: rgba(46, 107, 230, 0.12);
  border: 1px solid #2e6be6;
  display: flex; align-items: center; gap: 8px;
  box-sizing: border-box;
}
.banner-text { flex: 1; min-width: 0; font-size: 12px; color: #a8b4cc; }
.banner-act { flex: none; font-size: 12px; font-weight: 800; color: #7fa7ef; }
.banner-x { flex: none; font-size: 16px; color: #8b93a5; padding: 0 4px; }

.chat-scroll {
  flex: 1;
  height: 0;
  min-height: 0;
  width: 100%;
  margin: 8px 0 0;
  box-sizing: border-box;
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.chat-scroll::-webkit-scrollbar,
.chat-scroll :deep(uni-scroll-view)::-webkit-scrollbar,
.chat-scroll :deep(.uni-scroll-view)::-webkit-scrollbar {
  display: none !important;
  width: 0 !important;
  height: 0 !important;
}
.chat-stack {
  width: 100%;
  max-width: 100%;
  padding: 4px 18px 10px;
  box-sizing: border-box;
  overflow: hidden;
}
.chat-end { height: 4px; }
.msg {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  align-items: flex-start;
}
.msg.me {
  flex-direction: row-reverse;
  justify-content: flex-start;
}
.av {
  width: 36px; height: 36px; border-radius: 50%; flex: none;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; border: 2px solid; background: #161d2b;
}
.bubble-wrap {
  min-width: 0;
  max-width: calc(100% - 44px);
  box-sizing: border-box;
}
.msg.me .bubble-wrap {
  max-width: 82%;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.who {
  font-size: 11.5px; color: #5a6274; margin-bottom: 4px;
  display: flex; align-items: center; gap: 5px; flex-wrap: wrap;
}
.who-i {
  font-size: 9px; border: 1px solid #2a3040; border-radius: 5px;
  padding: 1px 6px; color: #8b93a5;
}
.tx {
  display: inline-block;
  background: #161d2b; border: 1px solid #2a3040;
  border-radius: 4px 14px 14px 14px; padding: 10px 12px;
  font-size: 14px; color: #d8dce6; line-height: 1.7;
  max-width: 100%;
  box-sizing: border-box;
  word-break: break-word;
  overflow-wrap: anywhere;
}
.app.lt .tx { background: #d4dbe9; border-color: #bfc5d5; color: #191d27; }
.tx-me {
  background: #2e6be6; border: none;
  border-radius: 14px 4px 14px 14px; color: #fff;
}
.app.lt .tx-me { background: #1956d1; color: #141414; }
.tx-text, .tx-rich {
  display: block;
  max-width: 100%;
  word-break: break-word;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  -webkit-user-select: text !important;
  user-select: text !important;
  cursor: text;
}
/* 富文本分层样式见 @/styles/qaBubbleRich.css（非 scoped，才能作用到 v-html） */
.bubble-img-wrap {
  width: 160px;
  max-width: min(160px, 70vw);
  min-height: 96px;
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 6px;
  background: rgba(0, 0, 0, 0.2);
}
.bubble-img {
  width: 100%;
  height: 120px;
  display: block;
  object-fit: cover;
}
.bubble-img-ph {
  min-height: 96px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.75);
  padding: 10px;
}
.thinking {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 20px;
  color: #6fcf8e;
  font-size: 13px;
  font-weight: 700;
}
.app.lt .thinking { color: #30904f; }
.thinking-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
  flex: none;
  animation: mliveBlink 1.2s ease-in-out infinite;
}
.thinking-t { line-height: 1; }
.thinking-ellipsis {
  display: inline-flex;
  width: 14px;
}
.thinking-ellipsis .te {
  display: inline-block;
  animation: mliveDot 1.2s ease-in-out infinite;
  opacity: 0.25;
}
.thinking-ellipsis .te:nth-child(2) { animation-delay: 0.2s; }
.thinking-ellipsis .te:nth-child(3) { animation-delay: 0.4s; }

.composer {
  flex-shrink: 0;
  padding: 8px 10px 10px;
  background: rgba(11, 14, 20, 0.96);
  border-top: 1px solid #232b3d;
}
.app.lt .composer {
  background: rgba(235, 238, 244, 0.96);
  border-top-color: #c2cadc;
}
.pending-inline {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  padding: 0 2px;
}
.pending-card {
  position: relative;
  width: 72px;
  height: 72px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.14);
  flex-shrink: 0;
  background: rgba(0, 0, 0, 0.25);
}
.app.lt .pending-card { border-color: #c2cadc; background: rgba(0, 0, 0, 0.06); }
.pending-thumb {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}
.pending-clear {
  position: absolute;
  top: 3px;
  right: 3px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
}
.pending-clear text { color: #fff; font-size: 10px; line-height: 1; }
.pending-hint {
  font-size: 12px;
  color: rgba(237, 235, 228, 0.55);
  flex: 1;
  min-width: 0;
}
.app.lt .pending-hint { color: #6b7280; }

.composer-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}
.composer .tool.voice {
  width: 36px;
  height: 44px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: #d8dce6;
}
.composer-main {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  min-height: 44px;
  padding: 4px 6px 4px 12px;
  border-radius: 22px;
  background: #161c2a;
  border: 1px solid #2a3348;
  box-sizing: border-box;
}
.app.lt .composer-main {
  background: #fff;
  border-color: #c8d0e0;
}
.composer-main .box {
  flex: 1;
  min-width: 0;
  height: 36px;
  line-height: 36px;
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
  font-size: 15px;
  color: #edebe4;
  box-sizing: border-box;
}
.app.lt .composer-main .box { color: #1b1912; }
.composer-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex: none;
}
.composer-actions .act {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}
.composer-actions .act.cam { color: #d8dce6; }
.composer-actions .act.cam.disabled { opacity: 0.4; pointer-events: none; }
.composer-actions .act.plus { color: #d8dce6; font-size: 22px; }
.composer-actions .act-ic { font-size: 20px; line-height: 1; }
.composer-actions .act.send {
  background: #4d6bfe;
  color: #fff;
  box-shadow: 0 2px 8px rgba(77, 107, 254, 0.35);
}
.composer-actions .act.send:active { transform: scale(0.96); }
.composer-actions .act.send.stop {
  background: #e05252;
  box-shadow: none;
}
.composer-actions .send-ic {
  font-size: 18px;
  font-weight: 700;
  line-height: 1;
  color: #fff;
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
.app.lt .foot { background: rgba(235, 238, 244, 0.94); border-top-color: #c2cadc; }
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

.hist, .setm {
  position: fixed; inset: 0; background: rgba(0,0,0,.6); z-index: 70;
  max-width: var(--app-max-width, 480px); margin: 0 auto;
}
.hbox {
  position: absolute; top: 0; right: 0; bottom: 0;
  width: 78%; max-width: 320px;
  background: #101623; border-left: 1.5px solid #2a3040;
  padding: 16px; display: flex; flex-direction: column;
}
.app.lt .hbox { background: #dce2ef; border-left-color: #bfc5d5; }
.ht { font-size: 15px; font-weight: 900; margin-bottom: 10px; }
.hnew {
  text-align: center; font-size: 13px; font-weight: 800; color: #6fcf8e;
  border: 1.5px solid #30904f; border-radius: 12px; padding: 8px; margin-bottom: 12px;
}
.hlist {
  flex: 1; height: 0;
  scrollbar-width: none; -ms-overflow-style: none;
}
.hlist::-webkit-scrollbar { display: none; width: 0; height: 0; }
.hitem {
  display: flex; align-items: center; gap: 8px;
  background: #161d2b; border: 1px solid #232b3d; border-radius: 12px;
  padding: 10px 12px; margin-bottom: 9px;
}
.hitem.active { border-color: #3d8bff; background: rgba(46, 107, 230, 0.12); }
.app.lt .hitem { background: #d4dbe9; border-color: #c2cadc; }
.app.lt .hitem.active { border-color: #1956d1; background: rgba(25, 86, 209, 0.1); }
.hitem-main { flex: 1; min-width: 0; }
.hitem-t {
  display: block; font-size: 12.5px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.hitem-s { font-size: 10px; color: #5a6274; }
.hitem-del {
  flex-shrink: 0; color: #f85149; font-size: 14px; padding: 4px 6px;
  line-height: 1; cursor: pointer;
}
.hempty { text-align: center; color: #5a6274; font-size: 12px; padding: 24px 0; }

.delm {
  position: fixed; inset: 0; z-index: 90;
  background: rgba(0,0,0,.55);
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
  max-width: var(--app-max-width, 480px); margin: 0 auto;
}
.delbox {
  width: 100%; max-width: 300px;
  background: #161d2b; border: 1px solid #2a3040; border-radius: 16px;
  padding: 18px 16px;
}
.app.lt .delbox { background: #e8ecf4; border-color: #c2cadc; }
.delt {
  display: block; text-align: center; font-size: 16px; font-weight: 800; margin-bottom: 8px;
}
.deld {
  display: block; text-align: center; font-size: 13px; color: #8b93a5;
  line-height: 1.5; margin-bottom: 16px;
}
.app.lt .deld { color: #5a6274; }
.delacts { display: flex; gap: 10px; }
.delbtn {
  flex: 1; text-align: center; border-radius: 10px; padding: 10px 0;
  font-size: 14px; font-weight: 700; cursor: pointer;
}
.delbtn.cancel { background: rgba(255,255,255,.06); color: #8b93a5; }
.app.lt .delbtn.cancel { background: rgba(0,0,0,.06); color: #5a6274; }
.delbtn.danger { background: rgba(248, 81, 73, 0.18); color: #f85149; }

.sbox {
  position: absolute; left: 50%; bottom: 0; transform: translateX(-50%);
  width: 100%; max-width: var(--app-max-width, 480px);
  background: #101623; border: 1.5px solid #2a3040; border-bottom: none;
  border-radius: 20px 20px 0 0; padding: 18px;
  box-sizing: border-box;
}
.app.lt .sbox { background: #dce2ef; border-color: #bfc5d5; }
.stitle { display: block; font-size: 16px; font-weight: 900; }
.ssub { display: block; font-size: 10.5px; color: #5a6274; margin: 4px 0 12px; }
.srow {
  display: flex; align-items: center; justify-content: space-between;
  gap: 10px; padding: 12px 2px; border-top: 1px solid #232b3d; font-size: 13px;
}
.srow-s { display: block; font-size: 10px; color: #5a6274; margin-top: 2px; }
.sw {
  width: 44px; height: 24px; border-radius: 12px; background: #232b3d; position: relative;
}
.sw-i {
  position: absolute; left: 3px; top: 3px; width: 18px; height: 18px;
  border-radius: 50%; background: #5a6274; transition: .25s;
}
.sw.on { background: #2e6be6; }
.sw.on .sw-i { left: 23px; background: #fff; }
.sclose {
  margin-top: 14px; text-align: center; font-size: 13px; font-weight: 800;
  color: #8b93a5; border: 1.5px solid #2a3040; border-radius: 12px; padding: 10px;
}

.img-sheet-mask {
  position: fixed;
  inset: 0;
  z-index: 90;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  max-width: var(--app-max-width, 480px);
  margin: 0 auto;
}
.img-sheet {
  width: 100%;
  padding: 10px 12px calc(10px + env(safe-area-inset-bottom, 0px));
  box-sizing: border-box;
}
.img-sheet-group {
  background: #f5f5f7;
  border-radius: 14px;
  overflow: hidden;
  margin-bottom: 8px;
}
.app:not(.lt) .img-sheet-group {
  background: #1c2333;
  border: 1px solid #2a3040;
}
.img-sheet-item {
  text-align: center;
  padding: 16px 12px;
  font-size: 17px;
  font-weight: 600;
  color: #007aff;
  border-bottom: 1px solid rgba(60, 60, 67, 0.18);
}
.app:not(.lt) .img-sheet-item {
  color: #6ea8ff;
  border-bottom-color: #2a3040;
}
.img-sheet-item:last-child {
  border-bottom: none;
}
.img-sheet-cancel {
  text-align: center;
  padding: 16px 12px;
  font-size: 17px;
  font-weight: 700;
  color: #007aff;
  background: #f5f5f7;
  border-radius: 14px;
}
.app:not(.lt) .img-sheet-cancel {
  color: #edebe4;
  background: #1c2333;
  border: 1px solid #2a3040;
}
</style>
