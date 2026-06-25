<template>
  <view class="app">
    <!-- Nav -->
    <view class="nav">
      <view class="nav-back" @tap="goBack">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#8b949e" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      </view>
      <text class="nav-title">天赋测试</text>
      <view class="nav-spacer"></view>
    </view>

    <!-- ===== PRE-TEST PHASES ===== -->
    <template v-if="isPreTest">
      <!-- DOOR -->
      <view v-if="phase === 'door'" class="phase" key="door">
        <view class="phase-inner">
          <text class="msg-title">首先我们来打开 Jnao 的大门，测试一下天赋吧！</text>
          <text class="msg-sub">以下您将完成 35 道题目，请问你想进行哪种类型的天赋测试呢？</text>
          <view class="card-row">
            <view class="pcard pcard-in" style="animation-delay:0.4s" @tap="handleChoice('孩子测试')">
              <view class="pcard-icon-wrap">
                <svg viewBox="0 0 48 48" width="36" height="36" fill="none" stroke="#58a6ff" stroke-width="2"><circle cx="16" cy="16" r="8"/><circle cx="34" cy="14" r="6"/><path d="M4 44c0-8.8 5.4-16 12-16s12 7.2 12 16"/><path d="M30 42c0-5.3 3.6-9.7 8-9.7s8 4.4 8 9.7"/></svg>
              </view>
              <text class="pcard-title">孩子测试</text>
              <text class="pcard-sub">家长辅助完成 / 了解孩子的天赋</text>
            </view>
            <view class="pcard pcard-in" style="animation-delay:0.55s" @tap="handleChoice('成人测试')">
              <view class="pcard-icon-wrap">
                <svg viewBox="0 0 48 48" width="36" height="36" fill="none" stroke="#58a6ff" stroke-width="2"><circle cx="24" cy="15" r="9"/><path d="M8 44c0-8.8 7.2-16 16-16s16 7.2 16 16"/></svg>
              </view>
              <text class="pcard-title">成人测试</text>
              <text class="pcard-sub">自行评估完成 / 探索内在潜能</text>
            </view>
          </view>
        </view>
      </view>

      <!-- AGE GATE -->
      <view v-if="phase === 'ageGate'" class="phase" key="ageGate">
        <view class="phase-inner">
          <text class="msg-title">注意！请确认您的孩子是否满18岁</text>
          <view class="card-row">
            <view class="pcard pcard-blue pcard-in" @tap="handleChoice('已满18岁')">
              <view class="pcard-icon-wrap"><svg viewBox="0 0 48 48" width="36" height="36" fill="none" stroke="#58a6ff" stroke-width="2"><circle cx="24" cy="15" r="9"/><path d="M8 44c0-8.8 7.2-16 16-16s16 7.2 16 16"/></svg></view>
              <text class="pcard-title">已满18岁</text>
              <text class="pcard-sub">进入成人测试</text>
            </view>
            <view class="pcard pcard-gold pcard-in" @tap="handleChoice('未满18岁')">
              <view class="pcard-icon-wrap pcard-icon-gold"><svg viewBox="0 0 48 48" width="36" height="36" fill="none" stroke="#f0a040" stroke-width="2"><circle cx="16" cy="16" r="8"/><circle cx="34" cy="14" r="6"/><path d="M4 44c0-8.8 5.4-16 12-16s12 7.2 12 16"/><path d="M30 42c0-5.3 3.6-9.7 8-9.7s8 4.4 8 9.7"/></svg></view>
              <text class="pcard-title">未满18岁</text>
              <text class="pcard-sub">家长辅助完成孩子测试</text>
            </view>
          </view>
        </view>
        <view v-if="ageGateNotice" class="notice-overlay" @tap="dismissNotice">
          <view class="notice-card"><text class="notice-text">您的孩子未满18岁，请您帮助您的孩子完成测试，否则测试可能会与事实产生误差</text></view>
        </view>
      </view>

      <!-- CONFIRM -->
      <view v-if="phase === 'confirm'" class="phase" key="confirm">
        <view class="phase-inner">
          <text class="msg-title">好的，{{ testType || '成人' }}测试。</text>
          <text class="msg-sub">共 35 道题，每题两个选项：「完全符合」或「有差异」。根据实际情况选择即可，大约需要 10-15 分钟。</text>
          <text class="msg-ready">准备好了吗？</text>
          <view class="card-row">
            <view class="pcard pcard-blue pcard-in" @tap="handleChoice('准备好了，开始吧')">
              <text class="pcard-emoji">✅</text>
              <text class="pcard-title">准备好了，开始吧</text>
            </view>
            <view class="pcard pcard-gray pcard-in" @tap="handleChoice('稍后再说')">
              <text class="pcard-emoji">⏸</text>
              <text class="pcard-title" style="color:var(--text-dim);">稍后再说</text>
            </view>
          </view>
        </view>
      </view>
    </template>

    <!-- ===== TESTING PHASE ===== -->
    <template v-if="phase === 'testing' && currentQuestion">
      <!-- Top bar -->
      <view class="test-top">
        <text class="test-type-tag">{{ testType === '成人' ? '成人测试' : '孩子测试' }}</text>
        <view class="progress-bar">
          <view class="progress-fill" :style="{ width: ((currentQIndex + 1) / 35 * 100) + '%' }"></view>
        </view>
        <text class="progress-text">{{ currentQIndex + 1 }}/35</text>
      </view>

      <!-- Background + Card -->
      <view class="test-body" :style="{ background: currentBg }">
        <view class="test-body-inner">
          <!-- Undo card -->
          <view v-if="prevCard && !undoMode" class="undo-card" @tap="handleUndo">
            <view class="undo-info">
              <text class="undo-label">第 {{ prevCard.idx }} 题</text>
              <text class="undo-answer">已答：{{ prevCard.answer }}</text>
            </view>
            <text class="undo-text">{{ prevCard.text }}</text>
            <view class="undo-overlay" :style="{ background: isLightTheme ? 'rgba(255,255,255,0.6)' : 'rgba(13,17,23,0.7)' }"><text>↩ 点击撤回</text></view>
          </view>

          <!-- Question Card -->
          <view class="q-card">
            <text class="q-badge">第 {{ currentQIndex + 1 }} 题</text>
            <view class="countdown-row">
              <view class="cd-ring-wrap">
                <svg viewBox="0 0 36 36" class="cd-svg">
                  <circle cx="18" cy="18" r="15.5" fill="none" stroke="rgba(88,166,255,0.12)" stroke-width="2.5"/>
                  <circle cx="18" cy="18" r="15.5" fill="none" :stroke="cdUrgent ? '#ff6b6b' : '#58a6ff'" stroke-width="2.5" stroke-linecap="round"
                    :stroke-dasharray="cdPct + ' 100'" pathLength="100"/>
                </svg>
                <text class="cd-num" :class="{ 'cd-urgent': cdUrgent }">{{ cdLeft }}</text>
              </view>
              <view class="cd-info">
                <text class="cd-hint" :class="{ 'cd-urgent': cdUrgent }">{{ cdHint }}</text>
                <view class="cd-bar"><view class="cd-bar-fill" :class="{ 'cd-warn': cdLeft <= 5, 'cd-danger': cdLeft <= 3 }" :style="{ width: cdPct + '%' }"></view></view>
              </view>
            </view>
            <text class="q-text">{{ currentQuestion.text }}</text>
            <view v-if="undoMode && currentQuestion.previous_answer" class="q-prev">
              <text>上次选择：{{ currentQuestion.previous_answer }}</text>
            </view>
            <view class="q-choices">
              <view class="q-btn q-btn-yes" @tap="handleAnswer('完全符合')"><text>完全符合</text></view>
              <view class="q-btn q-btn-no" @tap="handleAnswer('有差异')"><text>有差异</text></view>
            </view>
          </view>

          <view class="ai-hint"><text>🤖 {{ '凭第一感觉选择就好～' }}</text></view>
        </view>
      </view>
    </template>

    <!-- ===== COMPLETED ===== -->
    <view v-if="phase === 'completed'" class="phase" key="completed">
      <view class="phase-inner" style="padding-top:20vh;">
        <!-- Animation -->
        <view class="complete-anim">
          <view class="ca-check">✓</view>
        </view>
        <text v-if="compPhase >= 1" class="msg-title ca-fade">35 题已完成</text>
        <text v-if="compPhase >= 1" class="msg-sub ca-fade" style="animation-delay:0.15s">AI 将为你生成专属天赋解读</text>

        <!-- Error -->
        <text v-if="submitError" class="submit-err">{{ submitError }}</text>

        <view v-if="compPhase >= 2" class="ca-fade" style="animation-delay:0.3s;margin-top:24px;">
          <view class="gen-btn" @click="doSubmitReport">
            <text>{{ submitting ? '生成中...' : '生成报告' }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- Toast -->
    <view v-if="toast.text" class="toast" :class="'toast-' + toast.variant">
      <text>{{ toast.text }}</text>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, nextTick, onBeforeUnmount, watch } from 'vue'
import {
  ensureChildUser,
  ensureJnaoUid,
  submitTalentReport,
} from '@/utils/userApi.js'

// ── State ──
const phase = ref('door')
const testType = ref(null)
const ageGateNotice = ref(false)
const submitting = ref(false)
const submitError = ref('')
const compPhase = ref(0)
const toast = ref({ text: '', variant: 'ack' })

// Testing state
const questionOrder = ref([])       // shuffled question IDs
const currentQIndex = ref(0)
const answers = ref({})             // { qid: '完全符合' | '有差异' }
const prevCard = ref(null)          // { idx, text, answer }
const undoMode = ref(false)
const tickRef = ref(0)
const cdLeft = ref(60)
const busy = ref(false)

const TOTAL = 35
const QUESTION_SEC = 60
const UNDO_SEC = 5

let noticeTimer = null
let cdTimer = null
let undoTimer = null
let toastTimer = null

// ── Questions (simplified — 105 in data file) ──
import questions from '../../data/questions.js'

function getQuestions(set) {
  return questions.filter(q => q.set === set)
}

// ── Background themes ──
const BG_DARK = ['#1a1530','#15202b','#1f2233','#1e1a2e','#221a28','#1a2528','#2a1a24','#1a2a24','#25201a','#202528','#1e2420','#1c2330','#23201e','#242026','#26221a','#1a2630','#1e242a','#281e24','#24221c','#1e2820','#202820','#262028','#1c2428','#2a1e1e','#28201c','#202228','#22221e','#241e28','#1e2822','#281a1a','#201a28','#1a2826','#261c20','#2a2020','#202628']
const BG_LIGHT = ['#f0e6ff','#e6f0ff','#ffe6f0','#e6ffe6','#fff5e6','#e6f5ff','#f5e6ff','#f0ffe6','#ffe6e6','#e6fff5','#f0e6f0','#e6e6ff','#fff0e6','#e6fff0','#ffe6ff','#f5f0e6','#e6f0f0','#ffefe6','#eff0e6','#e6efff','#f5e6e6','#e0f0e8','#f0e8f0','#e8f0f0','#f2e8e0','#e0e8f2','#f0f0e8','#e8e0f0','#e8f0e0','#f0e0e0','#e0e0f5','#e8f2f0','#f5e8f0','#e8f0f8','#f8f0e8']
function getBg(idx) {
  const isLight = document.documentElement.getAttribute('data-theme') === 'white'
  const arr = isLight ? BG_LIGHT : BG_DARK
  return 'linear-gradient(135deg,' + (isLight ? '#f8f9fa' : '#0d1117') + ',' + arr[idx % arr.length] + ')'
}
const currentBg = computed(() => getBg(currentQIndex.value))

// ── Current question ──
const currentQuestion = computed(() => {
  const qid = questionOrder.value[currentQIndex.value]
  if (!qid) return null
  const pool = getQuestions(testType.value === '成人' ? 'adult' : 'child')
  const q = pool.find(x => x.id === qid)
  return q ? {
    ...q,
    index: currentQIndex.value + 1,
    previous_answer: undoMode.value ? answers.value[qid] : null,
  } : null
})

const isPreTest = computed(() => ['door','ageGate','confirm'].includes(phase.value))
const isLightTheme = computed(() => document.documentElement.getAttribute('data-theme') === 'white')

// ── Countdown ──
const cdPct = computed(() => (cdLeft.value / QUESTION_SEC) * 100)
const cdUrgent = computed(() => cdLeft.value <= 5)
const cdHint = computed(() => {
  if (cdLeft.value <= 3) return '快选一个，凭直觉就好'
  if (cdLeft.value <= 5) return '时间不多了'
  return '凭第一感觉选择就好～'
})

function startCd() {
  stopCd()
  cdLeft.value = undoMode.value ? UNDO_SEC : QUESTION_SEC
  cdTimer = setInterval(() => {
    cdLeft.value--
    if (cdLeft.value <= 0) {
      stopCd()
      if (!busy.value) handleQuestionTimeout()
    }
  }, 1000)
}

function stopCd() {
  if (cdTimer) { clearInterval(cdTimer); cdTimer = null }
}

// ── Toast ──
const ACKS = ['好的！','收到！','了解！','明白了！','没问题！','记下了！','OK！','嗯嗯！','好嘞！','知道了！','行！','收到～']
const MILESTONES = {
  5: '已完成 5 题，加油！',
  10: '进度不错，继续保持！',
  15: '快要过半了！',
  20: '已过半，坚持就是胜利！',
  25: '还剩最后 10 题！',
  30: '快了，最后冲刺！',
  35: '全部完成！',
}

function showToast(text, variant = 'ack') {
  toast.value = { text, variant }
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = { text: '', variant: 'ack' } }, variant === 'milestone' ? 2500 : 1500)
}

// ── Answers ──
function handleAnswer(choice) {
  if (busy.value) return
  busy.value = true
  stopCd()
  // 撤销模式下作答 → 用新选择覆盖旧答案
  if (undoMode.value) {
    undoMode.value = false
    if (undoTimer) { clearTimeout(undoTimer); undoTimer = null }
  }

  const qid = questionOrder.value[currentQIndex.value]
  answers.value = { ...answers.value, [qid]: choice }

  const qi = currentQIndex.value + 1
  prevCard.value = { idx: qi, text: currentQuestion.value?.text || '', answer: choice }

  showToast(ACKS[Math.floor(Math.random() * ACKS.length)], 'ack')
  const ms = MILESTONES[qi]
  if (ms) setTimeout(() => showToast(ms, 'milestone'), 1000)

  const next = currentQIndex.value + 1
  if (next >= TOTAL) {
    phase.value = 'completed'
    prevCard.value = null
    compPhase.value = 0
    toast.value = { text: '', variant: 'ack' }
    if (toastTimer) { clearTimeout(toastTimer); toastTimer = null }
    nextTick(() => {
      setTimeout(() => { compPhase.value = 1 }, 800)
      setTimeout(() => { compPhase.value = 2 }, 1400)
    })
  } else {
    currentQIndex.value = next
    tickRef.value++
  }
  setTimeout(() => { busy.value = false }, 400)
}

function handleQuestionTimeout() {
  if (undoMode.value) return
  showToast('好的，你慢慢想～', 'info')
}

function handleUndo() {
  if (!prevCard.value || undoMode.value) return
  // 保存撤回前的卡片信息，重置 prevCard 让撤回按钮立即消失
  const card = prevCard.value
  prevCard.value = null
  undoMode.value = true
  currentQIndex.value = card.idx - 1
  showToast(`已返回第 ${card.idx} 题，${UNDO_SEC}秒内可修改`, 'info')

  if (undoTimer) clearTimeout(undoTimer)
  undoTimer = setTimeout(() => {
    // 5秒未改 → 保留原答案，自动前进
    undoMode.value = false
    const next = card.idx  // card.idx 是原来的题号，+1 = 下一题
    if (next >= TOTAL) {
      phase.value = 'completed'
      compPhase.value = 0
      toast.value = { text: '', variant: 'ack' }
      if (toastTimer) { clearTimeout(toastTimer); toastTimer = null }
      nextTick(() => {
        setTimeout(() => { compPhase.value = 1 }, 800)
        setTimeout(() => { compPhase.value = 2 }, 1400)
      })
    } else {
      currentQIndex.value = next
      tickRef.value++
    }
    showToast(`${UNDO_SEC}秒未修改，已保留原答案`, 'info')
  }, UNDO_SEC * 1000)
}

// ── Pre-test ──
function handleChoice(choice) {
  if (phase.value === 'door') {
    if (choice === '孩子测试') {
      phase.value = 'ageGate'; testType.value = '孩子'
    } else {
      testType.value = '成人'; phase.value = 'confirm'
    }
  } else if (phase.value === 'ageGate') {
    if (choice === '已满18岁') { testType.value = '成人'; phase.value = 'confirm' }
    else {
      testType.value = '孩子'; ageGateNotice.value = true
      noticeTimer = setTimeout(() => { ageGateNotice.value = false; phase.value = 'confirm' }, 2200)
    }
  } else if (phase.value === 'confirm') {
    if (choice === '准备好了，开始吧') startTest()
    else { phase.value = 'door'; testType.value = null }
  }
}

function startTest() {
  const set = testType.value === '成人' ? 'adult' : 'child'
  const ids = getQuestions(set).map(q => q.id)
  const arr = [...ids]
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]]
  }
  questionOrder.value = arr
  currentQIndex.value = 0
  answers.value = {}
  prevCard.value = null
  undoMode.value = false
  if (undoTimer) { clearTimeout(undoTimer); undoTimer = null }
  tickRef.value++
  phase.value = 'testing'
  nextTick(() => startCd())
}

function encodeAnswers() {
  return questionOrder.value
    .slice().sort((a, b) => a - b)
    .map(qid => answers.value[qid] === '完全符合' ? '1' : '0')
    .join('')
}

async function doSubmitReport() {
  console.log('[doSubmitReport] called')
  if (submitting.value) { console.log('[doSubmitReport] already submitting'); return }
  submitting.value = true
  submitError.value = ''
  try {
    const bits = encodeAnswers()
    const childUserId = await ensureChildUser('测评学员')
    const jnaoUid = await ensureJnaoUid(childUserId)
    const type = testType.value === '成人' ? 0 : 1
    const json = await submitTalentReport(childUserId, { answer: bits, jnaoUid, type })
    if (json.code !== 1) throw new Error('报告生成失败')
    const aid = json.assessment_id
    uni.navigateTo({ url: `/pages/report/index?assessment_id=${aid}` })
  } catch (e) {
    submitError.value = '提交失败：' + (e.message || '请稍后重试')
  }
  submitting.value = false
}

function dismissNotice() {
  ageGateNotice.value = false
  if (noticeTimer) clearTimeout(noticeTimer)
  phase.value = 'confirm'
}

function goBack() {
  if (phase.value === 'ageGate') { phase.value = 'door'; testType.value = null; return }
  if (phase.value === 'confirm') { phase.value = testType.value === '成人' ? 'door' : 'ageGate'; return }
  if (phase.value === 'testing' || phase.value === 'completed') { phase.value = 'confirm'; return }
  // door → back to home
  uni.navigateBack({ delta: 1 })
}

// Watch for question change → restart countdown
watch(() => tickRef.value, () => {
  if (phase.value === 'testing') nextTick(() => startCd())
})

onBeforeUnmount(() => {
  stopCd()
  if (undoTimer) clearTimeout(undoTimer)
  if (toastTimer) clearTimeout(toastTimer)
})
</script>

<style scoped>
.app { display:flex; flex-direction:column; height:100vh; max-width:480px; margin:0 auto; background:var(--bg); font-family:-apple-system,"PingFang SC",sans-serif; position:relative; overflow:hidden; }

/* Nav */
.nav { display:flex; align-items:center; padding:14px 24px 0; }
.nav-back { width:36px; height:36px; border-radius:50%; background:var(--bg-card); display:flex; align-items:center; justify-content:center; cursor:pointer; }
.nav-title { flex:1; text-align:center; color:var(--text); font-size:16px; font-weight:600; }
.nav-spacer { width:36px; }

/* Pre-test */
.phase { flex:1; display:flex; align-items:flex-start; justify-content:center; padding:18vh 24px 0; }
.phase-inner { display:flex; flex-direction:column; align-items:center; width:100%; }
.msg-title { color:var(--text); font-size:19px; font-weight:600; text-align:center; line-height:1.5; margin-bottom:8px; }
.msg-sub { color:var(--text-dim); font-size:14px; text-align:center; line-height:1.6; max-width:300px; }
.msg-ready { color:var(--text); font-size:16px; font-weight:500; text-align:center; margin:14px 0 20px; }
.card-row { display:flex; gap:14px; width:100%; max-width:340px; margin-top:24px; }
.pcard { flex:1; aspect-ratio:1; background:var(--bg-card); border-radius:18px; border:2px solid var(--border); display:flex; flex-direction:column; align-items:center; justify-content:center; padding:16px 10px; cursor:pointer; transition:all 0.15s; opacity:0; transform:scale(0.9) translateY(12px); }
.pcard:active { transform:scale(0.95) !important; }
.pcard-in { animation:cardSpring 0.6s cubic-bezier(0.34,1.56,0.64,1) forwards; }
.pcard-blue { border-color:var(--accent); background:var(--accent-bg); }
.pcard-gold { border-color:rgba(240,160,64,0.3); background:rgba(240,160,64,0.06); }
.pcard-gray { border-color:var(--border); opacity:0.6; }
.pcard-gray:active { opacity:1; }
.pcard-icon-wrap { width:52px; height:52px; border-radius:14px; background:var(--accent-bg); display:flex; align-items:center; justify-content:center; margin-bottom:8px; }
.pcard-icon-gold { background:rgba(240,160,64,0.12); }
.pcard-emoji { font-size:28px; }
.pcard-title { color:var(--text); font-size:16px; font-weight:700; text-align:center; margin-bottom:4px; display:block; }
.pcard-sub { color:var(--text-dim); font-size:11px; text-align:center; line-height:1.4; display:block; }
.notice-overlay { position:fixed; inset:0; z-index:500; background:rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center; padding:40px; }
.notice-card { background:var(--bg-card); border-radius:20px; padding:28px 24px; max-width:320px; width:100%; }
.notice-text { color:var(--text); font-size:15px; line-height:1.7; text-align:center; }

.history-hint { text-align:center; margin-bottom:8px; cursor:pointer; }
.history-hint text { color:var(--text-dim); font-size:13px; }
.history-list { max-height:300px; overflow-y:auto; margin-bottom:8px; }
.history-item { padding:12px 0; border-bottom:1px solid var(--border); display:flex; align-items:center; gap:8px; }
.history-item-main { flex:1; display:flex; justify-content:space-between; align-items:center; cursor:pointer; min-width:0; }
.history-item-main:active { opacity:0.7; }
.history-del { width:32px; height:32px; border-radius:8px; background:rgba(239,68,68,0.1); display:flex; align-items:center; justify-content:center; flex-shrink:0; cursor:pointer; }
.history-del text { color:#ef4444; font-size:14px; font-weight:700; }
.history-del:active { background:rgba(239,68,68,0.2); }
.hi-talent { color:var(--accent); font-size:14px; font-weight:600; }
.hi-time { color:var(--text-dim); font-size:11px; }
.history-close { text-align:center; margin-top:10px; cursor:pointer; }
.history-close text { color:var(--text-dim); font-size:14px; }

/* Testing */
.test-top { display:flex; align-items:center; gap:10px; padding:12px 24px; }
.test-type-tag { color:var(--text-dim); font-size:12px; background:var(--bg-card); padding:3px 10px; border-radius:10px; flex-shrink:0; }
.progress-bar { flex:1; height:6px; background:var(--bg-card); border-radius:3px; overflow:hidden; }
.progress-fill { height:100%; background:linear-gradient(90deg,var(--accent),#a78bfa); border-radius:3px; transition:width 0.4s ease-out; }
.progress-text { color:var(--text-dim); font-size:12px; flex-shrink:0; }

.test-body { flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; padding:0 24px; overflow-y:auto; transition:background 0.5s; }
.test-body-inner { width:100%; max-width:340px; }

/* Undo */
.undo-card { background:var(--bg-card); border-radius:16px; padding:14px; margin-bottom:8px; position:relative; overflow:hidden; cursor:pointer; border:1px solid var(--border); box-shadow:0 4px 20px rgba(0,0,0,0.2); }
.undo-info { display:flex; align-items:center; gap:8px; margin-bottom:6px; }
.undo-label { font-size:12px; color:var(--text-dim); background:rgba(88,166,255,0.1); padding:2px 8px; border-radius:8px; }
.undo-answer { font-size:12px; color:var(--text-dim); }
.undo-text { font-size:14px; color:var(--text-dim); line-height:1.4; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.undo-overlay { position:absolute; inset:0; backdrop-filter:blur(3px); display:flex; align-items:center; justify-content:center; border-radius:16px; }
.undo-overlay text { color:var(--text); font-size:13px; font-weight:600; }

/* Question Card */
.q-card { background:var(--bg-card); border-radius:24px; padding:24px 20px; border:1px solid var(--border); box-shadow:0 8px 40px rgba(0,0,0,0.3); }
.q-badge { display:inline-block; color:var(--accent); font-size:13px; font-weight:600; background:var(--accent-bg); padding:4px 12px; border-radius:8px; margin-bottom:16px; }

.countdown-row { display:flex; align-items:center; gap:10px; margin-bottom:16px; }
.cd-ring-wrap { position:relative; width:40px; height:40px; flex-shrink:0; }
.cd-svg { width:100%; height:100%; }
.cd-num { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font-size:13px; font-weight:700; color:var(--accent); }
.cd-num.cd-urgent { color:#ff6b6b; }
.cd-info { flex:1; min-width:0; }
.cd-hint { font-size:13px; color:var(--text-dim); display:block; }
.cd-hint.cd-urgent { color:#ff6b6b; }
.cd-bar { height:3px; background:var(--bg-input); border-radius:1px; margin-top:4px; }
.cd-bar-fill { height:100%; background:var(--accent); border-radius:1px; transition:width 0.3s; }
.cd-bar-fill.cd-warn { background:#ff9800; }
.cd-bar-fill.cd-danger { background:#ff6b6b; }

.q-text { color:var(--text); font-size:18px; font-weight:500; line-height:1.6; margin-bottom:20px; display:block; }
.q-prev { text-align:center; margin-bottom:10px; }
.q-prev text { font-size:12px; color:var(--text-dim); background:var(--bg-input); padding:3px 10px; border-radius:8px; }

.q-choices { display:flex; gap:12px; }
.q-btn { flex:1; padding:16px; border-radius:14px; text-align:center; cursor:pointer; transition:all 0.15s; }
.q-btn:active { transform:scale(0.96); }
.q-btn-yes { background:linear-gradient(135deg,var(--accent),#3b8bff); }
.q-btn-yes text { color:#fff; font-size:16px; font-weight:600; }
.q-btn-no { background:transparent; border:2px solid var(--border); }
.q-btn-no text { color:var(--text-dim); font-size:16px; font-weight:500; }

.ai-hint { margin-top:12px; text-align:center; }
.ai-hint text { font-size:12px; color:var(--text-dim); }

/* Toast */
.toast { position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); z-index:600; padding:12px 24px; border-radius:20px; pointer-events:none; }
.toast-ack { background:var(--bg-card); color:var(--text); font-size:15px; font-weight:600; }
.toast-milestone { background:var(--accent); color:#fff; font-size:16px; font-weight:700; padding:16px 28px; }
.toast-info { background:var(--bg-card); color:var(--text-dim); font-size:14px; }

/* Completion */
.complete-anim { width:120px; height:120px; margin:0 auto 20px; display:flex; align-items:center; justify-content:center; }
.ca-check { width:80px; height:80px; border-radius:50%; background:var(--accent); color:#fff; font-size:40px; font-weight:700; display:flex; align-items:center; justify-content:center; animation:caPop 0.5s 0.1s cubic-bezier(0.34,1.56,0.64,1) both; }
.ca-fade { animation:caFade 0.5s ease-out both; }
.submit-err { color:#ff6b6b; font-size:13px; text-align:center; margin-top:12px; display:block; }
.gen-btn { padding:14px 40px; background:linear-gradient(135deg,var(--accent),#3b8bff); border-radius:16px; text-align:center; display:inline-block; cursor:pointer; }
.gen-btn text { color:#fff; font-size:16px; font-weight:600; }
.gen-btn:active { opacity:0.85; transform:scale(0.97); }
@keyframes caPop { 0%{transform:scale(0)} 60%{transform:scale(1.1)} 100%{transform:scale(1)} }
@keyframes caFade { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
@keyframes cardSpring { 0%{opacity:0;transform:scale(0.9) translateY(12px)} 100%{opacity:1;transform:scale(1) translateY(0)} }
</style>
