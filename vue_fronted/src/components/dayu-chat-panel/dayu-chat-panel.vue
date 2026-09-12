<template>
  <view class="chat-panel" :class="['theme-' + accent, { lt: light }]">
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
        <slot name="intro" />

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
              <view class="thinking-dots" aria-hidden="true">
                <view class="thinking-dot" />
                <view class="thinking-dot" />
                <view class="thinking-dot" />
              </view>
              <text class="thinking-label">{{ thinkingHint }}</text>
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
                  @tap="$emit('navigate', act)"
                >
                  <text>{{ act.label || '前往 ›' }}</text>
                </view>
                <view v-else-if="act.type === 'confirm'" class="confirm-wrap">
                  <text v-if="act.preview" class="preview">{{ act.preview }}</text>
                  <view class="act-row">
                    <view
                      class="go sm"
                      :class="{ muted: act._done || act._dismissed }"
                      @tap="$emit('confirm', { message: m, index: ai, action: act })"
                    >
                      <text>{{ act._done ? '已记下 ✓' : (act.label || '确认记下') }}</text>
                    </view>
                    <view
                      v-if="!act._done && !act._dismissed"
                      class="go sm ghost"
                      @tap="$emit('dismiss', { message: m, index: ai })"
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

    <view v-if="showSuggests" class="suggest-row">
      <view
        v-for="(c, i) in displaySuggests"
        :key="'sg' + i"
        class="suggest-chip"
        @tap="$emit('suggest', c.text || c.label)"
      >
        <text>{{ c.label || c.text }}</text>
      </view>
    </view>

    <view class="chat-ask">
      <input
        class="box"
        :value="modelValue"
        type="text"
        :placeholder="placeholder"
        :disabled="loading"
        confirm-type="send"
        :adjust-position="true"
        :hold-keyboard="true"
        maxlength="2000"
        @input="onInput"
        @confirm="$emit('send')"
      />
      <view
        class="send"
        :class="{ stop: loading, disabled: !canSend && !loading }"
        @tap="loading ? $emit('stop') : $emit('send')"
      >
        <text>{{ loading ? '■' : '➤' }}</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed } from 'vue'
import { formatGuideRichHtml } from '@/utils/chatRichText.js'
import 'katex/dist/katex.min.css'

const props = defineProps({
  /** gold=家长 · green=孩子 */
  accent: { type: String, default: 'green' },
  /** 孩子端浅色主题 */
  light: { type: Boolean, default: false },
  messages: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  thinkingHint: { type: String, default: 'agent思考中…' },
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '输入问题…' },
  scrollInto: { type: String, default: '' },
  /** 知识库提问引导 chips：[{label,text}] */
  suggests: { type: Array, default: () => [] },
  /** 是否展示引导 chips（有历史也可展示，引导继续提问） */
  showSuggests: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'send', 'stop', 'navigate', 'confirm', 'dismiss', 'suggest'])

const canSend = computed(() => !!String(props.modelValue || '').trim() && !props.loading)
const displaySuggests = computed(() => (Array.isArray(props.suggests) ? props.suggests.slice(0, 3) : []))

function onInput(e) {
  const v = e?.detail?.value ?? e?.target?.value ?? ''
  emit('update:modelValue', v)
}
</script>

<style scoped>
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
.chat-scroll {
  flex: 1;
  height: 0;
  min-height: 0;
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.chat-scroll::-webkit-scrollbar { display: none; width: 0; height: 0; }
.chat-stack { padding: 12px 12px 10px; }
.chat-end { height: 8px; }

.suggest-row {
  flex-shrink: 0;
  display: flex;
  flex-wrap: nowrap;
  gap: 8px;
  padding: 8px 10px 0;
  border-top: 1px solid #232b3d;
  overflow: hidden;
}
.suggest-chip {
  flex: 1 1 0;
  min-width: 0;
  text-align: center;
  border: 1.5px solid rgba(111, 207, 142, 0.45);
  background: rgba(111, 207, 142, 0.1);
  color: #8fefc0;
  font-size: 13px;
  font-weight: 800;
  border-radius: 99px;
  padding: 7px 10px;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.theme-gold .suggest-chip {
  border-color: rgba(201, 162, 39, 0.45);
  background: rgba(201, 162, 39, 0.1);
  color: #f5d9a8;
}
.theme-green .suggest-chip {
  border-color: rgba(111, 207, 142, 0.45);
  background: rgba(111, 207, 142, 0.1);
  color: #8fefc0;
}
.chat-panel.lt .suggest-row { border-top-color: #c2cadc; }
.chat-panel.lt .suggest-chip {
  border-color: rgba(46, 107, 230, 0.4);
  background: #e8eefc;
  color: #2e5bd6;
}
.chat-panel.lt.theme-green .suggest-chip {
  border-color: rgba(48, 144, 79, 0.45);
  background: #e5f5ea;
  color: #247a42;
}
.chat-panel.lt.theme-gold .suggest-chip {
  border-color: rgba(150, 117, 54, 0.5);
  background: rgba(201, 162, 39, 0.14);
  color: #967536;
}

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
.chat-ask .send {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex: none;
  font-weight: 900;
  color: #0b0e14;
}
.chat-ask .send.stop { background: #e05252 !important; color: #fff; }
.chat-ask .send.disabled { opacity: 0.45; }

.theme-green .chat-ask .send { background: #6fcf8e; }
.theme-gold .chat-ask .send {
  background: linear-gradient(135deg, #c9a227, #967536);
  color: #0d111f;
}

.av {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: url('/static/dayu/assets/avatar-dayu.jpg') center 12% / 120% auto;
  border: 2px solid #edebe4;
  flex: none;
}
.av.sm { width: 32px; height: 32px; border-width: 1.5px; }

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
.theme-gold .bubble.me {
  background: rgba(201, 162, 39, 0.16);
  border-color: rgba(201, 162, 39, 0.55);
}

.thinking {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 22px;
  padding: 2px 0;
}
.thinking-dots { display: flex; align-items: center; gap: 4px; flex: none; }
.thinking-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  opacity: 0.35;
  animation: thinkingBounce 1.15s ease-in-out infinite;
}
.theme-green .thinking-dot { background: #6fcf8e; }
.theme-gold .thinking-dot { background: #f5d576; }
.thinking-dot:nth-child(2) { animation-delay: 0.15s; }
.thinking-dot:nth-child(3) { animation-delay: 0.3s; }
.thinking-label {
  color: #8b93a5;
  font-size: 13px;
  font-weight: 600;
  animation: thinkingPulse 1.4s ease-in-out infinite;
}
@keyframes thinkingBounce {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.3; }
  40% { transform: translateY(-3px); opacity: 1; }
}
@keyframes thinkingPulse {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.act-row { display: flex; flex-wrap: wrap; align-items: center; }
.confirm-wrap { width: 100%; }
.preview {
  display: block;
  font-size: 12px;
  color: #8b93a5;
  margin: 6px 0 2px;
}
.go {
  display: inline-flex;
  margin-top: 8px;
  margin-right: 8px;
  padding: 8px 16px;
  border-radius: 99px;
  font-size: 13px;
  font-weight: 900;
  color: #0d111f;
}
.theme-green .go { background: #2e6be6; color: #fff; }
.theme-gold .go {
  background: linear-gradient(90deg, #f5d576, #c9a869);
  color: #0d111f;
}
.go.ghost {
  background: transparent;
  border: 1.5px solid #2a3040;
  color: #8b93a5;
}
.go.muted { opacity: 0.55; }

.rich :deep(b),
.rich :deep(strong) { color: #f5d9a8; font-weight: 800; }
.theme-green .rich :deep(b),
.theme-green .rich :deep(strong) { color: #9ad9ff; }

.chat-panel.lt {
  background: rgba(217, 223, 236, 0.72);
  border-color: #c2cadc;
}
.chat-panel.lt .chat-ask {
  border-top-color: #c2cadc;
  background: rgba(235, 238, 244, 0.88);
}
.chat-panel.lt .chat-ask .box {
  background: #d4dbe9;
  border-color: #bfc5d5;
  color: #1b1912;
}
.chat-panel.lt.theme-green .chat-ask .send { background: #30904f; color: #fff; }
.chat-panel.lt .bubble.ai {
  background: #d9dfec;
  border-color: #c2cadc;
  color: #191d27;
}
.chat-panel.lt .bubble.me {
  background: rgba(25, 86, 209, 0.14);
  border-color: #1956d1;
  color: #103880;
}
.chat-panel.lt .av { border-color: #1956d1; }
.chat-panel.lt .thinking-dot { background: #30904f; }
.chat-panel.lt .thinking-label { color: #5a6274; }
.chat-panel.lt.theme-green .go { background: #1956d1; color: #141414; }
.chat-panel.lt .rich :deep(b),
.chat-panel.lt .rich :deep(strong) { color: #103880; }
</style>
