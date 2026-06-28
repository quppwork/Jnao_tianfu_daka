<template>
  <view class="app">
    <view v-if="step >= 2 && step < 100" class="fixed-back" @tap="goBack">
      <text>← 返回</text>
    </view>
    <view class="card">
      <view class="logo-row">
        <text class="logo-j">J</text><text class="logo-nao">nao</text><text class="logo-ai">AI</text>
      </view>

      <!-- ═══ Step 1: 新/老学员 ═══ -->
      <template v-if="step === 1">
        <text class="subtitle">完善信息 1/2</text>
        <text class="question">请问你是新学员还是老学员？</text>
        <view class="card-row">
          <view class="pcard pcard-in" style="animation-delay:0.4s" @tap="selectStudentType('new')">
            <view class="pcard-icon-wrap">
              <svg viewBox="0 0 48 48" width="36" height="36" fill="none" stroke="#58a6ff" stroke-width="2"><circle cx="24" cy="16" r="7"/><path d="M16 44c0-6 4-11 8-11s8 5 8 11"/><circle cx="24" cy="16" r="9" stroke-dasharray="3 3" opacity="0.4"/><line x1="20" y1="20" x2="16" y2="24" stroke-width="2.5" stroke-linecap="round"/><line x1="28" y1="20" x2="32" y2="24" stroke-width="2.5" stroke-linecap="round"/></svg>
            </view>
            <text class="pcard-title">新学员</text>
            <text class="pcard-sub">第一次使用 Jnao · 设置天赋</text>
          </view>
          <view class="pcard pcard-in" style="animation-delay:0.55s" @tap="selectStudentType('returning')">
            <view class="pcard-icon-wrap">
              <svg viewBox="0 0 48 48" width="36" height="36" fill="none" stroke="#58a6ff" stroke-width="2"><circle cx="24" cy="14" r="8"/><path d="M10 44c0-7 6.3-13 14-13s14 6 14 13"/><path d="M24 24v6" stroke-width="2.5" stroke-linecap="round"/></svg>
            </view>
            <text class="pcard-title">老学员</text>
            <text class="pcard-sub">已有训练经验 · 快速设置</text>
          </view>
        </view>
      </template>

      <!-- ═══ Step 2: 选天赋（仅新学员） ═══ -->
      <template v-if="step === 2 && studentType === 'new'">
        <text class="subtitle">完善信息 2/2</text>
        <text class="question">请问你的主天赋是什么？</text>
        <view class="talent-grid">
          <view
            v-for="t in talents"
            :key="t.name"
            class="talent-card"
            :class="{ selected: selectedTalent === t.name }"
            :style="{ animationDelay: t.delay, borderColor: selectedTalent === t.name ? t.color : 'var(--border)', background: selectedTalent === t.name ? t.color + '14' : 'var(--bg-card)' }"
            @click="selectTalent(t.name)"
          >
            <view class="talent-dot" :style="{ background: t.color }"></view>
            <text class="talent-name" :style="{ color: t.color }">{{ t.name }}</text>
            <text class="talent-desc">{{ t.desc }}</text>
            <view v-if="selectedTalent === t.name" class="talent-check">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" :stroke="t.color" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            </view>
          </view>
          <view
            class="talent-card talent-unknown" :class="{ selected: selectedTalent === 'unknown' }"
            style="animation-delay:1.0s" @click="selectTalent('unknown')"
          >
            <view class="talent-dot unknown-dot"></view>
            <text class="talent-name unknown-name">不知道</text>
            <text class="talent-desc">帮我测一测天赋</text>
            <view v-if="selectedTalent === 'unknown'" class="talent-check">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#f0b90b" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            </view>
          </view>
        </view>
        <view class="btn-login" style="margin-top:18px" @click="confirmTalent">
          <text>确认并完成</text>
        </view>
      </template>

      <!-- ═══ Step 3: 老学员选天赋 ═══ -->
      <template v-if="step === 3 && studentType === 'returning'">
        <view class="step-fade" key="step3">
        <text class="subtitle">完善信息 2/3</text>
        <text class="question">请问你的主天赋是什么？</text>
        <view class="talent-grid">
          <view
            v-for="t in talents"
            :key="t.name"
            class="talent-card" :class="{ selected: selectedTalent === t.name }"
            :style="{ animationDelay: t.delay, borderColor: selectedTalent === t.name ? t.color : 'var(--border)', background: selectedTalent === t.name ? t.color + '14' : 'var(--bg-card)' }"
            @click="selectTalent(t.name)"
          >
            <view class="talent-dot" :style="{ background: t.color }"></view>
            <text class="talent-name" :style="{ color: t.color }">{{ t.name }}</text>
            <text class="talent-desc">{{ t.desc }}</text>
            <view v-if="selectedTalent === t.name" class="talent-check">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" :stroke="t.color" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            </view>
          </view>
          <view
            class="talent-card talent-unknown" :class="{ selected: selectedTalent === 'unknown' }"
            style="animation-delay:1.0s" @click="selectTalent('unknown')"
          >
            <view class="talent-dot unknown-dot"></view>
            <text class="talent-name unknown-name">不知道</text>
            <text class="talent-desc">帮我测一测天赋</text>
            <view v-if="selectedTalent === 'unknown'" class="talent-check">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#f0b90b" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            </view>
          </view>
        </view>
        <view class="btn-login" style="margin-top:18px" @click="confirmReturningTalent">
          <text>继续</text>
        </view>
        </view>
      </template>

      <!-- ═══ Step 4: 老学员选训练能力 ═══ -->
      <template v-if="step === 4 && studentType === 'returning'">
        <view class="step-fade" key="step4">
        <text class="subtitle">完善信息 3/3</text>
        <text class="question">请问之前做过哪些训练？</text>
        <text class="q-hint">可多选</text>
        <view class="ability-grid">
          <view
            v-for="(ab, ai) in allAbilities"
            :key="ai"
            class="ability-chip"
            :class="{ on: selectedAbilities.includes(ai) }"
            @click="toggleAbility(ai)"
          >
            <text>{{ ab }}</text>
          </view>
        </view>
        <view class="btn-login" style="margin-top:18px" :style="{ opacity: selectedAbilities.length ? 1 : 0.4 }" @click="confirmAbilities">
          <text>继续</text>
        </view>
        </view>
      </template>

      <!-- ═══ Step 5+: 老学员逐项填数据 ═══ -->
      <template v-if="step >= 5 && studentType === 'returning' && currentAbility">
        <view class="step-fade" :key="'data-' + step">
          <text class="subtitle">训练数据 {{ currentAbilityIndex + 1 }}/{{ selectedAbilityNames.length }}</text>
          <text class="question">请填写「{{ currentAbility }}」数据</text>
          <view class="form-list">
            <view class="form-item">
              <text class="form-label">第一次打卡时间</text>
              <input class="form-field" v-model="currentForm.firstDate" placeholder="如：2025年3月 或 2025-03" />
            </view>
            <view class="form-item">
              <text class="form-label">至今打卡次数（大概）</text>
              <input class="form-field" v-model="currentForm.totalCount" type="number" placeholder="如：30" />
            </view>
            <view class="form-item">
              <text class="form-label">最近一次打卡数据</text>
              <view class="form-inline">
                <input class="form-field short" v-model="currentForm.lastTime" type="number" placeholder="时长" />
                <text class="form-unit">分钟</text>
                <input class="form-field short" v-model="currentForm.lastResult" type="number" placeholder="正确率" />
                <text class="form-unit">%</text>
              </view>
            </view>
          </view>
          <view class="btn-login" style="margin-top:18px" :style="{ opacity: canNextData ? 1 : 0.4 }" @click="nextDataStep">
            <text>{{ isLastDataStep ? '完成' : '继续' }}</text>
          </view>
        </view>
      </template>

      <!-- ═══ 完成页 ═══ -->
      <template v-if="step === 100">
        <view style="text-align:center;padding:20px 0;">
          <text style="font-size:48px;display:block;margin-bottom:12px;">🎯</text>
          <text class="question">设置完成！</text>
          <text class="q-hint">已为你准备好训练方案</text>
        </view>
        <view class="btn-login" style="margin-top:18px" @click="goHome">
          <text>开始训练</text>
        </view>
      </template>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, reactive, watch } from 'vue'
import { getChildUserId, saveProfile } from '@/utils/userApi.js'

const step = ref(1)
const studentType = ref('')
const selectedTalent = ref('')
const selectedAbilities = ref([])
const formData = ref({})
const currentForm = reactive({ firstDate: '', totalCount: '', lastTime: '', lastResult: '' })

watch([() => step.value, currentAbility], () => {
  if (step.value >= 5 && currentAbility.value) {
    const saved = formData.value[currentAbility.value]
    if (saved) {
      currentForm.firstDate = saved.firstDate || ''
      currentForm.totalCount = saved.totalCount || ''
      currentForm.lastTime = saved.lastTime || ''
      currentForm.lastResult = saved.lastResult || ''
    } else {
      currentForm.firstDate = ''
      currentForm.totalCount = ''
      currentForm.lastTime = ''
      currentForm.lastResult = ''
    }
  }
}, { immediate: true })

const talents = [
  { name: '学者', color: '#12417A', desc: '逻辑思辨 · 知识探索', delay: '0.4s' },
  { name: '思者', color: '#22C55E', desc: '创意灵性 · 直觉洞察', delay: '0.5s' },
  { name: '行者', color: '#A57A1A', desc: '实践行动 · 执行推进', delay: '0.6s' },
  { name: '德者', color: '#582E1F', desc: '共情利他 · 关系建设', delay: '0.7s' },
  { name: '赢者', color: '#960D24', desc: '目标驱动 · 领导统领', delay: '0.8s' },
]

const allAbilities = [
  '超脑阅读','影像追忆','扫描速记','极速运算',
  '极速学习','难题专练','文科扫书','理科扫书',
  '高效作业','天赋绘画','音乐灵感','棋类专注'
]

const selectedAbilityNames = computed(() => selectedAbilities.value.map(i => allAbilities[i]))
const currentAbilityIndex = computed(() => step.value - 5)
const currentAbility = computed(() => selectedAbilityNames.value[currentAbilityIndex.value] || '')
const isLastDataStep = computed(() => currentAbilityIndex.value >= selectedAbilityNames.value.length - 1)

const canNextData = computed(() => {
  return currentForm.firstDate && currentForm.totalCount && currentForm.lastTime && currentForm.lastResult
})

function selectStudentType(type) {
  studentType.value = type
  if (type === 'new') {
    step.value = 2
  } else {
    step.value = 3
  }
}

function goBack() {
  if (step.value === 3) { step.value = 1; return }
  if (step.value === 4) { step.value = 3; selectedTalent.value = ''; return }
  if (step.value === 5) { step.value = 4; return }
  if (step.value > 5) { step.value--; return }
  step.value = 1
}

function selectTalent(name) { selectedTalent.value = name }

async function confirmTalent() {
  if (!selectedTalent.value) { uni.showToast({ title: '请选择一个天赋或"不知道"', icon: 'none' }); return }
  const userId = getChildUserId()
  const onboarding = { student_type: 'new', completed_at: new Date().toISOString() }
  if (selectedTalent.value === 'unknown') { onboarding.talent_unknown = true }
  else { onboarding.self_reported_talent = selectedTalent.value }
  try { await saveProfile(userId, { profile_json: { onboarding } }) } catch (_) {}
  if (selectedTalent.value === 'unknown') {
    uni.redirectTo({ url: '/pages/talent/index' })
  } else {
    uni.redirectTo({ url: '/pages/index' })
  }
}

function confirmReturningTalent() {
  if (!selectedTalent.value) { uni.showToast({ title: '请选择一个天赋', icon: 'none' }); return }
  if (selectedTalent.value === 'unknown') {
    uni.redirectTo({ url: '/pages/talent/index' })
  } else {
    step.value = 4
  }
}

function toggleAbility(ai) {
  const idx = selectedAbilities.value.indexOf(ai)
  if (idx >= 0) { selectedAbilities.value.splice(idx, 1) }
  else { selectedAbilities.value.push(ai) }
}

function confirmAbilities() {
  if (!selectedAbilities.value.length) { uni.showToast({ title: '请至少选择一项', icon: 'none' }); return }
  // 预初始化所有选中能力的表单数据
  for (const ab of selectedAbilityNames.value) {
    if (!formData.value[ab]) {
      formData.value[ab] = { firstDate: '', totalCount: '', lastTime: '', lastResult: '' }
    }
  }
  step.value = 5
}

function nextDataStep() {
  if (!canNextData.value) return
  // 保存当前表单到 formData
  formData.value[currentAbility.value] = { ...currentForm }
  if (isLastDataStep.value) {
    step.value = 100
  } else {
    step.value++
  }
}

function goHome() {
  uni.redirectTo({ url: '/pages/index' })
}
</script>

<style scoped>
.app { height:100vh; max-width:480px; margin:0 auto; background:var(--bg); display:flex; align-items:center; justify-content:center; padding:30px; font-family:-apple-system,"PingFang SC",sans-serif; }
.card { width:100%; max-height:100%; overflow-y:auto; }
.fixed-back { position:fixed; top:16px; left:16px; z-index:100; cursor:pointer; }
.fixed-back text { color: var(--accent); font-size:14px; }
.logo-row { display:flex; align-items:baseline; justify-content:center; gap:6px; margin-bottom:6px; }
.logo-j { color:#dc2626; font-size:44px; font-weight:800; }
.logo-nao { color:var(--text); font-size:34px; font-weight:700; }
.logo-ai { color:var(--text); font-size:34px; font-weight:300; }
.subtitle { color:var(--text-dim); font-size:13px; text-align:center; display:block; margin-bottom:8px; letter-spacing:0.06em; }
.question { color:var(--text); font-size:17px; font-weight:700; text-align:center; display:block; margin-bottom:20px; }
.q-hint { color:var(--text-dim); font-size:13px; text-align:center; display:block; margin-bottom:14px; }

/* ── Card row ── */
.card-row { display:flex; gap:14px; width:100%; max-width:340px; margin:24px auto 0; }
.pcard { flex:1; aspect-ratio:1; background:var(--bg-card); border-radius:18px; border:2px solid var(--border); display:flex; flex-direction:column; align-items:center; justify-content:center; padding:16px 10px; cursor:pointer; transition:all 0.15s; opacity:0; transform:scale(0.9) translateY(12px); }
.pcard:active { transform:scale(0.95) !important; }
.pcard-in { animation:cardSpring 0.6s cubic-bezier(0.34,1.56,0.64,1) forwards; }
.pcard-icon-wrap { width:52px; height:52px; border-radius:14px; background:var(--accent-bg); display:flex; align-items:center; justify-content:center; margin-bottom:8px; }
.pcard-title { color:var(--text); font-size:16px; font-weight:700; text-align:center; margin-bottom:4px; display:block; }
.pcard-sub { color:var(--text-dim); font-size:11px; text-align:center; line-height:1.4; display:block; }

/* Talent grid */
.talent-grid { display:flex; flex-direction:column; gap:10px; max-width:340px; margin:0 auto; }
.talent-card { display:flex; align-items:center; background:var(--bg-card); border-radius:14px; padding:14px; border:1.5px solid var(--border); cursor:pointer; transition:border-color .2s,background .2s,transform .15s; opacity:0; transform:scale(0.9) translateY(12px); animation:cardSpring 0.5s cubic-bezier(0.34,1.56,0.64,1) forwards; position:relative; }
.talent-card:active { transform:scale(0.97); }
.talent-card.selected { transform:scale(1.02); }
.talent-dot { width:14px; height:14px; border-radius:50%; margin-right:12px; flex-shrink:0; }
.talent-name { font-size:16px; font-weight:700; margin-right:10px; }
.talent-desc { color:var(--text-dim); font-size:12px; }
.talent-check { margin-left:auto; flex-shrink:0; animation:checkPop 0.3s cubic-bezier(0.34,1.56,0.64,1); }
.talent-unknown { }
.unknown-dot { width:14px; height:14px; border-radius:50%; background:linear-gradient(135deg,#f0b90b,#f5a623); }
.unknown-name { color:#d4a017; }
.talent-unknown.selected { border-color:#f0b90b; background:rgba(240,185,11,0.08); }

/* Ability grid (4×3) */
.ability-grid { display:flex; flex-wrap:wrap; gap:8px; max-width:340px; margin:0 auto; }
.ability-chip { width:calc(25% - 6px); padding:10px 4px; border-radius:12px; border:1.5px solid var(--border); background:var(--bg-card); text-align:center; cursor:pointer; transition:all 0.15s; box-sizing:border-box; }
.ability-chip text { font-size:12px; color:var(--text-dim); }
.ability-chip:active { background:var(--accent-bg); }
.ability-chip.on { border-color:var(--accent); background:var(--accent-bg); }
.ability-chip.on text { color:var(--accent); font-weight:600; }

/* Form list */
.form-list { display:flex; flex-direction:column; gap:16px; max-width:340px; margin:0 auto; }
.form-item { }
.form-label { color:var(--text-dim); font-size:13px; display:block; margin-bottom:6px; }
.form-field { width:100%; padding:12px 14px; border:1.5px solid var(--border); border-radius:12px; font-size:14px; color:var(--text); background:var(--bg-card); outline:none; box-sizing:border-box; }
.form-field.short { width:80px; flex:none; }
.form-inline { display:flex; align-items:center; gap:8px; }
.form-unit { color:var(--text-dim); font-size:13px; }

@keyframes checkPop { 0%{transform:scale(0)} 60%{transform:scale(1.3)} 100%{transform:scale(1)} }

.btn-login { max-width:340px; margin:18px auto 0; background:linear-gradient(135deg,var(--accent),#3b8bff); border-radius:14px; padding:15px; text-align:center; cursor:pointer; }
.btn-login text { color:#fff; font-size:16px; font-weight:700; }
.btn-login:active { opacity:0.85; }

@keyframes cardSpring { 0%{opacity:0;transform:scale(0.9) translateY(12px)} 100%{opacity:1;transform:scale(1) translateY(0)} }

.step-fade { animation: stepFadeIn 0.35s ease-out; }
@keyframes stepFadeIn { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
</style>
