<template>
  <view class="app">
    <view class="nav">
      <view class="nav-back" @click="goBack">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#8b949e" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      </view>
      <text class="nav-title">称号管理</text>
      <view class="nav-spacer"></view>
    </view>

    <scroll-view class="body" scroll-y :show-scrollbar="false" :enhanced="true">
      <!-- 当前称号 -->
      <view class="current-title-card">
        <text class="card-label">当前佩戴</text>
        <view v-if="currentTitle" class="title-display">
          <view class="title-badge" :class="currentTitle.color_theme">
            <svg viewBox="0 0 24 24" width="32" height="32" fill="currentColor">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
          </view>
          <text class="title-name">{{ currentTitle.title }}</text>
          <text class="title-source">来源：{{ currentTitle.name }}</text>
        </view>
        <view v-else class="no-title">
          <text class="no-title-text">暂未佩戴称号</text>
          <text class="no-title-hint">解锁勋章后可以选择佩戴称号</text>
        </view>
      </view>

      <!-- 称号列表 -->
      <view class="section-title">全部称号</view>
      <view v-if="loading" class="skeleton">
        <view v-for="i in 5" :key="'sk'+i" class="sk-title-item"></view>
      </view>
      <view v-else class="title-list">
        <view
          v-for="item in titleList"
          :key="item.id"
          class="title-item"
          :class="{ active: currentTitle?.title === item.title, locked: item.status !== 'claimed' }"
          @click="selectTitle(item)"
        >
          <view class="title-icon" :class="item.color_theme">
            <svg v-if="item.status === 'claimed'" viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
            <svg v-else viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
          </view>
          <view class="title-info">
            <text class="title-text">{{ item.title }}</text>
            <text class="title-achievement">{{ item.name }}</text>
            <text class="title-condition">{{ item.description }}</text>
          </view>
          <view class="title-status">
            <view v-if="item.status === 'claimed'" class="status-badge unlocked">
              <text>已解锁</text>
            </view>
            <view v-else class="status-badge locked">
              <text>{{ item.progress_text }}</text>
            </view>
          </view>
        </view>
      </view>

      <view style="height: 40px;"></view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import {
  ensureChildUser,
  fetchUserTitle,
  setUserTitle,
  fetchAchievementList,
  readAchievementCache,
} from '@/utils/userApi.js'

const loading = ref(true)
const currentTitle = ref(null)
const titleList = ref([])

async function loadData() {
  try {
    const uid = await ensureChildUser()
    const cached = readAchievementCache(uid)
    if (cached?.items?.length) {
      titleList.value = cached.items
      loading.value = false
    } else {
      loading.value = true
    }
    const [titleData, listData] = await Promise.all([
      fetchUserTitle(uid).catch(() => null),
      fetchAchievementList(uid),
    ])

    currentTitle.value = titleData?.title || null
    titleList.value = listData.items
  } catch (e) {
    console.error('加载称号失败:', e)
    if (e?.cached?.items?.length) {
      titleList.value = e.cached.items
    } else if (!titleList.value.length) {
      uni.showToast({ title: '加载失败', icon: 'none' })
    }
  }
  loading.value = false
}

async function selectTitle(item) {
  if (item.status !== 'claimed') {
    uni.showToast({ title: '尚未解锁该称号', icon: 'none' })
    return
  }

  if (currentTitle.value?.title === item.title) {
    uni.showToast({ title: '已佩戴该称号', icon: 'none' })
    return
  }

  try {
    const uid = await ensureChildUser()
    await setUserTitle(uid, item.title)
    uni.showToast({ title: '佩戴成功', icon: 'success' })
    await loadData()
  } catch (e) {
    uni.showToast({ title: e.message || '设置失败', icon: 'none' })
  }
}

function goBack() {
  uni.navigateBack({ delta: 1 })
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

/* 当前称号卡片 */
.current-title-card {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  border-radius: 20px;
  padding: 20px;
  margin-bottom: 20px;
  text-align: center;
}
.card-label {
  color: rgba(255,255,255,0.8);
  font-size: 12px;
  display: block;
  margin-bottom: 16px;
}
.title-display {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.title-badge {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}
.title-badge.yellow { background: linear-gradient(135deg, #f59e0b, #d97706); }
.title-badge.blue { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.title-badge.purple { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }
.title-badge.green { background: linear-gradient(135deg, #10b981, #059669); }
.title-badge.pink { background: linear-gradient(135deg, #ec4899, #db2777); }
.title-name {
  color: #fff;
  font-size: 24px;
  font-weight: 800;
  text-shadow: 0 2px 8px rgba(0,0,0,0.3);
}
.title-source {
  color: rgba(255,255,255,0.8);
  font-size: 12px;
}
.no-title {
  padding: 20px 0;
}
.no-title-text {
  color: rgba(255,255,255,0.9);
  font-size: 16px;
  font-weight: 600;
  display: block;
}
.no-title-hint {
  color: rgba(255,255,255,0.7);
  font-size: 12px;
  display: block;
  margin-top: 8px;
}

/* 区块标题 */
.section-title {
  color: var(--text);
  font-size: 15px;
  font-weight: 700;
  display: block;
  margin-bottom: 12px;
}

/* 称号列表 */
.title-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.title-item {
  background: var(--bg-card);
  border: 2px solid var(--border);
  border-radius: 16px;
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.title-item:active {
  transform: scale(0.98);
}
.title-item.active {
  border-color: var(--accent);
  background: var(--accent-bg);
}
.title-item.locked {
  opacity: 0.6;
}
.title-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}
.title-icon.yellow { background: linear-gradient(135deg, #f59e0b, #d97706); }
.title-icon.blue { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.title-icon.purple { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }
.title-icon.green { background: linear-gradient(135deg, #10b981, #059669); }
.title-icon.pink { background: linear-gradient(135deg, #ec4899, #db2777); }
.title-item.locked .title-icon {
  background: var(--bg);
  color: var(--text-dim);
}
.title-info {
  flex: 1;
  min-width: 0;
}
.title-text {
  color: var(--text);
  font-size: 16px;
  font-weight: 700;
  display: block;
}
.title-achievement {
  color: var(--accent);
  font-size: 12px;
  display: block;
  margin-top: 2px;
}
.title-condition {
  color: var(--text-dim);
  font-size: 11px;
  display: block;
  margin-top: 4px;
  line-height: 1.3;
}
.title-status {
  flex-shrink: 0;
}
.status-badge {
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}
.status-badge.unlocked {
  background: var(--accent);
  color: #fff;
}
.status-badge.locked {
  background: var(--bg);
  color: var(--text-dim);
}

/* 骨架屏 */
.skeleton {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.sk-title-item {
  height: 80px;
  background: var(--bg-card);
  border-radius: 16px;
  animation: skPulse 1.4s ease-in-out infinite;
}
@keyframes skPulse { 0%,100% { opacity:0.3; } 50% { opacity:0.7; } }
</style>
