<template>
  <view class="app">
    <!-- Nav -->
    <view class="nav">
      <view class="nav-back" @click="goBack">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#8b5cf6" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      </view>
      <text class="nav-title">我的天赋报告</text>
      <view class="nav-spacer"></view>
    </view>

    <!-- Loading -->
    <view v-if="loading" class="load-wrap">
      <view class="load-spin"></view>
      <text class="load-text">正在发现你的超能力...</text>
    </view>

    <!-- Error -->
    <view v-else-if="loadError" class="err-wrap">
      <text class="err-icon">😅</text>
      <text class="err-text">{{ loadError }}</text>
      <view class="err-btn" @click="loadReport">
        <text>再试一次</text>
      </view>
    </view>

    <!-- Report Content -->
    <scroll-view v-else-if="report" class="body" scroll-y :show-scrollbar="false">
      <view class="content" :class="{ 'content-in': showContent }">

        <!-- Mizhe Warning -->
        <view v-if="isMizhe" class="card warn-card">
          <text class="warn-emoji">⚠️</text>
          <text class="warn-title">结果不太明确哦</text>
          <text class="warn-desc">重新测一次吧，会更准确的！</text>
          <view class="warn-btn" @click="reTest"><text>🔄 重新测试</text></view>
        </view>

        <!-- Conflict -->
        <view v-if="talentConflict" class="card warn-card" style="border-color:#8b5cf6;background:rgba(139,92,246,0.04);">
          <text class="warn-emoji">🔄</text>
          <text class="warn-title" style="color:#7c3aed;">天赋结果不一样了</text>
          <text class="warn-desc">你之前是「{{ currentTalent }}」，这次测出来是「{{ report?.talent || '--' }}」。要换吗？</text>
          <view class="warn-btns">
            <view class="warn-btn warn-btn-outline" @click="handleConflictResolve('keep_old')"><text>保留「{{ currentTalent }}」</text></view>
            <view class="warn-btn" @click="handleConflictResolve('use_new')"><text>换成「{{ report?.talent || '--' }}」</text></view>
          </view>
        </view>

        <!-- Locked -->
        <view v-if="talentLocked" class="card warn-card" style="border-color:#cbd5e1;">
          <text class="warn-emoji">🔒</text>
          <text class="warn-title" style="color:#64748b;">天赋已锁定</text>
          <text class="warn-desc">{{ lockMessage }}</text>
        </view>

        <!-- Hero -->
        <view class="card hero-card">
          <image v-if="talentBgFig" :src="talentBgFig" mode="aspectFit" class="hero-bg" />
          <view class="hero-row">
            <image v-if="talentLogo" :src="talentLogo" class="hero-avatar" mode="aspectFill" />
            <view v-else class="hero-avatar hero-avatar-fallback">
              <text class="hero-avatar-emoji">{{ talentEmoji }}</text>
            </view>
            <view class="hero-text">
              <text class="hero-greet">🚀 嗨，小小探险家！</text>
              <text class="hero-name">{{ talentDisplay }}</text>
              <text class="hero-tagline">{{ kidTagline }}</text>
            </view>
          </view>
        </view>

        <!-- Stats -->
        <view class="card stats-card">
          <view class="stat">
            <text class="stat-val" :style="{ color: kidColor }">{{ talentVal }}</text>
            <text class="stat-lbl">⭐ 能量值</text>
          </view>
          <view class="stat">
            <text class="stat-val">🌱</text>
            <text class="stat-lbl">成长中</text>
          </view>
          <view class="stat">
            <text class="stat-val">{{ stateEmoji }}</text>
            <text class="stat-lbl">{{ stateLabel }}</text>
          </view>
        </view>

        <!-- Radar -->
        <view class="card" v-if="kidAbilities.length">
          <text class="sec-title">🌟 超能力雷达</text>
          <view v-html="kidRadarSvg" class="radar-wrap"></view>
        </view>

        <!-- Super Powers -->
        <view class="card" v-if="kidAbilities.length">
          <text class="sec-title">⭐ 你的神奇能量</text>
          <view v-for="(a, i) in kidAbilities" :key="a.id || i" class="eng-row">
            <view class="eng-top">
              <text class="eng-emoji">{{ a.emoji }}</text>
              <text class="eng-name">{{ a.label }}</text>
              <view class="eng-gems">
                <text v-for="g in 5" :key="g" class="eng-gem" :class="{ on: g <= a.stars }">{{ g <= a.stars ? '⭐' : '☆' }}</text>
              </view>
            </view>
            <view class="eng-bar"><view class="eng-fill" :style="{ width: Math.min(a.value||0,100) + '%', background: a.color }"></view></view>
            <text class="eng-tip">{{ a.tip }}</text>
          </view>
        </view>

        <!-- Teacher Messages -->
        <view class="card" v-if="wordsForYou || goldenAdvice.length">
          <text class="sec-title">💬 老师悄悄对你说</text>

          <view v-if="wordsForYou" class="bub bub-l">
            <text class="bub-t" v-html="cleanWords"></text>
          </view>

          <view v-if="goldenAdvice.length" style="margin-top:12px;">
            <text class="challenge-title">🎯 给你的小挑战</text>
            <view v-for="(t, i) in goldenAdvice" :key="i" class="bub" :class="i % 2 === 0 ? 'bub-l' : 'bub-r'">
              <view class="bub-num">{{ i + 1 }}</view>
              <text class="bub-t">{{ t }}</text>
            </view>
          </view>
        </view>

        <!-- Video -->
        <view class="card video-card" @click="openVideo">
          <view class="video-inner">
            <text class="video-emoji">▶️</text>
            <text class="video-text">看看你的天赋视频讲解</text>
          </view>
        </view>

        <!-- Parent Link -->
        <view class="parent-link" @click="goParentReport">
          <text class="parent-link-text">👨‍👩‍👧 给爸爸妈妈看的详细报告 →</text>
        </view>

        <view style="height:100px;"></view>
      </view>
    </scroll-view>

    <!-- Fallback: should never reach here -->
    <view v-else class="load-wrap">
      <text class="load-text">加载中...</text>
    </view>

    <!-- Bottom Bar -->
    <view v-if="report" class="bbar">
      <view class="bbtn" @click="goHome"><text>🚀 开始新的探险</text></view>
    </view>

    <!-- Video Overlay -->
    <view v-if="showVideo" class="video-overlay" @click="closeVideo">
      <view class="video-card-pop" @click.stop>
        <view class="video-head">
          <text class="video-title">天赋视频讲解</text>
          <view class="video-close" @click="closeVideo"><text>✕</text></view>
        </view>
        <view class="video-body">
          <video v-if="talentVideoUrl" class="talent-video" :src="talentVideoUrl" controls autoplay />
          <text v-else class="video-loading">视频加载中...</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import {
  ensureChildUser,
  fetchAssessmentReport,
  fetchLatestAssessment,
  resolveTalentConflict,
  resolveTrainingStreamUrl,
} from '@/utils/userApi.js'

// Theme
let prevTheme = null
onMounted(() => {
  prevTheme = document.documentElement.getAttribute('data-theme') || null
  document.documentElement.setAttribute('data-theme', 'white')
  loadReport()
})
onBeforeUnmount(() => {
  if (prevTheme) {
    document.documentElement.setAttribute('data-theme', prevTheme)
  } else {
    document.documentElement.removeAttribute('data-theme')
  }
})

// State
const loading = ref(true)
const loadError = ref('')
const report = ref(null)
const reportId = ref('')
const showContent = ref(false)
const talentConflict = ref(false)
const currentTalent = ref('')
const talentLocked = ref(false)
const lockMessage = ref('')
const resolving = ref(false)

async function loadReport() {
  loading.value = true
  loadError.value = ''
  try {
    let assessmentId = ''
    let fromUrl = false
    const pages = getCurrentPages()
    if (pages && pages.length > 0) {
      const page = pages[pages.length - 1]
      assessmentId = page?.options?.assessment_id || ''
      if (assessmentId) fromUrl = true

      if (page?.options?.talent_conflict === '1') {
        talentConflict.value = true
        currentTalent.value = decodeURIComponent(page?.options?.current_talent || '')
      }
      if (page?.options?.talent_locked === '1') {
        talentLocked.value = true
        lockMessage.value = decodeURIComponent(page?.options?.lock_message || '天赋已锁定')
      }
    }

    const uid = await ensureChildUser()

    // 先尝试拿最新的测评作为兜底
    let latestId = ''
    try {
      const latest = await fetchLatestAssessment(uid)
      if (latest?.id) latestId = String(latest.id)
    } catch (_) {}

    // URL 里没有 assessment_id，直接用最新的
    if (!assessmentId) {
      assessmentId = latestId
    }

    if (!assessmentId) {
      loadError.value = '还没有天赋报告哦，先去测试一下吧！'
      return
    }

    // 尝试加载指定测评
    let json
    try {
      json = await fetchAssessmentReport(uid, assessmentId)
    } catch (e) {
      // 如果 URL 里的 ID 无效但有最新测评，自动回退
      if (fromUrl && latestId && latestId !== assessmentId) {
        console.warn('URL 里的测评不存在，回退到最新测评:', latestId)
        json = await fetchAssessmentReport(uid, latestId)
      } else {
        throw e
      }
    }

    if (json.code !== 1) throw new Error('报告加载失败')
    reportId.value = String(json.assessment_id || '')
    report.value = json.data

    nextTick(() => {
      setTimeout(() => { showContent.value = true }, 150)
    })
  } catch (e) {
    console.error('加载报告失败:', e)
    loadError.value = e.message || '报告加载失败，请稍后再试'
  } finally {
    loading.value = false
  }
}

// Computed
const isMizhe = computed(() => {
  const t = report.value?.talent || report.value?.talent_primary || ''
  return t === '迷者'
})

const TALENT_KID_COLORS = { '学者': '#3B82F6', '思者': '#4ADE80', '行者': '#F59E0B', '赢者': '#EF4444', '德者': '#8B5CF6' }
const TALENT_LOGOS = { '学者': '/static/xue.jpg', '思者': '/static/si.jpg', '赢者': '/static/ying.jpg', '德者': '/static/de.jpg', '行者': '/static/xing.jpg' }
const TALENT_FIGS = { '学者': '/static/talent-xuezhe.png', '思者': '/static/talent-sizhe.png', '赢者': '/static/talent-yingzhe.png', '德者': '/static/talent-dezhe.png', '行者': '/static/talent-xingzhe.png' }
const TALENT_EMOJI = { '学者': '📚', '思者': '💡', '行者': '🏃', '德者': '⚖️', '赢者': '🏆' }
const STATE_EMOJI_MAP = { '相争': '🔥', '难辨': '🤔', '牵制': '🎭', '双生': '✨', '本命': '💎', '孤显': '🌙', '无向': '🌫️', '无神': '😴' }
const STATE_LABEL_MAP = { '相争': '充满能量', '难辨': '有点纠结', '牵制': '需要平衡', '双生': '双重力量', '本命': '做自己', '孤显': '独自闪耀', '无向': '找方向中', '无神': '需要休息' }

const kidColor = computed(() => TALENT_KID_COLORS[report.value?.talent] || '#8b5cf6')
const talentLogo = computed(() => TALENT_LOGOS[report.value?.talent] || '')
const talentBgFig = computed(() => TALENT_FIGS[report.value?.talent] || '')
const talentEmoji = computed(() => TALENT_EMOJI[report.value?.talent] || '🧬')

const talentDisplay = computed(() => {
  const ct = report.value?.check_talent
  if (!ct) return report.value?.talent || '--'
  if (Array.isArray(ct) && ct.length >= 2) {
    return String(ct[0]).replace(/者$/, '') + '偏' + String(ct[1]).replace(/者$/, '')
  }
  if (typeof ct === 'string' && ct.includes('偏')) {
    const p = ct.split('偏')
    return p[0].replace(/者$/, '') + '偏' + p[1].replace(/者$/, '')
  }
  return report.value?.talent || '--'
})

const talentVal = computed(() => report.value?.results?.Talent?.value || report.value?.results?.State?.id || '--')
const stateName = computed(() => report.value?.results?.State?.name || '--')
const stateEmoji = computed(() => STATE_EMOJI_MAP[stateName.value] || '😊')
const stateLabel = computed(() => STATE_LABEL_MAP[stateName.value] || stateName.value)
const attrShort = computed(() => stripHtml(report.value?.results?.Attribute?.desp || '').slice(0, 80))

const kidTagline = computed(() => {
  const m = {
    '学者': '你是个爱思考的小天才！',
    '思者': '你脑子转得飞快，总有新点子！',
    '行者': '你是个行动派，做什么都很有干劲！',
    '赢者': '你天生就是小领袖，大家都愿意跟着你！',
    '德者': '你心地善良，总是为别人着想！',
  }
  return m[report.value?.talent] || attrShort.value
})

const Ability = computed(() => {
  const list = Array.isArray(report.value?.results?.Ability) ? [...report.value.results.Ability] : []
  const t = report.value?.results?.Talent
  if (t?.abilityName && t?.abilityID && !list.find(a => a.abilityID === t.abilityID)) {
    list.push({ abilityName: t.abilityName, abilityID: t.abilityID, value: t.value || 0, desp: '', grade: t.grade || 0 })
  }
  return list
})

const KID_LABELS = { '协调力': '🤝 合作力', '执行力': '⚡ 行动力', '公信力': '📢 表达力', '领导力': '👑 领导力', '创新力': '✨ 想象力' }

const kidAbilities = computed(() => Ability.value.map((a, i) => {
  const v = a.value || 0
  const labelPair = KID_LABELS[a.abilityName] || ('⭐ ' + a.abilityName)
  return {
    ...a,
    id: a.abilityID || i,
    label: labelPair.split(' ').slice(1).join(' ') || a.abilityName,
    emoji: labelPair.split(' ')[0] || '⭐',
    stars: v >= 90 ? 5 : v >= 70 ? 4 : v >= 50 ? 3 : v >= 30 ? 2 : 1,
    color: v >= 80 ? '#10b981' : v >= 60 ? '#8b5cf6' : v >= 40 ? '#f59e0b' : '#ef4444',
    tip: v >= 80 ? '太厉害了！' : v >= 60 ? '继续保持哦！' : v >= 40 ? '加油，你可以的！' : '多练练会更好！',
  }
}))

const parsedTalent = computed(() => {
  const html = report.value?.results?.Talent?.desp || ''
  if (!html) return { abilityDesc: '', wordsForYou: '', goldenAdvice: [] }
  const wordsIdx = html.search(/想对你说的话/)
  const goldenIdx = html.search(/三条黄金建议/)
  let abilityDesc = '', wordsForYou = ''
  const goldenAdvice = []
  if (wordsIdx >= 0) {
    abilityDesc = html.slice(0, wordsIdx).replace(/<p[^>]*>\s*<strong>【?天赋能力解读】?<\/strong>\s*<\/p>/gi, '').trim()
    if (goldenIdx >= 0) {
      wordsForYou = html.slice(wordsIdx, goldenIdx).replace(/<[^>]*>\s*想对你说的话\s*<\/[^>]*>/gi, '').trim()
      const goldenBlock = stripHtml(html.slice(goldenIdx)).replace(/三条黄金建议[：:]?/g, '').trim()
      goldenBlock.split(/(?=\d+\.)/).filter(Boolean).forEach(item => {
        const c = item.replace(/^\d+\.\s*/, '').trim()
        if (c) goldenAdvice.push(c)
      })
    } else {
      wordsForYou = html.slice(wordsIdx).replace(/<p[^>]*>\s*<strong>想对你说的话<\/strong>\s*<\/p>/gi, '').trim()
    }
  } else {
    abilityDesc = html.replace(/<p[^>]*>\s*<strong>【?天赋能力解读】?<\/strong>\s*<\/p>/gi, '').trim()
  }
  return { abilityDesc, wordsForYou, goldenAdvice }
})

const wordsForYou = computed(() => parsedTalent.value.wordsForYou)
const goldenAdvice = computed(() => parsedTalent.value.goldenAdvice)
const cleanWords = computed(() => {
  const text = stripHtml(wordsForYou.value)
  return text.replace(/\n/g, '<br>')
})

function stripHtml(h) {
  if (!h) return ''
  return h.replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').trim()
}

// Radar SVG
const ro2 = [{ x: 110, y: 12 }, { x: 190, y: 68 }, { x: 162, y: 158 }, { x: 58, y: 158 }, { x: 30, y: 68 }]
const kidRadarSvg = computed(() => {
  const items = kidAbilities.value.slice(0, 5)
  const pts = items.map((a, i) => {
    const r = Math.min(100, Math.max(0, a.value || 0)) / 100
    const v = ro2[i]
    return `${110 + (v.x - 110) * r},${110 + (v.y - 110) * r}`
  }).join(' ')
  const dots = items.map((a, i) => {
    const r = Math.min(100, Math.max(0, a.value || 0)) / 100
    const v = ro2[i]
    const x = 110 + (v.x - 110) * r
    const y = 110 + (v.y - 110) * r
    return `<circle cx="${x}" cy="${y}" r="3.5" fill="${r >= 0.6 ? '#8b5cf6' : '#c4b5fd'}" stroke="#fff" stroke-width="1.5"/>`
  }).join('')
  const labs = [{ x: 110, y: 6, a: 'middle' }, { x: 200, y: 68, a: 'start' }, { x: 162, y: 180, a: 'middle' }, { x: 58, y: 180, a: 'middle' }, { x: 18, y: 68, a: 'end' }]
  const names = items.map(a => a.label)
  return `<svg viewBox="-8 -8 236 210" style="width:220px;height:190px;display:block;margin:0 auto;">
    <polygon points="${ro2.map(v => `${v.x},${v.y}`).join(' ')}" fill="none" stroke="#ede9fe" stroke-width="1.5"/>
    <polygon points="110,42 155,68 138,122 82,122 65,68" fill="none" stroke="#ede9fe" stroke-width="1"/>
    <polygon points="110,66 140,76 128,102 92,102 80,76" fill="none" stroke="#ede9fe" stroke-width="1"/>
    <polygon points="${pts}" fill="rgba(139,92,246,0.08)" stroke="#8b5cf6" stroke-width="1.5" stroke-linejoin="round"/>
    ${dots}
    ${labs.map((l, i) => `<text x="${l.x}" y="${l.y}" font-size="11" fill="#6d5a9e" text-anchor="${l.a}" font-weight="700">${names[i] || ''}</text>`).join('')}
  </svg>`
})

// Video
const talentVideoUrl = ref('')
const showVideo = ref(false)
async function openVideo() {
  if (!talentVideoUrl.value) {
    try {
      const uid = await ensureChildUser()
      talentVideoUrl.value = resolveTrainingStreamUrl('/api/training/video/talent/stream', uid)
    } catch (_) {}
  }
  showVideo.value = true
}
function closeVideo() { showVideo.value = false }

// Conflict
async function handleConflictResolve(action) {
  resolving.value = true
  try {
    const uid = await ensureChildUser()
    await resolveTalentConflict(uid, action)
    talentConflict.value = false
    uni.showToast({ title: action === 'use_new' ? '已更新天赋' : '已保留原天赋', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '操作失败', icon: 'none' })
  }
  resolving.value = false
}

// Navigation
function reTest() {
  uni.redirectTo({ url: '/pages/talent/index?type=child' })
}
function goHome() {
  uni.reLaunch({ url: '/pages/index' })
}
function goBack() {
  uni.reLaunch({ url: '/pages/index' })
}
function goParentReport() {
  if (reportId.value) {
    uni.navigateTo({ url: `/pages/report/index?assessment_id=${reportId.value}` })
  }
}
</script>

<style scoped>
.app {
  min-height: 100vh; min-height: 100dvh; height: 100dvh;
  max-width: var(--app-max-width, 480px); margin: 0 auto;
  background: #faf8ff; font-family: -apple-system, "PingFang SC", sans-serif;
  display: flex; flex-direction: column; overflow: hidden;
}

.nav { display: flex; align-items: center; padding: 14px 20px 0; }
.nav-back {
  width: 36px; height: 36px; border-radius: 50%;
  background: #f3f0ff; border: 1px solid #e8e0f8;
  display: flex; align-items: center; justify-content: center; cursor: pointer;
}
.nav-title { flex: 1; text-align: center; color: #1e1b2e; font-size: 16px; font-weight: 600; }
.nav-spacer { width: 36px; }

.load-wrap { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px; }
.load-spin { width: 40px; height: 40px; border: 3px solid #ede9fe; border-top-color: #8b5cf6; border-radius: 50%; animation: spin 0.8s linear infinite; }
.load-text { color: #9089b0; font-size: 15px; }
@keyframes spin { to { transform: rotate(360deg); } }

.err-wrap { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px; }
.err-icon { font-size: 48px; display: block; margin-bottom: 12px; }
.err-text { color: #9089b0; font-size: 14px; text-align: center; line-height: 1.6; margin-bottom: 20px; }
.err-btn { padding: 12px 32px; border-radius: 14px; background: linear-gradient(135deg, #8b5cf6, #6366f1); cursor: pointer; }
.err-btn text { color: #fff; font-size: 15px; font-weight: 600; }

.body { flex: 1; overflow-y: auto; }
.content { padding: 12px 16px 0; opacity: 0; transform: translateY(12px); transition: all 0.5s ease-out; }
.content-in { opacity: 1; transform: translateY(0); }

.card {
  background: #fff; border: 1px solid #f0ebff; border-radius: 20px;
  padding: 20px; margin-bottom: 12px; box-shadow: 0 2px 16px rgba(139,92,246,0.04);
}
.sec-title { font-size: 16px; font-weight: 700; color: #1e1b2e; display: block; margin-bottom: 16px; }

.warn-card { text-align: center; padding: 24px 20px; }
.warn-emoji { font-size: 36px; display: block; margin-bottom: 8px; }
.warn-title { font-size: 16px; font-weight: 700; color: #e67e00; display: block; margin-bottom: 6px; }
.warn-desc { font-size: 13px; color: #9089b0; line-height: 1.6; display: block; margin-bottom: 14px; }
.warn-btn { display: inline-block; padding: 10px 28px; border-radius: 14px; background: linear-gradient(135deg,#f59e0b,#e67e00); cursor: pointer; }
.warn-btn text { color: #fff; font-size: 14px; font-weight: 600; }
.warn-btn-outline { background: none; border: 1.5px solid #e5e7eb; }
.warn-btn-outline text { color: #6b7280; }
.warn-btns { display: flex; gap: 10px; justify-content: center; }

.hero-card { position: relative; overflow: hidden; }
.hero-bg { position: absolute; right: -20px; top: -40px; width: 160px; height: 220px; opacity: 0.15; pointer-events: none; z-index: 0; }
.hero-row { display: flex; align-items: center; gap: 14px; position: relative; z-index: 1; }
.hero-avatar { width: 64px; height: 64px; border-radius: 50%; border: 3px solid #ede9fe; flex-shrink: 0; }
.hero-avatar-fallback { background: #f3f0ff; display: flex; align-items: center; justify-content: center; }
.hero-avatar-emoji { font-size: 28px; }
.hero-text { flex: 1; }
.hero-greet { font-size: 13px; color: #8b7fbf; display: block; }
.hero-name { font-size: 26px; font-weight: 800; color: #1e1b2e; display: block; margin: 4px 0; }
.hero-tagline { font-size: 13px; color: #9089b0; line-height: 1.5; display: block; }

.stats-card { display: flex; }
.stat { flex: 1; text-align: center; padding: 8px 0; }
.stat:not(:last-child) { border-right: 1px solid #f0ebff; }
.stat-val { font-size: 22px; font-weight: 800; display: block; }
.stat-lbl { font-size: 11px; color: #9089b0; display: block; margin-top: 4px; }

.eng-row { margin-bottom: 16px; }
.eng-row:last-child { margin-bottom: 0; }
.eng-top { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.eng-emoji { font-size: 18px; }
.eng-name { font-size: 13px; font-weight: 600; color: #3d3766; flex: 1; }
.eng-gems { display: flex; gap: 3px; }
.eng-gem { font-size: 15px; color: #ddd6f0; }
.eng-gem.on { color: #f59e0b; }
.eng-bar { height: 8px; background: #f3f0ff; border-radius: 4px; overflow: hidden; margin-bottom: 4px; }
.eng-fill { height: 100%; border-radius: 4px; transition: width 0.6s ease-out; }
.eng-tip { font-size: 11px; color: #9089b0; }

.radar-wrap { text-align: center; overflow: visible; }
.radar-wrap :deep(svg) { overflow: visible; }

.bub { max-width: 86%; padding: 12px 16px; border-radius: 16px; margin-bottom: 10px; display: flex; align-items: flex-start; gap: 10px; }
.bub:last-child { margin-bottom: 0; }
.bub-l { background: #f3f0ff; border-bottom-left-radius: 4px; margin-right: auto; }
.bub-r { background: #fef9e7; border-bottom-right-radius: 4px; margin-left: auto; }
.bub-num { width: 24px; height: 24px; border-radius: 8px; background: #8b5cf6; color: #fff; font-size: 12px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.bub-t { font-size: 13px; color: #4a4166; line-height: 1.7; flex: 1; }

.challenge-title { font-size: 14px; font-weight: 700; color: #6d5a9e; display: block; margin-bottom: 12px; }

.video-card { cursor: pointer; }
.video-inner { display: flex; align-items: center; gap: 10px; padding: 8px 0; }
.video-emoji { font-size: 22px; }
.video-text { font-size: 14px; color: #8b5cf6; font-weight: 500; }

.parent-link { text-align: center; padding: 16px 0; cursor: pointer; }
.parent-link-text { font-size: 13px; color: #9089b0; }

.bbar { padding: 12px 20px; padding-bottom: max(12px, env(safe-area-inset-bottom)); }
.bbtn { padding: 16px; text-align: center; border-radius: 16px; background: linear-gradient(135deg,#8b5cf6,#6366f1); cursor: pointer; box-shadow: 0 4px 20px rgba(139,92,246,0.2); }
.bbtn text { color: #fff; font-size: 16px; font-weight: 700; }
.bbtn:active { opacity: 0.85; transform: scale(0.98); }

.video-overlay { position: fixed; inset: 0; z-index: 1000; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; }
.video-card-pop { width: 92vw; max-width: 640px; background: #fff; border-radius: 16px; overflow: hidden; }
.video-head { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid #f0ebff; }
.video-title { font-size: 16px; font-weight: 700; color: #1e1b2e; }
.video-close { font-size: 20px; color: #9089b0; cursor: pointer; padding: 4px; }
.video-body { background: #000; }
.talent-video { width: 100%; display: block; }
.video-loading { color: #9089b0; font-size: 14px; display: block; text-align: center; padding: 40px; }
</style>
