<template>
  <view class="app">
    <view class="nav">
      <view class="nav-back" @click.stop="goBack">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#8b949e" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      </view>
      <text class="nav-title">历史记录</text>
      <view class="nav-refresh" @click.stop="loadHistory(true)">
        <text>{{ loading ? '…' : '刷新' }}</text>
      </view>
    </view>

    <view class="body">
      <view v-if="errorText" class="state-box error">
        <text>{{ errorText }}</text>
        <view class="retry-btn" @click.stop="loadHistory(true)"><text>重试</text></view>
      </view>

      <view v-else-if="loading && !historyDays.length" class="state-box">
        <text>加载中...</text>
      </view>

      <template v-else-if="historyDays.length">
        <view v-for="(day, di) in historyDays" :key="day.date || di" class="day-section">
          <text class="day-label">{{ formatDayLabel(day.date) }}</text>
          <view
            v-for="(rec, ri) in day.records"
            :key="rec.id || `${di}-${ri}`"
            class="card summary-card"
          >
            <view class="summary-header">
              <text class="summary-label">📝 打卡 {{ cardsFromRecord(rec).length }} 项</text>
              <text v-if="rec.checkin_time" class="summary-time">{{ rec.checkin_time }}</text>
            </view>
            <view class="summary-mini-cards">
              <view
                v-for="(c, ci) in cardsFromRecord(rec)"
                :key="`${ri}-${ci}`"
                class="mini-card mini-card-v1"
              >
                <view class="mini-card-accent"></view>
                <view class="mini-card-left">
                  <text class="mini-card-name">{{ c.name }}{{ c.phaseBlock ? ` · 训练${c.phaseBlock}` : '' }}</text>
                  <text class="mini-card-summary">{{ miniCardSummary(c) }}</text>
                  <text v-if="c.result" class="mini-card-extra">结果：{{ c.result }}</text>
                  <text v-if="c.note" class="mini-card-extra">备注：{{ c.note }}</text>
                </view>
              </view>
            </view>
            <view v-if="rec.attitude_pct != null" class="summary-attitude">
              <text class="sa-label">配合度</text>
              <view class="sa-badge">
                <text class="sa-pct">{{ rec.attitude_pct }}%</text>
                <text class="sa-emoji">{{ attitudeEmoji(rec.attitude_pct) }}</text>
              </view>
            </view>
          </view>
        </view>
      </template>

      <view v-else class="state-box empty">
        <text class="empty-title">暂无历史记录</text>
        <text class="empty-hint">今日打卡请在训练页查看；完成训练并进入新训练日后，记录会出现在这里</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { ensureChildUser, fetchTrainingHistory } from '@/utils/userApi.js'
import { miniCardSummary, cardsFromRecord, attitudeEmoji } from '@/utils/trainingCardDisplay.js'

const loading = ref(false)
const errorText = ref('')
const historyDays = ref([])

function formatDayLabel(dateStr) {
  if (!dateStr || dateStr === 'unknown') return '未知日期'
  const d = new Date(`${dateStr}T12:00:00`)
  if (Number.isNaN(d.getTime())) return dateStr
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

async function loadHistory(force = false) {
  if (loading.value && !force) return
  loading.value = true
  errorText.value = ''
  try {
    const uid = await ensureChildUser()
    const data = await fetchTrainingHistory(uid, 100, { excludeToday: true })
    historyDays.value = data.days || []
  } catch (e) {
    historyDays.value = []
    errorText.value = e.message || '加载失败，请检查网络或稍后重试'
  } finally {
    loading.value = false
  }
}

function goBack() {
  uni.navigateBack({ delta: 1 })
}

onMounted(() => loadHistory(true))
onShow(() => loadHistory(true))
</script>

<style scoped>
.app {
  height: 100vh;
  max-width: 480px;
  width: 100%;
  margin: 0 auto;
  background: #0b111e;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  overflow: hidden;
  font-family: PingFang SC, Roboto, sans-serif;
}
.nav {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  padding: 14px 14px 10px;
  background: #0b111e;
  box-sizing: border-box;
  width: 100%;
}
.nav-back {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(0, 210, 255, 0.08);
  border: 1px solid rgba(0, 210, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.nav-title {
  flex: 1;
  text-align: center;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
}
.nav-refresh {
  min-width: 36px;
  height: 28px;
  padding: 0 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.nav-refresh text {
  color: rgba(255, 255, 255, 0.55);
  font-size: 10px;
  font-weight: 700;
}
.body {
  flex: 1;
  width: 100%;
  box-sizing: border-box;
  overflow-y: auto;
  padding: 0 14px 24px;
  -webkit-overflow-scrolling: touch;
}
.day-section {
  width: 100%;
  box-sizing: border-box;
  margin-bottom: 12px;
}
.day-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #9ca3af;
  margin: 8px 0 8px;
  padding-left: 2px;
}
.summary-card {
  width: 100%;
  box-sizing: border-box;
  background: rgba(0, 210, 255, 0.04);
  border: 2px solid rgba(0, 210, 255, 0.15);
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 10px;
}
.summary-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  gap: 8px;
}
.summary-label {
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
  font-weight: 500;
}
.summary-time {
  color: rgba(255, 255, 255, 0.35);
  font-size: 11px;
  flex-shrink: 0;
}
.summary-mini-cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  box-sizing: border-box;
}
.mini-card {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  box-sizing: border-box;
  background: rgba(0, 210, 255, 0.04);
  border: 1px solid rgba(0, 210, 255, 0.1);
  border-radius: 8px;
  padding: 10px 10px 10px 0;
  overflow: hidden;
}
.mini-card-v1 {
  padding-left: 8px;
}
.mini-card-v1 .mini-card-accent {
  width: 3px;
  height: 60%;
  min-height: 28px;
  border-radius: 0 2px 2px 0;
  background: linear-gradient(180deg, #00d2ff, #0088cc);
  box-shadow: 0 0 8px rgba(0, 210, 255, 0.4);
  flex-shrink: 0;
  align-self: center;
}
.mini-card-left {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}
.mini-card-name {
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  display: block;
  word-break: break-all;
}
.mini-card-summary {
  color: rgba(255, 255, 255, 0.45);
  font-size: 10px;
  display: block;
  margin-top: 2px;
  line-height: 1.4;
  word-break: break-all;
}
.mini-card-extra {
  color: rgba(255, 255, 255, 0.4);
  font-size: 10px;
  display: block;
  margin-top: 2px;
  line-height: 1.4;
  word-break: break-all;
}
.summary-attitude {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid rgba(0, 210, 255, 0.1);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.sa-label {
  color: rgba(255, 255, 255, 0.4);
  font-size: 10px;
  font-weight: 500;
}
.sa-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid #00d2ff;
  background: rgba(0, 136, 204, 0.2);
}
.sa-pct {
  color: #00d2ff;
  font-size: 11px;
  font-weight: 700;
}
.sa-emoji {
  font-size: 12px;
}
.state-box {
  text-align: center;
  padding: 48px 16px;
  color: #6b7280;
  font-size: 14px;
  box-sizing: border-box;
}
.state-box.error {
  color: #f87171;
}
.empty-title {
  display: block;
  color: rgba(255, 255, 255, 0.55);
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 10px;
}
.empty-hint {
  display: block;
  color: rgba(255, 255, 255, 0.35);
  font-size: 12px;
  line-height: 1.6;
}
.retry-btn {
  margin-top: 16px;
  display: inline-flex;
  padding: 8px 20px;
  border-radius: 999px;
  background: rgba(0, 210, 255, 0.15);
  border: 1px solid rgba(0, 210, 255, 0.35);
}
.retry-btn text {
  color: #00d2ff;
  font-size: 13px;
}
</style>
