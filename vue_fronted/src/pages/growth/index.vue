<template>
  <view class="app">
    <view class="nav">
      <view class="nav-back" @click="goBack">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#8b949e" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      </view>
      <text class="nav-title">成长里程碑</text>
      <view class="nav-spacer"></view>
    </view>

    <scroll-view class="body" scroll-y>
      <!-- Summary -->
      <view v-if="summary" class="summary-card">
        <text class="sum-honor">{{ summary.honor_level }}</text>
        <text class="sum-nick">{{ summary.nickname || '学员' }}</text>
        <view class="sum-stats">
          <view class="sum-stat"><text class="sum-num">{{ summary.total_checkins }}</text><text class="sum-lbl">累计打卡</text></view>
          <view class="sum-stat"><text class="sum-num">{{ summary.checkin_streak }}</text><text class="sum-lbl">连续天数</text></view>
          <view class="sum-stat"><text class="sum-num">{{ summary.badges_earned }}/{{ summary.badges_total }}</text><text class="sum-lbl">徽章</text></view>
        </view>
        <text v-if="summary.talent_primary" class="sum-talent">主导天赋：{{ summary.talent_primary }}</text>
      </view>

      <!-- Milestones -->
      <text class="sec-title">🏆 荣誉级别</text>
      <view class="milestone-list">
        <view v-for="(m, i) in milestones" :key="i" class="ms-item" :class="{ achieved: m.achieved }">
          <view class="ms-dot">{{ m.achieved ? '✓' : '' }}</view>
          <view class="ms-body">
            <text class="ms-level">{{ m.level }}</text>
            <text class="ms-cond">{{ m.condition }} · {{ m.progress }}</text>
          </view>
        </view>
      </view>

      <!-- Badges -->
      <text class="sec-title">🏅 荣誉徽章</text>
      <view class="badge-row">
        <view v-for="b in badges" :key="b.name" class="badge-item" :class="{ locked: !b.earned }">
          <view class="badge-circle" :class="{ earned: b.earned }"><text>{{ b.icon }}</text></view>
          <text class="badge-name">{{ b.name }}</text>
          <text class="badge-cond">{{ b.cond }}</text>
        </view>
      </view>

      <!-- Timeline -->
      <text class="sec-title">📅 成长时间线</text>
      <view class="timeline">
        <view class="tl-line"></view>
        <view v-for="(e,i) in events" :key="i" class="tl-item" :class="{ future: !e.done }">
          <view class="tl-dot" :class="{ done: e.done }"></view>
          <view class="tl-card">
            <text class="tl-title">{{ e.title }}</text>
            <text class="tl-date">{{ e.date }} · {{ e.desc }}</text>
          </view>
        </view>
      </view>

      <!-- Share -->
      <view class="share-card">
        <text class="share-title">📤 一键分享</text>
        <text class="share-hint">复制成长成就文案，分享到微信/朋友圈</text>
        <view v-if="sharePreview" class="share-preview">{{ sharePreview }}</view>
        <view class="share-btn" @click="copyShare"><text>{{ sharing ? '复制中...' : '复制分享文案' }}</text></view>
      </view>

      <view style="height:40px;"></view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import {
  ensureChildUser,
  fetchGrowthBadges,
  fetchGrowthTimeline,
  fetchGrowthSummary,
  fetchGrowthMilestones,
  fetchGrowthShare,
} from '@/utils/userApi.js'

const badges = ref([])
const events = ref([])
const milestones = ref([])
const summary = ref(null)
const sharePreview = ref('')
const sharing = ref(false)
const loading = ref(true)

async function loadGrowth() {
  loading.value = true
  try {
    const uid = await ensureChildUser()
    const [b, t, s, m, sh] = await Promise.all([
      fetchGrowthBadges(uid),
      fetchGrowthTimeline(uid),
      fetchGrowthSummary(uid).catch(() => null),
      fetchGrowthMilestones(uid).catch(() => []),
      fetchGrowthShare(uid).catch(() => null),
    ])
    badges.value = b
    events.value = t
    summary.value = s
    milestones.value = m
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
.app { height:100vh; max-width:480px; margin:0 auto; background:var(--bg); font-family:-apple-system,"PingFang SC",sans-serif; display:flex; flex-direction:column; position:relative; overflow:hidden; box-sizing:border-box; }
.nav { display:flex; align-items:center; padding:14px 14px 0; }
.nav-back { width:36px; height:36px; border-radius:50%; background:var(--bg-card); display:flex; align-items:center; justify-content:center; cursor:pointer; }
.nav-title { flex:1; text-align:center; color:var(--text); font-size:16px; font-weight:600; }
.nav-spacer { width:36px; }
.body { flex:1; overflow-y:auto; overflow-x:hidden; padding:12px 14px 0; box-sizing:border-box; width:100%; }
.body::-webkit-scrollbar { display:none; }
.sec-title { color:var(--text); font-size:15px; font-weight:700; display:block; margin:0 0 12px; }

.summary-card { background:linear-gradient(135deg, rgba(88,166,255,0.12), rgba(124,58,237,0.08)); border:1px solid var(--border); border-radius:16px; padding:18px; margin-bottom:20px; text-align:center; box-sizing:border-box; }
.sum-honor { color:var(--accent); font-size:20px; font-weight:800; display:block; margin-bottom:4px; }
.sum-nick { color:var(--text-dim); font-size:13px; display:block; margin-bottom:12px; }
.sum-stats { display:flex; justify-content:space-around; margin-bottom:8px; }
.sum-stat { text-align:center; }
.sum-num { color:var(--text); font-size:18px; font-weight:700; display:block; }
.sum-lbl { color:var(--text-dim); font-size:10px; display:block; margin-top:2px; }
.sum-talent { color:var(--text-dim); font-size:12px; display:block; margin-top:8px; }

.milestone-list { margin-bottom:20px; }
.ms-item { display:flex; align-items:flex-start; gap:10px; padding:10px 12px; border-radius:12px; margin-bottom:8px; background:var(--bg-card); opacity:0.45; box-sizing:border-box; }
.ms-item.achieved { opacity:1; border:1px solid rgba(88,166,255,0.25); }
.ms-dot { width:22px; height:22px; border-radius:50%; background:var(--bg); border:2px solid var(--border); flex-shrink:0; display:flex; align-items:center; justify-content:center; font-size:11px; color:var(--accent); margin-top:2px; }
.ms-item.achieved .ms-dot { background:var(--accent-bg); border-color:var(--accent); }
.ms-level { color:var(--text); font-size:13px; font-weight:600; display:block; }
.ms-cond { color:var(--text-dim); font-size:11px; display:block; margin-top:2px; }

.badge-row { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:20px; }
.badge-item { text-align:center; }
.badge-item.locked { opacity:0.35; }
.badge-circle { width:50px; height:50px; border-radius:50%; margin:0 auto 4px; display:flex; align-items:center; justify-content:center; font-size:22px; }
.badge-circle.earned { background:var(--accent-bg); }
.badge-circle.locked { background:var(--bg-card); }
.badge-name { color:var(--text); font-size:11px; font-weight:600; display:block; }
.badge-cond { color:var(--text-dim); font-size:9px; display:block; margin-top:1px; }

.timeline { position:relative; padding-left:20px; margin-bottom:20px; box-sizing:border-box; }
.tl-line { position:absolute; left:6px; top:4px; bottom:4px; width:2px; background:var(--border); }
.tl-item { position:relative; margin-bottom:14px; }
.tl-item.future { opacity:0.35; }
.tl-dot { position:absolute; left:-18px; top:4px; width:10px; height:10px; border-radius:50%; background:var(--bg-card); border:2px solid var(--border); }
.tl-dot.done { background:var(--accent); border-color:var(--accent); }
.tl-title { color:var(--text); font-size:13px; font-weight:600; display:block; }
.tl-date { color:var(--text-dim); font-size:11px; display:block; margin-top:2px; }

.share-card { background:var(--bg-card); border-radius:16px; padding:20px; text-align:center; margin-bottom:20px; border:1px dashed var(--border); box-sizing:border-box; }
.share-title { color:var(--text); font-size:15px; font-weight:700; display:block; margin-bottom:4px; }
.share-hint { color:var(--text-dim); font-size:12px; display:block; margin-bottom:12px; }
.share-preview { background:var(--bg); border-radius:10px; padding:12px; text-align:left; font-size:11px; color:var(--text-dim); line-height:1.5; margin-bottom:12px; white-space:pre-wrap; max-height:120px; overflow-y:auto; box-sizing:border-box; }
.share-btn { background:var(--accent); border-radius:12px; padding:12px; display:inline-block; cursor:pointer; }
.share-btn text { color:#fff; font-size:14px; font-weight:600; }
.share-btn:active { opacity:0.85; }
</style>
