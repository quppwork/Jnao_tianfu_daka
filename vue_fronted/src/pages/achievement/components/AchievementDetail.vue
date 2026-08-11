<template>
  <view v-if="visible" class="modal-mask" @click="close">
    <view class="modal-content" @click.stop>
      <view v-if="achievement" class="detail-container">
        <!-- 头部 -->
        <view class="detail-header" :class="achievement.color_theme">
          <view class="medal-icon-large">
            <svg v-if="achievement.status === 'claimed'" viewBox="0 0 24 24" width="48" height="48" fill="currentColor">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
            <svg v-else-if="achievement.status === 'ready'" viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
            </svg>
            <svg v-else viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
          </view>
          <text class="detail-name">{{ achievement.name }}</text>
          <text class="detail-title">{{ achievement.title }}</text>
        </view>

        <!-- 内容 -->
        <view class="detail-body">
          <!-- 状态标签 -->
          <view class="status-section">
            <view class="status-badge" :class="achievement.status">
              <text v-if="achievement.status === 'claimed'">已获得</text>
              <text v-else-if="achievement.status === 'ready'">可领取</text>
              <text v-else>未解锁</text>
            </view>
            <text v-if="achievement.claimed_at" class="claim-time">
              {{ formatDate(achievement.claimed_at) }} 获得
            </text>
          </view>

          <!-- 描述 -->
          <view class="desc-section">
            <text class="section-label">获取条件</text>
            <text class="desc-text">{{ achievement.description }}</text>
          </view>

          <!-- 进度 -->
          <view v-if="achievement.status !== 'claimed' && achievement.progress_target > 1" class="progress-section">
            <text class="section-label">当前进度</text>
            <view class="progress-bar">
              <view class="progress-fill" :style="{ width: (achievement.progress_current / achievement.progress_target * 100) + '%' }"></view>
            </view>
            <text class="progress-text">{{ achievement.progress_text }}</text>
          </view>

          <!-- 奖励说明 -->
          <view class="reward-section">
            <text class="section-label">解锁奖励</text>
            <view class="reward-item">
              <view class="reward-icon">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                </svg>
              </view>
              <view class="reward-info">
                <text class="reward-name">称号「{{ achievement.title }}」</text>
                <text class="reward-desc">解锁后可在称号管理中佩戴</text>
              </view>
            </view>
          </view>
        </view>

        <!-- 底部按钮 -->
        <view class="detail-footer">
          <view v-if="achievement.status === 'ready'" class="btn-primary" @click="handleClaim">
            <text>立即领取</text>
          </view>
          <view v-else-if="achievement.status === 'claimed'" class="btn-secondary" @click="handleSetTitle">
            <text>佩戴称号</text>
          </view>
          <view v-else class="btn-disabled">
            <text>未满足条件</text>
          </view>
        </view>

        <!-- 关闭按钮 -->
        <view class="close-btn" @click="close">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { defineProps, defineEmits } from 'vue'

const props = defineProps({
  visible: Boolean,
  achievement: Object,
})

const emit = defineEmits(['update:visible', 'claim', 'set-title'])

function close() {
  emit('update:visible', false)
}

function handleClaim() {
  emit('claim', props.achievement)
}

function handleSetTitle() {
  emit('set-title', props.achievement)
}

function formatDate(isoStr) {
  if (!isoStr) return ''
  const d = new Date(isoStr)
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}
</script>

<style scoped>
.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
  backdrop-filter: blur(4px);
}
.modal-content {
  background: var(--bg-card);
  border-radius: 24px;
  width: 100%;
  max-width: 400px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
}

.detail-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* 头部 */
.detail-header {
  padding: 32px 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #fff;
}
.detail-header.yellow { background: linear-gradient(135deg, #f59e0b, #d97706); }
.detail-header.blue { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.detail-header.purple { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }
.detail-header.green { background: linear-gradient(135deg, #10b981, #059669); }
.detail-header.pink { background: linear-gradient(135deg, #ec4899, #db2777); }
.medal-icon-large {
  width: 96px;
  height: 96px;
  border-radius: 50%;
  background: rgba(255,255,255,0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(10px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.2);
}
.detail-name {
  font-size: 20px;
  font-weight: 800;
  text-shadow: 0 2px 8px rgba(0,0,0,0.3);
}
.detail-title {
  font-size: 16px;
  font-weight: 600;
  opacity: 0.9;
}

/* 内容 */
.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}
.status-section {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}
.status-badge {
  padding: 6px 16px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
}
.status-badge.claimed {
  background: #10b981;
  color: #fff;
}
.status-badge.ready {
  background: #f59e0b;
  color: #fff;
}
.status-badge.locked {
  background: var(--bg);
  color: var(--text-dim);
}
.claim-time {
  color: var(--text-dim);
  font-size: 12px;
}

.section-label {
  color: var(--text-dim);
  font-size: 12px;
  font-weight: 600;
  display: block;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.desc-section {
  margin-bottom: 20px;
}
.desc-text {
  color: var(--text);
  font-size: 14px;
  line-height: 1.6;
}

.progress-section {
  margin-bottom: 20px;
}
.progress-bar {
  height: 8px;
  background: var(--bg);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), #00f2fe);
  border-radius: 4px;
  transition: width 0.6s ease;
}
.progress-text {
  color: var(--text-dim);
  font-size: 12px;
  text-align: center;
  display: block;
}

.reward-section {
  margin-bottom: 20px;
}
.reward-item {
  display: flex;
  gap: 12px;
  align-items: center;
  background: var(--bg);
  border-radius: 12px;
  padding: 12px;
}
.reward-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--accent-bg);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.reward-info {
  flex: 1;
}
.reward-name {
  color: var(--text);
  font-size: 14px;
  font-weight: 600;
  display: block;
}
.reward-desc {
  color: var(--text-dim);
  font-size: 12px;
  display: block;
  margin-top: 2px;
}

/* 底部按钮 */
.detail-footer {
  padding: 16px 24px 24px;
  border-top: 1px solid var(--border);
}
.btn-primary {
  background: linear-gradient(135deg, var(--accent), #00f2fe);
  border-radius: 12px;
  padding: 14px;
  text-align: center;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(79, 172, 254, 0.4);
  transition: all 0.2s;
}
.btn-primary:active {
  transform: scale(0.98);
  box-shadow: 0 2px 8px rgba(79, 172, 254, 0.3);
}
.btn-secondary {
  background: var(--bg);
  border: 1px solid var(--accent);
  border-radius: 12px;
  padding: 14px;
  text-align: center;
  color: var(--accent);
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-secondary:active {
  background: var(--accent-bg);
}
.btn-disabled {
  background: var(--bg);
  border-radius: 12px;
  padding: 14px;
  text-align: center;
  color: var(--text-dim);
  font-size: 16px;
  font-weight: 600;
  cursor: not-allowed;
}

/* 关闭按钮 */
.close-btn {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(0,0,0,0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  cursor: pointer;
  transition: all 0.2s;
}
.close-btn:active {
  background: rgba(0,0,0,0.4);
  transform: scale(0.9);
}
</style>
