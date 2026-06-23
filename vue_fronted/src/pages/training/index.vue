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
      <view class="card plan-card">
        <text class="plan-label">📋 方案</text>
        <text class="plan-text">训练内容 + 验收标准</text>
      </view>

      <!-- Training A -->
      <text class="section-title">训练 A</text>

      <view class="step">
        <view class="step-num">1</view>
        <view class="step-content">
          <text class="step-label">视频训练</text>
          <view class="step-box">🎬 训练用视频</view>
          <text class="step-time">约 X 分钟</text>
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

      <view class="btn-checkin" @click="showPicker = !showPicker">
        <text>✅ 训练 A 打卡</text>
      </view>

      <!-- 3x3 能力选择 -->
      <view v-if="showPicker" class="picker-grid">
        <view v-for="item in abilities" :key="item" class="picker-item" :class="{ active: selected === item }" @click="selectAbility(item)">
          <text class="pi-text">{{ item }}</text>
        </view>
      </view>

      <!-- 训练记录表单：极速运算 -->
      <view v-if="selected === '极速运算'" class="form-card">
        <text class="form-title">⚡ 极速运算 — 训练记录</text>
        <view class="form-row">
          <text class="form-label">时间</text>
          <input class="form-input" v-model="form.time" placeholder="训练时长（分钟），如：15" type="number" />
        </view>
        <view class="form-row">
          <text class="form-label">内容</text>
          <view class="form-tags">
            <text class="ftag" :class="{ on: form.tag === '加减法' }" @click="form.tag = '加减法'">加减法</text>
            <text class="ftag" :class="{ on: form.tag === '乘除法' }" @click="form.tag = '乘除法'">乘除法</text>
            <text class="ftag" :class="{ on: form.tag === '混合运算' }" @click="form.tag = '混合运算'">混合运算</text>
            <text class="ftag" :class="{ on: form.tag === '口算' }" @click="form.tag = '口算'">口算</text>
          </view>
        </view>
        <view class="form-row">
          <text class="form-label">结果</text>
          <view class="form-inline">
            <input class="form-input short" v-model="form.count" placeholder="完成题数" type="number" />
            <text class="form-unit">题</text>
            <input class="form-input short" v-model="form.accuracy" placeholder="正确率" type="number" />
            <text class="form-unit">%</text>
          </view>
        </view>
        <view class="btn-checkin" @click="submitForm">
          <text>✅ 提交打卡</text>
        </view>
      </view>

      <!-- 训练记录表单：通用 -->
      <view v-if="selected && selected !== '极速运算'" class="form-card">
        <text class="form-title">{{ selected }} — 训练记录</text>
        <view class="form-row">
          <text class="form-label">时间</text>
          <input class="form-input" v-model="form.time" placeholder="训练时长/分钟" />
        </view>
        <view class="form-row">
          <text class="form-label">内容</text>
          <textarea class="form-textarea" v-model="form.content" placeholder="训练了什么内容？" />
        </view>
        <view class="form-row">
          <text class="form-label">结果</text>
          <textarea class="form-textarea" v-model="form.result" placeholder="训练效果如何？" />
        </view>
        <view class="btn-checkin" @click="submitForm">
          <text>✅ 提交打卡</text>
        </view>
      </view>

      <!-- Summary -->
      <view class="card summary-card">
        <text class="summary-label">📝 打卡的训练总结</text>
        <text class="summary-text">{{ summary }}</text>
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
const summary = ref('完成训练后自动生成今日总结...')
const showPicker = ref(false)
const selected = ref('')
const form = ref({ time: '', content: '', result: '', tag: '', count: '', accuracy: '' })
const abilities = ['极速运算','多元感知','无界外语','吸星大法','三错一讲','极速学习','高效作业','超脑阅读','影像追忆']

function selectAbility(item) {
  if (selected.value === item) {
    selected.value = ''
    return
  }
  selected.value = item
  form.value = { time: '', content: '', result: '', tag: '', count: '', accuracy: '' }
}

function submitForm() {
  bUnlocked.value = true
  bTip.value = '✅ A 已完成，开始训练 B'
  if (selected.value === '极速运算') {
    summary.value = '极速运算：' + form.value.tag + '，' + form.value.time + '分钟，' + form.value.count + '题，正确率' + form.value.accuracy + '%'
  } else {
    summary.value = selected.value + '：' + form.value.time + ' — ' + form.value.content + ' — 结果：' + form.value.result
  }
  selected.value = ''
  showPicker.value = false
  uni.showToast({ title: '✅ 训练 A 打卡成功！', icon: 'none' })
}

function goBack() {
  uni.navigateBack({ delta: 1 })
}
</script>

<style scoped>
.app { height:100vh; max-width:480px; margin:0 auto; background:var(--bg); font-family:-apple-system,"PingFang SC",sans-serif; display:flex; flex-direction:column; position:relative; overflow:hidden; }
.nav { display:flex; align-items:center; padding:14px 14px 0; }
.nav-back { width:36px; height:36px; border-radius:50%; background:var(--bg-card); display:flex; align-items:center; justify-content:center; cursor:pointer; }
.nav-title { flex:1; text-align:center; color:var(--text); font-size:16px; font-weight:600; }
.nav-spacer { width:36px; }
.body { flex:1; overflow-y:auto; padding:12px 14px 0; }

.card { background:var(--bg-card); border-radius:14px; padding:14px 16px; margin-bottom:12px; }
.plan-card { }
.plan-label { color:var(--accent); font-size:12px; font-weight:600; display:block; margin-bottom:4px; }
.plan-text { color:var(--text-sub); font-size:13px; line-height:1.6; }

.section-title { color:var(--text); font-size:14px; font-weight:700; margin-bottom:8px; display:block; }
.section-title.dim { color:var(--text-hint); }

.step { background:var(--bg-card); border-radius:12px; padding:14px; display:flex; gap:10px; align-items:flex-start; border-left:3px solid var(--accent); margin-bottom:8px; }
.step.dim-step { border-left-color:var(--border); }
.step-num { width:22px; height:22px; border-radius:50%; background:var(--accent); color:#fff; display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:700; flex-shrink:0; }
.step-num.dim { background:var(--border); }
.step-content { flex:1; }
.step-label { color:var(--text); font-size:13px; font-weight:500; display:block; margin-bottom:6px; }
.step-label.dim-text { color:var(--text-hint); }
.step-box { background:var(--bg-input); border-radius:10px; padding:20px 14px; text-align:center; font-size:24px; color:var(--text-sub); }
.step-box.dim-box { opacity:0.5; }
.step-time { color:var(--text-hint); font-size:10px; text-align:center; display:block; margin-top:4px; }
.step-time.dim-text { color:var(--text-hint); }

.btn-checkin { background:linear-gradient(135deg,var(--accent),#3b8bff); border-radius:12px; padding:14px; text-align:center; margin-bottom:12px; cursor:pointer; }
.btn-checkin text { color:#fff; font-size:15px; font-weight:600; }
.btn-checkin:active { opacity:0.85; }

.summary-card { border:1px dashed var(--border); }
.summary-label { color:var(--text-dim); font-size:12px; font-weight:500; display:block; margin-bottom:4px; }
.summary-text { color:var(--text-hint); font-size:12px; line-height:1.6; }

.divider { height:1px; background:var(--border); margin:8px 0 12px; }
.b-section { }
.b-section.locked { opacity:0.35; pointer-events:none; }
.lock-tip { text-align:center; color:var(--text-hint); font-size:12px; display:block; margin-top:6px; }

/* Picker Grid */
.picker-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-bottom:12px; }
.picker-item { background:var(--bg-card); border-radius:14px; padding:14px 6px; text-align:center; cursor:pointer; border:1.5px solid var(--border); transition:all 0.15s; }
.picker-item:active { border-color:var(--accent); background:var(--accent-bg); transform:scale(0.96); }
.pi-text { color:var(--text-sub); font-size:12px; font-weight:600; }
.picker-item.active { border-color:var(--accent); background:var(--accent-bg); }

/* Form */
.form-card { background:var(--bg-card); border-radius:16px; padding:18px; margin-bottom:12px; border:1px solid var(--accent); }
.form-title { color:var(--text); font-size:14px; font-weight:700; display:block; margin-bottom:14px; }
.form-row { display:flex; align-items:center; gap:10px; margin-bottom:10px; }
.form-label { color:var(--text-dim); font-size:13px; width:110px; flex-shrink:0; }
.form-input { flex:1; background:var(--bg-input); border-radius:10px; padding:10px 12px; font-size:13px; color:var(--text); border:1px solid var(--border); }
.form-textarea { flex:1; background:var(--bg-input); border-radius:10px; padding:10px 12px; font-size:13px; color:var(--text); border:1px solid var(--border); height:60px; }
.form-placeholder { color:var(--text-hint); font-size:13px; text-align:center; display:block; padding:20px 0; }
.form-tags { display:flex; flex-wrap:wrap; gap:6px; flex:1; }
.ftag { padding:6px 14px; border-radius:10px; background:var(--bg-input); color:var(--text-dim); font-size:12px; border:1px solid var(--border); cursor:pointer; transition:all 0.15s; }
.ftag.on { background:var(--accent-bg); border-color:var(--accent); color:var(--accent); }
.form-inline { display:flex; align-items:center; gap:6px; flex:1; }
.form-input.short { width:80px; flex:none; }
.form-unit { color:var(--text-dim); font-size:12px; }

/* Player */
.player-overlay { position:fixed; inset:0; z-index:500; background:rgba(0,0,0,0.8); display:flex; align-items:center; justify-content:center; padding:16px; }
.player-card { background:var(--bg-card); border-radius:20px; padding:20px; width:100%; max-width:400px; }
.player-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:14px; }
.player-title { color:var(--text); font-size:16px; font-weight:700; }
.player-close { color:var(--text-dim); font-size:20px; cursor:pointer; padding:4px; }
.player-video { width:100%; border-radius:12px; background:#000; }
.player-audio-wrap { text-align:center; padding:20px 0; }
.pa-icon { font-size:48px; display:block; margin-bottom:12px; }
.player-audio { width:100%; margin-top:8px; }
.player-empty { text-align:center; padding:30px 10px; }
.pe-text { color:var(--text); font-size:15px; display:block; margin-bottom:8px; }
.pe-hint { color:var(--text-dim); font-size:12px; display:block; margin-bottom:12px; }
.pe-input { background:var(--bg-input); border-radius:10px; padding:10px 14px; color:var(--text); font-size:13px; border:1px solid var(--border); width:100%; }
.player-actions { margin-top:14px; }
.player-url-row { margin-top:8px; }
</style>
