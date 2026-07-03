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

        <view style="display:flex;align-items:center;gap:5px;"><view v-html="subjectIcon[s]" style="display:flex;align-items:center;"></view><text>{{ s }}</text></view>

      </view>

    </view>



    <view class="chat-scroll" id="chatScroll">




      <view

        v-for="(m, i) in messages"

        :key="i"

        class="msg-row"

        :class="m.role === 'user' ? 'msg-user' : 'msg-ai'"

      >

        <view v-if="m.role !== 'user'" class="msg-avatar ai">

          <img class="avatar-img" src="/static/teacher-avatar.png" alt="张宇老师" />

        </view>

        <view class="msg-body">

          <view v-if="m.role === 'user'" class="bubble-user bubble-user-tail">

            <img
              v-if="m.imageUrl"
              :src="m.imageUrl"
              class="bubble-img"
              loading="lazy"
              @click.stop="previewMessageImage(i)"
              @error="onMsgImageError(i)"
            />

            <text v-if="m.text && !(m.imageUrl && m.text === '请帮我看这道题')" class="bubble-text">{{ m.text }}</text>

          </view>

          <view v-else class="bubble-ai bubble-ai-tail">

            <text class="bubble-sender">张宇老师</text>

            <text class="bubble-text">{{ m.text }}</text>

          </view>

        </view>

        <view v-if="m.role === 'user'" class="msg-user-label">

          <text>{{ userDisplayName }}</text>

        </view>

      </view>



      <view v-if="loading" class="msg-row msg-ai">

        <view class="msg-avatar ai">

          <img class="avatar-img" src="/static/teacher-avatar.png" alt="张宇老师" />

        </view>

        <view class="msg-body">

          <view class="bubble-ai bubble-ai-tail typing-wrap">

            <text class="typing-dots">思考中</text>

          </view>

        </view>

      </view>

    </view>



    <view class="composer">

      <view v-if="pendingImage" class="pending-bubble-wrap">
        <view class="pending-bubble">
          <img
            :src="pendingImage.preview"
            class="pending-thumb"
            @click="previewImage(pendingImage.preview)"
          />
          <view class="pending-clear" @tap="clearPendingImage()"><text>✕</text></view>
        </view>
      </view>

      <view class="input-panel">

        <view class="input-wrap">

          <input

            class="chat-input"

            v-model="inputText"

            placeholder="输入问题，也可拍照发题…"

            :disabled="loading"

            @confirm="sendMsg"

          />

          <view class="input-btns">

            <view class="btn-camera" @tap="openImageSheet">

              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--text-dim)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="7" width="18" height="13" rx="3"/><circle cx="12" cy="13.5" r="3.5"/><circle cx="8" cy="9" r="1" fill="var(--text-dim)" stroke="none"/></svg>

            </view>

            <view class="btn-send" :class="{ disabled: !canSend }" @tap="sendMsg">

              <text style="color:#fff;font-size:14px;">➤</text>

            </view>

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

            <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="#374151" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="7" width="18" height="13" rx="3"/><circle cx="12" cy="13.5" r="3.5"/></svg>

            <text class="sheet-card-label">拍照</text>


          </view>

          <view class="sheet-card" @tap="onPickSource('album')">

            <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="#374151" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>

            <text class="sheet-card-label">从相册选择</text>


          </view>

        </view>

        <view class="sheet-cancel" @tap="closeImageSheet"><text>取消</text></view>

      </view>

    </view>



    <view v-if="showWebcam" class="camera-fullscreen">
      <view class="camera-top">
        <view class="camera-close" @tap="closeWebcam">
          <text>✕</text>
        </view>
        <text class="camera-hint">对准题目，点击底部按钮拍摄</text>
      </view>
      <video id="qaWebcamVideo" class="camera-video" autoplay playsinline muted></video>
      <view class="camera-bottom">
        <view class="camera-album" @tap="pickAlbumFromCamera"><text>相册</text></view>
        <view class="camera-shutter" @tap="captureWebcam">
          <view class="camera-shutter-inner"></view>
        </view>
        <view class="camera-album-spacer"></view>
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

    <view v-if="deleteTargetId" class="delete-confirm-mask" @tap="cancelDeleteSession">
      <view class="delete-confirm-card" @tap.stop>
        <text class="delete-confirm-title">删除对话</text>
        <text class="delete-confirm-desc">确定删除这条对话记录？删除后无法恢复。</text>
        <view class="delete-confirm-actions">
          <view class="delete-btn cancel" @tap="cancelDeleteSession"><text>取消</text></view>
          <view class="delete-btn danger" @tap="confirmDeleteSession"><text>{{ deleteSubmitting ? '删除中...' : '删除' }}</text></view>
        </view>
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

  resolveMessageImageDisplay,

  sendQaMessageStream,

  uploadQaImage,

  transcribeVoice,

  transcribeVoicePath,

  updateLearnerProfile,

  fetchProfile,

  gradeToSchoolStage,

} from '@/utils/userApi.js'

import {
  chooseQuestionImage,
  needsWebcamCapture,
  isMobileH5,
  compressImage,
  buildPendingImageFromPath,
  browserCanUseCamera,
  pickImageViaNativeInput,
  fileToDataUrl,
  putQaImageLocal,
  parseQaImageId,
  getQaImageLocal,
} from '@/utils/qaMedia.js'

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
const subjectIcon = {
  数学: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="20" x2="20" y2="20"/><path d="M6 4l6 14"/><path d="M18 4l-6 14"/></svg>',
  语文: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7V4h16v3"/><path d="M9 20h6"/><path d="M12 4v16"/></svg>',
  英语: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
  科学: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
}

const subject = ref('数学')

const userDisplayName = ref('我')

const inputText = ref('')

const inputFocused = ref(false)

const loading = ref(false)

const qaSessionId = ref(null)

const pendingImage = ref(null)

const recording = ref(false)

const showImageSheet = ref(false)

const pickingImage = ref(false)

const showWebcam = ref(false)

const showSessionSheet = ref(false)

const sessionList = ref([])

const deleteTargetId = ref(null)

const deleteSubmitting = ref(false)

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

  { role: 'assistant', text: '你好！我是张宇老师 ✨ 可以拍照发题或打字提问～我会根据你的天赋特点来辅导～' },

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

function onMsgImageError(msgIndex) {
  const m = messages.value[msgIndex]
  if (!m) return
  if (m.imageId) {
    const cached = getQaImageLocal(m.imageId)
    if (cached && m.imageUrl !== cached) {
      m.imageUrl = cached
      return
    }
  }
  if (m.serverImageUrl && m.imageUrl !== m.serverImageUrl) {
    m.imageUrl = m.serverImageUrl
    return
  }
  if (!m.text || m.text === '请帮我看这道题') {
    m.text = '📷 题目图片（点击查看原图）'
  }
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

    const grade = profile.profile_json?.grade || profile.profile_json?.learner?.grade

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



const DEFAULT_GREETING = { role: 'assistant', text: '你好！我是张宇老师 ✨ 可以拍照发题或打字提问～我会根据你的天赋特点来辅导～' }



function mapSessionMessages(data, uid) {

  if (!data.messages?.length) return [DEFAULT_GREETING]

  return data.messages.map(m => ({

    role: m.role === 'user' ? 'user' : 'assistant',

    text: m.content,

    imageUrl: resolveMessageImageDisplay(m.image_url, uid) || null,

    imageId: parseQaImageId(m.image_url),

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

    // profile + sessionList 并行（互不依赖）
    const [profile] = await Promise.all([
      fetchProfile(uid),
      loadSessionList(),
    ])
    await ensureLearnerProfile(uid, profile)
    if (profile.nickname && profile.nickname !== '学员') {
      userDisplayName.value = profile.nickname
    }

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

    if (qaSessionId.value === sessionId) {

      qaSessionId.value = null

      messages.value = [DEFAULT_GREETING]

    }

    deleteTargetId.value = null

    await loadSessionList()

    if (!sessionList.value.length) closeSessionSheet()

    uni.showToast({ title: '已删除', icon: 'none' })

  } catch (e) {

    uni.showToast({ title: e.message || '删除失败', icon: 'none' })

  }

  deleteSubmitting.value = false

}



function openImageSheet() {
  if (pickingImage.value || loading.value) return
  // 手机 H5：点相机直接进入全屏拍照（DeepSeek 式）
  if (isWebH5() && isMobileH5()) {
    openWebcam()
    return
  }
  showImageSheet.value = true
}

async function pickAlbumFromCamera() {
  closeWebcam()
  pickingImage.value = true
  try {
    uni.showLoading({ title: '打开相册...' })
    const path = await chooseQuestionImage('album')
    uni.hideLoading()
    await setPendingFromPick(path)
    uni.showToast({ title: '已选图片，点发送提问', icon: 'none' })
  } catch (e) {
    uni.hideLoading()
    if (e.message && e.message !== 'cancel') {
      uni.showToast({ title: e.message, icon: 'none', duration: 2500 })
    }
  }
  pickingImage.value = false
}



function closeImageSheet() {

  showImageSheet.value = false

}



function trackPendingPreview(preview) {
  if (preview?.startsWith('blob:')) messageBlobUrls.add(preview)
}

async function setPendingFromPick(path) {
  if (isWebH5()) {
    try {
      const pending = await buildPendingImageFromPath(path)
      trackPendingPreview(pending.preview)
      pendingImage.value = pending
      return
    } catch (_) { /* fallback to raw path */ }
  }
  pendingImage.value = { path, preview: path }
}

async function setPendingFromNativePick(captureMode = 'environment') {
  const pending = await pickImageViaNativeInput(captureMode)
  trackPendingPreview(pending.preview)
  pendingImage.value = pending
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
    await setPendingFromPick(path)
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
  if (!browserCanUseCamera()) {
    try {
      await setPendingFromNativePick('environment')
      uni.showToast({ title: '已选图片，点发送提问', icon: 'none' })
    } catch (e) {
      if (e.message !== 'cancel') {
        uni.showToast({ title: '无法打开相机，请用相册选图', icon: 'none', duration: 3000 })
      }
    }
    return
  }
  try {
    webcamStream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: 'environment' },
        width: { ideal: 1920 },
        height: { ideal: 1080 },
      },
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
    try {
      await setPendingFromNativePick('environment')
      uni.showToast({ title: '已选图片，点发送提问', icon: 'none' })
    } catch (e) {
      if (e.message !== 'cancel') {
        uni.showToast({ title: '摄像头权限被拒，请允许后重试或用相册选图', icon: 'none', duration: 3000 })
      }
    }
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
  if (!resp.ok) throw new Error('读取图片失败，请重新选择')
  const blob = await resp.blob()
  if (!blob.size) throw new Error('图片为空，请重新拍摄')
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

  let displayImageUrl = pending?.preview || null

  if (pending) {
    try {
      const rawFile = await resolveImageFile(pending)
      displayImageUrl = await fileToDataUrl(rawFile)
    } catch (_) { /* keep blob preview */ }
  }

  if (displayImageUrl?.startsWith('blob:')) {
    messageBlobUrls.add(displayImageUrl)
  }

  const userMsgIdx = messages.value.length

  messages.value.push({ role: 'user', text, imageUrl: displayImageUrl })

  inputText.value = ''

  clearPendingImage({ keepPreview: displayImageUrl?.startsWith('blob:') ? displayImageUrl : null })

  loading.value = true

  await nextTick()

  scrollChat()



  try {

    const uid = await ensureChildUser()

    let imageId = null

    if (pending) {

      const rawFile = await resolveImageFile(pending)
      const file = await compressImage(rawFile)

      const up = await uploadQaImage(uid, file)

      imageId = up.image_id

      if (up.url && messages.value[userMsgIdx]) {
        messages.value[userMsgIdx].serverImageUrl = resolveQaImageUrl(up.url, uid)
        messages.value[userMsgIdx].imageId = imageId
        if (displayImageUrl?.startsWith('data:')) {
          putQaImageLocal(imageId, displayImageUrl)
        }
      }

    }

    const aiIdx = messages.value.length
    messages.value.push({ role: 'assistant', text: '' })
    loading.value = false
    await nextTick()
    scrollChat()

    await sendQaMessageStream(uid, text, qaSessionId.value, {
      subject: subject.value,
      image_id: imageId,
    }, {
      onToken(chunk) {
        messages.value[aiIdx].text += chunk
        scrollChat()
      },
      onDone(data) {
        qaSessionId.value = data.session_id
        if (data.reply) messages.value[aiIdx].text = data.reply
      },
    })

  } catch (e) {

    const errText = e?.message || '请求失败，请稍后再试'

    if (messages.value.length && messages.value[messages.value.length - 1].role === 'assistant' && !messages.value[messages.value.length - 1].text) {
      messages.value[messages.value.length - 1].text = `出错了：${errText}`
    } else {
      messages.value.push({ role: 'assistant', text: `出错了：${errText}` })
    }

  } finally {
    loading.value = false
  }

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

  height: 100vh; height: 100dvh;

  max-width: var(--app-max-width, 480px);

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

  padding: 24rpx 32rpx;

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
.session-panel { max-height:70vh; max-height:70dvh; }
.session-new { text-align: center; padding: 10px; margin-bottom: 8px; border: 1px dashed var(--border); border-radius: 10px; cursor: pointer; }
.session-new text { color: var(--accent); font-size: 13px; font-weight: 600; }
.session-list { max-height:45vh; max-height:45dvh; }
.session-row { display: flex; align-items: center; gap: 8px; padding: 10px 8px; border-bottom: 1px solid var(--border); cursor: pointer; }
.session-row.active { background: var(--accent-bg); border-radius: 8px; }
.session-info { flex: 1; min-width: 0; }
.session-title { color: var(--text); font-size: 13px; font-weight: 600; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.session-meta { color: var(--text-dim); font-size: 11px; display: block; margin-top: 2px; }
.session-del { color: #f85149; font-size: 14px; padding: 0 4px; flex-shrink: 0; }
.session-empty { color: var(--text-dim); font-size: 12px; text-align: center; padding: 16px 0; display: block; }

.delete-confirm-mask {
  position: fixed;
  inset: 0;
  z-index: 1100;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.delete-confirm-card {
  width: 100%;
  max-width: 300px;
  background: var(--bg-card);
  border-radius: 16px;
  padding: 20px 18px 16px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.18);
}

.delete-confirm-title { color: var(--text); font-size: 16px; font-weight: 700; display: block; text-align: center; margin-bottom: 8px; }

.delete-confirm-desc { color: var(--text-dim); font-size: 13px; line-height: 1.5; display: block; text-align: center; margin-bottom: 18px; }

.delete-confirm-actions { display: flex; gap: 10px; }

.delete-btn { flex: 1; padding: 11px 0; border-radius: 10px; text-align: center; cursor: pointer; }

.delete-btn.cancel { background: var(--bg-input); border: 1px solid var(--border); }

.delete-btn.cancel text { color: var(--text-dim); font-size: 14px; }

.delete-btn.danger { background: #ef4444; }

.delete-btn.danger text { color: #fff; font-size: 14px; font-weight: 600; }



.subject-bar {

  display: flex;

  gap: 16rpx;

  padding: 20rpx 32rpx 24rpx;

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

.subject-chip { color: var(--text-dim); }
.subject-chip text { font-size: 13px; font-weight: 500; }

.subject-chip.active {

  border-color: var(--accent);

  background: var(--accent-bg);

  box-shadow: 0 2px 8px var(--mic-shadow);

}

.subject-chip.active { color: var(--accent); }
.subject-chip.active text { font-weight: 600; }



.chat-scroll {

  flex: 1;

  overflow-y: auto;

  padding: 32rpx;

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

  gap: 20rpx;

  margin-bottom: 40rpx;

  align-items: flex-end;

  max-width: 100%;

}

.msg-user { flex-direction: row-reverse; justify-content: flex-start; }

.msg-ai { justify-content: flex-start; }



.msg-avatar {

  width: 40px;

  height: 40px;

  border-radius: 10px;

  flex-shrink: 0;

  display: flex;

  align-items: center;

  justify-content: center;

  overflow: hidden;

}

.msg-avatar.ai {

  border: 1px solid var(--border);

  box-shadow: var(--bubble-shadow);

}

.avatar-img { width: 100%; height: 100%; object-fit: cover; display: block; }



.msg-user-label {

  flex-shrink: 0;

  max-width: 56px;

  text-align: center;

}

.msg-user-label text {

  font-size: 11px;

  color: var(--text-dim);

  line-height: 1.2;

  word-break: break-all;

}



.msg-body {

  max-width: calc(100% - 108px);

  min-width: 0;

}

.msg-ai .msg-body { max-width: calc(100% - 56px); }



.bubble-user {
  position: relative;
  background: var(--accent);
  color: #fff;
  border-radius: 32rpx;
  border-bottom-right-radius: 8rpx;
  padding: 20rpx 28rpx;
  font-size: 28rpx;
  line-height: 1.55;
  word-break: break-word;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25);
}
.bubble-user-tail::after {
  content: '';
  position: absolute;
  right: -6px;
  bottom: 10px;
  border-top: 6px solid transparent;
  border-bottom: 6px solid transparent;
  border-left: 8px solid var(--accent);
}
.bubble-user .bubble-text { color: #fff; white-space: pre-wrap; }
.bubble-sender {
  display: block;
  font-size: 12px;
  color: var(--text-dim);
  margin-bottom: 4px;
  font-weight: 600;
}
.bubble-ai {
  position: relative;
  background: var(--chat-ai-bg);
  border-radius: 32rpx;
  border-bottom-left-radius: 8rpx;
  padding: 20rpx 28rpx;
  font-size: 28rpx;
  line-height: 1.55;
  color: var(--text);
  word-break: break-word;
}
.bubble-ai-tail::before {
  content: '';
  position: absolute;
  left: -6px;
  bottom: 10px;
  border-top: 6px solid transparent;
  border-bottom: 6px solid transparent;
  border-right: 8px solid var(--chat-ai-bg);
}
.bubble-ai .bubble-text { white-space: pre-wrap; color: var(--text); }



.bubble-img {
  width: auto;
  max-width: 400rpx;
  min-width: 160rpx;
  height: auto;
  max-height: 480rpx;
  border-radius: 20rpx;
  margin-bottom: 12rpx;
  display: block;
  object-fit: contain;
  background: rgba(255, 255, 255, 0.08);
  cursor: pointer;
}

/* 待发送预览：右对齐气泡，尾巴向下指向输入框 */
.pending-bubble-wrap {
  display: flex;
  justify-content: flex-end;
  padding: 0 14px 12px;
}
.pending-bubble {
  position: relative;
  max-width: 400rpx;
  background: var(--accent);
  border-radius: 16px;
  border-bottom-right-radius: 4px;
  padding: 6px;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25);
}
.pending-bubble::after {
  content: '';
  position: absolute;
  right: -6px;
  bottom: 10px;
  border-top: 6px solid transparent;
  border-bottom: 6px solid transparent;
  border-left: 8px solid var(--accent);
}
.pending-thumb {
  width: 100%;
  max-width: 360rpx;
  max-height: 280rpx;
  border-radius: 20rpx;
  display: block;
  object-fit: cover;
}
.pending-clear {
  position: absolute;
  top: -8px;
  right: -8px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
}
.pending-clear text { color: #fff; font-size: 12px; line-height: 1; }



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

  max-height:80vh; max-height:80dvh;

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



.composer {
  flex-shrink: 0;
  padding: 20rpx 28rpx calc(20rpx + env(safe-area-inset-bottom));
  background: var(--bg-card);
  border-top: 1px solid var(--border);
}
.input-panel { }
.input-wrap {
  display: flex; align-items: center;
  background: rgba(255,255,255,0.1);
  border-radius: 48rpx; padding: 2px 2px 2px 28rpx;
  border: 1px solid rgba(255,255,255,0.15);
}
[data-theme="white"] .input-wrap { background: #f3f4f6; border-color: #d1d5db; }
.input-wrap .chat-input {
  flex: 1; background: transparent; border: none; outline: none;
  font-size: 14px; color: var(--text); height: 36px; line-height: 36px;
}
.input-wrap .chat-input::placeholder { color: var(--text-hint); }
.input-btns { display: flex; align-items: center; gap: 2px; flex-shrink: 0; }
.btn-camera {
  width: 34px; height: 34px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; opacity: 0.7;
}
.btn-camera:active { opacity: 1; background: rgba(255,255,255,0.1); }
.btn-send {
  width: 34px; height: 34px; border-radius: 50%;
  background: var(--accent);
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; flex-shrink: 0;
}
.btn-send.disabled { opacity: 0.45; pointer-events: none; }
.btn-send:active:not(.disabled) { opacity: 0.8; }

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

.sheet-card-icon { font-size: 32px; display: flex; align-items: center; justify-content: center; }

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

/* DeepSeek 式全屏拍照 */
.camera-fullscreen {
  position: fixed;
  inset: 0;
  z-index: 1200;
  background: #000;
  display: flex;
  flex-direction: column;
}
.camera-top {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: calc(12px + env(safe-area-inset-top)) 16px 12px;
  background: linear-gradient(180deg, rgba(0,0,0,0.55) 0%, transparent 100%);
}
.camera-close {
  position: absolute;
  left: 16px;
  top: calc(12px + env(safe-area-inset-top));
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(255,255,255,0.15);
  display: flex;
  align-items: center;
  justify-content: center;
}
.camera-close text { color: #fff; font-size: 18px; }
.camera-hint { color: #fff; font-size: 14px; font-weight: 500; }
.camera-video {
  flex: 1;
  width: 100%;
  height: 100%;
  object-fit: cover;
  background: #000;
}
.camera-bottom {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 32px calc(28px + env(safe-area-inset-bottom));
  background: linear-gradient(0deg, rgba(0,0,0,0.55) 0%, transparent 100%);
}
.camera-album {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  background: rgba(255,255,255,0.12);
  display: flex;
  align-items: center;
  justify-content: center;
}
.camera-album text { color: #fff; font-size: 13px; }
.camera-album-spacer { width: 56px; height: 56px; }
.camera-shutter {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  border: 4px solid rgba(255,255,255,0.9);
  display: flex;
  align-items: center;
  justify-content: center;
}
.camera-shutter:active { opacity: 0.85; transform: scale(0.96); }
.camera-shutter-inner {
  width: 58px;
  height: 58px;
  border-radius: 50%;
  background: #fff;
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


