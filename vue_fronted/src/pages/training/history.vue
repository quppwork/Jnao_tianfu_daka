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
          <view class="card day-card">
            <text class="day-card-title">{{ formatDayLabel(day.date) }}</text>
            <view v-for="(rec, ri) in day.records" :key="rec.id || `${di}-${ri}`" class="day-card-body">
              <view
                v-for="(c, ci) in cardsFromRecord(rec)"
                :key="`${ri}-${ci}`"
                class="day-item"
                @click="openRecordDetail(rec)"
              >
                <view class="day-item-head">
                  <text class="day-item-name">{{ c.name }}{{ c.phaseBlock ? ` · 训练${c.phaseBlock}` : '' }}</text>
                  <view v-if="rec.attitude_pct != null" class="day-item-att">
                    <text class="day-att-emoji">{{ attitudeEmoji(rec.attitude_pct) }}</text>
                    <text>{{ rec.attitude_pct }}%</text>
                  </view>
                </view>
                <text class="day-item-detail">{{ miniCardSummary(c) }}</text>
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

    <!-- 打卡详情弹窗 -->
    <view v-if="showDetail" class="picker-overlay" @click="closeDetail">
      <view class="picker-card detail-modal" @click.stop>
        <view class="modal-header">
          <text class="modal-title">打卡详情</text>
          <view class="modal-close" @click="closeDetail">✕</view>
        </view>
        <view class="detail-body">
          <view v-for="(c, ci) in detailCards" :key="ci" class="detail-card-item">
            <text class="detail-card-name">{{ c.name }}{{ c.phaseBlock ? ` · 训练${c.phaseBlock}` : '' }}</text>
            <view class="detail-fields">
              <view v-if="c.time" class="detail-field"><text class="dfl">用时</text><text class="dfv">{{ c.time }}分钟</text></view>
              <view v-if="c.wordCount" class="detail-field"><text class="dfl">完成</text><text class="dfv">{{ c.wordCount }}字</text></view>
              <view v-if="c.count" class="detail-field"><text class="dfl">题数</text><text class="dfv">{{ c.count }}题</text></view>
              <view v-if="c.accuracy" class="detail-field"><text class="dfl">正确率</text><text class="dfv">{{ c.accuracy }}%</text></view>
              <view v-if="c.tool" class="detail-field"><text class="dfl">工具</text><text class="dfv">{{ c.tool }}</text></view>
              <view v-if="c.completed" class="detail-field"><text class="dfl">状态</text><text class="dfv">{{ c.completed }}</text></view>
              <view v-if="c.materialType" class="detail-field"><text class="dfl">材料</text><text class="dfv">{{ c.materialType }}</text></view>
              <view v-if="c.materialName" class="detail-field"><text class="dfl">名称</text><text class="dfv">《{{ c.materialName }}》</text></view>
              <view v-if="c.result" class="detail-field"><text class="dfl">效果</text><text class="dfv">{{ c.result }}</text></view>
              <view v-if="c.note" class="detail-field"><text class="dfl">备注</text><text class="dfv">{{ c.note }}</text></view>
            </view>
          </view>
        </view>
        <view class="btn-close-detail" @click="closeDetail"><text>关闭</text></view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { ensureChildUser, fetchTrainingHistory } from '@/utils/userApi.js'
import { miniCardSummary, cardsFromRecord, attitudeEmoji } from '@/utils/trainingCardDisplay.js'

function miniCardDetail(c) {
  const parts = []
  if (c.time) parts.push(`用时${c.time}min`)
  if (c.wordCount) parts.push(`完成${c.wordCount}字`)
  if (c.count) parts.push(`${c.count}题`)
  if (c.accuracy) parts.push(`正确率${c.accuracy}%`)
  if (c.tool) parts.push(`工具：${c.tool}`)
  if (c.completed) parts.push(c.completed)
  return parts.length ? parts.join('  ') : '已记录'
}

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
const showDetail = ref(false)
const detailCards = ref([])

function openRecordDetail(rec) {
  detailCards.value = cardsFromRecord(rec)
  showDetail.value = true
}
function closeDetail() {
  showDetail.value = false
  detailCards.value = []
}

onMounted(() => loadHistory(true))
onShow(() => loadHistory(true))
</script>

<style scoped>
.app {
  height: 100vh; height: 100dvh;
  max-width: var(--app-max-width, 480px);
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
.day-card {
  width: 100%; box-sizing: border-box;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 16px; padding: 16px; margin-bottom: 12px;
  position: relative; overflow: hidden;
  box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}
.day-card::after {
  content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
  background: linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.6) 45%, rgba(255,255,255,0.8) 50%, rgba(255,255,255,0.6) 55%, transparent 60%);
  animation: cardShine 3s ease-in-out infinite;
  pointer-events: none;
}
@keyframes cardShine {
  0% { transform: translateX(-100%) translateY(-100%); }
  100% { transform: translateX(100%) translateY(100%); }
}
.day-card-title { color:#1f2937; font-size:14px; font-weight:600; display:block; margin-bottom:12px; position:relative; z-index:1; }
.day-card-body { display:flex; flex-direction:column; gap:8px; position:relative; z-index:1; }
.day-item { display:flex; flex-direction:column; gap:3px; padding:8px 0; border-bottom:1px solid #f3f4f6; }
.day-item:last-child { border-bottom:none; }
.day-item-head { display:flex; justify-content:space-between; align-items:center; }
.day-item-name { color:#374151; font-size:13px; font-weight:500; }
.day-item-att { display:flex; align-items:center; gap:3px; color:#2563eb; font-size:12px; font-weight:600; }
.day-att-emoji { font-size:14px; }
.day-item { cursor:pointer; }
.day-item:active { background:#f9fafb; border-radius:8px; }

/* Detail popup */
.picker-overlay { position:fixed; inset:0; z-index:500; background:rgba(0,0,0,0.6); display:flex; align-items:center; justify-content:center; padding:20px; }
.detail-modal { background:#fff; border-radius:16px; padding:20px; width:100%; max-width:360px; max-height:70vh; overflow-y:auto; }
.modal-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; }
.modal-title { color:#1f2937; font-size:16px; font-weight:700; }
.modal-close { width:28px; height:28px; border-radius:50%; background:#f3f4f6; display:flex; align-items:center; justify-content:center; cursor:pointer; font-size:14px; color:#9ca3af; }
.detail-body { display:flex; flex-direction:column; gap:12px; }
.detail-card-item { border:1px solid #f3f4f6; border-radius:10px; padding:12px; }
.detail-card-name { color:#1f2937; font-size:14px; font-weight:600; display:block; margin-bottom:8px; }
.detail-fields { display:flex; flex-direction:column; gap:6px; }
.detail-field { display:flex; align-items:center; gap:8px; }
.dfl { color:#9ca3af; font-size:12px; width:48px; flex-shrink:0; }
.dfv { color:#374151; font-size:13px; }
.btn-close-detail { margin-top:16px; padding:12px; text-align:center; background:#f3f4f6; border-radius:10px; cursor:pointer; }
.btn-close-detail text { color:#6b7280; font-size:14px; font-weight:500; }
.day-item-detail { color:#9ca3af; font-size:11px; }
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
.mini-card-v2 {
  padding:12px 14px;
  flex-direction:column; align-items:stretch; gap:6px;
}
.mini-card-v2-head { display:flex; justify-content:space-between; align-items:center; }
.mini-card-v2-name { color:#fff; font-size:13px; font-weight:600; }
.mini-card-v2-detail { color:rgba(255,255,255,0.5); font-size:11px; line-height:1.5; }
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

[data-theme="white"] .app { background: #f0f2f5; }
[data-theme="white"] .nav { background: #f0f2f5; }
[data-theme="white"] .nav-title { color: #1a1a2e; }
[data-theme="white"] .nav-back { background: #f3f4f6; border-color: #e5e7eb; }
[data-theme="white"] .nav-refresh { background: #f3f4f6; border-color: #e5e7eb; }
[data-theme="white"] .nav-refresh text { color: #374151; }
[data-theme="white"] .day-label { color: #6b7280; }
[data-theme="white"] .summary-card { background: #fff; border-color: #e5e7eb; }
[data-theme="white"] .summary-label { color: #6b7280; }
[data-theme="white"] .summary-time { color: #9ca3af; }
[data-theme="white"] .mini-card { background: #f9fafb; border-color: #e5e7eb; }
[data-theme="white"] .mini-card-name { color: #1a1a2e; }
[data-theme="white"] .mini-card-summary { color: #6b7280; }
[data-theme="white"] .mini-card-extra { color: #9ca3af; }
[data-theme="white"] .mini-card-v1 .mini-card-accent { background: linear-gradient(180deg,#2563eb,#1d4ed8); }
[data-theme="white"] .sa-label { color: #6b7280; }
[data-theme="white"] .sa-badge { border-color: #2563eb; background: rgba(37,99,235,0.08); }
[data-theme="white"] .sa-pct { color: #2563eb; }
[data-theme="white"] .empty-title { color: #6b7280; }
[data-theme="white"] .empty-hint { color: #9ca3af; }
[data-theme="white"] .state-box { color: #9ca3af; }
[data-theme="white"] .retry-btn { background: #f3f4f6; border-color: #d1d5db; }
[data-theme="white"] .retry-btn text { color: #2563eb; }
</style>
