<template>
  <view class="app">
    <view class="nav">
      <view class="nav-back" @click="goBack">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#8b949e" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      </view>
      <text class="nav-title">成就殿堂</text>
      <view class="nav-spacer"></view>
    </view>

    <scroll-view class="body" scroll-y :show-scrollbar="false" :enhanced="true">
      <!-- 骨架屏：仅首次无缓存时展示 -->
      <view v-if="loading && items.length === 0" class="skeleton">
        <view class="sk-actions"><view class="sk-action"></view><view class="sk-action"></view></view>
        <view class="sk-title"></view>
        <view class="sk-badges"><view v-for="i in 6" :key="'b'+i" class="sk-badge"></view></view>
      </view>

      <template v-else>
        <view v-if="refreshing" class="refresh-bar"></view>
        <!-- 快捷入口 -->
        <view class="quick-actions">
          <view class="action-btn" @click="goShowcase">
            <view class="action-icon showcase">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
            </view>
            <text class="action-text">荣誉展柜</text>
          </view>
          <view class="action-btn" @click="goTitles">
            <view class="action-icon title">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
            </view>
            <text class="action-text">称号管理</text>
          </view>
        </view>

        <!-- 分类筛选 -->
        <view class="filter-tabs">
          <view
            v-for="tab in tabs"
            :key="tab.key"
            class="tab-item"
            :class="{ active: activeTab === tab.key }"
            @click="activeTab = tab.key"
          >
            <text>{{ tab.name }}</text>
            <view v-if="tab.hasReady" class="tab-dot"></view>
          </view>
        </view>

        <!-- 勋章列表 -->
        <view class="achievement-grid">
          <view
            v-for="item in filteredAchievements"
            :key="item.id"
            class="achievement-card"
            :class="[item.status, item.color_theme]"
            @click="showDetail(item)"
          >
            <view class="card-header">
              <view class="medal-icon">
                <svg v-if="item.status === 'claimed'" viewBox="0 0 24 24" width="32" height="32" fill="currentColor">
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                </svg>
                <svg v-else-if="item.status === 'ready'" viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                </svg>
                <svg v-else viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                </svg>
              </view>
              <view v-if="item.status === 'ready'" class="ready-dot"></view>
            </view>
            <text class="medal-name">{{ item.name }}</text>
            <text class="medal-title">{{ item.title }}</text>
            <text class="medal-desc">{{ item.description }}</text>
            <view v-if="item.status !== 'claimed' && item.progress_target > 1" class="progress-section">
              <view class="mini-progress">
                <view class="mini-progress-fill" :style="{ width: (item.progress_current / item.progress_target * 100) + '%' }"></view>
              </view>
              <text class="progress-label">{{ item.progress_text }}</text>
            </view>
            <view v-else-if="item.status === 'claimed'" class="claimed-time">
              <text>{{ formatDate(item.claimed_at) }} 获得</text>
            </view>
          </view>
        </view>

        <!-- 空状态 -->
        <view v-if="filteredAchievements.length === 0" class="empty-state">
          <text class="empty-text">暂无该分类的勋章</text>
        </view>
      </template>

      <view style="height: 40px;"></view>
    </scroll-view>

    <!-- 成就详情弹窗 -->
    <AchievementDetail
      v-model:visible="detailVisible"
      :achievement="selectedAchievement"
      @claim="handleClaim"
      @set-title="handleSetTitle"
    />
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  ensureChildUser,
  fetchAchievementList,
  claimAchievement,
  readAchievementCache,
} from '@/utils/userApi.js'
import AchievementDetail from './components/AchievementDetail.vue'

const loading = ref(true)
const refreshing = ref(false)
const items = ref([])
const activeTab = ref('all')
const detailVisible = ref(false)
const selectedAchievement = ref(null)

const tabs = computed(() => [
  { key: 'all', name: '全部', count: 0, hasReady: items.value.some(i => i.status === 'ready') },
  { key: 'streak', name: '坚持', count: 0, hasReady: items.value.some(i => i.category === 'streak' && i.status === 'ready') },
  { key: 'skill', name: '技能', count: 0, hasReady: items.value.some(i => i.category === 'skill' && i.status === 'ready') },
  { key: 'talent', name: '天赋', count: 0, hasReady: items.value.some(i => i.category === 'talent' && i.status === 'ready') },
  { key: 'milestone', name: '里程碑', count: 0, hasReady: items.value.some(i => i.category === 'milestone' && i.status === 'ready') },
])

const filteredAchievements = computed(() => {
  if (activeTab.value === 'all') return items.value
  return items.value.filter(i => i.category === activeTab.value)
})

async function loadData({ silent = false } = {}) {
  let uid
  try {
    uid = await ensureChildUser()
  } catch (e) {
    loading.value = false
    uni.showToast({ title: '加载失败', icon: 'none' })
    return
  }

  const cached = readAchievementCache(uid)
  if (cached?.items?.length) {
    items.value = cached.items
    loading.value = false
    refreshing.value = true
  } else if (!silent) {
    loading.value = true
  }

  try {
    const data = await fetchAchievementList(uid)
    items.value = data.items
  } catch (e) {
    console.error('加载成就失败:', e)
    if (e?.cached?.items?.length) {
      items.value = e.cached.items
    } else if (!items.value.length) {
      uni.showToast({ title: e.message || '加载失败', icon: 'none' })
    }
  }
  loading.value = false
  refreshing.value = false
}

function showDetail(item) {
  selectedAchievement.value = item
  detailVisible.value = true
}

async function handleClaim(item) {
  const prevStatus = item.status
  const prevClaimed = item.claimed_at
  items.value = items.value.map((i) => (
    i.id === item.id
      ? { ...i, status: 'claimed', claimed_at: new Date().toISOString() }
      : i
  ))
  detailVisible.value = false
  try {
    const uid = await ensureChildUser()
    await claimAchievement(uid, item.id)
    uni.showToast({ title: '领取成功！', icon: 'success' })
    await loadData({ silent: true })
  } catch (e) {
    items.value = items.value.map((i) => (
      i.id === item.id
        ? { ...i, status: prevStatus, claimed_at: prevClaimed }
        : i
    ))
    uni.showToast({ title: e.message || '领取失败', icon: 'none' })
  }
}

function handleSetTitle(item) {
  // 跳转到称号管理页面
  uni.navigateTo({ url: '/pages/achievement/titles' })
}

function goShowcase() {
  uni.navigateTo({ url: '/pages/achievement/showcase' })
}

function goTitles() {
  uni.navigateTo({ url: '/pages/achievement/titles' })
}

function goBack() {
  uni.navigateBack({ delta: 1 })
}

function formatDate(isoStr) {
  if (!isoStr) return ''
  const d = new Date(isoStr)
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

onMounted(loadData)
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

.refresh-bar {
  height: 2px;
  margin: -4px 0 12px;
  border-radius: 2px;
  background: var(--accent);
  opacity: 0.7;
}

/* 统计卡片（已隐藏） */
.stats-card { display: none; }

/* 快捷入口 */
.quick-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.action-btn {
  flex: 1;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.action-btn:active {
  transform: scale(0.98);
  background: var(--accent-bg);
}
.action-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.action-icon.showcase {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  color: #fff;
}
.action-icon.title {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: #fff;
}
.action-text {
  color: var(--text);
  font-size: 14px;
  font-weight: 600;
}

/* 分类筛选 */
.filter-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  overflow-x: auto;
  padding-bottom: 4px;
}
.tab-item {
  padding: 8px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 13px;
  color: var(--text-dim);
  cursor: pointer;
  white-space: nowrap;
  position: relative;
  transition: all 0.2s;
}
.tab-item.active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
.tab-dot {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 8px;
  height: 8px;
  background: #ef4444;
  border-radius: 50%;
  box-shadow: 0 0 0 2px var(--bg-card);
}
.tab-item.active .tab-dot {
  box-shadow: 0 0 0 2px var(--accent);
}

/* 勋章网格 */
.achievement-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
.achievement-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  overflow: hidden;
}
.achievement-card:active {
  transform: scale(0.98);
}
.achievement-card.locked {
  opacity: 0.6;
}
.achievement-card.ready {
  border-color: #f59e0b;
  box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.2);
}
.achievement-card.claimed {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
  border-color: var(--accent);
}

/* 颜色主题 */
.achievement-card.yellow { border-left: 3px solid #f59e0b; }
.achievement-card.blue { border-left: 3px solid #3b82f6; }
.achievement-card.purple { border-left: 3px solid #8b5cf6; }
.achievement-card.green { border-left: 3px solid #10b981; }
.achievement-card.pink { border-left: 3px solid #ec4899; }

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}
.medal-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--bg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-dim);
}
.achievement-card.ready .medal-icon {
  background: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
}
.achievement-card.claimed .medal-icon {
  background: var(--accent-bg);
  color: var(--accent);
}
.ready-dot {
  width: 10px;
  height: 10px;
  background: #ef4444;
  border-radius: 50%;
  box-shadow: 0 0 0 3px var(--bg-card);
  animation: dotPulse 2s ease-in-out infinite;
}
@keyframes dotPulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.1); opacity: 0.8; }
}
.medal-name {
  color: var(--text);
  font-size: 14px;
  font-weight: 700;
  display: block;
  margin-bottom: 4px;
}
.medal-title {
  color: var(--accent);
  font-size: 12px;
  font-weight: 600;
  display: block;
  margin-bottom: 6px;
}
.medal-desc {
  color: var(--text-dim);
  font-size: 11px;
  line-height: 1.4;
  display: block;
  margin-bottom: 10px;
}
.progress-section {
  margin-top: 8px;
}
.mini-progress {
  height: 4px;
  background: var(--bg);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 4px;
}
.mini-progress-fill {
  height: 100%;
  background: var(--accent);
  border-radius: 2px;
}
.progress-label {
  color: var(--text-dim);
  font-size: 10px;
}
.claimed-time {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--border);
}
.claimed-time text {
  color: var(--text-hint);
  font-size: 10px;
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 40px 20px;
}
.empty-text {
  color: var(--text-dim);
  font-size: 14px;
}

/* 骨架屏 */
.skeleton { padding: 0; }
.sk-actions { display:flex; gap:12px; margin-bottom:16px; }
.sk-action { flex:1; height:72px; background:var(--bg-card); border-radius:16px; }
.sk-title { width:80px; height:15px; background:var(--bg-card); border-radius:6px; margin:0 0 12px; }
.sk-badges { display:grid; grid-template-columns:repeat(2,1fr); gap:12px; }
.sk-badge { height:180px; border-radius:16px; background:var(--bg-card); }
.skeleton .sk-action,
.skeleton .sk-title,
.skeleton .sk-badge { animation: skPulse 1.4s ease-in-out infinite; }
@keyframes skPulse { 0%,100% { opacity:0.3; } 50% { opacity:0.7; } }
</style>
