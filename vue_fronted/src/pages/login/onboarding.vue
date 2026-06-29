<template>
  <view class="app">
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
          <view class="pcard pcard-in pcard-locked" style="animation-delay:0.55s" @tap="onReturningTap">
            <view class="pcard-icon-wrap pcard-icon-dim">
              <svg viewBox="0 0 48 48" width="36" height="36" fill="none" stroke="#8b949e" stroke-width="2"><circle cx="24" cy="14" r="8"/><path d="M10 44c0-7 6.3-13 14-13s14 6 14 13"/><path d="M24 24v6" stroke-width="2.5" stroke-linecap="round"/></svg>
            </view>
            <text class="pcard-title" style="color:var(--text-dim);">老学员</text>
            <text class="pcard-sub" style="color:var(--text-dim);">已有经验 · 即将开放</text>
            <view class="lock-badge">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#8b949e" stroke-width="2.5" stroke-linecap="round"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 1 1 8 0v4"/></svg>
            </view>
          </view>
        </view>
      </template>

      <!-- ═══ Step 2: 选天赋（仅新学员） ═══ -->
      <template v-if="step === 2">
        <text class="subtitle">完善信息 2/2</text>
        <text class="question">请问你的主天赋是什么？</text>
        <view class="talent-grid">
          <view
            v-for="t in talents"
            :key="t.name"
            class="talent-card"
            :class="{ selected: selectedTalent === t.name }"
            :style="{
              animationDelay: t.delay,
              borderColor: selectedTalent === t.name ? t.color : 'var(--border)',
              background: selectedTalent === t.name ? t.color + '14' : 'var(--bg-card)'
            }"
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
            class="talent-card talent-unknown"
            :class="{ selected: selectedTalent === 'unknown' }"
            style="animation-delay:1.0s"
            @click="selectTalent('unknown')"
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
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { getChildUserId, saveProfile } from '@/utils/userApi.js'

const step = ref(1)
const studentType = ref('')
const selectedTalent = ref('')

const talents = [
  { name: '学者', color: '#12417A', desc: '逻辑思辨 · 知识探索', delay: '0.4s' },
  { name: '思者', color: '#22C55E', desc: '创意灵性 · 直觉洞察', delay: '0.5s' },
  { name: '行者', color: '#A57A1A', desc: '实践行动 · 执行推进', delay: '0.6s' },
  { name: '德者', color: '#582E1F', desc: '共情利他 · 关系建设', delay: '0.7s' },
  { name: '赢者', color: '#960D24', desc: '目标驱动 · 领导统领', delay: '0.8s' },
]

function onReturningTap() {
  uni.showToast({ title: '暂无老学员功能，等待后续完善', icon: 'none', duration: 2000 })
}

async function selectStudentType(type) {
  if (type === 'returning') return // locked
  studentType.value = type
  step.value = 2
}

function selectTalent(name) {
  selectedTalent.value = name
}

async function confirmTalent() {
  if (!selectedTalent.value) {
    uni.showToast({ title: '请选择一个天赋或"不知道"', icon: 'none' })
    return
  }

  const userId = getChildUserId()
  const onboarding = {
    student_type: 'new',
    completed_at: new Date().toISOString(),
  }

  if (selectedTalent.value === 'unknown') {
    onboarding.self_reported_talent = null
    onboarding.talent_unknown = true
  } else {
    const talentCodeMap = { '学者': 1, '思者': 2, '行者': 3, '德者': 4, '赢者': 5 }
    onboarding.self_reported_talent = selectedTalent.value
    onboarding.self_reported_talent_code = talentCodeMap[selectedTalent.value]
    onboarding.talent_unknown = false
  }

  try {
    await saveProfile(userId, { profile_json: { onboarding } })
  } catch (_) { /* ignore */ }

  if (selectedTalent.value === 'unknown') {
    uni.redirectTo({ url: '/pages/talent/index' })
    setTimeout(() => {
      uni.showToast({ title: '请开始天赋测试，了解你的天赋类型吧！', icon: 'none', duration: 2500 })
    }, 600)
  } else {
    uni.redirectTo({ url: '/pages/index' })
  }
}
</script>

<style scoped>
.app { height:100vh; max-width:480px; margin:0 auto; background:var(--bg); display:flex; align-items:center; justify-content:center; padding:30px; font-family:-apple-system,"PingFang SC",sans-serif; }
.card { width:100%; }
.logo-row { display:flex; align-items:baseline; justify-content:center; gap:6px; margin-bottom:6px; }
.logo-j { color:#dc2626; font-size:44px; font-weight:800; }
.logo-nao { color:var(--text); font-size:34px; font-weight:700; }
.logo-ai { color:var(--text); font-size:34px; font-weight:300; }
.subtitle { color:var(--text-dim); font-size:13px; text-align:center; display:block; margin-bottom:8px; letter-spacing:0.06em; }
.question { color:var(--text); font-size:17px; font-weight:700; text-align:center; display:block; margin-bottom:20px; }

/* ── Card row (matching talent test page) ── */
.card-row { display:flex; gap:14px; width:100%; max-width:340px; margin:24px auto 0; }

.pcard { flex:1; aspect-ratio:1; background:var(--bg-card); border-radius:18px; border:2px solid var(--border); display:flex; flex-direction:column; align-items:center; justify-content:center; padding:16px 10px; cursor:pointer; transition:all 0.15s; opacity:0; transform:scale(0.9) translateY(12px); }
.pcard:active { transform:scale(0.95) !important; }
.pcard-in { animation:cardSpring 0.6s cubic-bezier(0.34,1.56,0.64,1) forwards; }
.pcard-locked { opacity:0.55; cursor:not-allowed; position:relative; }
.pcard-locked:active { transform:scale(1) !important; }

.pcard-icon-wrap { width:52px; height:52px; border-radius:14px; background:var(--accent-bg); display:flex; align-items:center; justify-content:center; margin-bottom:8px; }
.pcard-icon-dim { background:rgba(139,148,158,0.08); }
.pcard-title { color:var(--text); font-size:16px; font-weight:700; text-align:center; margin-bottom:4px; display:block; }
.pcard-sub { color:var(--text-dim); font-size:11px; text-align:center; line-height:1.4; display:block; }

.lock-badge { position:absolute; top:8px; right:8px; width:24px; height:24px; border-radius:50%; background:rgba(139,148,158,0.12); display:flex; align-items:center; justify-content:center; }

/* Talent grid (step 2) */
.talent-grid { display:flex; flex-direction:column; gap:10px; max-width:340px; margin:0 auto; }
.talent-card { display:flex; align-items:center; background:var(--bg-card); border-radius:14px; padding:14px; border:1.5px solid var(--border); cursor:pointer; transition:border-color .2s,background .2s,transform .15s; opacity:0; transform:scale(0.9) translateY(12px); animation:cardSpring 0.5s cubic-bezier(0.34,1.56,0.64,1) forwards; position:relative; }
.talent-card:active { transform:scale(0.97); }
.talent-card.selected { transform:scale(1.02); }
.talent-dot { width:14px; height:14px; border-radius:50%; margin-right:12px; flex-shrink:0; }
.talent-name { font-size:16px; font-weight:700; margin-right:10px; }
.talent-desc { color:var(--text-dim); font-size:12px; }
.talent-check { margin-left:auto; flex-shrink:0; animation:checkPop 0.3s cubic-bezier(0.34,1.56,0.64,1); }

/* Unknown option — same shape as talent cards */
.talent-unknown { }
.unknown-dot { width:14px; height:14px; border-radius:50%; background:linear-gradient(135deg,#f0b90b,#f5a623); }
.unknown-name { color:#d4a017; }
.talent-unknown.selected { border-color:#f0b90b; background:rgba(240,185,11,0.08); }

@keyframes checkPop { 0%{transform:scale(0)} 60%{transform:scale(1.3)} 100%{transform:scale(1)} }

.btn-login { max-width:340px; margin:18px auto 0; background:linear-gradient(135deg,var(--accent),#3b8bff); border-radius:14px; padding:15px; text-align:center; cursor:pointer; }
.btn-login text { color:#fff; font-size:16px; font-weight:700; }
.btn-login:active { opacity:0.85; }

@keyframes cardSpring { 0%{opacity:0;transform:scale(0.9) translateY(12px)} 100%{opacity:1;transform:scale(1) translateY(0)} }
</style>
