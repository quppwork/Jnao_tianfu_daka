<template>

  <view class="qa-app">

    <view class="qa-header">

      <view class="nav-back" @tap="goBack">

        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>

      </view>

      <text class="nav-title">学科答疑</text>

      <view class="nav-history" @tap="openSessionSheet"><text>历史</text></view>

    </view>



    <view class="subject-bar">

      <view

        v-for="s in subjects"

        :key="s"

        class="subject-chip"

        :class="{ active: subject === s }"

        @tap="subject = s"

      >

        <text>{{ subjectEmoji[s] || '' }} {{ s }}</text>

      </view>

    </view>



    <view class="chat-scroll" id="chatScroll">

      <view v-if="messages.length <= 1" class="empty-hint">

        <view class="empty-icon">✨</view>

        <text class="empty-title">张宇老师在线</text>

        <text class="empty-desc">拍照发题或打字提问，我会结合你的天赋特点来辅导～</text>

      </view>



      <view

        v-for="(m, i) in messages"

        :key="i"

        class="msg-row"

        :class="m.role === 'user' ? 'msg-user' : 'msg-ai'"

      >

        <view v-if="m.role !== 'user'" class="msg-avatar ai">

          <image class="avatar-img" src="/static/teacher-avatar.png" mode="aspectFill" />

        </view>



        <view class="msg-body">

          <view v-if="m.role === 'user'" class="bubble-user">

            <image
              v-if="m.imageUrl"
              :src="m.imageUrl"
              mode="widthFix"
              class="bubble-img"
              @tap.stop="previewMessageImage(i)"
            />

            <text v-if="m.text && !(m.imageUrl && m.text === '请帮我看这道题')" class="bubble-text">{{ m.text }}</text>

          </view>

          <view v-else class="bubble-ai">

            <text class="bubble-sender">张宇老师</text>

            <text class="bubble-text">{{ m.text }}</text>

          </view>

        </view>



        <view v-if="m.role === 'user'" class="msg-avatar user">

          <text>我</text>

        </view>

      </view>



      <view v-if="loading" class="msg-row msg-ai">

        <view class="msg-avatar ai"><image class="avatar-img" src="/static/teacher-avatar.png" mode="aspectFill" /></view>

        <view class="msg-body">

          <view class="bubble-ai typing-wrap">

            <text class="typing-dots">思考中</text>

          </view>

        </view>

      </view>



      <text v-if="coachHint" class="coach-hint">💡 {{ coachHint }}</text>

    </view>



    <view class="composer">

      <view v-if="QA_VOICE_ENABLED && (micBlockedHint || isMobileH5())" class="mic-hint-bar" :class="{ ok: !micBlockedHint && isMobileH5() }">

        <text class="mic-hint-text">{{ micBlockedHint || (isMobileH5() ? '按住 🎤 说话，松开发送' : '') }}</text>

        <view v-if="micBlockedHint" class="mic-hint-close" @tap="micBlockedHint = ''"><text>✕</text></view>

      </view>



      <view v-if="pendingImage" class="pending-bar">

        <image :src="pendingImage.preview" mode="aspectFill" class="pending-thumb" @tap="previewImage(pendingImage.preview)" />

        <text class="pending-label">题目图片已添加</text>

        <view class="pending-clear" @tap="clearPendingImage()"><text>✕</text></view>

      </view>



      <view class="input-box" :class="{ focused: inputFocused }">

        <input

          class="chat-input"

          v-model="inputText"

          placeholder="输入问题，也可拍照发题…"

          confirm-type="send"

          @confirm="sendMsg"

          @focus="inputFocused = true"

          @blur="inputFocused = false"

          :disabled="loading"

        />

        <view class="input-actions">

          <view class="act-btn" @tap="openImageSheet" title="添加图片">

            <text class="act-icon">📷</text>

          </view>

          <view
            v-if="QA_VOICE_ENABLED"
            class="act-btn"
            :class="{ recording }"
            @tap="onMicTap"
            @touchstart.prevent="onMicTouchStart"
            @touchend.prevent="onMicTouchEnd"
            @touchcancel.prevent="onMicTouchEnd"
            title="语音"
          >

            <text class="act-icon">🎤</text>

          </view>

          <view class="send-btn" :class="{ disabled: !canSend }" @tap="sendMsg">

            <text>发送</text>

          </view>

        </view>

      </view>

    </view>

    <view v-if="previewUrl" class="img-preview-mask" @tap="previewUrl = null">
      <image :src="previewUrl" mode="widthFix" class="img-preview-full" @tap.stop />
      <text class="img-preview-hint">点击空白处关闭</text>
    </view>

    <view v-if="showImageSheet" class="sheet-mask" @tap="closeImageSheet">

      <view class="sheet-panel" @tap.stop>

        <text class="sheet-title">添加题目图片</text>

        <view class="sheet-options">

          <view class="sheet-card" @tap="onPickSource('camera')">

            <text class="sheet-card-icon">📷</text>

            <text class="sheet-card-label">拍照</text>

            <text class="sheet-card-desc">{{ isDesktop ? '电脑：打开摄像头' : '使用手机相机' }}</text>

          </view>

          <view class="sheet-card" @tap="onPickSource('album')">

            <text class="sheet-card-icon">🖼️</text>

            <text class="sheet-card-label">从相册选择</text>

            <text class="sheet-card-desc">{{ isDesktop ? '选择本机图片' : '从相册选图' }}</text>

          </view>

        </view>

        <view class="sheet-cancel" @tap="closeImageSheet"><text>取消</text></view>

      </view>

    </view>



    <view v-if="showWebcam" class="sheet-mask" @tap="closeWebcam">

      <view class="webcam-panel" @tap.stop>

        <text class="webcam-title">摄像头拍照</text>

        <view class="webcam-video-wrap">

          <video id="qaWebcamVideo" class="webcam-video" autoplay playsinline muted></video>

        </view>

        <view class="webcam-actions">

          <view class="webcam-btn cancel" @tap="closeWebcam"><text>取消</text></view>

          <view class="webcam-btn shoot" @tap="captureWebcam"><text>拍摄</text></view>

        </view>

      </view>

    </view>

    <view v-if="showSessionSheet" class="sheet-mask" @tap="closeSessionSheet">
      <view class="sheet-panel session-panel" @tap.stop>
        <text class="sheet-title">对话历史</text>
        <view class="session-new" @tap="startNewSession"><text>＋ 新建对话</text></view>
        <scroll-view class="session-list" scroll-y>
          <view v-for="s in sessionList" :key="s.id" class="session-row" :class="{ active: s.id === qaSessionId }" @tap="switchSession(s.id)">
            <view class="session-info">
              <text class="session-title">{{ s.title || '新对话' }}</text>
              <text class="session-meta">{{ s.subject || '通用' }} · {{ formatSessionTime(s.created_at) }}</text>
            </view>
            <text class="session-del" @tap.stop="removeSession(s.id)">✕</text>
          </view>
          <text v-if="!sessionList.length" class="session-empty">暂无历史，开始新对话吧</text>
        </scroll-view>
        <view class="sheet-cancel" @tap="closeSessionSheet"><text>关闭</text></view>
      </view>
    </view>

  </view>

</template>



<script setup>

import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'

import {

  ensureChildUser,

  fetchQaSessions,

  createQaSession,

  deleteQaSession,

  fetchQaSession,

  resolveQaImageUrl,

  sendQaMessage,

  uploadQaImage,

  transcribeVoice,

  transcribeVoicePath,

  updateLearnerProfile,

  fetchProfile,

  gradeToSchoolStage,

} from '@/utils/userApi.js'

import { chooseQuestionImage, needsWebcamCapture, isMobileH5 } from '@/utils/qaMedia.js'

import {
  BrowserVoiceRecorder,
  browserCanUseMic,
  buildMicAccessHint,
  isWebH5,
  probeMicrophoneAccess,
} from '@/utils/qaVoice.js'

/** 语音暂搁置（H5 需 HTTPS + 手机证书，影响开发）；恢复时改为 true */
const QA_VOICE_ENABLED = false



const subjects = ['数学', '语文', '英语', '科学']
const subjectEmoji = { 数学: '📐', 语文: '📖', 英语: '🔤', 科学: '🔬' }

const subject = ref('数学')

const inputText = ref('')

const inputFocused = ref(false)

const loading = ref(false)

const qaSessionId = ref(null)

const coachHint = ref('')

const pendingImage = ref(null)

const recording = ref(false)

const showImageSheet = ref(false)

const pickingImage = ref(false)

const showWebcam = ref(false)

const showSessionSheet = ref(false)

const sessionList = ref([])

const isDesktop = ref(false)

const previewUrl = ref(null)

const micBlockedHint = ref('')



const messageBlobUrls = new Set()



let webcamStream = null

let webcamVideoEl = null

let uniRecorder = null

let speechRecognition = null

let browserRecorder = null

let voiceMode = 'browser-media' // browser-media | uni-recorder | browser-asr



const messages = ref([

  { role: 'assistant', text: '你好！我是张宇老师 ✨ 可以拍照发题或打字提问～' },

])

let qaLearnerDefaultApplied = false



const canSend = computed(() => !loading.value && (inputText.value.trim() || pendingImage.value))



function goBack() { uni.navigateBack({ delta: 1 }) }



function previewImage(url, allUrls) {

  if (!url) return

  const urls = (allUrls && allUrls.length) ? allUrls : [url]

  if (typeof uni !== 'undefined' && uni.previewImage) {

    uni.previewImage({

      urls,

      current: url,

      fail: () => { previewUrl.value = url },

    })

    return

  }

  previewUrl.value = url

}



function previewMessageImage(msgIndex) {

  const current = messages.value[msgIndex]?.imageUrl

  if (!current) return

  const urls = messages.value.map((m) => m.imageUrl).filter(Boolean)

  previewImage(current, urls)

}



function warnMicBlocked() {

  const hint = buildMicAccessHint()

  if (!hint) return

  micBlockedHint.value = hint

  uni.showToast({ title: hint, icon: 'none', duration: 4500 })

}



async function processVoiceResult(blob, filename) {

  try {

    uni.showLoading({ title: '识别中...' })

    const text = await transcribeVoice(blob, filename)

    uni.hideLoading()

    inputText.value = text

    if (text.trim()) await sendMsg()

  } catch (err) {

    uni.hideLoading()

    uni.showToast({ title: err.message || '语音识别失败', icon: 'none', duration: 3000 })

  }

}



async function startBrowserRecord() {

  if (recording.value || loading.value) return

  if (!browserCanUseMic()) {

    warnMicBlocked()

    return

  }

  try {

    if (!browserRecorder) browserRecorder = new BrowserVoiceRecorder()

    await browserRecorder.start()

    recording.value = true

    uni.showToast({ title: isMobileH5() ? '松开发送' : '录音中，再点结束', icon: 'none' })

  } catch (e) {

    recording.value = false

    const msg = e?.name === 'NotAllowedError'

      ? '麦克风权限被拒，请在浏览器或系统设置中允许'

      : (e?.message || '无法启动录音')

    micBlockedHint.value = msg

    uni.showToast({ title: msg, icon: 'none', duration: 3500 })

  }

}



async function stopBrowserRecord() {

  if (!recording.value || voiceMode !== 'browser-media') return

  recording.value = false

  try {

    const { blob, filename } = await browserRecorder.stop()

    await processVoiceResult(blob, filename)

  } catch (e) {

    browserRecorder?.cancel()

    if (e.message !== '未录到音频') {

      uni.showToast({ title: e.message || '录音失败', icon: 'none' })

    }

  }

}



function initUniRecorder() {

  if (typeof uni === 'undefined' || !uni.getRecorderManager) return false

  uniRecorder = uni.getRecorderManager()

  uniRecorder.onStop(async (res) => {

    recording.value = false

    if (!res.tempFilePath) {

      uni.showToast({ title: '未录到音频', icon: 'none' })

      return

    }

    try {

      uni.showLoading({ title: '识别中...' })

      const text = await transcribeVoicePath(res.tempFilePath)

      uni.hideLoading()

      inputText.value = text

      if (text.trim()) await sendMsg()

    } catch (err) {

      uni.hideLoading()

      uni.showToast({ title: err.message || '语音识别失败', icon: 'none' })

    }

  })

  uniRecorder.onError(() => {

    recording.value = false

    uni.showToast({ title: '录音失败，请检查麦克风权限', icon: 'none' })

  })

  return true

}



function initBrowserSpeech() {

  const SR = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition)

  if (!SR) return false

  speechRecognition = new SR()

  speechRecognition.lang = 'zh-CN'

  speechRecognition.interimResults = false

  speechRecognition.continuous = false

  speechRecognition.onresult = (e) => {

    let text = ''

    for (let i = e.resultIndex; i < e.results.length; i++) {

      text += e.results[i][0].transcript

    }

    inputText.value = text

    recording.value = false

    if (text.trim()) sendMsg()

  }

  speechRecognition.onerror = (e) => {

    recording.value = false

    const msg = e.error === 'not-allowed'

      ? '麦克风权限被拒，请在浏览器地址栏允许麦克风'

      : '语音识别失败'

    uni.showToast({ title: msg, icon: 'none', duration: 3000 })

  }

  speechRecognition.onend = () => { recording.value = false }

  return true

}



async function ensureLearnerProfile(uid, profileData = null) {

  try {

    const profile = profileData || await fetchProfile(uid)

    const grade = profile.profile_json?.grade

    if (grade) {

      await updateLearnerProfile(uid, {

        grade,

        school_stage: gradeToSchoolStage(grade),

      })

      return

    }

    if (qaLearnerDefaultApplied) return

    await updateLearnerProfile(uid, { grade: '四年级', age: 10, school_stage: 'primary_high' })

    qaLearnerDefaultApplied = true

  } catch (e) { /* ignore */ }

}



const DEFAULT_GREETING = { role: 'assistant', text: '你好！我是张宇老师 ✨ 可以拍照发题或打字提问～' }



function mapSessionMessages(data, uid) {

  if (!data.messages?.length) return [DEFAULT_GREETING]

  return data.messages.map(m => ({

    role: m.role === 'user' ? 'user' : 'assistant',

    text: m.content,

    imageUrl: resolveQaImageUrl(m.image_url, uid) || null,

  }))

}



async function loadSessionList() {

  try {

    const uid = await ensureChildUser()

    sessionList.value = await fetchQaSessions(uid)

  } catch (e) {

    sessionList.value = []

  }

}



async function loadSession(sessionId = null) {

  try {

    const uid = await ensureChildUser()

    const profile = await fetchProfile(uid)

    await ensureLearnerProfile(uid, profile)

    await loadSessionList()

    let sid = sessionId

    if (!sid) {

      const latest = sessionList.value[0]

      if (!latest) return

      sid = latest.id

    }

    qaSessionId.value = sid

    const data = await fetchQaSession(uid, sid)

    messages.value = mapSessionMessages(data, uid)

  } catch (e) { /* 新用户 */ }

}



function formatSessionTime(iso) {

  if (!iso) return ''

  const d = new Date(iso)

  if (Number.isNaN(d.getTime())) return iso.slice(0, 10)

  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`

}



function openSessionSheet() {

  loadSessionList()

  showSessionSheet.value = true

}



function closeSessionSheet() {

  showSessionSheet.value = false

}



async function startNewSession() {

  try {

    const uid = await ensureChildUser()

    const data = await createQaSession(uid, subject.value)

    qaSessionId.value = data.id

    messages.value = [DEFAULT_GREETING]

    await loadSessionList()

    closeSessionSheet()

  } catch (e) {

    uni.showToast({ title: '新建失败', icon: 'none' })

  }

}



async function switchSession(sessionId) {

  if (sessionId === qaSessionId.value) {

    closeSessionSheet()

    return

  }

  try {

    const uid = await ensureChildUser()

    qaSessionId.value = sessionId

    const data = await fetchQaSession(uid, sessionId)

    messages.value = mapSessionMessages(data, uid)

    closeSessionSheet()

    await nextTick()

    scrollChat()

  } catch (e) {

    uni.showToast({ title: '加载失败', icon: 'none' })

  }

}



function removeSession(sessionId) {

  uni.showModal({

    title: '删除对话',

    content: '确定删除这条对话记录？',

    success: async (res) => {

      if (!res.confirm) return

      try {

        const uid = await ensureChildUser()

        await deleteQaSession(uid, sessionId)

        if (qaSessionId.value === sessionId) {

          qaSessionId.value = null

          messages.value = [DEFAULT_GREETING]

        }

        await loadSessionList()

      } catch (e) {

        uni.showToast({ title: '删除失败', icon: 'none' })

      }

    },

  })

}



function openImageSheet() {

  if (pickingImage.value || loading.value) return

  showImageSheet.value = true

}



function closeImageSheet() {

  showImageSheet.value = false

}



async function onPickSource(source) {

  if (pickingImage.value) return

  closeImageSheet()



  if (needsWebcamCapture(source)) {

    await openWebcam()

    return

  }



  pickingImage.value = true

  try {

    uni.showLoading({ title: source === 'camera' ? '打开相机...' : '打开相册...' })

    const path = await chooseQuestionImage(source)

    uni.hideLoading()

    pendingImage.value = { path, preview: path }

    uni.showToast({ title: '已选图片，点发送提问', icon: 'none' })

  } catch (e) {

    uni.hideLoading()

    if (e.code === 'WEBCAM') {

      await openWebcam()

    } else if (e.message && e.message !== 'cancel') {

      uni.showToast({ title: e.message, icon: 'none', duration: 2500 })

    }

  }

  pickingImage.value = false

}



async function openWebcam() {

  if (!browserCanUseMic()) {

    warnMicBlocked()

    return

  }

  if (!navigator.mediaDevices?.getUserMedia) {

    uni.showToast({ title: '当前浏览器不支持摄像头，请用「从相册选择」', icon: 'none' })

    return

  }

  try {

    webcamStream = await navigator.mediaDevices.getUserMedia({

      video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },

      audio: false,

    })

    showWebcam.value = true

    await nextTick()

    webcamVideoEl = document.getElementById('qaWebcamVideo')

    if (webcamVideoEl) {

      webcamVideoEl.srcObject = webcamStream

      await webcamVideoEl.play().catch(() => {})

    }

  } catch (_) {

    closeWebcam()

    uni.showToast({ title: '摄像头权限被拒，请允许后重试或用相册选图', icon: 'none', duration: 3000 })

  }

}



function closeWebcam() {

  if (webcamStream) {

    webcamStream.getTracks().forEach((t) => t.stop())

    webcamStream = null

  }

  if (webcamVideoEl) {

    webcamVideoEl.srcObject = null

    webcamVideoEl = null

  }

  showWebcam.value = false

}



function captureWebcam() {

  const video = webcamVideoEl || document.getElementById('qaWebcamVideo')

  if (!video || !video.videoWidth) {

    uni.showToast({ title: '摄像头未就绪', icon: 'none' })

    return

  }

  const canvas = document.createElement('canvas')

  canvas.width = video.videoWidth

  canvas.height = video.videoHeight

  canvas.getContext('2d').drawImage(video, 0, 0)

  canvas.toBlob((blob) => {

    if (!blob) return

    const preview = URL.createObjectURL(blob)

    messageBlobUrls.add(preview)

    const file = new File([blob], 'webcam.jpg', { type: 'image/jpeg' })

    pendingImage.value = { file, preview, path: preview }

    closeWebcam()

    uni.showToast({ title: '已拍摄，点发送提问', icon: 'none' })

  }, 'image/jpeg', 0.9)

}



function revokeBlobUrl(url) {

  if (!url?.startsWith('blob:')) return

  try {

    URL.revokeObjectURL(url)

    messageBlobUrls.delete(url)

  } catch (_) { /* ignore */ }

}



function clearPendingImage({ keepPreview } = {}) {

  const preview = pendingImage.value?.preview

  if (preview?.startsWith('blob:') && preview !== keepPreview) {

    revokeBlobUrl(preview)

  }

  pendingImage.value = null

}



async function resolveImageFile(pending) {

  if (pending.file) return pending.file

  const resp = await fetch(pending.path)

  const blob = await resp.blob()

  const ext = blob.type.includes('png') ? 'png' : 'jpg'

  return new File([blob], `photo.${ext}`, { type: blob.type || 'image/jpeg' })

}



const micTouchActive = ref(false)



function onMicTap() {

  if (isMobileH5()) return

  toggleVoiceDesktop()

}



function onMicTouchStart() {

  if (!isMobileH5()) return

  micTouchActive.value = true

  if (voiceMode === 'browser-media') startBrowserRecord()

}



async function onMicTouchEnd() {

  if (!isMobileH5() || !micTouchActive.value) return

  micTouchActive.value = false

  if (voiceMode === 'browser-media' && recording.value) await stopBrowserRecord()

}



function toggleVoiceDesktop() {

  if (recording.value) {

    stopVoice()

    return

  }

  if (!browserCanUseMic()) {

    warnMicBlocked()

    return

  }

  if (voiceMode === 'browser-media') {

    startBrowserRecord()

    return

  }

  if (voiceMode === 'browser-asr' && speechRecognition) {

    try {

      recording.value = true

      speechRecognition.start()

      uni.showToast({ title: '请说话…', icon: 'none' })

    } catch (e) {

      recording.value = false

      uni.showToast({ title: '无法启动语音识别', icon: 'none' })

    }

    return

  }

  if (uniRecorder) {

    recording.value = true

    uniRecorder.start({ duration: 60000, format: 'mp3', sampleRate: 16000, numberOfChannels: 1 })

    uni.showToast({ title: '正在录音，再点结束', icon: 'none' })

    return

  }

  uni.showToast({ title: '当前环境不支持录音', icon: 'none' })

}



function stopVoice() {

  if (voiceMode === 'browser-media' && recording.value) {

    stopBrowserRecord()

    return

  }

  if (voiceMode === 'browser-asr' && speechRecognition) {

    try { speechRecognition.stop() } catch (e) { /* ignore */ }

    recording.value = false

    return

  }

  if (uniRecorder && recording.value) {

    uniRecorder.stop()

  }

}



async function sendMsg() {

  const text = inputText.value.trim() || (pendingImage.value ? '请帮我看这道题' : '')

  if (!text || loading.value) return



  const pending = pendingImage.value

  const displayImageUrl = pending?.preview || null

  if (displayImageUrl?.startsWith('blob:')) {

    messageBlobUrls.add(displayImageUrl)

  }



  const userMsgIdx = messages.value.length

  messages.value.push({ role: 'user', text, imageUrl: displayImageUrl })

  inputText.value = ''

  clearPendingImage({ keepPreview: displayImageUrl })

  loading.value = true

  await nextTick()

  scrollChat()



  try {

    const uid = await ensureChildUser()

    let imageId = null

    if (pending) {

      const file = await resolveImageFile(pending)

      const up = await uploadQaImage(uid, file)

      imageId = up.image_id

      if (up.url && messages.value[userMsgIdx]) {

        const oldUrl = messages.value[userMsgIdx].imageUrl

        messages.value[userMsgIdx].imageUrl = resolveQaImageUrl(up.url, uid)

        if (oldUrl?.startsWith('blob:')) revokeBlobUrl(oldUrl)

      }

    }

    const data = await sendQaMessage(uid, text, qaSessionId.value, {

      subject: subject.value,

      image_id: imageId,

    })

    qaSessionId.value = data.session_id

    coachHint.value = data.coach_hint || ''

    messages.value.push({ role: 'assistant', text: data.reply || '抱歉，AI 暂时无法响应' })

  } catch (e) {

    const errText = e?.message || '请求失败，请稍后再试'

    messages.value.push({ role: 'assistant', text: `出错了：${errText}` })

  }

  loading.value = false

  await nextTick()

  scrollChat()

}



function scrollChat() {

  const el = document.getElementById('chatScroll')

  if (el) el.scrollTop = el.scrollHeight

}



onMounted(async () => {

  try { localStorage.removeItem('jnao_learner_profile_set') } catch (_) {}

  isDesktop.value = !isMobileH5()

  if (QA_VOICE_ENABLED) {

    if (isWebH5()) {

      voiceMode = 'browser-media'

    } else if (initUniRecorder()) {

      voiceMode = 'uni-recorder'

    } else if (initBrowserSpeech()) {

      voiceMode = 'browser-asr'

    }

    const probe = await probeMicrophoneAccess()

    micBlockedHint.value = probe || buildMicAccessHint()

  }

  loadSession()

})



onBeforeUnmount(() => {

  stopVoice()

  browserRecorder?.cancel()

  closeWebcam()

  messageBlobUrls.forEach((url) => revokeBlobUrl(url))

  clearPendingImage()

})

</script>



<style scoped>

.qa-app {

  height: 100vh;

  max-width: 768px;

  margin: 0 auto;

  background: var(--bg);

  font-family: -apple-system, "PingFang SC", "Segoe UI", sans-serif;

  display: flex;

  flex-direction: column;

  color: var(--text);

}



.qa-header {

  display: flex;

  align-items: center;

  padding: 12px 16px;

  background: var(--bg-card);

  border-bottom: 1px solid var(--border);

  flex-shrink: 0;

}

.nav-back {

  width: 36px;

  height: 36px;

  border-radius: 10px;

  display: flex;

  align-items: center;

  justify-content: center;

  cursor: pointer;

  color: #6b7280;

}

.nav-back:active { background: #f3f4f6; }

.nav-title { flex: 1; text-align: center; font-size: 16px; font-weight: 600; color: var(--text); }

.nav-spacer { width: 36px; }
.nav-history { padding: 6px 12px; border-radius: 999px; background: var(--accent-bg); border: 1px solid rgba(88,166,255,0.2); cursor: pointer; }
.nav-history text { color: var(--accent); font-size: 13px; font-weight: 600; }
.session-panel { max-height: 70vh; }
.session-new { text-align: center; padding: 10px; margin-bottom: 8px; border: 1px dashed var(--border); border-radius: 10px; cursor: pointer; }
.session-new text { color: var(--accent); font-size: 13px; font-weight: 600; }
.session-list { max-height: 45vh; }
.session-row { display: flex; align-items: center; gap: 8px; padding: 10px 8px; border-bottom: 1px solid var(--border); cursor: pointer; }
.session-row.active { background: var(--accent-bg); border-radius: 8px; }
.session-info { flex: 1; min-width: 0; }
.session-title { color: var(--text); font-size: 13px; font-weight: 600; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.session-meta { color: var(--text-dim); font-size: 11px; display: block; margin-top: 2px; }
.session-del { color: #f85149; font-size: 14px; padding: 0 4px; flex-shrink: 0; }
.session-empty { color: var(--text-dim); font-size: 12px; text-align: center; padding: 16px 0; display: block; }



.subject-bar {

  display: flex;

  gap: 8px;

  padding: 10px 16px 12px;

  background: var(--bg-card);

  border-bottom: 1px solid var(--border);

  flex-shrink: 0;

  overflow-x: auto;

}

.subject-chip {

  padding: 8px 16px;

  border-radius: 999px;

  border: 1px solid var(--border);

  background: var(--bg-input);

  cursor: pointer;

  flex-shrink: 0;

  transition: all 0.18s cubic-bezier(0.22,0.61,0.36,1);

}

.subject-chip text { font-size: 13px; color: var(--text-dim); font-weight: 500; }

.subject-chip.active {

  border-color: var(--accent);

  background: var(--accent-bg);

  box-shadow: 0 2px 8px var(--mic-shadow);

}

.subject-chip.active text { color: var(--accent); font-weight: 600; }



.chat-scroll {

  flex: 1;

  overflow-y: auto;

  padding: 16px;

  background: var(--chat-surface);

  scrollbar-width: none;

}

.chat-scroll::-webkit-scrollbar { display: none; }



.empty-hint {

  text-align: center;

  padding: 32px 20px 24px;

}

.empty-icon { font-size: 36px; margin-bottom: 12px; }

.empty-title { display: block; font-size: 18px; font-weight: 600; color: #1a1a2e; margin-bottom: 8px; }

.empty-desc { display: block; font-size: 13px; color: #6b7280; line-height: 1.6; max-width: 280px; margin: 0 auto; }



.msg-row {

  display: flex;

  gap: 12px;

  margin-bottom: 20px;

  align-items: flex-start;

  max-width: 100%;

}

.msg-user { justify-content: flex-end; }

.msg-ai { justify-content: flex-start; }



.msg-avatar {

  width: 36px;

  height: 36px;

  border-radius: 50%;

  flex-shrink: 0;

  display: flex;

  align-items: center;

  justify-content: center;

  overflow: hidden;

}

.msg-avatar.ai {

  border: 2px solid var(--border);

  box-shadow: var(--bubble-shadow);

}

.avatar-img { width: 100%; height: 100%; object-fit: cover; }

.msg-avatar.user {

  background: var(--accent-bg);

  color: var(--accent);

  font-size: 12px;

  font-weight: 700;

  border: 1px solid var(--border);

}



.msg-body {

  max-width: 78%;

  min-width: 0;

}

.msg-ai .msg-body { flex: 1; max-width: calc(100% - 44px); }



.bubble-user {

  background: linear-gradient(135deg, var(--accent), #3b82f6);

  color: #fff;

  border-radius: 18px;

  border-bottom-right-radius: 6px;

  padding: 11px 14px;

  font-size: 14px;

  line-height: 1.65;

  box-shadow: var(--bubble-shadow);

  word-break: break-word;

}

.bubble-user .bubble-text { color: #fff; white-space: pre-wrap; }

.bubble-sender {

  display: block;

  font-size: 11px;

  color: var(--text-dim);

  margin-bottom: 4px;

  font-weight: 500;

}

.bubble-ai {

  background: var(--chat-ai-bg);

  border: 1px solid rgba(88,166,255,0.12);

  border-radius: 18px;

  border-bottom-left-radius: 6px;

  padding: 10px 14px;

  font-size: 14px;

  line-height: 1.7;

  color: var(--text);

  word-break: break-word;

  box-shadow: var(--bubble-shadow);

}

.bubble-ai .bubble-text { white-space: pre-wrap; color: var(--text); }



.bubble-img {

  width: 100%;

  max-width: 220px;

  border-radius: 10px;

  margin-bottom: 6px;

  display: block;

  background: rgba(255, 255, 255, 0.15);

  cursor: pointer;

}



.img-preview-mask {

  position: fixed;

  inset: 0;

  z-index: 2000;

  background: rgba(0, 0, 0, 0.85);

  display: flex;

  flex-direction: column;

  align-items: center;

  justify-content: center;

  padding: 24px;

}

.img-preview-full {

  max-width: 100%;

  max-height: 80vh;

  border-radius: 8px;

}

.img-preview-hint {

  margin-top: 16px;

  font-size: 13px;

  color: rgba(255, 255, 255, 0.6);

}



.typing-wrap { padding: 4px 0; }

.typing-dots {

  color: #9ca3af;

  font-size: 14px;

  animation: pulse 1.2s ease-in-out infinite;

}

@keyframes pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 1; } }



.coach-hint {

  display: block;

  font-size: 12px;

  color: #6b7280;

  background: #f9fafb;

  border: 1px solid #e5e7eb;

  border-radius: 12px;

  padding: 10px 12px;

  line-height: 1.5;

  margin-top: 4px;

}



.composer {

  flex-shrink: 0;

  padding: 12px 16px calc(12px + env(safe-area-inset-bottom));

  background: var(--bg-card);

  border-top: 1px solid var(--border);

  box-shadow: 0 -4px 20px rgba(0,0,0,0.04);

}



.mic-hint-bar {

  display: flex;

  align-items: flex-start;

  gap: 8px;

  margin-bottom: 10px;

  padding: 10px 12px;

  background: #fffbeb;

  border: 1px solid #fde68a;

  border-radius: 12px;

}

.mic-hint-bar.ok {

  background: #eff6ff;

  border-color: #bfdbfe;

}

.mic-hint-bar.ok .mic-hint-text { color: #1d4ed8; }



.mic-hint-text { flex: 1; font-size: 12px; color: #92400e; line-height: 1.5; }

.mic-hint-close {

  width: 22px; height: 22px; border-radius: 6px;

  display: flex; align-items: center; justify-content: center; flex-shrink: 0;

}

.mic-hint-close text { font-size: 11px; color: #b45309; }



.pending-bar {

  display: flex;

  align-items: center;

  gap: 10px;

  margin-bottom: 10px;

  padding: 8px 10px;

  background: #fff;

  border: 1px solid #e5e7eb;

  border-radius: 12px;

}

.pending-thumb { width: 44px; height: 44px; border-radius: 8px; object-fit: cover; }

.pending-label { flex: 1; font-size: 13px; color: #6b7280; }

.pending-clear {

  width: 28px; height: 28px; border-radius: 8px;

  background: #fef2f2; display: flex; align-items: center; justify-content: center; cursor: pointer;

}

.pending-clear text { color: #ef4444; font-size: 12px; }



.input-box {

  display: flex;

  flex-direction: column;

  gap: 8px;

  background: var(--bg-card);

  border: 1px solid var(--border);

  border-radius: 20px;

  padding: 12px 14px;

  box-shadow: var(--bubble-shadow);

  transition: border-color 0.2s, box-shadow 0.2s;

}

.input-box.focused {

  border-color: var(--accent);

  box-shadow: 0 2px 16px var(--mic-shadow);

}



.chat-input {

  width: 100%;

  border: none;

  outline: none;

  font-size: 15px;

  line-height: 1.5;

  color: var(--text);

  background: transparent;

  min-height: 24px;

}

.chat-input::placeholder { color: var(--text-hint); }



.input-actions {

  display: flex;

  align-items: center;

  gap: 6px;

  justify-content: flex-end;

}

.act-btn {

  width: 34px; height: 34px; border-radius: 10px;

  display: flex; align-items: center; justify-content: center;

  cursor: pointer; transition: background 0.15s;

}

.act-btn:active { background: #f3f4f6; }

.act-btn.recording { background: #fef2f2; animation: recPulse 1s infinite; }

@keyframes recPulse { 50% { opacity: 0.6; } }

.act-icon { font-size: 18px; line-height: 1; }



.send-btn {

  padding: 8px 16px;

  border-radius: 12px;

  background: #2563eb;

  cursor: pointer;

  margin-left: 4px;

  transition: opacity 0.15s;

}

.send-btn text { color: #fff; font-size: 14px; font-weight: 500; }

.send-btn.disabled { opacity: 0.45; pointer-events: none; }

.send-btn:active:not(.disabled) { background: #1d4ed8; }



.sheet-mask {

  position: fixed; inset: 0; z-index: 1000;

  background: rgba(0, 0, 0, 0.45);

  display: flex; align-items: flex-end; justify-content: center;

}

.sheet-panel {

  width: 100%; max-width: 768px; background: #fff;

  border-radius: 20px 20px 0 0;

  padding: 20px 16px calc(16px + env(safe-area-inset-bottom));

  animation: sheetUp 0.25s ease-out;

}

@keyframes sheetUp { from { transform: translateY(100%); } to { transform: translateY(0); } }

.sheet-title { display: block; text-align: center; font-size: 15px; font-weight: 600; margin-bottom: 16px; }

.sheet-options { display: flex; gap: 12px; margin-bottom: 12px; }

.sheet-card {

  flex: 1; background: #f9fafb; border: 1.5px solid #e5e7eb;

  border-radius: 16px; padding: 20px 12px; text-align: center;

  display: flex; flex-direction: column; align-items: center; gap: 6px;

}

.sheet-card:active { border-color: #2563eb; background: rgba(37, 99, 235, 0.06); }

.sheet-card-icon { font-size: 32px; }

.sheet-card-label { font-size: 15px; font-weight: 600; }

.sheet-card-desc { font-size: 11px; color: #6b7280; }

.sheet-cancel { margin-top: 4px; padding: 14px; text-align: center; border-radius: 12px; background: #f3f4f6; }

.sheet-cancel text { font-size: 15px; color: #6b7280; }



.webcam-panel {

  width: 100%; max-width: 768px; background: #fff;

  border-radius: 20px 20px 0 0;

  padding: 16px 16px calc(16px + env(safe-area-inset-bottom));

  animation: sheetUp 0.25s ease-out;

}

.webcam-title { display: block; text-align: center; font-size: 14px; font-weight: 600; margin-bottom: 12px; }

.webcam-video-wrap { width: 100%; aspect-ratio: 4/3; background: #000; border-radius: 12px; overflow: hidden; }

.webcam-video { width: 100%; height: 100%; object-fit: cover; display: block; }

.webcam-actions { display: flex; gap: 12px; margin-top: 14px; }

.webcam-btn { flex: 1; padding: 14px; border-radius: 12px; text-align: center; }

.webcam-btn.cancel { background: #f3f4f6; }

.webcam-btn.cancel text { color: #6b7280; font-size: 15px; }

.webcam-btn.shoot { background: #2563eb; }

.webcam-btn.shoot text { color: #fff; font-size: 15px; font-weight: 600; }

</style>


