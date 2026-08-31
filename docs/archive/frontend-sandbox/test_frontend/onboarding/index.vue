<template>
  <view class="obo-app">
    <!-- ========== 进度条（问答阶段显示） ========== -->
    <view v-if="showProgress" class="obo-progress-wrap">
      <view class="obo-progress-back" @tap="prevStep">
        <text>←</text>
      </view>
      <view class="obo-progress-track">
        <view class="obo-progress-fill" :style="{ width: progressPct + '%' }"></view>
      </view>
    </view>

    <!-- ========== 步骤 0：欢迎页 ========== -->
    <view v-if="step === 0" class="obo-page obo-welcome">
      <view class="obo-hero">
        <image class="obo-mascot" src="/static/teacher.png" mode="aspectFit" />
      </view>
      <text class="obo-welcome-title">嗨，你好！</text>
      <text class="obo-welcome-sub">我是你的专属教练</text>
      <text class="obo-welcome-desc">帮你量身定制训练方案的AI伙伴</text>
      <view class="obo-bottom-fixed">
        <view class="obo-btn obo-btn-primary" @tap="step = 1">
          <text>继续</text>
        </view>
      </view>
    </view>

    <!-- ========== 步骤 1：过渡页 ========== -->
    <view v-if="step === 1" class="obo-page obo-transition">
      <view class="obo-hero obo-hero-sm">
        <text class="obo-emoji">✨</text>
      </view>
      <text class="obo-transition-title">课程开始前</text>
      <text class="obo-transition-sub">先快速问几个问题，帮你定制专属方案</text>
      <view class="obo-bottom-fixed">
        <view class="obo-btn obo-btn-primary" @tap="nextStep">
          <text>开始</text>
        </view>
      </view>
    </view>

    <!-- ========== Q1：老学员？ step=2 ========== -->
    <view v-if="step === 2" class="obo-page obo-quiz">
      <view class="obo-quiz-inner">
        <view class="obo-quiz-question">
          <text class="obo-q-text">你是否是老学员？</text>
        </view>
        <view class="obo-options">
          <view class="obo-option" @tap="selectAndGoQ1(0)">
            <text class="obo-option-tag obo-tag-yes">是</text>
            <text class="obo-option-desc">已经训练过一段时间</text>
          </view>
          <view class="obo-option" @tap="selectAndGoQ1(1)">
            <text class="obo-option-tag obo-tag-no">否</text>
            <text class="obo-option-desc">刚开始使用，还未开始训练</text>
          </view>
        </view>
      </view>
    </view>

    <!-- ========== Q2：主天赋？ step=3 ========== -->
    <view v-if="step === 3" class="obo-page obo-quiz">
      <view class="obo-quiz-inner">
        <view class="obo-quiz-question">
          <text class="obo-q-text">您的主天赋是？</text>
        </view>
        <view class="obo-options">
          <view
            v-for="(t, ti) in talents"
            :key="ti"
            class="obo-option"
            :class="{ selected: selectedOption === ti }"
            @tap="selectAndGoQ2(ti)"
          >
            <view class="obo-option-icon"><text>{{ t.icon }}</text></view>
            <view class="obo-option-body">
              <text class="obo-option-label">{{ t.label }}</text>
              <text class="obo-option-desc">{{ t.desc }}</text>
            </view>
            <view v-if="selectedOption === ti" class="obo-option-check"><text>✓</text></view>
          </view>
        </view>
      </view>
    </view>

    <!-- ========== Q3：训练能力多选 step=4 ========== -->
    <view v-if="step === 4" class="obo-page obo-quiz obo-quiz-multi">
      <view class="obo-quiz-inner">
        <view class="obo-quiz-question">
          <text class="obo-q-text">请问之前做过哪些训练？</text>
          <text class="obo-q-sub">可多选</text>
        </view>
        <view class="obo-options obo-options-grid">
          <view
            v-for="(ab, ai) in allAbilities"
            :key="ai"
            class="obo-option obo-option-grid"
            :class="{ selected: selectedMulti.includes(ai) }"
            @tap="toggleMulti(ai)"
          >
            <text class="obo-option-grid-label">{{ ab }}</text>
          </view>
        </view>
      </view>
      <view class="obo-bottom-fixed">
        <view class="obo-btn" :class="selectedMulti.length > 0 ? 'obo-btn-primary' : 'obo-btn-disabled'" @tap="answerQ3">
          <text>继续</text>
        </view>
      </view>
    </view>

    <!-- ========== Q4~：逐项填数据 step >= 5 ========== -->
    <view v-if="step >= 5 && step < 5 + selectedAbilities.length" class="obo-page obo-quiz obo-quiz-data">
      <view class="obo-quiz-inner">
        <view class="obo-quiz-question">
          <text class="obo-q-text">请填写「{{ currentAbility }}」训练数据</text>
        </view>
        <view class="obo-form">
          <view class="obo-form-item">
            <text class="obo-form-label">第一次打卡时间</text>
            <input class="obo-form-input" v-model="currentForm.firstDate" placeholder="如：2025年3月 或 2025-03" />
          </view>
          <view class="obo-form-item">
            <text class="obo-form-label">至今打卡次数（大概）</text>
            <input class="obo-form-input" v-model="currentForm.totalCount" type="number" placeholder="如：30" />
          </view>
          <view class="obo-form-item">
            <text class="obo-form-label">最近一次打卡数据</text>
            <view class="obo-form-row obo-form-row-half">
              <input class="obo-form-input short" v-model="currentForm.lastTime" placeholder="训练时长（分钟）" type="number" />
              <text class="obo-form-unit">分钟</text>
            </view>
            <view class="obo-form-row obo-form-row-half" style="margin-top:8px;">
              <input class="obo-form-input short" v-model="currentForm.lastResult" placeholder="正确率" type="number" />
              <text class="obo-form-unit">%</text>
            </view>
          </view>
        </view>
      </view>
      <view class="obo-bottom-fixed">
        <view class="obo-btn" :class="canNextData ? 'obo-btn-primary' : 'obo-btn-disabled'" @tap="nextDataStep">
          <text>{{ isLastDataStep ? '完成' : '继续' }}</text>
        </view>
      </view>
    </view>

    <!-- ========== 完成 → 跳主界面 step=200 ========== -->
    <view v-if="step === 200" class="obo-page obo-done">
      <view class="obo-hero">
        <text class="obo-emoji obo-emoji-lg">🎯</text>
      </view>
      <text class="obo-done-title">搞定！</text>
      <text class="obo-done-sub">已为你定制好训练方案</text>
      <view class="obo-bottom-fixed">
        <view class="obo-btn obo-btn-primary" @tap="goMain">
          <text>开始学习</text>
        </view>
      </view>
    </view>

    <!-- ========== 去天赋测试 step=100 ========== -->
    <view v-if="step === 100" class="obo-page obo-done">
      <view class="obo-hero">
        <text class="obo-emoji obo-emoji-lg">🧬</text>
      </view>
      <text class="obo-done-title">先测天赋</text>
      <text class="obo-done-sub">完成天赋测试后，才能定制专属方案</text>
      <view class="obo-bottom-fixed">
        <view class="obo-btn obo-btn-primary" @tap="goTalent">
          <text>去测试</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'

const step = ref(0)
const selectedOption = ref(null)
const selectedMulti = ref([])
const isOldUser = ref(null) // Q1 answer: true=是, false=否

const talents = [
  { icon: '📚', label: '学者',   desc: '热衷钻研，系统严谨的学习者' },
  { icon: '💡', label: '思者',   desc: '善于反思，举一反三的思考者' },
  { icon: '🏃', label: '行者',   desc: '行动力强，边做边学的实践者' },
  { icon: '⚖️', label: '德者',   desc: '自律坚韧，以德驭学的修养者' },
  { icon: '🏆', label: '赢者',   desc: '目标明确，追求卓越的竞争者' },
]

const allAbilities = [
  '超脑阅读','影像追忆','扫描速记','极速运算',
  '极速学习','难题专练','文科扫书','理科扫书',
  '高效作业','天赋绘画','音乐灵感','棋类专注'
]

const selectedAbilities = computed(() => {
  return selectedMulti.value.map(i => allAbilities[i])
})

const currentAbilityIndex = computed(() => step.value - 5)
const currentAbility = computed(() => selectedAbilities.value[currentAbilityIndex.value] || '')
const isLastDataStep = computed(() => currentAbilityIndex.value >= selectedAbilities.value.length - 1)

// 每个能力对应的表单数据
const formData = ref({})
const currentForm = computed(() => {
  const key = currentAbility.value
  if (!formData.value[key]) {
    formData.value[key] = { firstDate: '', totalCount: '', lastTime: '', lastResult: '' }
  }
  return formData.value[key]
})

const totalSteps = computed(() => {
  return 4 + selectedAbilities.value.length // Q1+Q2+Q3 + 逐项
})
const showProgress = computed(() => step.value >= 2 && step.value < totalSteps.value + 1 && step.value < 100)
const progressPct = computed(() => {
  if (step.value < 2) return 0
  const cur = Math.min(step.value, totalSteps.value)
  return Math.round((cur / totalSteps.value) * 100)
})

function selectAndGoQ1(oi) {
  isOldUser.value = oi === 0
  step.value = 3
}

function selectAndGoQ2(ti) {
  // Q1=否 + 五者之一 → 直接跳主界面
  if (isOldUser.value === false) {
    step.value = 200
    saveAnswers()
    return
  }
  // Q1=是 + 五者之一 → 继续 Q3
  step.value = 4
}

function toggleMulti(ai) {
  const idx = selectedMulti.value.indexOf(ai)
  if (idx >= 0) {
    selectedMulti.value.splice(idx, 1)
  } else {
    selectedMulti.value.push(ai)
  }
}

function answerQ3() {
  if (selectedMulti.value.length === 0) return
  // 初始化表单
  for (const ab of selectedAbilities.value) {
    if (!formData.value[ab]) {
      formData.value[ab] = { firstDate: '', totalCount: '', lastTime: '', lastResult: '' }
    }
  }
  step.value = 5
}

const canNextData = computed(() => {
  const f = currentForm.value
  return f.firstDate && f.totalCount && f.lastTime && f.lastResult
})

function nextDataStep() {
  if (!canNextData.value) return
  if (isLastDataStep.value) {
    step.value = 200
    saveAnswers()
  } else {
    step.value++
  }
}

function prevStep() {
  if (step.value <= 2) return
  selectedOption.value = null
  // 从数据步骤返回 Q3
  if (step.value === 5) {
    step.value = 4
    return
  }
  step.value--
}

function saveAnswers() {
  const answers = {
    isOldUser: isOldUser.value,
    talent: selectedOption.value !== null ? talents[selectedOption.value]?.label : null,
    abilities: selectedAbilities.value,
    abilityData: formData.value,
  }
  uni.setStorageSync('onboarding_answers', JSON.stringify(answers))
  uni.setStorageSync('onboarding_done', '1')
}

function goMain() {
  uni.switchTab({ url: '/pages/index' })
}

function goTalent() {
  uni.navigateTo({ url: '/pages/talent/index' })
}

function nextStep() {
  step.value++
}
</script>

<style>
.obo-app {
  height: 100vh;
  max-width: 768px;
  margin: 0 auto;
  background: #fff;
  display: flex;
  flex-direction: column;
  font-family: -apple-system, "PingFang SC", sans-serif;
  position: relative;
  overflow: hidden;
}

/* ===== 进度条 ===== */
.obo-progress-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  flex-shrink: 0;
}
.obo-progress-track {
  flex: 1;
  height: 8px;
  background: #e5e7eb;
  border-radius: 99px;
  overflow: hidden;
}
.obo-progress-fill {
  height: 100%;
  background: #58cc02;
  border-radius: 99px;
  transition: width 0.35s cubic-bezier(0.4,0,0.2,1);
}
.obo-progress-back {
  width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}
.obo-progress-back text { font-size: 18px; color: #9ca3af; font-weight: 600; }

/* ===== 页面容器 ===== */
.obo-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 40px 28px;
  animation: oboFadeIn 0.4s ease-out;
}
@keyframes oboFadeIn {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ===== 欢迎页 + 过渡页 ===== */
.obo-hero { margin-bottom: 24px; }
.obo-hero-sm { margin-bottom: 16px; }
.obo-mascot { width: 160px; height: 160px; }
.obo-emoji { font-size: 56px; }
.obo-emoji-lg { font-size: 72px; }
.obo-welcome-title { font-size: 28px; font-weight: 700; color: #1a1a2e; margin-bottom: 8px; }
.obo-welcome-sub { font-size: 20px; color: #4b5563; margin-bottom: 4px; }
.obo-welcome-desc { font-size: 14px; color: #9ca3af; }
.obo-transition-title { font-size: 24px; font-weight: 700; color: #1a1a2e; margin-bottom: 8px; }
.obo-transition-sub { font-size: 18px; color: #4b5563; }
.obo-done-title { font-size: 28px; font-weight: 700; color: #1a1a2e; margin-bottom: 8px; }
.obo-done-sub { font-size: 16px; color: #6b7280; }

/* ===== 问答页 ===== */
.obo-quiz { padding-top: 24px; justify-content: flex-start; }
.obo-quiz-inner { flex: 1; width: 100%; animation: oboFadeIn 0.35s ease-out; }
.obo-quiz-question { margin-bottom: 28px; }
.obo-q-text { display: block; font-size: 22px; font-weight: 700; color: #1a1a2e; line-height: 1.4; }
.obo-q-sub { display: block; font-size: 14px; color: #9ca3af; margin-top: 6px; }

/* ===== 选项 ===== */
.obo-options { display: flex; flex-direction: column; gap: 10px; }
.obo-options-grid { flex-direction: row; flex-wrap: wrap; gap: 8px; }
.obo-option {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  border: 2px solid #e5e7eb;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.2s;
}
.obo-option:active { background: #f9fafb; }
.obo-option.selected { border-color: #58cc02; background: #f7fdf4; }
.obo-option-grid {
  flex: 0 0 calc(25% - 6px);
  box-sizing: border-box;
  padding: 10px 4px;
  gap: 0;
  position: relative;
  flex-direction: column;
  align-items: center;
  text-align: center;
}
.obo-option-icon { width: 44px; height: 44px; border-radius: 12px; background: #f3f4f6; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.obo-option.selected .obo-option-icon { background: #e8f8e0; }
.obo-option-icon text { font-size: 20px; color: #374151; }
.obo-option-body { flex: 1; }
.obo-option-label { display: block; font-size: 16px; font-weight: 600; color: #1f2937; }
.obo-option-desc { display: block; font-size: 13px; color: #9ca3af; margin-top: 2px; }
.obo-option-check { width: 26px; height: 26px; border-radius: 50%; background: #58cc02; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.obo-option-check text { font-size: 14px; color: #fff; font-weight: 700; }
.obo-option-grid-label { font-size: 12px; font-weight: 500; color: #374151; }
/* Q1 是/否 */
.obo-option-tag { width: 56px; height: 56px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 22px; font-weight: 700; flex-shrink: 0; }
.obo-tag-yes { background: #e8f8e0; color: #46a302; }
.obo-tag-no { background: #fef2f2; color: #dc2626; }

/* ===== 表单 ===== */
.obo-form { display: flex; flex-direction: column; gap: 20px; }
.obo-form-item { margin-bottom: 0; }
.obo-form-label { display: block; font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; }
.obo-form-input {
  width: 100%;
  padding: 12px 14px;
  border: 1.5px solid #e5e7eb;
  border-radius: 12px;
  font-size: 15px;
  color: #1f2937;
  background: #f9fafb;
  outline: none;
}
.obo-form-input.short { width: 100px; }
.obo-form-row { display: flex; align-items: center; gap: 8px; }
.obo-form-unit { font-size: 14px; color: #9ca3af; }
.obo-form-picker {
  padding: 12px 14px;
  border: 1.5px solid #e5e7eb;
  border-radius: 12px;
  font-size: 15px;
  color: #1f2937;
  background: #f9fafb;
}

/* ===== 底部 ===== */
.obo-bottom-fixed {
  padding: 16px 28px calc(20px + env(safe-area-inset-bottom));
  width: 100%;
  flex-shrink: 0;
}
.obo-btn {
  width: 100%;
  padding: 16px 0;
  border-radius: 16px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
}
.obo-btn-primary { background: #58cc02; box-shadow: 0 2px 0 #46a302; }
.obo-btn-primary:active { background: #46a302; }
.obo-btn-primary text { color: #fff; font-size: 17px; font-weight: 700; }
.obo-btn-disabled { background: #e5e7eb; pointer-events: none; }
.obo-btn-disabled text { color: #9ca3af; font-size: 17px; font-weight: 600; }
</style>
