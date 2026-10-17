<template>
  <view class="chatdemo" :class="{ page: asPage }">
    <view v-if="asPage" class="nav">
      <view class="nav-back" @click="goBack"><text>‹</text></view>
      <text class="nav-title">对话大宇 · 就现在</text>
      <view class="nav-spacer" />
    </view>
    <view v-else class="cd-h">对话大宇 · 就现在</view>

    <scroll-view
      class="cd-thread"
      scroll-y
      :scroll-into-view="scrollInto"
      :show-scrollbar="false"
    >
      <view v-if="bootError" class="cd-banner err">{{ bootError }}</view>
      <view v-else-if="loading" class="cd-banner">正在打开这份报告的对话…</view>
      <template v-else>
        <view id="msg-open" class="cd-b ai">
          <text><text class="cd-name">大宇：</text>{{ opening }}</text>
        </view>
        <view
          v-for="m in messages"
          :id="'msg-' + m.id"
          :key="m.id"
          class="cd-b"
          :class="m.role === 'user' ? 'me' : 'ai'"
        >
          <text v-if="m.role === 'user'">{{ m.content }}</text>
          <text v-else><text class="cd-name">大宇：</text>{{ m.content }}</text>
        </view>
        <view v-if="sending" class="cd-banner soft">大宇正在查阅…</view>
        <view id="msg-end" class="cd-tail" />
      </template>
    </scroll-view>

    <view class="cd-form">
      <input
        class="cd-field"
        v-model="draft"
        :disabled="!canSend"
        maxlength="2000"
        confirm-type="send"
        placeholder="问问大宇任何问题…"
        @confirm="onSend"
      />
      <view
        class="cd-send"
        :class="{ on: canSend && draft.trim() && !sending }"
        @click="onSend"
      >
        <text>发送 ↑</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import {
  ensureReportUser,
  fetchReportTalentChat,
  sendReportTalentChat,
} from '@/utils/userApi.js'

const props = defineProps({
  assessmentId: { type: [Number, String], default: 0 },
  asPage: { type: Boolean, default: false },
})

const OPENING_FALLBACK =
  '您好我是你的天赋解答助手，有什么疑问都可以通过对话框向我提问，我会为您解答。'

const opening = ref(OPENING_FALLBACK)
const messages = ref([])
const draft = ref('')
const loading = ref(true)
const sending = ref(false)
const bootError = ref('')
const scrollInto = ref('msg-open')
let userId = 0

const aid = computed(() => parseInt(props.assessmentId, 10) || 0)
const canSend = computed(() => !!aid.value && !loading.value && !bootError.value)

function goBack() {
  uni.navigateBack({ fail: () => uni.redirectTo({ url: '/pages/report/index' }) })
}

function bumpScroll(id) {
  nextTick(() => {
    scrollInto.value = ''
    nextTick(() => {
      scrollInto.value = id
    })
  })
}

async function loadThread() {
  if (!aid.value) {
    bootError.value = '缺少报告 ID'
    loading.value = false
    return
  }
  loading.value = true
  bootError.value = ''
  try {
    userId = await ensureReportUser()
    const data = await fetchReportTalentChat(userId, aid.value)
    opening.value = data.opening || OPENING_FALLBACK
    messages.value = Array.isArray(data.messages) ? data.messages : []
    const last = messages.value[messages.value.length - 1]
    bumpScroll(last ? `msg-${last.id}` : 'msg-open')
  } catch (e) {
    bootError.value = e?.message || '打不开这份报告的对话'
  } finally {
    loading.value = false
  }
}

async function onSend() {
  const text = draft.value.trim()
  if (!text || !canSend.value || sending.value) return
  sending.value = true
  draft.value = ''
  try {
    const data = await sendReportTalentChat(userId, aid.value, text)
    if (data?.user) messages.value.push(data.user)
    if (data?.assistant) messages.value.push(data.assistant)
    const last = messages.value[messages.value.length - 1]
    bumpScroll(last ? `msg-${last.id}` : 'msg-end')
  } catch (e) {
    draft.value = text
    uni.showToast({ title: e?.message || '发送失败', icon: 'none' })
  } finally {
    sending.value = false
  }
}

watch(
  () => aid.value,
  (id, prev) => {
    if (id && id !== prev) loadThread()
  },
  { immediate: true },
)

defineExpose({ reload: loadThread })
</script>

<style scoped>
.chatdemo {
  display: flex;
  flex-direction: column;
  border-radius: 18px;
  background: rgba(0, 0, 0, 0.3);
  border: 1.5px solid rgba(78, 160, 216, 0.35);
  padding: 12px;
  box-sizing: border-box;
}
.chatdemo.page {
  min-height: 100vh;
  border-radius: 0;
  border: 0;
  padding: 0;
  background: #0b1220;
}
.nav {
  display: flex;
  align-items: center;
  padding: 12px;
  padding-top: calc(12px + env(safe-area-inset-top));
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.nav-back {
  width: 36px;
  height: 36px;
  border-radius: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.06);
  color: #9fb0c7;
  font-size: 28px;
}
.nav-title {
  flex: 1;
  text-align: center;
  font-size: 16px;
  font-weight: 900;
  color: #8fc3e8;
  letter-spacing: 1px;
}
.nav-spacer {
  width: 36px;
}
.cd-h {
  font-size: 16px;
  font-weight: 900;
  color: #8fc3e8;
  margin-bottom: 10px;
  text-align: center;
  letter-spacing: 1px;
}
.cd-thread {
  flex: 1;
  max-height: 320px;
  min-height: 120px;
  padding: 0 2px;
  box-sizing: border-box;
}
.chatdemo.page .cd-thread {
  max-height: none;
  height: 0;
  padding: 14px 14px 8px;
}
.cd-b {
  max-width: 82%;
  font-size: 16px;
  line-height: 1.6;
  border-radius: 14px;
  padding: 9px 12px;
  margin-bottom: 8px;
  word-break: break-word;
  white-space: pre-wrap;
}
.cd-b.me {
  margin-left: auto;
  background: linear-gradient(135deg, #e05252, #b03a3e);
  color: #fff;
  border-bottom-right-radius: 4px;
}
.cd-b.ai {
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #e6e0da;
  border-bottom-left-radius: 4px;
}
.cd-name {
  color: #f0a3a3;
  font-weight: 700;
}
.cd-banner {
  margin: 6px 0 10px;
  font-size: 13px;
  color: #7f8fa6;
}
.cd-banner.err {
  color: #ffb4b4;
}
.cd-banner.soft {
  color: #6f829c;
}
.cd-tail {
  height: 4px;
}
.cd-form {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  background: rgba(255, 255, 255, 0.06);
  border: 1.5px dashed rgba(143, 195, 232, 0.4);
  border-radius: 99px;
  padding: 6px 8px 6px 14px;
}
.chatdemo.page .cd-form {
  margin: 0 12px;
  margin-bottom: calc(10px + env(safe-area-inset-bottom));
}
.cd-field {
  flex: 1;
  font-size: 16px;
  color: #e8eef7;
  min-height: 28px;
}
.cd-send {
  flex-shrink: 0;
  padding: 6px 10px;
  color: #7a5560;
  font-weight: 900;
  font-size: 15px;
}
.cd-send.on {
  color: #f0a3a3;
}
</style>
