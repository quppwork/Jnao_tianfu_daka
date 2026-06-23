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
        <text class="plan-label">📋 方案</text>
        <text class="plan-text">训练内容 + 验收标准</text>
      </view>

      <!-- Training A -->
      <text class="section-title">训练 A</text>

      <view class="step step-ready" @click="playVideo">
        <view class="step-num step-num-ready">1</view>
        <view class="step-content">
          <text class="step-label">视频训练</text>
          <view class="step-box step-box-ready">🎬 五者天赋视频</view>
          <text class="step-time ready-text">▶ 点击播放</text>
        </view>
      </view>

      <view class="step">
        <view class="step-num">2</view>
        <view class="step-content">
          <text class="step-label">音频训练</text>
          <view class="step-box">🎧 训练用音频</view>
          <text class="step-time">约 X 分钟</text>
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
        </template>
      </view>

      </TransitionGroup>

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

  </view>
</template>

<script setup>
import { ref } from 'vue'

const bUnlocked = ref(false)
const bTip = ref('⚠ 训练 A 未完成，B 暂不开放')
const showPicker = ref(false)
const showSummary = ref(false)
const submittedCards = ref([])
const cards = ref([])
const abilities = ['高效作业','超脑阅读','扫描速记','影像追忆','数学奥秘','极速运算','极速学习','英语奥秘','精力恢复','文科奥秘','理科奥秘','考前解压','天赋绘画','音乐灵感','棋类专注','我是冠军']

function hasCard(name) { return cards.value.some(c => c.name === name) }

function toggleCard(name) {
  const idx = cards.value.findIndex(c => c.name === name)
  if (idx >= 0) {
    cards.value.splice(idx, 1)
  } else {
    cards.value.push({ name, time: '', content: '', result: '', tag: '', count: '', accuracy: '' })
  }
}

function removeCard(idx) { cards.value.splice(idx, 1) }

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

function playVideo() {
  window.open('/static/training_video.mp4', '_blank')
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
.plan-label { color:#00d2ff; font-size:12px; font-weight:600; display:block; margin-bottom:4px; }
.plan-text { color:#fff; font-size:13px; line-height:1.6; }

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
.picker-item:nth-child(13),.picker-item:nth-child(14),.picker-item:nth-child(15),.picker-item:nth-child(16) { animation-delay:0.35s; }
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
.form-input.short { width:80px; flex:none; background:#fff; color:#0b111e; }
.form-inline .form-unit { color:rgba(255,255,255,0.7); }
.form-unit { color:rgba(255,255,255,0.5); font-size:12px; }

.card-enter-active { animation:scanDown 0.4s cubic-bezier(0.25,0.8,0.25,1); }
.card-leave-active { animation:cardOut 0.25s ease-in forwards; max-height:200px; overflow:hidden; }
.card-leave-to { max-height:0; padding-top:0; padding-bottom:0; margin-bottom:0; opacity:0; }
@keyframes cardOut {
  0% { clip-path:polygon(10px 0,100% 0,100% calc(100% - 10px),calc(100% - 10px) 100%,0 100%,0 10px); opacity:1; }
  100% { clip-path:polygon(10px 0,100% 0,100% 4px,calc(100% - 10px) 4px,0 4px,0 4px); opacity:0; }
}
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
