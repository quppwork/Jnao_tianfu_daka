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
            <text class="pcard-sub">第一次使用 Jnao · 完成天赋测试</text>
          </view>
          <view class="pcard pcard-in" style="animation-delay:0.55s" @tap="selectStudentType('returning')">
            <view class="pcard-icon-wrap">
              <svg viewBox="0 0 48 48" width="36" height="36" fill="none" stroke="#58a6ff" stroke-width="2"><circle cx="24" cy="14" r="8"/><path d="M10 44c0-7 6.3-13 14-13s14 6 14 13"/><path d="M24 24v6" stroke-width="2.5" stroke-linecap="round"/></svg>
            </view>
            <text class="pcard-title">老学员</text>
            <text class="pcard-sub">已有训练经验 · 补录历史数据</text>
          </view>
        </view>
      </template>

      <!-- ═══ Step 2: 天赋测试（新/老学员统一） ═══ -->
      <template v-if="step === 2">
        <text class="subtitle">{{ studentType === 'returning' ? '完善信息 2/3' : '完善信息 2/2' }}</text>
        <text class="question">接下来请完成天赋测试</text>
        <text class="q-hint">通过专业测评了解主天赋，为训练方案提供依据</text>
        <view class="card-row single-card">
          <view class="pcard pcard-in pcard-test" style="animation-delay:0.4s" @tap="startTalentTest">
            <view class="pcard-icon-wrap">
              <text style="font-size:32px">🎯</text>
            </view>
            <text class="pcard-title">开始天赋测试</text>
            <text class="pcard-sub">约 5 分钟 · 35 道选择题</text>
          </view>
        </view>
      </template>

      <!-- ═══ Step 4: 老学员选训练能力 + 总体数据 ═══ -->
      <template v-if="step === 4 && studentType === 'returning'">
        <view class="step-fade" key="s4">
        <text class="subtitle">完善信息 3/3</text>
        <!-- 初次训练日期 -->
        <view class="form-list" style="margin-bottom:16px">
          <view class="form-item">
            <text class="form-label">初次训练日期</text>
            <picker mode="date" fields="month" :value="globalPickerDate" :end="todayStr" @change="onPickGlobalDate">
              <view class="form-field picker-field">
                <text :class="{ placeholder: !globalFirstDate }">{{ globalFirstDate || '点击选择年月' }}</text>
                <text class="picker-arrow">▼</text>
              </view>
            </picker>
          </view>
          <view class="form-item">
            <text class="form-label">训练总次数</text>
            <view style="width:100%;">
              <input v-model="globalTotalCount" placeholder="如：120" style="width:100%;height:44px;padding:0 14px;border:2px solid rgba(0,210,255,0.2);border-radius:10px;font-size:14px;color:#0b111e;background:#fff;box-sizing:border-box;" />
            </view>
          </view>
        </view>
        <!-- 训练项目选择 -->
        <text class="question" style="margin-top:0">请问之前做过哪些训练？</text>
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
        <view class="step-fade" :key="'s5-' + step">
        <text class="subtitle">训练数据 {{ currentAbilityIndex + 1 }}/{{ selectedAbilityNames.length }}</text>
        <text class="question">请填写「{{ currentAbility }}」数据</text>
        <text class="q-hint">以下为选填，可留空</text>
        <view class="form-list">
          <!-- 第一次打卡时间 — 年月选择器 -->
          <view class="form-item">
            <text class="form-label">第一次打卡时间</text>
            <picker mode="date" fields="month" :value="pickerDate" :end="todayStr" @change="onPickDate">
              <view class="form-field picker-field">
                <text :class="{ placeholder: !fFirstDate }">{{ fFirstDate || '点击选择年月' }}</text>
                <text class="picker-arrow">▼</text>
              </view>
            </picker>
          </view>
          <!-- 打卡次数 -->
          <view class="form-item">
            <text class="form-label">打卡次数</text>
            <view style="width:100%;">
              <input v-model="fTotalCount" placeholder="如：30" style="width:100%;height:44px;padding:0 14px;border:2px solid rgba(0,210,255,0.2);border-radius:10px;font-size:14px;color:#0b111e;background:#fff;box-sizing:border-box;" />
            </view>
          </view>
          <!-- 最近一次打卡 -->
          <view class="form-item">
            <text class="form-label">最近一次打卡数据</text>
            <view style="display:flex;align-items:center;gap:8px;">
              <input v-model="fLastTime" placeholder="时长" style="width:80px;height:44px;padding:0 8px;border:2px solid rgba(0,210,255,0.2);border-radius:10px;font-size:14px;color:#0b111e;background:#fff;box-sizing:border-box;text-align:center;" />
              <text class="form-unit">分钟</text>
              <input v-model="fLastResult" placeholder="正确率" style="width:80px;height:44px;padding:0 8px;border:2px solid rgba(0,210,255,0.2);border-radius:10px;font-size:14px;color:#0b111e;background:#fff;box-sizing:border-box;text-align:center;" />
              <text class="form-unit">%</text>
            </view>
          </view>
          <!-- 备注 -->
          <view class="form-item">
            <text class="form-label">备注（可选）</text>
            <view style="width:100%;">
              <input v-model="fNote" placeholder="如：中途停过两个月、换过训练项目等" style="width:100%;height:44px;padding:0 14px;border:2px solid rgba(0,210,255,0.2);border-radius:10px;font-size:14px;color:#0b111e;background:#fff;box-sizing:border-box;" />
            </view>
          </view>
        </view>
        <view class="btn-login" style="margin-top:18px" @click="nextDataStep">
          <text>{{ isLastDataStep ? '完成' : '继续' }}</text>
        </view>
        <view class="skip-hint" @click="nextDataStep">
          <text>跳过此项 →</text>
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
import { ref, computed, onMounted } from 'vue'
import { getChildUserId, saveProfile, fetchProfile } from '@/utils/userApi.js'
import { clearTalentState, refreshTalentState } from '@/utils/talentState.js'

const step = ref(1)
const studentType = ref('')
const selectedAbilities = ref([])
const formData = ref({})
const fFirstDate = ref('')
const fTotalCount = ref('')
const fLastTime = ref('')
const fLastResult = ref('')
const fNote = ref('')

// 全局训练数据（Step 4）
const globalFirstDate = ref('')
const globalTotalCount = ref('')

// 日期选择器 — 默认当前年月，不晚于今天
const todayStr = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
})
const pickerDate = computed(() => {
  const m = String(fFirstDate.value || '').match(/(\d{4}).*?(\d{1,2})/)
  if (m) return `${m[1]}-${String(parseInt(m[2])).padStart(2, '0')}`
  return todayStr.value
})
function onPickDate(e) {
  const v = e.detail.value
  const [y, mo] = v.split('-')
  fFirstDate.value = `${y}年${parseInt(mo)}月`
}
const globalPickerDate = computed(() => {
  const m = String(globalFirstDate.value || '').match(/(\d{4}).*?(\d{1,2})/)
  if (m) return `${m[1]}-${String(parseInt(m[2])).padStart(2, '0')}`
  return todayStr.value
})
function onPickGlobalDate(e) {
  const v = e.detail.value
  const [y, mo] = v.split('-')
  globalFirstDate.value = `${y}年${parseInt(mo)}月`
}


const allAbilities = [
  '超脑阅读','影像追忆','扫描速记','极速运算',
  '极速学习','难题专练','文科扫书','理科扫书',
  '高效作业','天赋绘画','音乐灵感','棋类专注'
]

const selectedAbilityNames = computed(() => selectedAbilities.value.map(i => allAbilities[i]))
const currentAbilityIndex = computed(() => step.value - 5)
const currentAbility = computed(() => selectedAbilityNames.value[currentAbilityIndex.value] || '')
const isLastDataStep = computed(() => currentAbilityIndex.value >= selectedAbilityNames.value.length - 1)

function loadCurrentForm() {
  const key = currentAbility.value
  const saved = formData.value[key]
  fFirstDate.value = saved?.firstDate || ''
  fTotalCount.value = saved?.totalCount || ''
  fLastTime.value = saved?.lastTime || ''
  fLastResult.value = saved?.lastResult || ''
  fNote.value = saved?.note || ''
}

function selectStudentType(type) {
  studentType.value = type
  step.value = 2
}

function goBack() {
  if (step.value === 4) { step.value = 2; return }
  if (step.value === 5) { step.value = 4; return }
  if (step.value > 5) { step.value--; return }
  if (step.value === 2) { step.value = 1; return }
  step.value = 1
}

function buildOnboardingPayload({ finalize = false } = {}) {
  const onboarding = {
    student_type: studentType.value || 'new',
    talent_unknown: true,
  }
  if (finalize) {
    onboarding.completed_at = new Date().toISOString()
  }
  if (studentType.value === 'returning') {
    onboarding.first_training_date = globalFirstDate.value || null
    onboarding.total_training_sessions = globalTotalCount.value ? parseInt(globalTotalCount.value) || null : null
    onboarding.prior_abilities = selectedAbilityNames.value
    onboarding.prior_training_data = formData.value
  }
  return onboarding
}

async function persistOnboarding({ finalize = false } = {}) {
  const userId = getChildUserId()
  if (!userId) return
  clearTalentState()
  let existing = {}
  try {
    const p = await fetchProfile(userId)
    existing = p.profile_json?.onboarding || {}
  } catch (_) {}
  const onboarding = { ...existing, ...buildOnboardingPayload({ finalize }) }
  await saveProfile(userId, { profile_json: { onboarding } })
  await refreshTalentState(userId)
}

async function startTalentTest() {
  try { await persistOnboarding() } catch (_) {}
  const st = studentType.value || 'new'
  uni.navigateTo({ url: `/pages/talent/index?from=onboarding&student_type=${st}` })
}

function toggleAbility(ai) {
  const idx = selectedAbilities.value.indexOf(ai)
  if (idx >= 0) { selectedAbilities.value.splice(idx, 1) }
  else { selectedAbilities.value.push(ai) }
}

function confirmAbilities() {
  if (!selectedAbilities.value.length) { uni.showToast({ title: '请至少选择一项', icon: 'none' }); return }
  for (const ab of selectedAbilityNames.value) {
    if (!formData.value[ab]) formData.value[ab] = { firstDate: '', totalCount: '', lastTime: '', lastResult: '' }
  }
  step.value = 5
  loadCurrentForm()
}

function nextDataStep() {
  formData.value[currentAbility.value] = {
    firstDate: fFirstDate.value, totalCount: fTotalCount.value,
    lastTime: fLastTime.value, lastResult: fLastResult.value,
    note: fNote.value,
  }
  if (isLastDataStep.value) { step.value = 100 }
  else { step.value++; loadCurrentForm() }
}

async function goHome() {
  try { await persistOnboarding({ finalize: true }) } catch (_) {}
  uni.redirectTo({ url: '/pages/index' })
}

onMounted(async () => {
  const pages = getCurrentPages()
  const opts = pages[pages.length - 1]?.options || {}
  if (opts.resume === '4') {
    studentType.value = 'returning'
    step.value = 4
    return
  }
  const uid = getChildUserId()
  if (!uid) {
    uni.redirectTo({ url: '/pages/login/index' })
    return
  }
  try {
    const p = await fetchProfile(uid)
    const ob = p.profile_json?.onboarding || {}
    if (ob.completed_at) {
      uni.redirectTo({ url: '/pages/index' })
      return
    }
    if (ob.student_type) studentType.value = ob.student_type
    if (ob.talent_test_done && ob.student_type === 'returning') {
      step.value = 4
      globalFirstDate.value = ob.first_training_date || ''
      globalTotalCount.value = ob.total_training_sessions ? String(ob.total_training_sessions) : ''
      if (ob.prior_abilities?.length) {
        selectedAbilities.value = ob.prior_abilities
          .map((n) => allAbilities.indexOf(n))
          .filter((i) => i >= 0)
      }
      formData.value = ob.prior_training_data || {}
    } else if (ob.student_type) {
      step.value = 2
    }
  } catch (_) {}
})
</script>

<style scoped>
.app { min-height:100vh; max-width:480px; margin:0 auto; background:var(--bg); display:flex; align-items:flex-start; justify-content:center; padding:30px; padding-top:60px; font-family:-apple-system,"PingFang SC",sans-serif; }
.card { width:100%; padding-bottom:40px; }
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
.card-row.single-card { justify-content:center; }
.card-row.single-card .pcard { max-width:220px; }
.pcard-test { border-color:var(--accent); }
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
.form-field { width:100%; padding:12px 14px; border:2px solid rgba(0,210,255,0.2); border-radius:10px; font-size:14px; color:#0b111e; background:#fff; outline:none; box-sizing:border-box; }
.form-field.short { width:80px; flex:none; }
.form-inline { display:flex; align-items:center; gap:8px; }
.form-unit { color:var(--text-dim); font-size:13px; }

/* ── Picker ── */
.picker-field { display:flex; align-items:center; justify-content:space-between; cursor:pointer; }
.picker-field .placeholder { color:var(--text-dim); }
.picker-arrow { color:var(--text-dim); font-size:10px; margin-left:8px; }

/* ── Skip hint ── */
.skip-hint { text-align:center; margin-top:12px; cursor:pointer; }
.skip-hint text { color:var(--text-dim); font-size:12px; }

@keyframes checkPop { 0%{transform:scale(0)} 60%{transform:scale(1.3)} 100%{transform:scale(1)} }

.btn-login { max-width:340px; margin:18px auto 0; background:linear-gradient(135deg,var(--accent),#3b8bff); border-radius:14px; padding:15px; text-align:center; cursor:pointer; }
.btn-login text { color:#fff; font-size:16px; font-weight:700; }
.btn-login:active { opacity:0.85; }

@keyframes cardSpring { 0%{opacity:0;transform:scale(0.9) translateY(12px)} 100%{opacity:1;transform:scale(1) translateY(0)} }

.step-fade { }
</style>
