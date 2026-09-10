<template>
  <view class="app" :class="{ 'is-kid': isKidMode, 'is-quiz': phase === 'testing' || phase === 'confirm' || phase === 'completed' }">
    <!-- Dayu brand topbar（对齐 test.html） -->
    <view class="dy-top">
      <view class="dy-brand" @tap="goBack">
        <view class="dy-logo"></view>
        <view>
          <text class="dy-t1">天赋测试</text>
          <text class="dy-t2">TALENT TEST</text>
        </view>
      </view>
      <text class="dy-hist" @tap="showHistory = true">历史报告</text>
    </view>

    <!-- ===== PRE-TEST PHASES ===== -->
    <template v-if="isPreTest">
      <!-- DOOR · 选测试对象 -->
      <view v-if="phase === 'door' || phase === 'ageGate'" class="phase door-phase" key="door">
        <view class="phase-inner door-inner">
          <text class="door-title">个人测试 · 请选择测试对象</text>
          <text class="door-sub">35 道快答题 · 约 3 分钟 · 凭第一感觉选择</text>
          <view class="card-row door-cards">
            <view class="pcard pcard-in door-card door-kid" @tap="handleChoice('孩子测试')">
              <image class="door-icon" src="/static/dayu/assets/ic/family.png" mode="aspectFit" />
              <text class="pcard-title">给孩子测</text>
              <text class="pcard-sub">未满18岁 · 家长代测</text>
            </view>
            <view class="pcard pcard-in door-card door-adu" @tap="handleChoice('成人测试')">
              <image class="door-icon" src="/static/dayu/assets/ic/person.png" mode="aspectFit" />
              <text class="pcard-title">给自己测</text>
              <text class="pcard-sub">已满18岁 · 本人作答</text>
            </view>
          </view>
          <view class="door-notice">
            <text class="door-notice-ic">🛡️</text>
            <text class="door-notice-text">未满18岁的孩子不能自己测试。儿童测试必须由家长根据孩子的日常真实表现代为作答，孩子本人作答会导致结果失真。</text>
          </view>
        </view>
      </view>

      <!-- History Overlay -->
      <view v-if="showHistory" class="history-overlay" @tap="showHistory = false">
        <view class="history-panel" @tap.stop>
          <view class="history-header">
            <text class="history-title">历史报告</text>
            <view class="history-header-close" @tap="showHistory = false"><text>✕</text></view>
          </view>
          <view v-if="historyList.length" class="history-grid">
            <view v-for="(h,i) in historyList" :key="h.id || i" class="history-box" @tap="viewHistory(h)">
              <view class="history-box-row">
                <view class="history-box-icon">
                  <image v-if="talentAvatar[h.talent_primary]" :src="talentAvatar[h.talent_primary]" mode="aspectFill" style="width:100%;height:100%;border-radius:50%;" />
                  <text v-else>{{ talentEmoji[h.talent_primary] || '🧬' }}</text>
                </view>
                <text class="history-box-talent">{{ h.talent_primary || h.talent || '--' }}</text>
                <text class="history-box-time">{{ formatHistoryDate(h.create_time || h.assessed_at) }}</text>
                <view class="history-box-del" @tap.stop="confirmDeleteHistory(h)"><text>✕</text></view>
              </view>
            </view>
          </view>
          <text v-else class="history-empty">暂无历史报告</text>
        </view>
      </view>

      <!-- AGE GATE -->
      <view v-if="phase === 'ageGate'" class="age-overlay" key="ageGate">
        <view class="age-box">
          <text class="age-ic">⚠️</text>
          <text class="age-title">注意！请确认您的孩子<text class="age-em">是否已满 18 岁</text></text>
          <text class="age-p">您的孩子未满18岁，请您（家长）帮助孩子完成本次测试。题目将由家长根据孩子的日常真实表现作答，孩子本人作答或凭想象作答，结果会与事实产生误差。</text>
          <view class="age-ok" @tap="handleChoice('未满18岁')"><text>我是家长 · 我来帮孩子测</text></view>
          <view class="age-back" @tap="handleChoice('返回')"><text>返回重选</text></view>
        </view>
      </view>

      <!-- CONFIRM · 准备页 -->
      <view v-if="phase === 'confirm'" class="phase confirm-phase" key="confirm">
        <view class="phase-inner confirm-inner">
          <view class="confirm-card">
            <text class="confirm-emoji">{{ testType === '孩子' ? '👨‍👧' : '🙌' }}</text>
            <text class="confirm-title">{{ testType === '孩子' ? '好的！家长代测 · 儿童版' : '好的！成人测试' }}</text>
            <text class="confirm-desc">
              {{ testType === '孩子'
                ? '请家长放下预判，根据孩子平时的真实表现作答，35道快答题，凭第一反应选择，越真实越准确。'
                : '接下来是 35 道快答题，凭第一感觉作答，没有对错，越诚实越准确。' }}
            </text>
            <view class="confirm-tags">
              <text class="confirm-tag">35 题</text>
              <text class="confirm-tag">每题 60 秒</text>
              <text class="confirm-tag">可撤回上一题</text>
            </view>
            <view class="confirm-actions">
              <view class="confirm-later" @tap="handleChoice('稍后再说')"><text>稍后再说</text></view>
              <view class="confirm-go" @tap="handleChoice('准备好了')"><text>准备好了 · 开始答题</text></view>
            </view>
          </view>
        </view>
      </view>
    </template>

    <!-- ===== TESTING · 对齐 jnao10 test.html 答题卡 ===== -->
    <template v-if="phase === 'testing' && currentQuestion">
      <view class="qbar">
        <text class="qmode">{{ modeLabel }}</text>
        <view class="qprog"><view class="qprog-i" :style="{ width: ((currentQIndex + 1) / TOTAL * 100) + '%' }"></view></view>
        <text class="qnum">{{ currentQIndex + 1 }}/{{ TOTAL }}</text>
      </view>

      <view v-if="prevCard && !undoMode" class="undo on" @tap="handleUndo">
        <text class="uaw">上一题「{{ (prevCard.text || '').slice(0, 14) }}…」 已选 <text class="uaw-b">{{ prevCard.answer }}</text></text>
        <text class="ubtn">↩︎ 点击撤回</text>
      </view>

      <view class="qcard">
        <text class="qtag">第 {{ currentQIndex + 1 }} 题</text>
        <view class="qtm">
          <view class="ring" :class="{ warn: cdUrgent }">
            <svg viewBox="0 0 46 46" class="ring-svg">
              <circle class="rb" cx="23" cy="23" r="20" />
              <circle
                class="rf"
                cx="23" cy="23" r="20"
                :stroke-dasharray="RING_C"
                :stroke-dashoffset="ringOffset"
              />
            </svg>
            <text class="ring-n">{{ cdLeft }}</text>
          </view>
          <view class="qhint">
            <text class="qhint-tx" :class="{ urgent: cdUrgent }">{{ quizHint }}</text>
            <view class="qhint-bar"><view class="qhint-i" :style="{ width: cdPct + '%' }"></view></view>
          </view>
        </view>
        <text class="qq">{{ isKidMode ? '🧒 ' : '' }}{{ currentQuestion.text }}</text>
        <view v-if="undoMode && currentQuestion.previous_answer" class="q-prev">
          <text>上次选择：{{ currentQuestion.previous_answer }}</text>
        </view>
        <view class="qans">
          <view class="qa yes" @tap="handleAnswer('完全符合')"><text>完全符合</text></view>
          <view class="qa no" @tap="handleAnswer('有差异')"><text>有差异</text></view>
        </view>
      </view>
      <text class="robotip">{{ robotTip }}</text>
    </template>

    <!-- ===== COMPLETED ===== -->
    <view v-if="phase === 'completed'" class="done-wrap" key="completed">
      <view class="done">
        <view class="ck">✓</view>
        <text v-if="compPhase >= 1" class="done-h2">35 题已完成</text>
        <text v-if="compPhase >= 1" class="done-p">AI 将为你生成专属天赋解读</text>
        <text v-if="submitError" class="submit-err">{{ submitError }}</text>
        <view v-if="compPhase >= 2" class="done-go" @tap="doSubmitReport">
          <text>{{ submitting ? '生成中...' : '生成报告' }}</text>
        </view>
      </view>
    </view>

    <!-- Cheer toast（对齐 test.html） -->
    <view v-if="toast.text" class="cheer on" :class="{ 'cheer-mile': toast.variant === 'milestone' }">
      <text>{{ toast.text }}</text>
    </view>

    <!-- Bottom nav -->
    <view class="dy-foot">
      <view class="dy-fa" @tap="goFoot('/pages/dayu/home')"><image class="dy-fic" src="/static/dayu/assets/ic/robot.png" mode="aspectFit" /><text>大宇AI</text></view>
      <view class="dy-fa" @tap="goFoot('/pages/training/index')"><image class="dy-fic" src="/static/dayu/assets/ic/map.png" mode="aspectFit" /><text>今日修炼</text></view>
      <view class="dy-fa" @tap="goFoot('/pages/qa/index')"><image class="dy-fic" src="/static/dayu/assets/ic/cap.png" mode="aspectFit" /><text>学科答疑</text></view>
      <view class="dy-fa" @tap="goFoot('/pages/hub/academy')"><image class="dy-fic" src="/static/dayu/assets/ic/bubble.png" mode="aspectFit" /><text>天赋学院</text></view>
      <view class="dy-fa" @tap="goFoot('/pages/hub/console')"><image class="dy-fic" src="/static/dayu/assets/ic/computer.png" mode="aspectFit" /><text>中央电脑</text></view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, nextTick, onBeforeUnmount, watch, onMounted } from 'vue'
import { onShow, onLoad } from '@dcloudio/uni-app'
import {
  ensureChildUser,
  ensureJnaoUid,
  fetchAssessmentHistory,
  deleteAssessmentReport,
  submitTalentReport,
} from '@/utils/userApi.js'
import { clearTalentState, refreshTalentState, TALENT_AVATAR } from '@/utils/talentState.js'

// ── State ──
const fromOnboarding = ref(false)
const studentTypeFromOnboarding = ref('new')
const phase = ref('door')
const testType = ref(null)
const ageGateNotice = ref(false)
const submitting = ref(false)
const submitError = ref('')
const compPhase = ref(0)
const showHistory = ref(false)
const enteredFromHub = ref(false)
const historyList = ref([])

async function loadHistory() {
  try {
    const uid = await ensureChildUser()
    historyList.value = await fetchAssessmentHistory(uid)
  } catch (_) { historyList.value = [] }
}

function viewHistory(h) {
  showHistory.value = false
  if (h.id) {
    const modeQ = (h.type === 0 || h.report_type === 0 || h.mode === 'adult') ? 'adult' : 'kid'
    uni.navigateTo({ url: `/pages/report/index?assessment_id=${h.id}&mode=${modeQ}` })
  }
}

function confirmDeleteHistory(h) {
  if (!h?.id) return
  uni.showModal({
    title: '删除报告',
    content: `确定删除「${h.talent_primary || h.talent || '测评'}」报告？`,
    confirmText: '删除',
    confirmColor: '#ef4444',
    success: (res) => { if (res.confirm) deleteHistory(h.id) },
  })
}

async function deleteHistory(assessmentId) {
  try {
    const uid = await ensureChildUser()
    await deleteAssessmentReport(uid, assessmentId)
    historyList.value = historyList.value.filter(h => h.id !== assessmentId)
    uni.showToast({ title: '已删除', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '删除失败', icon: 'none' })
  }
}

onMounted(loadHistory)
onShow(loadHistory)

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
const isKidMode = computed(() => testType.value === '孩子')
const modeLabel = computed(() => isKidMode.value ? '家长代测 · 儿童版' : '成人测试 · 本人作答')
const robotTip = computed(() =>
  isKidMode.value ? '🧒 按孩子真实表现作答，不美化、不苛求～' : '🤖 凭第一感觉选择就好～'
)

const RING_C = 125.6

// ── Countdown ──
const cdPct = computed(() => (cdLeft.value / QUESTION_SEC) * 100)
const cdUrgent = computed(() => cdLeft.value <= 5)
const ringOffset = computed(() => RING_C * (1 - cdLeft.value / QUESTION_SEC))
const quizHint = computed(() => {
  if (cdLeft.value <= 3) return '快选一个，凭直觉就好'
  if (cdLeft.value <= 5) return '时间不多了'
  return isKidMode.value
    ? '家长朋友：想孩子平时的样子，别想要的样子～'
    : '凭第一感觉选择就好～'
})

function goFoot(url) {
  if (!url) return
  uni.reLaunch({ url })
}

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
  if (qi % 5 === 0 && qi < TOTAL) {
    const mile = isKidMode.value
      ? `已记录 ${qi} 题，继续想孩子的日常～`
      : (MILESTONES[qi] || `已完成 ${qi} 题，加油！`)
    setTimeout(() => showToast(mile, 'milestone'), 1000)
  } else {
    const ms = MILESTONES[qi]
    if (ms) setTimeout(() => showToast(ms, 'milestone'), 1000)
  }

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
    // 图一：给孩子测先弹年龄确认；给自己测直接成人确认
    if (choice === '孩子测试') {
      phase.value = 'ageGate'
    } else {
      testType.value = '成人'
      phase.value = 'confirm'
    }
  } else if (phase.value === 'ageGate') {
    if (choice === '返回' || choice === '已满18岁') {
      phase.value = 'door'
      testType.value = null
      return
    }
    // 我是家长 · 我来帮孩子测
    testType.value = '孩子'
    phase.value = 'confirm'
  } else if (phase.value === 'confirm') {
    if (choice === '准备好了') startTest()
    else if (fromOnboarding.value) {
      uni.navigateBack({ delta: 1 })
    } else if (enteredFromHub.value) {
      uni.navigateBack({ delta: 1 })
    } else {
      phase.value = 'door'; testType.value = null
    }
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
    await loadHistory()
    const aid = json.assessment_id
    const modeQ = testType.value === '成人' ? 'adult' : 'kid'
    let url = `/pages/report/index?assessment_id=${aid}&mode=${modeQ}`
    if (json.talent_conflict) {
      url += `&talent_conflict=1&current_talent=${encodeURIComponent(json.current_talent || '')}`
    }
    if (json.talent_locked) {
      url += `&talent_locked=1&lock_message=${encodeURIComponent(json.lock_message || '')}`
    }
    if (json.talent_last_chance) {
      url += `&talent_last_chance=1&current_talent=${encodeURIComponent(json.current_talent || '')}&new_talent=${encodeURIComponent(json.data?.talent || '')}`
    }
    if (fromOnboarding.value) {
      url += `&from=onboarding&student_type=${encodeURIComponent(studentTypeFromOnboarding.value || 'new')}`
    }
    clearTalentState()
    await refreshTalentState(childUserId)
    uni.navigateTo({ url })
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

const talentEmoji = { 学者:'📚', 思者:'💡', 行者:'🏃', 德者:'⚖️', 赢者:'🏆' }
const talentAvatar = TALENT_AVATAR

function formatHistoryDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return String(iso).slice(0,10)
  const p = n => String(n).padStart(2,'0')
  return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}`
}

function goBack() {
  if (phase.value === 'door') {
    if (getCurrentPages().length > 1) uni.navigateBack({ delta: 1 })
    else uni.reLaunch({ url: '/pages/talent/hub' })
    return
  }
  if (phase.value === 'ageGate') { phase.value = 'door'; testType.value = null; return }
  if (phase.value === 'confirm') {
    if (enteredFromHub.value || fromOnboarding.value) {
      uni.navigateBack({ delta: 1 })
      return
    }
    phase.value = 'door'
    testType.value = null
    return
  }
  if (phase.value === 'testing' || phase.value === 'completed') { phase.value = 'confirm'; return }
  if (fromOnboarding.value) {
    uni.navigateBack({ delta: 1 })
    return
  }
  uni.navigateBack({ delta: 1 })
}

onLoad((opts) => {
  fromOnboarding.value = opts?.from === 'onboarding'
  studentTypeFromOnboarding.value = opts?.student_type || 'new'
  if (opts?.history === '1' || opts?.history === 'true') {
    showHistory.value = true
    loadHistory()
  }
  const mode = String(opts?.mode || '').toLowerCase()
  const autoStart = opts?.start === '1' || opts?.start === 'true'
  if (mode === 'kid' || mode === 'child') {
    enteredFromHub.value = true
    testType.value = '孩子'
    if (autoStart) startTest()
    else phase.value = 'confirm'
  } else if (mode === 'adult' || mode === 'adu') {
    enteredFromHub.value = true
    testType.value = '成人'
    if (autoStart) startTest()
    else phase.value = 'confirm'
  }
})

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
.app {
  display: flex; flex-direction: column;
  min-height: 100vh; min-height: 100dvh;
  max-width: var(--app-max-width, 480px); margin: 0 auto;
  background: #0B0E14; font-family: "PingFang SC", "MiSans", -apple-system, sans-serif;
  position: relative; overflow-x: hidden; padding-bottom: 96px; box-sizing: border-box;
}

/* Brand topbar */
.dy-top {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 18px 4px; flex-shrink: 0;
}
.dy-brand { display: flex; align-items: center; gap: 10px; cursor: pointer; }
.dy-logo {
  width: 44px; height: 44px; border-radius: 50%; flex: none;
  background: url("/static/dayu/assets/avatar_sizhe.jpg") center/cover;
  border: 2px solid #6FCF8E; box-shadow: 0 0 10px rgba(111, 207, 142, 0.4);
}
.dy-t1 { display: block; font-size: 19px; font-weight: 800; color: #EDEBE4; line-height: 1.2; }
.dy-t2 { display: block; font-size: 11px; color: #8B93A5; letter-spacing: 2px; }
.dy-hist { font-size: 14px; color: #8B93A5; font-weight: 700; }

/* Foot */
.dy-foot {
  position: fixed; bottom: 0; left: 50%; transform: translateX(-50%);
  width: 100%; max-width: 430px;
  background: rgba(11, 14, 20, 0.96); backdrop-filter: blur(12px);
  border-top: 1px solid #232B3D; padding: 6px 8px;
  display: flex; justify-content: space-around; z-index: 50;
}
.dy-fa {
  flex: 1; text-align: center; color: #8B93A5; font-size: 10px;
  display: flex; flex-direction: column; align-items: center; gap: 1px; padding: 2px 0;
}
.dy-fic { width: 34px; height: 34px; }

/* Pre-test */
.phase { flex: 1; display: flex; align-items: flex-start; justify-content: center; padding: 8vh 18px 0; padding: 8dvh 18px 0; }
.phase-inner { display: flex; flex-direction: column; align-items: center; width: 100%; }
.card-row { display: flex; gap: 14px; width: 100%; max-width: 340px; margin-top: 24px; }
.pcard {
  flex: 1; min-height: 260px; background: #131926; border-radius: 18px; border: 2px solid #232B3D;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 28px 10px; cursor: pointer;
}
.pcard-title { color: #EDEBE4; font-size: 16px; font-weight: 700; text-align: center; margin-bottom: 4px; display: block; }
.pcard-sub { color: #8B93A5; font-size: 11px; text-align: center; line-height: 1.4; display: block; }

.door-phase { padding-top: 4vh; padding-top: 4dvh; }
.door-inner { max-width: 400px; }
.door-title { color: #EDEBE4; font-size: 18px; font-weight: 800; text-align: center; margin-bottom: 6px; }
.door-sub { color: #8B93A5; font-size: 13px; text-align: center; margin-bottom: 8px; line-height: 1.45; }
.door-cards { max-width: 100%; margin-top: 18px; }
.door-card { min-height: 220px; justify-content: flex-start; padding-top: 22px; border-width: 1.5px; }
.door-kid { border-color: rgba(111, 207, 142, 0.55); box-shadow: 0 0 16px rgba(111, 207, 142, 0.12); }
.door-adu { border-color: rgba(46, 107, 230, 0.45); box-shadow: 0 0 16px rgba(46, 107, 230, 0.1); }
.door-icon { width: 96px; height: 96px; margin-bottom: 12px; }
.door-notice {
  margin-top: 18px; width: 100%; max-width: 400px;
  display: flex; gap: 10px; align-items: flex-start;
  background: rgba(180, 60, 60, 0.12); border: 1px solid rgba(220, 100, 100, 0.35);
  border-radius: 12px; padding: 12px 14px; box-sizing: border-box;
}
.door-notice-ic { flex-shrink: 0; font-size: 16px; line-height: 1.4; }
.door-notice-text { color: #e8a0a0; font-size: 12.5px; line-height: 1.55; flex: 1; }

.age-overlay {
  position: fixed; inset: 0; z-index: 80;
  background: rgba(5, 8, 16, 0.72);
  display: flex; align-items: center; justify-content: center; padding: 28px 22px;
}
.age-box {
  width: 100%; max-width: 340px;
  background: #131926; border: 1.5px solid rgba(224, 82, 82, 0.55);
  border-radius: 22px; padding: 22px 18px 16px; text-align: center;
}
.age-ic { font-size: 34px; display: block; margin-bottom: 8px; }
.age-title { display: block; color: #fff; font-size: 18px; font-weight: 900; line-height: 1.45; margin-bottom: 10px; }
.age-em { color: #F5A3A3; }
.age-p { display: block; color: #C9CFDC; font-size: 13px; line-height: 1.7; text-align: left; margin-bottom: 16px; }
.age-ok { background: #3E8E5A; border-radius: 99px; padding: 13px 16px; cursor: pointer; }
.age-ok text { color: #fff; font-size: 15px; font-weight: 900; }
.age-back { margin-top: 12px; cursor: pointer; }
.age-back text { color: #8B93A5; font-size: 13px; font-weight: 700; }

.confirm-phase { padding-top: 6vh; padding-top: 6dvh; }
.confirm-inner { max-width: 400px; }
.confirm-card {
  width: 100%; background: #131926; border: 1.5px solid #2A3040; border-radius: 26px;
  padding: 32px 22px 24px; text-align: center;
  box-shadow: 0 16px 40px rgba(46, 107, 230, 0.18);
}
.confirm-emoji { font-size: 48px; display: block; margin-bottom: 8px; }
.confirm-title { display: block; color: #EDEBE4; font-size: 22px; font-weight: 900; margin-bottom: 10px; }
.confirm-desc { display: block; color: #8B93A5; font-size: 15px; line-height: 1.75; margin-bottom: 14px; }
.confirm-tags { display: flex; justify-content: center; gap: 8px; flex-wrap: wrap; margin-bottom: 22px; }
.confirm-tag {
  font-size: 13px; font-weight: 800; color: #8FB4FF;
  background: rgba(46, 107, 230, 0.12); border: 1px solid rgba(46, 107, 230, 0.4);
  border-radius: 8px; padding: 4px 10px;
}
.confirm-actions { display: flex; gap: 12px; }
.confirm-later, .confirm-go {
  border-radius: 14px; padding: 14px 8px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.confirm-later { flex: 1; background: #161D2B; border: 1.5px solid #2A3040; }
.confirm-later text { color: #8B93A5; font-size: 15px; font-weight: 700; }
.confirm-go { flex: 1.4; background: linear-gradient(135deg, #3A7BFF, #2E5BD6); box-shadow: 0 8px 20px rgba(46, 107, 230, 0.4); }
.confirm-go text { color: #fff; font-size: 15px; font-weight: 900; }

.history-overlay { position: fixed; inset: 0; z-index: 500; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; padding: 40px; }
.history-panel { width: 100%; max-width: 320px; background: #131926; border-radius: 16px; padding: 20px 16px; max-height: 60vh; max-height: 60dvh; overflow-y: auto; border: 1px solid #232B3D; }
.history-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.history-title { font-size: 17px; font-weight: 700; color: #EDEBE4; }
.history-header-close { width: 28px; height: 28px; border-radius: 50%; background: #1A2233; display: flex; align-items: center; justify-content: center; cursor: pointer; }
.history-header-close text { font-size: 14px; color: #8B93A5; }
.history-grid { display: flex; flex-direction: column; gap: 8px; }
.history-box { background: #161D2B; border-radius: 14px; padding: 14px; cursor: pointer; }
.history-box-row { display: flex; align-items: center; gap: 10px; }
.history-box-icon { width: 36px; height: 36px; border-radius: 50%; background: #0D1119; display: flex; align-items: center; justify-content: center; flex-shrink: 0; overflow: hidden; }
.history-box-icon text { font-size: 18px; }
.history-box-talent { font-size: 14px; font-weight: 600; color: #EDEBE4; }
.history-box-time { font-size: 12px; color: #8B93A5; margin-left: auto; }
.history-box-del { width: 20px; height: 20px; border-radius: 50%; background: rgba(255,255,255,0.06); display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; }
.history-box-del text { color: #8B93A5; font-size: 9px; }
.history-empty { text-align: center; padding: 32px 0; color: #8B93A5; font-size: 14px; }

/* ===== Quiz (test.html sQuiz) ===== */
.qbar { display: flex; align-items: center; gap: 10px; margin: 8px 18px 0; }
.qmode {
  flex: none; font-size: 14px; font-weight: 800; color: #8FB4FF;
  background: rgba(46, 107, 230, 0.14); border: 1px solid rgba(46, 107, 230, 0.45);
  border-radius: 99px; padding: 4px 11px;
}
.qprog { flex: 1; height: 7px; border-radius: 99px; background: #1A2233; overflow: hidden; }
.qprog-i {
  display: block; height: 100%; border-radius: 99px;
  background: linear-gradient(90deg, #2E6BE6, #7AA6FF); transition: width 0.35s ease;
}
.qnum { flex: none; font-size: 14px; font-weight: 800; color: #8B93A5; font-variant-numeric: tabular-nums; }

.undo {
  margin: 14px 18px 0; background: #161D2B; border: 1px solid #2A3040; border-radius: 14px;
  padding: 10px 14px; display: flex; align-items: center; gap: 10px; font-size: 14px; color: #8B93A5;
}
.uaw { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.uaw-b { color: #7AA6FF; font-weight: 800; }
.ubtn {
  flex: none; font-size: 14px; font-weight: 800; color: #8FB4FF;
  border: 1px solid rgba(46, 107, 230, 0.5); border-radius: 9px; padding: 4px 10px;
}

.qcard {
  margin: 14px 18px 0; background: #131926; border: 1.5px solid #232B3D;
  border-radius: 26px; padding: 24px 20px 22px; position: relative; overflow: hidden;
}
.qcard::after {
  content: ""; position: absolute; top: -46px; right: -46px; width: 140px; height: 140px;
  border-radius: 50%; background: radial-gradient(circle, rgba(46, 107, 230, 0.16), transparent 70%);
  pointer-events: none;
}
.qtag {
  display: inline-block; font-size: 14px; font-weight: 800; color: #8FB4FF;
  background: rgba(46, 107, 230, 0.14); border-radius: 8px; padding: 3px 10px; margin-bottom: 14px;
}
.qtm { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; position: relative; z-index: 1; }
.ring { width: 46px; height: 46px; flex: none; position: relative; }
.ring-svg { width: 46px; height: 46px; transform: rotate(-90deg); display: block; }
.ring .rb { fill: none; stroke: #232B3D; stroke-width: 4; }
.ring .rf {
  fill: none; stroke: #3A7BFF; stroke-width: 4; stroke-linecap: round;
  transition: stroke-dashoffset 1s linear, stroke 0.3s;
}
.ring.warn .rf { stroke: #E05252; }
.ring-n {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  font-size: 17px; font-weight: 900; color: #EDEBE4; font-variant-numeric: tabular-nums;
}
.qhint { flex: 1; min-width: 0; }
.qhint-tx { font-size: 14px; color: #8B93A5; display: block; line-height: 1.35; }
.qhint-tx.urgent { color: #E05252; }
.qhint-bar { height: 4px; border-radius: 99px; background: #1A2233; margin-top: 6px; overflow: hidden; }
.qhint-i {
  display: block; height: 100%; background: #3A7BFF; border-radius: 99px;
  transition: width 1s linear;
}
.qq {
  font-size: 20px; font-weight: 900; color: #EDEBE4; line-height: 1.65;
  min-height: 100px; position: relative; z-index: 1; display: block;
}
.q-prev { text-align: center; margin: 8px 0; position: relative; z-index: 1; }
.q-prev text { font-size: 12px; color: #8B93A5; background: #1A2233; padding: 3px 10px; border-radius: 8px; }
.qans { display: flex; gap: 12px; margin-top: 18px; position: relative; z-index: 1; }
.qa {
  flex: 1; border-radius: 16px; padding: 16px 8px; text-align: center; cursor: pointer;
}
.qa:active { transform: scale(0.95); }
.qa text { font-size: 18px; font-weight: 900; }
.qa.yes {
  background: linear-gradient(135deg, #3A7BFF, #2E5BD6);
  box-shadow: 0 8px 20px rgba(46, 107, 230, 0.38);
}
.qa.yes text { color: #fff; }
.qa.no { background: #161D2B; border: 1.5px solid #2A3040; }
.qa.no text { color: #8B93A5; }
.robotip {
  display: block; text-align: center; font-size: 14px; color: #5A6274;
  margin: 16px 18px 0;
}

/* Kid theme */
.is-kid .qmode {
  color: #8FEFC0; background: rgba(111, 207, 142, 0.14); border-color: rgba(111, 207, 142, 0.5);
}
.is-kid .qprog-i { background: linear-gradient(90deg, #3E8E5A, #6FCF8E); }
.is-kid .qcard {
  border-color: rgba(111, 207, 142, 0.45);
  background: linear-gradient(170deg, #14201A, #131926 60%);
}
.is-kid .qcard::after { background: radial-gradient(circle, rgba(111, 207, 142, 0.18), transparent 70%); }
.is-kid .qtag { color: #8FEFC0; background: rgba(111, 207, 142, 0.14); }
.is-kid .ring .rf { stroke: #6FCF8E; }
.is-kid .qhint-i { background: #6FCF8E; }
.is-kid .qa.yes {
  background: linear-gradient(135deg, #4FAE72, #35824F);
  box-shadow: 0 8px 20px rgba(111, 207, 142, 0.35);
}
.is-kid .uaw-b { color: #8FEFC0; }
.is-kid .ubtn { color: #8FEFC0; border-color: rgba(111, 207, 142, 0.5); }
.is-kid .cheer { background: linear-gradient(135deg, #4FAE72, #35824F); box-shadow: 0 10px 26px rgba(111, 207, 142, 0.5); }

.cheer {
  position: fixed; left: 50%; bottom: 110px; transform: translateX(-50%);
  background: linear-gradient(135deg, #3A7BFF, #2E5BD6); color: #fff;
  font-size: 17px; font-weight: 900; border-radius: 99px; padding: 11px 22px;
  box-shadow: 0 10px 26px rgba(46, 107, 230, 0.5); z-index: 60; pointer-events: none;
}
.cheer text { color: #fff; font-size: 16px; font-weight: 900; }

/* Done */
.done-wrap { padding: 60px 26px 0; text-align: center; }
.done { display: flex; flex-direction: column; align-items: center; }
.ck {
  width: 96px; height: 96px; border-radius: 50%;
  background: linear-gradient(135deg, #3A7BFF, #2E5BD6);
  display: flex; align-items: center; justify-content: center;
  font-size: 46px; color: #fff;
  box-shadow: 0 0 0 12px rgba(46, 107, 230, 0.14), 0 0 0 26px rgba(46, 107, 230, 0.06);
}
.done-h2 { display: block; font-size: 26px; font-weight: 900; color: #EDEBE4; margin: 26px 0 8px; }
.done-p { display: block; font-size: 16px; color: #8B93A5; margin-bottom: 30px; }
.submit-err { color: #E05252; font-size: 13px; text-align: center; margin-bottom: 12px; display: block; }
.done-go {
  width: 100%; max-width: 320px;
  background: linear-gradient(135deg, #3A7BFF, #2E5BD6); border-radius: 16px; padding: 16px;
  box-shadow: 0 10px 26px rgba(46, 107, 230, 0.42); cursor: pointer;
}
.done-go text { color: #fff; font-size: 18px; font-weight: 900; }
</style>
