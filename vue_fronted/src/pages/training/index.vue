<template>
  <view class="app">
    <view class="nav">
      <view class="nav-back" @click="goBack">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#8b949e" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      </view>
      <text class="nav-title">今日训练</text>
      <view class="nav-spacer"></view>
    </view>

    <view class="body">
      <!-- Plan -->
      <view class="card plan-card" data-augmented-ui="tl-clip tr-clip br-clip bl-clip border">
        <text class="plan-label">📋 今日方案</text>
        <view class="plan-list">
          <view class="plan-item"><text class="pl-dot">▸</text><text class="pl-text">观看"五者天赋"训练视频，理解天赋类型特点</text></view>
          <view class="plan-item"><text class="pl-dot">▸</text><text class="pl-text">完成音频听力训练，提升听觉记忆能力</text></view>
        </view>
      </view>

      <!-- 今日训练时段 -->
      <view class="card time-card">
        <view class="time-header">
          <text class="plan-label">⏰ 今日训练时段</text>
          <text v-if="devMode" class="time-dev-tag">DEV</text>
        </view>
        <view class="time-row">
          <input class="time-inp" v-model="trainStart" type="time" />
          <text class="time-to">至</text>
          <input class="time-inp" v-model="trainEnd" type="time" />
          <view class="time-dev-btn" @click="devMode = !devMode"><text>{{ devMode ? '🔓' : '🔒' }}</text></view>
        </view>
        <view v-if="devMode" class="time-dev-hint"><text>开发者模式：时段限制已关闭</text></view>
      </view>

      <!-- Training A -->
      <text class="section-title">训练 A</text>

      <view class="step step-ready" @click="openMedia('video')">
        <view class="step-num step-num-ready">1</view>
        <view class="step-content">
          <text class="step-label">视频训练</text>
          <view class="step-box step-box-ready">🎬 五者天赋视频</view>
          <text class="step-time ready-text">▶ 点击播放</text>
        </view>
      </view>

      <view class="step" @click="openMedia('audio')">
        <view class="step-num">2</view>
        <view class="step-content">
          <text class="step-label">音频训练</text>
          <view class="step-box">🎧 训练用音频</view>
          <text class="step-time">点击播放</text>
        </view>
      </view>

      <view class="btn-checkin btn-cyber" data-augmented-ui="tl-clip br-clip border" @click="openPicker">
        <text>✅ 训练 A 打卡</text>
      </view>

      <!-- 能力选择面板 -->
      <view v-if="showPicker" class="picker-panel" data-augmented-ui="tl-clip tr-clip br-clip bl-clip border">
        <view class="picker-panel-header">
          <text class="pph-dot">◆</text>
          <text class="pph-title">选择训练能力</text>
          <text class="pph-dot">◆</text>
        </view>
        <view class="picker-grid">
          <view v-for="item in abilities" :key="item" class="picker-item" :class="{ active: hasCard(item) }" @click="toggleCard(item)">
            <text class="pi-text">{{ item }}</text>
          </view>
        </view>
      </view>

      <!-- 已选卡片列表 -->
      <TransitionGroup name="card">
        <view v-for="(card, idx) in cards" :key="card.name" class="form-card">
        <view class="scan-line"></view>
        <view class="form-header">
          <text class="form-title">{{ card.name }} — 训练记录</text>
          <view class="form-del" @click="removeCard(idx)">✕</view>
        </view>

        <template v-if="card.name === '极速运算'">
          <view class="form-row">
            <text class="form-label">时间</text>
            <input class="form-input" v-model="card.time" placeholder="训练时长（分钟）" type="number" />
          </view>
          <view class="form-row">
            <text class="form-label">内容</text>
            <view class="form-tags">
              <text class="ftag" :class="{ on: card.tag === '加减法' }" @click="card.tag = '加减法'">加减法</text>
              <text class="ftag" :class="{ on: card.tag === '乘除法' }" @click="card.tag = '乘除法'">乘除法</text>
              <text class="ftag" :class="{ on: card.tag === '混合运算' }" @click="card.tag = '混合运算'">混合运算</text>
              <text class="ftag" :class="{ on: card.tag === '口算' }" @click="card.tag = '口算'">口算</text>
            </view>
          </view>
          <view class="form-row">
            <text class="form-label">结果</text>
            <view class="form-inline">
              <input class="form-input short" v-model="card.count" placeholder="题数" type="number" />
              <text class="form-unit">题</text>
              <input class="form-input short" v-model="card.accuracy" placeholder="正确率" type="number" />
              <text class="form-unit">%</text>
            </view>
          </view>
          <view class="form-row">
            <text class="form-label">图片/视频</text>
            <view class="form-file-wrap">
              <view class="file-btn" @click="pickFile(idx)"><text>📷 选择文件</text></view>
              <view v-if="card.files && card.files.length" class="file-previews">
                <view v-for="(f,fi) in card.files" :key="fi" class="file-preview">
                  <image v-if="f.type === 'image'" :src="f.url" mode="aspectFill" class="preview-img" />
                  <video v-if="f.type === 'video'" :src="f.url" class="preview-video" />
                  <text class="file-del" @click="removeFile(idx, fi)">✕</text>
                </view>
              </view>
            </view>
          </view>
          <view class="form-row">
            <text class="form-label">备注</text>
            <textarea class="form-textarea" v-model="card.note" placeholder="补充说明..." style="height:50px;" />
          </view>
        </template>
        <template v-else-if="card.name === '扫描速记'">
          <view class="form-row">
            <text class="form-label">用时</text>
            <input class="form-input" v-model="card.time" placeholder="如：1秒" />
          </view>
          <view class="form-row">
            <text class="form-label">完成</text>
            <view class="form-inline">
              <input class="form-input short" v-model="card.wordCount" placeholder="字数" />
              <text class="form-unit">字的</text>
              <input class="form-input short" v-model="card.bookName" placeholder="书名" />
              <text class="form-unit">训练</text>
            </view>
          </view>
          <view class="form-row">
            <text class="form-label">达到</text>
            <view class="form-tags">
              <text class="ftag" :class="{ on: card.result === '逐字倒背' }" @click="card.result = '逐字倒背'">逐字倒背</text>
              <text class="ftag" :class="{ on: card.result === '逐字复述' }" @click="card.result = '逐字复述'">逐字复述</text>
              <text class="ftag" :class="{ on: card.result === '复述80%准确' }" @click="card.result = '复述80%准确'">复述80%准确</text>
            </view>
          </view>
          <view class="form-row">
            <text class="form-label">图片/视频</text>
            <view class="form-file-wrap">
              <view class="file-btn" @click="pickFile(idx)"><text>📷 选择文件</text></view>
              <view v-if="card.files && card.files.length" class="file-previews">
                <view v-for="(f,fi) in card.files" :key="fi" class="file-preview">
                  <image v-if="f.type === 'image'" :src="f.url" mode="aspectFill" class="preview-img" />
                  <video v-if="f.type === 'video'" :src="f.url" class="preview-video" />
                  <text class="file-del" @click="removeFile(idx, fi)">✕</text>
                </view>
              </view>
            </view>
          </view>
          <view class="form-row">
            <text class="form-label">备注</text>
            <textarea class="form-textarea" v-model="card.note" placeholder="补充说明..." style="height:50px;" />
          </view>
        </template>
        <template v-else>
          <view class="form-row">
            <text class="form-label">时间</text>
            <input class="form-input" v-model="card.time" placeholder="训练时长/分钟" />
          </view>
          <view class="form-row">
            <text class="form-label">内容</text>
            <textarea class="form-textarea" v-model="card.content" placeholder="训练了什么内容？" />
          </view>
          <view class="form-row">
            <text class="form-label">结果</text>
            <textarea class="form-textarea" v-model="card.result" placeholder="训练效果如何？" />
          </view>
          <view class="form-row">
            <text class="form-label">图片/视频</text>
            <view class="form-file-wrap">
              <view class="file-btn" @click="pickFile(idx)"><text>📷 选择文件</text></view>
              <text class="file-hint" v-if="!card.files.length">支持图片和视频</text>
              <view v-if="card.files.length" class="file-previews">
                <view v-for="(f,fi) in card.files" :key="fi" class="file-preview">
                  <image v-if="f.type === 'image'" :src="f.url" mode="aspectFill" class="preview-img" />
                  <video v-if="f.type === 'video'" :src="f.url" class="preview-video" />
                  <text class="file-del" @click="removeFile(idx, fi)">✕</text>
                </view>
              </view>
            </view>
          </view>
          <view class="form-row">
            <text class="form-label">备注</text>
            <textarea class="form-textarea" v-model="card.note" placeholder="补充说明..." style="height:50px;" />
          </view>
        </template>
      </view>

      </TransitionGroup>

      <!-- 配合度打分 -->
      <view v-if="showPicker && cards.length" class="score-panel">
        <view class="score-header">
          <text class="pph-dot">◆</text>
          <text class="pph-title">训练配合度</text>
          <text class="pph-dot">◆</text>
        </view>
        <view class="score-grid">
          <view v-for="s in scores" :key="s.pct" class="score-item" :class="{ active: attitude === s.pct }" @click="attitude = s.pct">
            <text class="si-pct">{{ s.pct }}%</text>
            <text class="si-emoji">{{ s.emoji }}</text>
            <text class="si-desc">{{ s.desc }}</text>
          </view>
        </view>
      </view>

      <view v-if="showPicker" class="btn-checkin" @click="submitFormWithAnim" style="margin-top:8px;">
        <text>✅ 提交打卡 {{ cards.length ? '(' + cards.length + ')' : '' }}</text>
      </view>

      <!-- Summary -->
      <view class="card summary-card" @click="submittedCards.length ? showSummary = true : null">
        <text class="summary-label">📝 打卡的训练总结</text>
        <text class="summary-text">{{ submittedCards.length ? '今日已打卡 ' + submittedCards.length + ' 项' : '完成训练后自动生成今日总结...' }}</text>
        <text v-if="submittedCards.length" class="summary-more">点击管理打卡 ›</text>
      </view>

      <view v-if="showSummary && submittedCards.length" class="picker-overlay" @click="showSummary = false">
        <view class="picker-card" @click.stop>
          <text class="picker-title">📝 已打卡项目</text>
          <view v-for="(c, idx) in submittedCards" :key="idx" class="submitted-item">
            <text class="si-text">{{ getCardSummary(c) }}</text>
            <view class="si-actions">
              <text class="si-edit" @click="editCard(idx)">✎</text>
              <text class="si-del" @click="deleteCard(idx)">✕</text>
            </view>
          </view>
          <view class="picker-close" @click="showSummary = false"><text>关闭</text></view>
        </view>
      </view>

      <!-- Divider -->
      <view class="divider"></view>

      <!-- Training B -->
      <view class="b-section" :class="{ locked: !bUnlocked }">
        <text class="section-title" :class="{ dim: !bUnlocked }">训练 B {{ !bUnlocked ? '🔒' : '' }}</text>

        <view class="step dim-step">
          <view class="step-num dim">1</view>
          <view class="step-content">
            <text class="step-label dim-text">视频训练</text>
            <view class="step-box dim-box">🎬 训练用视频</view>
            <text class="step-time dim-text">约 X 分钟</text>
          </view>
        </view>

        <view class="step dim-step">
          <view class="step-num dim">2</view>
          <view class="step-content">
            <text class="step-label dim-text">音频训练</text>
            <view class="step-box dim-box">🎧 训练用音频</view>
            <text class="step-time dim-text">约 X 分钟</text>
          </view>
        </view>

        <text class="lock-tip">{{ bTip }}</text>
      </view>

      <view style="height:40px;"></view>
    </view>

    <!-- Media Player Overlay -->
    <view v-if="mediaPlayer.show" class="player-overlay" @click="closeMedia">
      <view class="player-card" @click.stop>
        <view class="player-header">
          <text class="player-title">{{ mediaPlayer.type === 'video' ? '🎬 视频训练' : '🎧 音频训练' }}</text>
          <view class="player-close" @click="closeMedia">✕</view>
        </view>
        <view v-if="mediaPlayer.type === 'video'" class="player-body">
          <view v-html="videoHtml"></view>
        </view>
        <view v-if="mediaPlayer.type === 'audio'" class="player-body">
          <text class="pa-icon" style="font-size:48px;display:block;text-align:center;margin-bottom:8px;">🎧</text>
          <view v-html="audioHtml"></view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'

const devMode = ref(false)
const trainStart = ref('')
const trainEnd = ref('')
const bUnlocked = ref(false)
const bTip = ref('⚠ 训练 A 未完成，B 暂不开放')
const showPicker = ref(false)
const showSummary = ref(false)
const submittedCards = ref([])
const attitude = ref(0)
const scores = [
  { pct:100, emoji:'🔴', desc:'身体已透支，精神还要求进步' },
  { pct:80,  emoji:'🟡', desc:'能完成任务，但还有余力学习' },
  { pct:60,  emoji:'🔵', desc:'做基本任务，被动的低效训练' },
  { pct:40,  emoji:'🟤', desc:'不完成任务，不认真逃避训练' },
  { pct:20,  emoji:'⚫️', desc:'不完成任务，基本不配合训练' },
  { pct:0,   emoji:'☠️', desc:'不完成任务，严重不配合训练' },
]
const mediaPlayer = ref({ show: false, type: 'video' })
const mediaSrc = ref('/static/training_video.mp4')

const videoHtml = computed(() => mediaSrc.value ? `<video src="${mediaSrc.value}" controls autoplay style="width:100%;border-radius:10px;background:#000;"></video>` : '<text>暂无视频资源</text>')
const audioHtml = computed(() => mediaSrc.value ? `<audio src="${mediaSrc.value}" controls autoplay style="width:100%;"></audio>` : '<text>暂无音频资源</text>')
const cards = ref([])
const abilities = ['超脑阅读','影像追忆','扫描速记','极速运算','极速学习','难题专练','文科扫书','理科扫书','高效作业','天赋绘画','音乐灵感','棋类专注']

function hasCard(name) { return cards.value.some(c => c.name === name) }

function toggleCard(name) {
  const idx = cards.value.findIndex(c => c.name === name)
  if (idx >= 0) {
    cards.value.splice(idx, 1)
  } else {
    cards.value.push({ name, time: '', content: '', result: '', tag: '', count: '', accuracy: '', note: '', files: [] })
  }
}

function removeCard(idx) { cards.value.splice(idx, 1) }
function pickFile(idx) {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*,video/*'
  input.multiple = true
  input.onchange = (e) => {
    const files = e.target.files
    for (let i = 0; i < files.length; i++) {
      const f = files[i]
      const url = URL.createObjectURL(f)
      cards.value[idx].files.push({ name: f.name, url, type: f.type.startsWith('video') ? 'video' : 'image' })
    }
  }
  input.click()
}
function removeFile(cardIdx, fileIdx) {
  const card = cards.value[cardIdx]
  URL.revokeObjectURL(card.files[fileIdx].url)
  card.files.splice(fileIdx, 1)
}

function openPicker() {
  showPicker.value = !showPicker.value
  // 赛博点击特效
  const btn = document.querySelector('.btn-cyber')
  if (btn) {
    btn.classList.add('spark')
    setTimeout(() => btn.classList.remove('spark'), 400)
  }
}

function submitFormWithAnim() {
  // 脉冲扩散动画
  const btn = document.querySelector('.btn-checkin')
  if (btn) {
    btn.classList.add('pulse-out')
    setTimeout(() => btn.classList.remove('pulse-out'), 500)
  }
  submitForm()
}

function submitForm() {
  const hasContent = cards.value.some(c => c.time || c.content || c.result || c.count || c.tag)
  if (!hasContent) {
    const btn = document.querySelector('.btn-checkin')
    if (btn) { btn.classList.add('warn-flash'); setTimeout(() => btn.classList.remove('warn-flash'), 600) }
    uni.showToast({ title: '请先填写训练记录再提交', icon: 'none', duration: 2000 })
    return
  }
  if (!attitude.value) {
    uni.showToast({ title: '请选择训练配合度', icon: 'none', duration: 2000 })
    return
  }
  bUnlocked.value = true
  bTip.value = '✅ A 已完成，开始训练 B'
  // 保存到已提交列表
  submittedCards.value.push(...cards.value.map(c => ({ ...c })))
  cards.value = []
  showPicker.value = false
  uni.showToast({ title: '✅ 训练 A 打卡成功！', icon: 'none' })
}

function getCardSummary(c) {
  if (c.name === '极速运算') return c.name + '(' + (c.tag || '运算') + ',' + c.time + '分钟,' + c.count + '题,' + c.accuracy + '%)'
  if (c.name === '扫描速记') return '扫描速记：用时' + (c.time||'?') + '，完成' + (c.wordCount||'?') + '字《' + (c.bookName||'?') + '》，' + (c.result||'待选')
  return c.name + '(' + c.time + '分钟)'
}

function editCard(idx) {
  const c = submittedCards.value[idx]
  cards.value.push({ ...c })
  submittedCards.value.splice(idx, 1)
  showPicker.value = true
}

function deleteCard(idx) {
  submittedCards.value.splice(idx, 1)
  if (!submittedCards.value.length) {
    bUnlocked.value = false
    bTip.value = '⚠ 训练 A 未完成，B 暂不开放'
  }
}

function openMedia(type) {
  // 检查训练时段
  if (!devMode.value && trainStart.value && trainEnd.value) {
    const now = new Date()
    const [sh, sm] = trainStart.value.split(':').map(Number)
    const [eh, em] = trainEnd.value.split(':').map(Number)
    const startMin = sh * 60 + sm
    const endMin = eh * 60 + em
    const nowMin = now.getHours() * 60 + now.getMinutes()
    if (nowMin < startMin || nowMin > endMin) {
      uni.showToast({ title: '当前不在训练时段内', icon: 'none', duration: 2000 })
      return
    }
  }
  mediaPlayer.value = { show: true, type }
  if (type === 'video') mediaSrc.value = '/static/training_video.mp4'
  else mediaSrc.value = ''
}
function closeMedia() {
  mediaPlayer.value.show = false
}
function goBack() {
  uni.navigateBack({ delta: 1 })
}
</script>

<style scoped>
@import 'augmented-ui/augmented-ui.min.css';
.app { height:100vh; max-width:480px; margin:0 auto; background:#0b111e; font-family:PingFang SC,Roboto,sans-serif; display:flex; flex-direction:column; position:relative; overflow:hidden; }
.nav { display:flex; align-items:center; padding:14px 14px 0; }
.nav-back { width:36px; height:36px; border-radius:50%; background:rgba(0,210,255,0.08); border:1px solid rgba(0,210,255,0.2); display:flex; align-items:center; justify-content:center; cursor:pointer; }
.nav-title { flex:1; text-align:center; color:#fff; font-size:16px; font-weight:600; }
.nav-spacer { width:36px; }
.body { flex:1; overflow-y:auto; padding:12px 14px 0; scrollbar-width:none; -ms-overflow-style:none; }
.body::-webkit-scrollbar { display:none; }

.card { background:#243046; border-radius:10px; padding:14px 16px; margin-bottom:12px; position:relative; border:2px solid rgba(0,210,255,0.2); clip-path:polygon(8px 0,100% 0,100% calc(100% - 8px),calc(100% - 8px) 100%,0 100%,0 8px); }
.plan-label { color:#00d2ff; font-size:13px; font-weight:700; display:block; margin-bottom:8px; }
.plan-item { display:flex; gap:6px; align-items:flex-start; margin-bottom:6px; }
.pl-dot { color:#00d2ff; font-size:12px; flex-shrink:0; margin-top:2px; }
.pl-text { color:#fff; font-size:12px; line-height:1.5; }
[data-theme="white"] .pl-text { color:#374151; }
[data-theme="white"] .pl-dot { color:#2563eb; }

.section-title { color:#fff; font-size:14px; font-weight:700; margin-bottom:8px; display:block; }
.section-title.dim { color:rgba(255,255,255,0.35); }

.step { background:#243046; border-radius:6px; padding:14px; display:flex; gap:10px; align-items:flex-start; border-left:4px solid #00d2ff; margin-bottom:8px; cursor:pointer; transition:all 0.15s; position:relative; clip-path:polygon(0 0,100% 0,100% calc(100% - 8px),calc(100% - 8px) 100%,0 100%); }
.step:active { background:#1a3040; }
.step.dim-step { border-left-color:rgba(255,255,255,0.1); }
.step.dim-step::after { border-color:rgba(255,255,255,0.1); }
.step-num { width:22px; height:22px; border-radius:50%; background:#00d2ff; color:#0b111e; display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:700; flex-shrink:0; }
.step-num.dim { background:rgba(255,255,255,0.1); }
.step-ready { border-left-color:#22c55e; }
.step-ready::after { border-color:#22c55e; }
.step-num-ready { background:#22c55e; }
.step-box-ready { background:rgba(34,197,94,0.08); border:1px solid rgba(34,197,94,0.15); }
.ready-text { color:#22c55e; }
.step-content { flex:1; }
.step-label { color:#fff; font-size:13px; font-weight:500; display:block; margin-bottom:6px; }
.step-label.dim-text { color:rgba(255,255,255,0.35); }
.step-box { background:#fff; border:2px solid rgba(0,210,255,0.2); border-radius:10px; padding:20px 14px; text-align:center; font-size:24px; color:#0b111e; }
.step-box.dim-box { opacity:0.3; }
.step-time { color:rgba(255,255,255,0.4); font-size:10px; text-align:center; display:block; margin-top:4px; }
.step-time.dim-text { color:rgba(255,255,255,0.35); }

.btn-checkin { background:linear-gradient(135deg,rgba(0,210,255,0.25),rgba(0,136,204,0.25)); border-radius:10px; padding:14px; text-align:center; margin-bottom:12px; cursor:pointer; box-shadow:0 0 20px rgba(0,210,255,0.15); }
.btn-checkin text { color:#00d2ff; font-size:15px; font-weight:600; }
.btn-checkin:active { opacity:0.85; }

.summary-card { border:2px dashed rgba(0,210,255,0.25); cursor:pointer; clip-path:polygon(8px 0,100% 0,100% calc(100% - 8px),calc(100% - 8px) 100%,0 100%,0 8px); }
.summary-card:active { background:#1a3040; }
.summary-label { color:rgba(255,255,255,0.5); font-size:12px; font-weight:500; display:block; margin-bottom:4px; }
.summary-text { color:rgba(255,255,255,0.4); font-size:12px; line-height:1.6; }
.summary-more { color:#00d2ff; font-size:11px; display:block; margin-top:4px; }

.picker-overlay { position:fixed; inset:0; z-index:500; background:rgba(0,0,0,0.75); display:flex; align-items:center; justify-content:center; padding:20px; }
.picker-card { background:#1a2840; border:1px solid #00d2ff; border-radius:14px; padding:24px 20px; width:100%; max-width:360px; box-shadow:0 0 30px rgba(0,210,255,0.1); position:relative; }
.picker-card::before, .picker-card::after { content:''; position:absolute; width:10px; height:10px; border-color:#00d2ff; border-style:solid; }
.picker-card::before { top:0; left:0; border-width:1px 0 0 1px; }
.picker-card::after { bottom:0; right:0; border-width:0 1px 1px 0; }
.picker-title { color:#fff; font-size:16px; font-weight:700; text-align:center; display:block; margin-bottom:16px; }
.picker-close { text-align:center; margin-top:16px; cursor:pointer; }
.picker-close text { color:rgba(255,255,255,0.5); font-size:14px; }
.submitted-item { display:flex; align-items:center; gap:8px; padding:10px 0; border-bottom:1px solid rgba(0,210,255,0.1); }
.submitted-item:last-child { border-bottom:none; }
.si-text { flex:1; color:#fff; font-size:13px; }
.si-actions { display:flex; gap:10px; flex-shrink:0; }
.si-edit { color:#00d2ff; font-size:16px; cursor:pointer; }
.si-del { color:rgba(255,255,255,0.4); font-size:16px; cursor:pointer; }
.si-del:active { color:#ff6b6b; }

.time-card { }
.time-header { display:flex; align-items:center; gap:8px; margin-bottom:8px; }
.time-dev-tag { background:rgba(0,210,255,0.15); color:#00d2ff; font-size:9px; padding:2px 6px; border-radius:4px; }
.time-row { display:flex; align-items:center; gap:8px; }
.time-inp { flex:1; background:rgba(0,210,255,0.05); border:1px solid rgba(0,210,255,0.15); border-radius:10px; padding:10px; color:#fff; font-size:14px; text-align:center; }
.time-to { color:rgba(255,255,255,0.4); font-size:13px; }
.time-dev-btn { width:32px; height:32px; border-radius:50%; background:rgba(255,255,255,0.05); display:flex; align-items:center; justify-content:center; cursor:pointer; }
.time-dev-btn text { font-size:14px; }
.time-dev-hint { margin-top:8px; }
.time-dev-hint text { color:rgba(255,255,255,0.3); font-size:10px; }
[data-theme="white"] .time-inp { background:#f9fafb; border-color:#e5e7eb; color:#1a1a2e; }
[data-theme="white"] .time-to { color:#9ca3af; }
[data-theme="white"] .time-dev-btn { background:#f3f4f6; }

.divider { height:1px; background:linear-gradient(90deg,transparent,rgba(0,210,255,0.3),transparent); margin:12px 0; }
.b-section { }
.b-section.locked { opacity:0.25; pointer-events:none; }
.lock-tip { text-align:center; color:rgba(255,255,255,0.4); font-size:12px; display:block; margin-top:6px; }

.picker-panel { padding:16px 14px; margin-bottom:12px; background:rgba(13,23,40,0.6); box-shadow:0 0 24px rgba(0,210,255,0.08),inset 0 0 40px rgba(0,210,255,0.02); }
[data-augmented-ui].picker-panel { --aug-border-bg:rgba(0,210,255,0.35); --aug-border-all:2px; --aug-clip-tl:12px; --aug-clip-tr:12px; --aug-clip-br:12px; --aug-clip-bl:12px; }
[data-augmented-ui].btn-checkin { --aug-border-bg:rgba(0,210,255,0.3); --aug-border-all:1px; --aug-clip-tl:10px; --aug-clip-br:10px; }
.picker-panel-header { display:flex; align-items:center; justify-content:center; gap:8px; margin-bottom:12px; }
.pph-dot { color:#00d2ff; font-size:8px; }
.pph-title { color:rgba(255,255,255,0.5); font-size:11px; letter-spacing:0.1em; text-transform:uppercase; }

.picker-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:6px; }
.picker-item { background:rgba(200,210,230,0.25); border-radius:8px; padding:12px 4px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.1); transition:all 0.2s; opacity:0; animation:matrixReveal 0.5s ease-out forwards; }
.picker-item:nth-child(1),.picker-item:nth-child(2),.picker-item:nth-child(3),.picker-item:nth-child(4) { animation-delay:0.05s; }
.picker-item:nth-child(5),.picker-item:nth-child(6),.picker-item:nth-child(7),.picker-item:nth-child(8) { animation-delay:0.15s; }
.picker-item:nth-child(9),.picker-item:nth-child(10),.picker-item:nth-child(11),.picker-item:nth-child(12) { animation-delay:0.25s; }
.picker-item:nth-child(13) { animation-delay:0.35s; }
@keyframes matrixReveal {
  0% { opacity:0; transform:translateY(-8px) scale(0.95); }
  60% { opacity:0.6; }
  100% { opacity:1; transform:translateY(0) scale(1); }
}
.picker-item:active { border-color:#00d2ff; transform:scale(0.96); }
.pi-text { color:#fff; font-size:11px; font-weight:600; letter-spacing:0.02em; }
.picker-item.active { border-color:#00d2ff; background:#0088cc; box-shadow:0 0 20px rgba(0,210,255,0.35),inset 0 0 10px rgba(0,0,0,0.15); }
.picker-item.active .pi-text { color:#fff; text-shadow:0 0 6px rgba(0,210,255,0.5); }

.form-card { background:#1a2840; border:2px solid rgba(0,210,255,0.5); border-radius:12px; padding:18px; margin-bottom:10px; position:relative; box-shadow:0 0 20px rgba(0,210,255,0.12), inset 0 0 30px rgba(0,210,255,0.02); clip-path:polygon(10px 0,100% 0,100% calc(100% - 10px),calc(100% - 10px) 100%,0 100%,0 10px); animation:scanDown 0.4s cubic-bezier(0.25,0.8,0.25,1) both; }
@keyframes scanDown {
  0% { clip-path:polygon(10px 0,100% 0,100% 4px,calc(100% - 10px) 4px,0 4px,0 4px); opacity:0.3; box-shadow:0 0 60px rgba(0,210,255,0.4); }
  50% { box-shadow:0 0 40px rgba(0,210,255,0.3); }
  100% { clip-path:polygon(10px 0,100% 0,100% calc(100% - 10px),calc(100% - 10px) 100%,0 100%,0 10px); opacity:1; box-shadow:0 0 20px rgba(0,210,255,0.12); }
}
.scan-line { position:absolute; top:0; left:8%; width:84%; height:1px; background:linear-gradient(90deg,transparent,#00d2ff,transparent); animation:scanLine 0.4s cubic-bezier(0.25,0.8,0.25,1) forwards; pointer-events:none; z-index:1; }
@keyframes scanLine {
  0% { top:0; opacity:1; }
  100% { top:100%; opacity:0; }
}
.form-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:14px; }
.form-title { color:#fff; font-size:14px; font-weight:700; }
.form-del { color:rgba(255,255,255,0.4); font-size:18px; cursor:pointer; padding:2px 6px; }
.form-del:active { color:#ff6b6b; }
.form-row { display:flex; align-items:center; gap:10px; margin-bottom:10px; }
.form-label { color:rgba(255,255,255,0.5); font-size:13px; width:110px; flex-shrink:0; }
.form-input { flex:1; background:#fff; border:2px solid rgba(0,210,255,0.2); border-radius:10px; padding:10px 12px; font-size:13px; color:#0b111e; }
.form-textarea { flex:1; background:#fff; border:2px solid rgba(0,210,255,0.2); border-radius:10px; padding:10px 12px; font-size:13px; color:#0b111e; height:60px; }
.form-tags { display:flex; flex-wrap:wrap; gap:6px; flex:1; }
.ftag { padding:6px 14px; border-radius:8px; background:rgba(255,255,255,0.08); color:rgba(255,255,255,0.6); font-size:12px; border:1px solid rgba(0,210,255,0.2); cursor:pointer; transition:all 0.15s; }
.ftag.on { background:#0088cc; border-color:#00d2ff; color:#fff; box-shadow:0 0 10px rgba(0,210,255,0.2); }
.form-inline { display:flex; align-items:center; gap:6px; flex:1; }
.form-file-wrap { flex:1; }
.file-btn { background:rgba(0,210,255,0.1); border:1px dashed rgba(0,210,255,0.25); border-radius:10px; padding:10px; text-align:center; cursor:pointer; }
.file-btn text { color:#00d2ff; font-size:12px; }
.file-hint { color:rgba(255,255,255,0.3); font-size:10px; display:block; margin-top:4px; text-align:center; }
.file-previews { display:flex; flex-wrap:wrap; gap:6px; margin-top:6px; }
.file-preview { position:relative; width:60px; height:60px; border-radius:8px; overflow:hidden; }
.preview-img, .preview-video { width:100%; height:100%; object-fit:cover; }
.file-del { position:absolute; top:2px; right:2px; background:rgba(0,0,0,0.6); color:#fff; font-size:10px; width:16px; height:16px; border-radius:50%; display:flex; align-items:center; justify-content:center; cursor:pointer; }
[data-theme="white"] .file-btn { background:#f3f4f6; border-color:#e5e7eb; }
[data-theme="white"] .file-btn text { color:#2563eb; }
[data-theme="white"] .file-hint { color:#9ca3af; }

.form-input.short { width:80px; flex:none; background:#fff; color:#0b111e; }
.form-inline .form-unit { color:rgba(255,255,255,0.7); }
.form-unit { color:rgba(255,255,255,0.5); font-size:12px; }

.score-panel { border:2px solid rgba(0,210,255,0.2); border-radius:10px; padding:14px; margin-bottom:12px; background:rgba(13,23,40,0.5); }
.score-header { display:flex; align-items:center; justify-content:center; gap:8px; margin-bottom:10px; }
.score-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:6px; }
.score-item { background:rgba(200,210,230,0.1); border-radius:8px; padding:10px 6px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06); transition:all 0.2s; opacity:0; animation:popIn 0.4s cubic-bezier(0.34,1.56,0.64,1) forwards; }
.score-item:nth-child(1) { animation-delay:0.05s; }
.score-item:nth-child(2) { animation-delay:0.12s; }
.score-item:nth-child(3) { animation-delay:0.19s; }
.score-item:nth-child(4) { animation-delay:0.26s; }
.score-item:nth-child(5) { animation-delay:0.33s; }
.score-item:nth-child(6) { animation-delay:0.40s; }
.score-item:active { transform:scale(0.96); }
.score-item.active { border-color:#00d2ff; background:rgba(0,136,204,0.3); box-shadow:0 0 12px rgba(0,210,255,0.15); }
/* White theme */
[data-theme="white"] .app { background:#f0f2f5; }
[data-theme="white"] .nav-title { color:#1a1a2e; }
[data-theme="white"] .nav-back { background:#fff; border-color:#e5e7eb; }
[data-theme="white"] .card { background:#fff; border:2px solid #e5e7eb; box-shadow:0 2px 12px rgba(0,0,0,0.04); }
[data-theme="white"] .card::before, [data-theme="white"] .card::after { border-color:#2563eb; }
[data-theme="white"] .plan-label { color:#2563eb; }
[data-theme="white"] .section-title { color:#1a1a2e; }
[data-theme="white"] .step { background:#fff; border-left-color:#2563eb; box-shadow:0 2px 8px rgba(0,0,0,0.03); }
[data-theme="white"] .step-num { background:#2563eb; }
[data-theme="white"] .step-label { color:#1a1a2e; }
[data-theme="white"] .step-box { background:#f9fafb; border-color:#e5e7eb; color:#1a1a2e; }
[data-theme="white"] .step-time { color:#9ca3af; }
[data-theme="white"] .btn-checkin { background:linear-gradient(135deg,#2563eb,#1d4ed8); }
[data-theme="white"] .btn-checkin text { color:#fff; }
[data-theme="white"] .summary-card { border-color:#e5e7eb; }
[data-theme="white"] .summary-label { color:#6b7280; }
[data-theme="white"] .summary-text { color:#9ca3af; }
[data-theme="white"] .summary-more { color:#2563eb; }
[data-theme="white"] .picker-panel { background:#fff; border-color:#e5e7eb; box-shadow:0 4px 24px rgba(0,0,0,0.06); }
[data-theme="white"] .pph-dot { color:#2563eb; }
[data-theme="white"] .pph-title { color:#6b7280; }
[data-theme="white"] .picker-item { background:#f3f4f6; border-color:#e5e7eb; }
[data-theme="white"] .pi-text { color:#374151; }
[data-theme="white"] .picker-item.active { background:#2563eb; border-color:#2563eb; }
[data-theme="white"] .picker-item.active .pi-text { color:#fff; text-shadow:none; }
[data-theme="white"] .form-card { background:#fff; border-color:#2563eb; box-shadow:0 4px 20px rgba(0,0,0,0.06); }
[data-theme="white"] .form-title { color:#1a1a2e; }
[data-theme="white"] .form-label { color:#6b7280; }
[data-theme="white"] .form-input { background:#f9fafb; border-color:#e5e7eb; color:#1a1a2e; }
[data-theme="white"] .form-textarea { background:#f9fafb; border-color:#e5e7eb; color:#1a1a2e; }
[data-theme="white"] .form-input.short { background:#fff; }
[data-theme="white"] .ftag { background:#f3f4f6; color:#6b7280; border-color:#e5e7eb; }
[data-theme="white"] .ftag.on { background:#2563eb; border-color:#2563eb; color:#fff; }
[data-theme="white"] .score-panel { background:#fff; border-color:#e5e7eb; box-shadow:0 4px 20px rgba(0,0,0,0.04); }
[data-theme="white"] .score-item { background:#f3f4f6; border-color:#e5e7eb; }
[data-theme="white"] .score-item.active { background:rgba(37,99,235,0.08); border-color:#2563eb; }
[data-theme="white"] .si-pct { color:#2563eb; }
[data-theme="white"] .si-desc { color:#6b7280; }
[data-theme="white"] .score-item.active .si-desc { color:#1a1a2e; }
[data-theme="white"] .divider { background:#e5e7eb; }
[data-theme="white"] .picker-overlay { background:rgba(0,0,0,0.4); }
[data-theme="white"] .picker-card { background:#fff; border-color:#e5e7eb; }
[data-theme="white"] .picker-title { color:#1a1a2e; }
[data-theme="white"] .si-text { color:#1a1a2e; }
[data-theme="white"] .lock-tip { color:#9ca3af; }
[data-theme="white"] .step-label.dim-text { color:#d1d5db; }
[data-theme="white"] .step-time.dim-text { color:#9ca3af; }
[data-theme="white"] .step.dim-step { border-left-color:rgba(0,0,0,0.06); }
[data-theme="white"] .step.dim-step::after { border-color:rgba(0,0,0,0.06); }
[data-theme="white"] .step-num.dim { background:#d1d5db; }
[data-theme="white"] .b-section.locked .section-title { color:#d1d5db; }
[data-theme="white"] .section-title.dim { color:#d1d5db; }
[data-theme="white"] .step-num { color:#fff; }
[data-theme="white"] .si-edit { color:#2563eb; }
[data-theme="white"] .si-del { color:#9ca3af; }
[data-theme="white"] .si-del:active { color:#ef4444; }
[data-theme="white"] .form-del { color:#9ca3af; }
[data-theme="white"] .form-del:active { color:#ef4444; }
[data-theme="white"] .submitted-item { border-bottom-color:#e5e7eb; }
[data-theme="white"] .step-content .step-time { color:#9ca3af; }
[data-theme="white"] .step-box.dim-box { opacity:0.6; }

@keyframes popIn {
  0% { opacity:0; transform:scale(0.5) translateY(10px); }
  100% { opacity:1; transform:scale(1) translateY(0); }
}
.si-pct { color:#00d2ff; font-size:18px; font-weight:800; display:block; }
.si-emoji { font-size:16px; display:block; margin:2px 0; }
.si-desc { color:rgba(255,255,255,0.5); font-size:9px; line-height:1.3; display:block; }
.score-item.active .si-desc { color:#fff; }

.card-enter-active { animation:scanDown 0.4s cubic-bezier(0.25,0.8,0.25,1); }
.card-leave-active { animation:cardOut 0.25s ease-in forwards; max-height:200px; overflow:hidden; }
.card-leave-to { max-height:0; padding-top:0; padding-bottom:0; margin-bottom:0; opacity:0; }
@keyframes cardOut {
  0% { clip-path:polygon(10px 0,100% 0,100% calc(100% - 10px),calc(100% - 10px) 100%,0 100%,0 10px); opacity:1; }
  100% { clip-path:polygon(10px 0,100% 0,100% 4px,calc(100% - 10px) 4px,0 4px,0 4px); opacity:0; }
}
.player-overlay { position:fixed; inset:0; z-index:600; background:rgba(0,0,0,0.85); display:flex; align-items:center; justify-content:center; padding:16px; }
.player-card { background:var(--bg-card,#1a2840); border:1px solid rgba(0,210,255,0.2); border-radius:16px; padding:16px; width:100%; max-width:420px; }
.player-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
.player-title { color:#fff; font-size:15px; font-weight:600; }
.player-close { color:rgba(255,255,255,0.5); font-size:20px; cursor:pointer; padding:4px 8px; }
.player-body { }
[data-theme="white"] .player-overlay { background:rgba(0,0,0,0.6); }
[data-theme="white"] .player-card { background:#fff; border-color:#e5e7eb; }
[data-theme="white"] .player-title { color:#1a1a2e; }
[data-theme="white"] .player-close { color:#9ca3af; }

.pulse-out { animation:pulseRing 0.5s ease-out; }
@keyframes pulseRing {
  0% { box-shadow:0 0 0 0 rgba(0,210,255,0.5); }
  100% { box-shadow:0 0 0 50px rgba(0,210,255,0); }
}
.spark { animation:btnSpark 0.4s ease-out; }
.warn-flash { animation:warnFlash 0.6s ease-out; }
@keyframes warnFlash {
  0%,100% { box-shadow:0 0 0 0 rgba(255,68,68,0); background:linear-gradient(135deg,rgba(0,210,255,0.25),rgba(0,136,204,0.25)); }
  20% { box-shadow:0 0 30px rgba(255,68,68,0.6),0 0 0 8px rgba(255,68,68,0.2); background:linear-gradient(135deg,rgba(255,68,68,0.3),rgba(255,68,68,0.2)); }
  40% { box-shadow:0 0 0 0 rgba(255,68,68,0); }
  60% { box-shadow:0 0 25px rgba(255,68,68,0.4),0 0 0 6px rgba(255,68,68,0.15); background:linear-gradient(135deg,rgba(255,68,68,0.25),rgba(255,68,68,0.15)); }
}
@keyframes btnSpark {
  0% { box-shadow:0 0 0 0 rgba(0,210,255,0.6), inset 0 0 30px rgba(0,210,255,0.3); transform:scale(1.02); }
  40% { box-shadow:0 0 20px rgba(0,210,255,0.3), 0 0 0 8px rgba(0,210,255,0.15); }
  100% { box-shadow:0 0 10px rgba(0,210,255,0.15); transform:scale(1); }
}
</style>
