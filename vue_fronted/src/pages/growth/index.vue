<template>
  <view class="app">
    <view class="nav">
      <view class="nav-back" @click="goBack">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#8b949e" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      </view>
      <text class="nav-title">成长里程碑</text>
      <view class="nav-spacer"></view>
    </view>

    <scroll-view class="body" scroll-y :show-scrollbar="false" :enhanced="true">
      <!-- 骨架屏：数据加载前显示，消除空白闪烁 -->
      <view v-if="loading" class="skeleton">
        <view class="sk-hero"><view class="sk-line w40"></view><view class="sk-line w60"></view><view class="sk-bar"></view><view class="sk-row"><view class="sk-stat"></view><view class="sk-stat"></view><view class="sk-stat"></view><view class="sk-stat"></view></view></view>
        <view class="sk-title"></view>
        <view class="sk-path"><view class="sk-dot"></view><view class="sk-dot"></view><view class="sk-dot"></view></view>
        <view class="sk-title"></view>
        <view class="sk-badges"><view v-for="i in 8" :key="'b'+i" class="sk-badge"></view></view>
        <view class="sk-title"></view>
        <view v-for="i in 3" :key="'tl'+i" class="sk-tl"><view class="sk-dot sm"></view><view class="sk-lines"><view class="sk-line w50"></view><view class="sk-line w30"></view></view></view>
      </view>

      <template v-else>
      <!-- 1. 荣誉 Hero 卡 -->
      <view v-if="summary" class="hero-card">
        <view class="hero-top">
          <view class="hero-id">
            <text class="hero-honor">{{ summary.honor_level }}</text>
            <text class="hero-nick">{{ summary.nickname || '学员' }}<text v-if="memberDays" class="hero-since"> · 加入 {{ memberDays }} 天</text></text>
          </view>
          <view class="hero-tier">
            <text class="hero-tier-num">Tier {{ overallTier }}</text>
            <text class="hero-tier-total"> / 9</text>
          </view>
        </view>
        <view class="tier-bar"><view class="tier-fill" :style="{ width: tierPercent + '%' }"></view></view>
        <view v-if="summary.checkin_streak >= 3" class="streak-pill">
          <view class="streak-ic" v-html="ic('flame', 12)"></view>
          <text>已连续 {{ summary.checkin_streak }} 天</text>
        </view>
        <view class="hero-stats">
          <view class="hero-stat"><text class="hs-num">{{ summary.total_checkins }}</text><text class="hs-lbl">累计打卡</text></view>
          <view class="hero-stat"><text class="hs-num">{{ summary.checkin_streak }}</text><text class="hs-lbl">连续天数</text></view>
          <view class="hero-stat"><text class="hs-num">{{ summary.qa_questions }}</text><text class="hs-lbl">学科提问</text></view>
          <view class="hero-stat"><text class="hs-num">{{ summary.badges_earned }}/{{ summary.badges_total }}</text><text class="hs-lbl">徽章</text></view>
        </view>
        <text v-if="summary.talent_primary" class="hero-talent">主导天赋：{{ summary.talent_primary }}</text>
      </view>

      <!-- 新用户空态引导 -->
      <view v-if="isFreshUser" class="fresh-card">
        <view class="fresh-ic" v-html="ic('flame', 18)"></view>
        <view class="fresh-body">
          <text class="fresh-title">开启你的成长之旅</text>
          <text class="fresh-desc">完成首次训练打卡，点亮第一枚徽章</text>
        </view>
        <view class="fresh-btn" @click="goTrain"><text>去训练</text></view>
      </view>

      <!-- 2. 进阶之路 -->
      <view class="sec-title"><view class="sec-ic" v-html="ic('trending')"></view><text>进阶之路</text></view>
      <view class="path-card">
        <view class="path-steps">
          <template v-for="(t, i) in TIER_TITLES" :key="t.name">
            <view class="path-step" :class="{ cur: i === currentTitleIndex, done: i < currentTitleIndex }">
              <view class="path-dot">
                <view v-if="i < currentTitleIndex" class="path-check" v-html="ic('check', 14)"></view>
                <text v-else>{{ i + 1 }}</text>
              </view>
              <text class="path-name">{{ t.name }}</text>
              <text class="path-range">Tier {{ t.min }}+</text>
            </view>
            <view v-if="i < TIER_TITLES.length - 1" class="path-link" :class="{ done: i < currentTitleIndex }"></view>
          </template>
        </view>
        <text v-if="nextTitleInfo" class="path-hint">再进 {{ nextTitleInfo.need }} 阶解锁「{{ nextTitleInfo.name }}」</text>
        <text v-else class="path-hint top">已达成最高荣誉</text>
      </view>

      <!-- 成就系统入口 -->
      <view class="achievement-entry" @click="goAchievement">
        <view class="entry-icon">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
        </view>
        <view class="entry-content">
          <text class="entry-title">成就殿堂</text>
          <text class="entry-desc">解锁勋章，收集称号，展示荣耀</text>
        </view>
        <view class="entry-arrow">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        </view>
      </view>

      <!-- 3. 荣誉徽章 -->
      <view class="sec-title"><view class="sec-ic" v-html="ic('medal')"></view><text>荣誉徽章</text></view>
      <view class="badge-grid">
        <view v-for="b in sortedBadges" :key="b.name" class="badge-item" :class="{ locked: !b.earned }">
          <view v-if="isNewBadge(b)" class="badge-new"><text>NEW</text></view>
          <view class="badge-circle" :class="{ pulse: isNewBadge(b) }" v-html="ic(BADGE_ICONS[b.name] || 'star', 20)"></view>
          <text class="badge-name">{{ b.name }}</text>
          <text v-if="b.earned && b.earned_at" class="badge-date">{{ b.earned_at.slice(5) }} 获得</text>
          <template v-else-if="!b.earned && badgeProgress(b)">
            <view class="badge-bar"><view class="badge-bar-fill" :style="{ width: badgeProgress(b).pct + '%' }"></view></view>
            <text class="badge-prog">{{ b.progress }}</text>
          </template>
          <text v-else class="badge-cond">{{ b.cond }}</text>
        </view>
      </view>

      <!-- 4. 核心能力 -->
      <template v-if="masteryChips.length">
        <view class="sec-title"><view class="sec-ic" v-html="ic('brain')"></view><text>核心能力</text><text class="sec-sub">{{ masteryDoneCount }}/{{ masteryChips.length }}</text></view>
        <view class="skill-row">
          <view v-for="s in masteryChips" :key="s.name" class="skill-chip" :class="{ done: s.done }">
            <view v-if="s.done" class="chip-ic" v-html="ic('check', 12)"></view>
            <text>{{ s.name }}</text>
          </view>
        </view>
      </template>

      <!-- 5. 下一个目标 -->
      <template v-if="goalCards.length">
        <view class="sec-title"><view class="sec-ic" v-html="ic('target')"></view><text>下一个目标</text></view>
        <view v-for="(g, i) in goalCards" :key="'g'+i" class="goal-card" :class="{ clickable: !!g.route }" @click="goGoal(g)">
          <view class="goal-ic" v-html="ic('target', 15)"></view>
          <view class="goal-body">
            <view class="goal-head">
              <text class="goal-title">{{ g.title }}</text>
              <text v-if="g.progressText" class="goal-prog-text">{{ g.progressText }}</text>
            </view>
            <view v-if="g.pct !== null" class="goal-bar"><view class="goal-bar-fill" :style="{ width: g.pct + '%' }"></view></view>
            <text class="goal-desc">{{ g.desc }}</text>
          </view>
          <view v-if="g.route" class="goal-arrow">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="9 18 15 12 9 6"/></svg>
          </view>
        </view>
      </template>

      <!-- 6. 成长足迹 -->
      <view v-if="doneEvents.length" class="sec-title"><view class="sec-ic" v-html="ic('clock')"></view><text>成长足迹</text></view>
      <view class="timeline">
        <view class="tl-line"></view>
        <view v-for="(e, i) in doneEvents" :key="i" class="tl-item">
          <view class="tl-icon" v-html="tlIcon(e)"></view>
          <view class="tl-body">
            <text class="tl-title">{{ e.title }}</text>
            <text class="tl-date">{{ e.date }} · {{ e.desc }}</text>
          </view>
        </view>
      </view>

      <!-- 7. 分享 -->
      <view class="share-card">
        <view class="share-poster">
          <text class="sp-honor">{{ summary?.honor_level || '成长中' }}</text>
          <text class="sp-name">{{ summary?.nickname || '学员' }} 的成长成就</text>
          <view class="sp-stats">
            <text class="sp-stat">打卡 {{ summary?.total_checkins || 0 }} 次</text>
            <text class="sp-stat">徽章 {{ summary?.badges_earned || 0 }} 枚</text>
            <text class="sp-stat">Tier {{ overallTier }}</text>
          </view>
        </view>
        <text class="share-hint">复制成长成就文案，分享到微信/朋友圈</text>
        <view class="share-btn" @click="copyShare"><view class="share-btn-ic" v-html="ic('share', 14)"></view><text>{{ sharing ? '复制中...' : '复制分享文案' }}</text></view>
      </view>
      </template>

      <view style="height:40px;"></view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  ensureChildUser,
  fetchGrowthBadges,
  fetchGrowthTimeline,
  fetchGrowthSummary,
  fetchGrowthShare,
} from '@/utils/userApi.js'

// 与后端 growth_service.get_tier_honor 的 tier 边界保持一致
const TIER_TITLES = [
  { name: '传承特使', min: 1 },
  { name: '劲脑学神', min: 5 },
  { name: '专利精英', min: 8 },
]

// 线性 SVG 图标（与首页/答疑页同一风格：24 视窗、currentColor 描边）
const ICON_PATHS = {
  star: '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
  flame: '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>',
  zap: '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
  trophy: '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>',
  calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><polyline points="8 14 11.5 17 16 14"/>',
  message: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  gem: '<path d="M6 3h12l4 6-10 13L2 9Z"/><path d="M2 9h20"/><path d="M9 3 7 9l5 13 5-13-2-6"/>',
  crown: '<path d="M3 18 2.5 8 8 12.5 12 4l4 8.5L21.5 8 21 18Z"/><line x1="4" y1="21" x2="20" y2="21"/>',
  brain: '<path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/><path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z"/>',
  target: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
  trending: '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
  medal: '<circle cx="12" cy="8" r="7"/><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/>',
  clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
  check: '<polyline points="20 6 9 17 4 12"/>',
  share: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>',
}

function ic(name, size = 14) {
  const body = ICON_PATHS[name] || ICON_PATHS.star
  return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`
}

// 徽章名 → 图标（徽章名为后端 growth_service 固定定义）
const BADGE_ICONS = {
  首次测评: 'star',
  初露锋芒: 'flame',
  持之以恒: 'zap',
  百炼成钢: 'trophy',
  连续一周: 'calendar',
  答疑新星: 'message',
  知识达人: 'gem',
  全能王者: 'crown',
}

// 时间线事件类型 → 图标
const TL_ICON_NAMES = { assessment: 'star', checkin: 'calendar', streak: 'flame', skill: 'brain', qa: 'message', goal: 'target' }

const badges = ref([])
const events = ref([])
const summary = ref(null)
const sharePreview = ref('')
const sharing = ref(false)
const loading = ref(true)

const overallTier = computed(() => summary.value?.overall_tier || 1)
const tierPercent = computed(() => Math.round((overallTier.value / 9) * 100))

const memberDays = computed(() => {
  const since = summary.value?.member_since
  if (!since) return null
  const diff = Date.now() - new Date(`${since}T00:00:00`).getTime()
  if (Number.isNaN(diff) || diff < 0) return null
  return Math.floor(diff / 86400000) + 1
})

const currentTitleIndex = computed(() => {
  const t = overallTier.value
  if (t >= TIER_TITLES[2].min) return 2
  if (t >= TIER_TITLES[1].min) return 1
  return 0
})

const nextTitleInfo = computed(() => {
  const idx = currentTitleIndex.value
  if (idx >= TIER_TITLES.length - 1) return null
  const next = TIER_TITLES[idx + 1]
  return { name: next.name, need: Math.max(1, next.min - overallTier.value) }
})

const masteryChips = computed(() => {
  const target = summary.value?.mastery_skills_target || []
  const done = new Set(summary.value?.mastery_skills_done || [])
  return target.map((name) => ({ name, done: done.has(name) }))
})
const masteryDoneCount = computed(() => (summary.value?.mastery_skills_done || []).length)

const goalEvents = computed(() => events.value.filter((e) => !e.done))
const doneEvents = computed(() => events.value.filter((e) => e.done).slice().reverse())

// 徽章陈列：已获得（最新在前）> 进行中（完成度高优先）> 未开始
const sortedBadges = computed(() =>
  badges.value.slice().sort((a, b) => {
    if (!!a.earned !== !!b.earned) return a.earned ? -1 : 1
    if (a.earned && b.earned) return (b.earned_at || '').localeCompare(a.earned_at || '')
    return (badgeProgress(b)?.pct || 0) - (badgeProgress(a)?.pct || 0)
  })
)

// 近 7 天新获得的徽章：NEW 角标 + 呼吸光环
function isNewBadge(b) {
  if (!b.earned || !b.earned_at) return false
  const t = new Date(`${b.earned_at}T00:00:00`).getTime()
  if (Number.isNaN(t)) return false
  return Date.now() - t <= 7 * 86400000
}

// 新用户：无打卡且无徽章 → 展示空态引导
const isFreshUser = computed(() => {
  if (!summary.value) return false
  return !summary.value.total_checkins && !summary.value.badges_earned
})

// 目标卡：量化进度 + 可点击跳转到对应页
const goalCards = computed(() =>
  goalEvents.value.map((e) => {
    const g = { ...e, route: '', pct: null, progressText: '' }
    if (/打卡/.test(e.title)) {
      g.route = '/pages/training/index'
      const m = e.title.match(/(\d+)/)
      if (m) {
        const target = +m[1]
        const cur = summary.value?.total_checkins || 0
        g.pct = Math.min(100, Math.round((cur / target) * 100))
        g.progressText = `${Math.min(cur, target)}/${target}`
      }
    } else if (/核心能力/.test(e.title)) {
      g.route = '/pages/training/index'
      const total = masteryChips.value.length
      if (total) {
        g.pct = Math.round((masteryDoneCount.value / total) * 100)
        g.progressText = `${masteryDoneCount.value}/${total}`
      }
    } else if (/提问|答疑/.test(e.title)) {
      g.route = '/pages/qa/index'
    }
    return g
  })
)

function goGoal(g) {
  if (!g.route) return
  uni.navigateTo({ url: g.route })
}

function goTrain() {
  uni.navigateTo({ url: '/pages/training/index' })
}

function goAchievement() {
  uni.navigateTo({ url: '/pages/achievement/index' })
}

function tlIcon(e) { return ic(TL_ICON_NAMES[e.type] || 'calendar', 11) }

function badgeProgress(b) {
  if (!b.progress) return null
  const m = String(b.progress).match(/(\d+)\/(\d+)/)
  if (!m) return null
  const cur = +m[1]
  const total = +m[2]
  if (!total) return null
  return { cur, total, pct: Math.round((cur / total) * 100) }
}

async function loadGrowth() {
  loading.value = true
  try {
    const uid = await ensureChildUser()
    const [b, t, s, sh] = await Promise.all([
      fetchGrowthBadges(uid),
      fetchGrowthTimeline(uid),
      fetchGrowthSummary(uid).catch(() => null),
      fetchGrowthShare(uid).catch(() => null),
    ])
    badges.value = b
    events.value = t
    summary.value = s
    sharePreview.value = sh?.text || ''
  } catch (e) {
    badges.value = []
    events.value = []
  }
  loading.value = false
}

onMounted(loadGrowth)

function goBack() { uni.navigateBack({ delta: 1 }) }

async function copyShare() {
  if (sharing.value) return
  sharing.value = true
  const text = sharePreview.value || '我在劲脑天赋成长平台坚持学习，一起来打卡吧！'
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    uni.showToast({ title: '已复制到剪贴板', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: '复制失败，请手动复制', icon: 'none' })
  }
  sharing.value = false
}
</script>

<style scoped>
.app { height:100vh;height:100dvh; max-width:var(--app-max-width, 480px); margin:0 auto; background:var(--bg); font-family:-apple-system,"PingFang SC",sans-serif; display:flex; flex-direction:column; position:relative; overflow:hidden; box-sizing:border-box; }
.nav { display:flex; align-items:center; padding:14px 14px 0; }
.nav-back { width:36px; height:36px; border-radius:50%; background:var(--bg-card); display:flex; align-items:center; justify-content:center; cursor:pointer; }
.nav-title { flex:1; text-align:center; color:var(--text); font-size:16px; font-weight:600; }
.nav-spacer { width:36px; }
.body { flex:1; overflow-y:auto; overflow-x:hidden; padding:12px 14px 0; box-sizing:border-box; width:100%; scrollbar-width:none; -ms-overflow-style:none; }
:deep(uni-scroll-view) ::-webkit-scrollbar,
:deep(.uni-scroll-view) ::-webkit-scrollbar,
.body *::-webkit-scrollbar,
.body::-webkit-scrollbar { display:none; width:0; height:0; }
.sec-title { color:var(--text); font-size:15px; font-weight:700; display:flex; align-items:center; gap:8px; margin:0 0 12px; }
.sec-ic { width:24px; height:24px; border-radius:7px; background:var(--accent-bg); color:var(--accent); display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.sec-sub { color:var(--text-dim); font-size:12px; font-weight:500; }

/* 1. 荣誉 Hero 卡 */
.hero-card {
  background:var(--focus-bg);
  border-radius:20px; padding:18px 18px 16px; margin-bottom:20px;
  box-shadow:0 8px 24px rgba(37,99,235,0.22);
  box-sizing:border-box;
}
.hero-top { display:flex; align-items:flex-start; justify-content:space-between; }
.hero-honor { color:#fff; font-size:22px; font-weight:800; display:block; text-shadow:0 2px 8px rgba(0,0,0,0.3); }
.hero-nick { color:rgba(255,255,255,0.75); font-size:12px; display:block; margin-top:4px; }
.hero-since { color:rgba(255,255,255,0.55); }
.hero-tier { text-align:right; flex-shrink:0; }
.hero-tier-num { color:#ffd666; font-size:20px; font-weight:800; }
.hero-tier-total { color:rgba(255,255,255,0.6); font-size:12px; }
.tier-bar { height:6px; border-radius:3px; background:rgba(255,255,255,0.18); margin:12px 0 14px; overflow:hidden; }
.tier-fill { height:100%; border-radius:3px; background:linear-gradient(90deg,#ffd666,#ffb020); transition:width 0.6s ease; }
.streak-pill {
  display:inline-flex; align-items:center; gap:4px;
  background:rgba(255,180,32,0.15); border:1px solid rgba(255,214,102,0.35);
  color:#ffd666; border-radius:999px; padding:4px 10px;
  font-size:11px; font-weight:600; margin:-6px 0 12px;
}
.streak-ic { display:flex; align-items:center; }
.hero-stats { display:flex; justify-content:space-around; background:rgba(255,255,255,0.08); border-radius:12px; padding:10px 0; }
.hs-num { color:#fff; font-size:17px; font-weight:700; display:block; text-align:center; }
.hs-lbl { color:rgba(255,255,255,0.65); font-size:10px; display:block; text-align:center; margin-top:2px; }
.hero-talent { color:rgba(255,255,255,0.75); font-size:11px; display:block; margin-top:10px; text-align:center; }

/* 新用户空态引导 */
.fresh-card {
  display:flex; align-items:center; gap:10px;
  background:linear-gradient(135deg, var(--accent-bg), transparent);
  border:1px solid var(--accent);
  border-radius:16px; padding:14px; margin-bottom:20px; box-sizing:border-box;
}
.fresh-ic {
  width:36px; height:36px; border-radius:10px; flex-shrink:0;
  background:var(--accent-bg); color:var(--accent);
  display:flex; align-items:center; justify-content:center;
}
.fresh-body { flex:1; min-width:0; }
.fresh-title { color:var(--text); font-size:14px; font-weight:700; display:block; }
.fresh-desc { color:var(--text-dim); font-size:11px; display:block; margin-top:2px; }
.fresh-btn { background:var(--accent); border-radius:999px; padding:8px 16px; flex-shrink:0; cursor:pointer; }
.fresh-btn text { color:#fff; font-size:12px; font-weight:600; }
.fresh-btn:active { opacity:0.85; }

/* 成就系统入口 */
.achievement-entry {
  display: flex;
  align-items: center;
  gap: 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 16px;
  padding: 16px;
  margin-bottom: 20px;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 4px 16px rgba(102, 126, 234, 0.3);
}
.achievement-entry:active {
  transform: scale(0.98);
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.2);
}
.entry-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: rgba(255,255,255,0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}
.entry-content {
  flex: 1;
  min-width: 0;
}
.entry-title {
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  display: block;
}
.entry-desc {
  color: rgba(255,255,255,0.85);
  font-size: 12px;
  display: block;
  margin-top: 2px;
}
.entry-arrow {
  color: rgba(255,255,255,0.8);
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

/* 2. 进阶之路 */
.path-card { background:var(--bg-card); border:1px solid var(--border); border-radius:16px; padding:16px 14px; margin-bottom:20px; box-sizing:border-box; }
.path-steps { display:flex; align-items:flex-start; }
.path-step { width:72px; flex-shrink:0; display:flex; flex-direction:column; align-items:center; gap:4px; }
.path-dot {
  width:30px; height:30px; border-radius:50%;
  background:var(--bg); border:2px solid var(--border);
  display:flex; align-items:center; justify-content:center;
  color:var(--text-dim); font-size:13px; font-weight:700;
}
.path-step.done .path-dot { background:var(--accent-bg); border-color:var(--accent); color:var(--accent); }
.path-step.cur .path-dot { background:var(--accent); border-color:var(--accent); color:#fff; box-shadow:0 0 12px var(--mic-shadow); }
.path-check { display:flex; align-items:center; justify-content:center; }
.path-name { color:var(--text-dim); font-size:11px; font-weight:600; }
.path-step.done .path-name { color:var(--text); }
.path-step.cur .path-name { color:var(--accent); }
.path-range { color:var(--text-hint); font-size:9px; }
.path-link { flex:1; height:2px; background:var(--border); margin-top:15px; }
.path-link.done { background:var(--accent); }
.path-hint { display:block; text-align:center; color:var(--accent); font-size:12px; font-weight:600; margin-top:12px; }
.path-hint.top { color:#f59e0b; }

/* 3. 荣誉徽章 */
.badge-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:20px; }
.badge-item { position:relative; text-align:center; background:var(--bg-card); border:1px solid var(--border); border-radius:14px; padding:10px 4px 8px; box-sizing:border-box; }
.badge-item.locked { opacity:0.55; }
.badge-new {
  position:absolute; top:4px; right:4px; z-index:1;
  background:#f59e0b; border-radius:4px; padding:1px 4px;
}
.badge-new text { color:#fff; font-size:8px; font-weight:700; }
.badge-circle.pulse { animation: badgePulse 2s ease-in-out infinite; }
@keyframes badgePulse {
  0%, 100% { box-shadow:0 0 0 2px rgba(245,158,11,0.45); }
  50% { box-shadow:0 0 0 6px rgba(245,158,11,0.12); }
}
.badge-circle { width:44px; height:44px; border-radius:50%; margin:0 auto 6px; display:flex; align-items:center; justify-content:center; background:var(--bg); color:var(--text-hint); }
.badge-item:not(.locked) .badge-circle { background:var(--accent-bg); color:var(--accent); box-shadow:0 0 0 2px rgba(245,158,11,0.45); }
.badge-name { color:var(--text); font-size:10px; font-weight:600; display:block; }
.badge-date { color:#f59e0b; font-size:9px; display:block; margin-top:3px; }
.badge-bar { height:4px; border-radius:2px; background:var(--bg); margin:5px 6px 3px; overflow:hidden; }
.badge-bar-fill { height:100%; border-radius:2px; background:var(--accent); }
.badge-prog { color:var(--text-dim); font-size:9px; display:block; }
.badge-cond { color:var(--text-dim); font-size:9px; display:block; margin-top:3px; }

/* 4. 核心能力 */
.skill-row { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:20px; }
.skill-chip { display:inline-flex; align-items:center; gap:5px; padding:7px 14px; border-radius:999px; background:var(--bg-card); border:1px solid var(--border); color:var(--text-dim); font-size:12px; }
.skill-chip.done { background:var(--accent-bg); border-color:var(--accent); color:var(--accent); font-weight:600; }
.chip-ic { display:flex; align-items:center; }

/* 5. 下一个目标 */
.goal-card { display:flex; align-items:flex-start; gap:10px; background:var(--bg-card); border:1px dashed var(--accent); border-radius:14px; padding:12px 14px; margin-bottom:8px; box-sizing:border-box; }
.goal-card.clickable { cursor:pointer; transition:background 0.15s; }
.goal-card.clickable:active { background:var(--accent-bg); }
.goal-ic { width:30px; height:30px; border-radius:9px; background:var(--accent-bg); color:var(--accent); display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.goal-body { flex:1; min-width:0; }
.goal-head { display:flex; align-items:center; justify-content:space-between; gap:8px; }
.goal-title { color:var(--text); font-size:13px; font-weight:600; }
.goal-prog-text { color:var(--accent); font-size:11px; font-weight:700; flex-shrink:0; }
.goal-bar { height:5px; border-radius:3px; background:var(--bg); margin:7px 0 2px; overflow:hidden; }
.goal-bar-fill { height:100%; border-radius:3px; background:var(--accent); transition:width 0.5s ease; }
.goal-desc { color:var(--text-dim); font-size:11px; display:block; margin-top:3px; }
.goal-arrow { color:var(--text-dim); align-self:center; flex-shrink:0; display:flex; align-items:center; }

/* 6. 成长足迹 */
.timeline { position:relative; padding-left:30px; margin-bottom:20px; box-sizing:border-box; }
.tl-line { position:absolute; left:10px; top:6px; bottom:6px; width:2px; background:var(--border); }
.tl-item { position:relative; margin-bottom:14px; }
.tl-icon {
  position:absolute; left:-30px; top:0;
  width:22px; height:22px; border-radius:50%;
  background:var(--bg-card); border:1px solid var(--border);
  color:var(--accent);
  display:flex; align-items:center; justify-content:center;
}
.tl-title { color:var(--text); font-size:13px; font-weight:600; display:block; }
.tl-date { color:var(--text-dim); font-size:11px; display:block; margin-top:2px; }

/* 7. 分享 */
.share-card { background:var(--bg-card); border-radius:16px; padding:16px; text-align:center; margin-bottom:20px; border:1px solid var(--border); box-sizing:border-box; }
.share-poster { background:var(--focus-bg); border-radius:14px; padding:18px 14px; margin-bottom:12px; box-shadow:0 6px 18px rgba(37,99,235,0.18); }
.sp-honor { color:#ffd666; font-size:18px; font-weight:800; display:block; }
.sp-name { color:rgba(255,255,255,0.85); font-size:13px; display:block; margin-top:4px; }
.sp-stats { display:flex; justify-content:center; gap:8px; margin-top:12px; flex-wrap:wrap; }
.sp-stat { color:rgba(255,255,255,0.8); font-size:10px; background:rgba(255,255,255,0.12); border-radius:999px; padding:3px 10px; }
.share-hint { color:var(--text-dim); font-size:11px; display:block; margin-bottom:12px; }
.share-btn { background:var(--accent); border-radius:12px; padding:12px 18px; display:inline-flex; align-items:center; gap:6px; cursor:pointer; color:#fff; }
.share-btn-ic { display:flex; align-items:center; }
.share-btn text { color:#fff; font-size:14px; font-weight:600; }
.share-btn:active { opacity:0.85; }

/* 骨架屏：加载期间显示，消除空白闪烁 */
.skeleton { padding: 0; }
.sk-hero { background:var(--bg-card); border-radius:20px; padding:18px; margin-bottom:20px; }
.sk-bar { height:6px; border-radius:3px; background:var(--bg); margin:12px 0 14px; }
.sk-stat { width:56px; height:40px; background:rgba(255,255,255,0.06); border-radius:8px; }
[data-theme="white"] .sk-stat { background:var(--bg); }
.sk-row { display:flex; justify-content:space-around; background:rgba(255,255,255,0.04); border-radius:12px; padding:10px 0; }
.sk-path { display:flex; justify-content:space-around; background:var(--bg-card); border:1px solid var(--border); border-radius:16px; padding:16px 14px; margin-bottom:20px; }
.sk-title { width:80px; height:15px; background:var(--bg-card); border-radius:6px; margin:0 0 12px; }
.sk-dot { width:30px; height:30px; border-radius:50%; background:var(--bg); flex-shrink:0; }
.sk-dot.sm { width:22px; height:22px; }
.sk-lines { flex:1; display:flex; flex-direction:column; gap:6px; }
.sk-line { height:12px; background:var(--bg); border-radius:4px; }
.sk-line.w40 { width:40%; }
.sk-line.w50 { width:50%; }
.sk-line.w60 { width:60%; }
.sk-line.w30 { width:30%; }
.sk-badges { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:20px; }
.sk-badge { width:100%; height:88px; border-radius:14px; background:var(--bg-card); }
.sk-tl { display:flex; align-items:flex-start; gap:10px; padding-left:30px; margin-bottom:14px; }
.sk-tl .sk-dot { margin-top:2px; }
.skeleton .sk-hero *,
.skeleton .sk-path *,
.skeleton .sk-title,
.skeleton .sk-badge,
.skeleton .sk-tl * { animation: skPulse 1.4s ease-in-out infinite; }
@keyframes skPulse { 0%,100% { opacity:0.3; } 50% { opacity:0.7; } }
</style>
