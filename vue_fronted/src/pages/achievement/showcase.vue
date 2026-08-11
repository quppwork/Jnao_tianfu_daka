<template>
  <view class="app">
    <view class="nav">
      <view class="nav-back" @click="goBack">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#8b949e" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      </view>
      <text class="nav-title">荣誉展柜</text>
      <view class="nav-spacer"></view>
    </view>

    <scroll-view class="body" scroll-y :show-scrollbar="false" :enhanced="true">
      <!-- 展柜说明 -->
      <view class="intro-card">
        <view class="intro-icon">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="18" height="18" rx="2"/>
            <circle cx="8.5" cy="8.5" r="1.5"/>
            <path d="M21 15l-5-5L5 21"/>
          </svg>
        </view>
        <view class="intro-content">
          <text class="intro-title">展示你的荣耀</text>
          <text class="intro-desc">选择3枚最引以为傲的勋章放入展柜，让好友见证你的成就</text>
        </view>
      </view>

      <!-- 展柜槽位 -->
      <view class="showcase-section">
        <text class="section-title">展柜槽位</text>
        <view class="slots-grid">
          <view
            v-for="slot in slots"
            :key="slot.slot"
            class="slot-card"
            :class="{ empty: slot.empty }"
            @click="selectSlot(slot)"
          >
            <view v-if="slot.empty" class="slot-empty">
              <view class="empty-icon">
                <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/>
                  <line x1="12" y1="8" x2="12" y2="16"/>
                  <line x1="8" y1="12" x2="16" y2="12"/>
                </svg>
              </view>
              <text class="empty-text">点击添加勋章</text>
            </view>
            <view v-else class="slot-filled">
              <view class="slot-medal" :class="slot.color_theme">
                <svg viewBox="0 0 24 24" width="32" height="32" fill="currentColor">
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                </svg>
              </view>
              <text class="slot-name">{{ slot.name }}</text>
              <text class="slot-title">{{ slot.title }}</text>
              <view class="remove-btn" @click.stop="removeSlot(slot.slot)">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"/>
                  <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </view>
            </view>
            <view class="slot-number">{{ slot.slot + 1 }}</view>
          </view>
        </view>
      </view>

      <!-- 可选勋章列表 -->
      <view class="available-section">
        <text class="section-title">可选勋章（已解锁）</text>
        <view v-if="availableAchievements.length === 0" class="empty-state">
          <text class="empty-text">暂无可展示勋章，快去解锁吧！</text>
        </view>
        <view v-else class="achievement-list">
          <view
            v-for="item in availableAchievements"
            :key="item.id"
            class="achievement-item"
            :class="{ disabled: isInShowcase(item.id) }"
            @click="selectAchievement(item)"
          >
            <view class="item-icon" :class="item.color_theme">
              <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
              </svg>
            </view>
            <view class="item-info">
              <text class="item-name">{{ item.name }}</text>
              <text class="item-title">{{ item.title }}</text>
            </view>
            <view v-if="isInShowcase(item.id)" class="in-showcase-badge">
              <text>已展示</text>
            </view>
          </view>
        </view>
      </view>

      <view style="height: 40px;"></view>
    </scroll-view>

    <!-- 槽位选择弹窗 -->
    <view v-if="slotModalVisible" class="modal-mask" @click="slotModalVisible = false">
      <view class="modal-content" @click.stop>
        <text class="modal-title">选择槽位 {{ selectedSlot + 1 }} 的勋章</text>
        <view class="modal-list">
          <view
            v-for="item in availableAchievements"
            :key="item.id"
            class="modal-item"
            @click="confirmSelect(item)"
          >
            <view class="item-icon" :class="item.color_theme">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
              </svg>
            </view>
            <view class="item-info">
              <text class="item-name">{{ item.name }}</text>
              <text class="item-title">{{ item.title }}</text>
            </view>
          </view>
        </view>
        <view class="modal-actions">
          <view class="btn-cancel" @click="slotModalVisible = false">取消</view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  ensureChildUser,
  fetchShowcase,
  setShowcaseSlot,
  fetchAchievementList,
} from '@/utils/userApi.js'

const loading = ref(true)
const slots = ref([{ slot: 0, empty: true }, { slot: 1, empty: true }, { slot: 2, empty: true }])
const availableAchievements = ref([])
const slotModalVisible = ref(false)
const selectedSlot = ref(0)

async function loadData() {
  loading.value = true
  try {
    const uid = await ensureChildUser()
    const [showcaseData, listData] = await Promise.all([
      fetchShowcase(uid),
      fetchAchievementList(uid),
    ])

    // 填充展柜
    slots.value = showcaseData

    // 筛选已解锁的勋章
    availableAchievements.value = listData.items.filter(i => i.status === 'claimed')
  } catch (e) {
    console.error('加载展柜失败:', e)
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
  loading.value = false
}

function isInShowcase(achievementId) {
  return slots.value.some(s => !s.empty && s.achievement_id === achievementId)
}

function selectSlot(slot) {
  if (slot.empty) {
    selectedSlot.value = slot.slot
    slotModalVisible.value = true
  }
}

function selectAchievement(item) {
  if (isInShowcase(item.id)) {
    uni.showToast({ title: '该勋章已在展柜中', icon: 'none' })
    return
  }
  // 找第一个空槽位
  const emptySlot = slots.value.find(s => s.empty)
  if (emptySlot) {
    selectedSlot.value = emptySlot.slot
    confirmSelect(item)
  } else {
    uni.showToast({ title: '展柜已满，请先移除', icon: 'none' })
  }
}

async function confirmSelect(item) {
  try {
    const uid = await ensureChildUser()
    await setShowcaseSlot(uid, selectedSlot.value, item.id)
    uni.showToast({ title: '设置成功', icon: 'success' })
    slotModalVisible.value = false
    await loadData()
  } catch (e) {
    uni.showToast({ title: e.message || '设置失败', icon: 'none' })
  }
}

async function removeSlot(slotIndex) {
  try {
    const uid = await ensureChildUser()
    await setShowcaseSlot(uid, slotIndex, null)
    uni.showToast({ title: '已移除', icon: 'success' })
    await loadData()
  } catch (e) {
    uni.showToast({ title: e.message || '移除失败', icon: 'none' })
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

/* 介绍卡片 */
.intro-card {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  border-radius: 16px;
  padding: 16px;
  margin-bottom: 20px;
  display: flex;
  gap: 12px;
  align-items: center;
}
.intro-icon {
  width: 48px;
  height: 48px;
  background: rgba(255,255,255,0.2);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}
.intro-content {
  flex: 1;
}
.intro-title {
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  display: block;
}
.intro-desc {
  color: rgba(255,255,255,0.85);
  font-size: 12px;
  display: block;
  margin-top: 4px;
  line-height: 1.4;
}

/* 区块标题 */
.section-title {
  color: var(--text);
  font-size: 15px;
  font-weight: 700;
  display: block;
  margin-bottom: 12px;
}

/* 展柜槽位 */
.showcase-section {
  margin-bottom: 24px;
}
.slots-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.slot-card {
  aspect-ratio: 1;
  background: var(--bg-card);
  border: 2px dashed var(--border);
  border-radius: 16px;
  position: relative;
  cursor: pointer;
  transition: all 0.2s;
  overflow: hidden;
}
.slot-card:not(.empty) {
  border-style: solid;
  border-color: var(--accent);
}
.slot-card:active {
  transform: scale(0.96);
}
.slot-empty {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.empty-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--bg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-dim);
}
.empty-text {
  color: var(--text-dim);
  font-size: 11px;
  text-align: center;
}
.slot-filled {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px;
}
.slot-medal {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}
.slot-medal.yellow { background: linear-gradient(135deg, #f59e0b, #d97706); }
.slot-medal.blue { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.slot-medal.purple { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }
.slot-medal.green { background: linear-gradient(135deg, #10b981, #059669); }
.slot-medal.pink { background: linear-gradient(135deg, #ec4899, #db2777); }
.slot-name {
  color: var(--text);
  font-size: 11px;
  font-weight: 700;
  text-align: center;
}
.slot-title {
  color: var(--accent);
  font-size: 10px;
  font-weight: 600;
}
.remove-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 24px;
  height: 24px;
  background: rgba(0,0,0,0.5);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}
.slot-number {
  position: absolute;
  top: 4px;
  left: 4px;
  width: 20px;
  height: 20px;
  background: var(--bg);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-dim);
  font-size: 10px;
  font-weight: 600;
}

/* 可选勋章列表 */
.available-section {
  margin-bottom: 20px;
}
.achievement-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.achievement-item {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.achievement-item:active {
  background: var(--accent-bg);
}
.achievement-item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.item-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}
.item-icon.yellow { background: linear-gradient(135deg, #f59e0b, #d97706); }
.item-icon.blue { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.item-icon.purple { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }
.item-icon.green { background: linear-gradient(135deg, #10b981, #059669); }
.item-icon.pink { background: linear-gradient(135deg, #ec4899, #db2777); }
.item-info {
  flex: 1;
  min-width: 0;
}
.item-name {
  color: var(--text);
  font-size: 14px;
  font-weight: 600;
  display: block;
}
.item-title {
  color: var(--text-dim);
  font-size: 12px;
  display: block;
  margin-top: 2px;
}
.in-showcase-badge {
  background: var(--accent-bg);
  color: var(--accent);
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 4px;
  font-weight: 600;
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

/* 弹窗 */
.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}
.modal-content {
  background: var(--bg-card);
  border-radius: 20px;
  width: 100%;
  max-width: 400px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.modal-title {
  color: var(--text);
  font-size: 16px;
  font-weight: 700;
  padding: 20px;
  text-align: center;
  border-bottom: 1px solid var(--border);
}
.modal-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.modal-item {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
}
.modal-item:active {
  background: var(--accent-bg);
}
.modal-actions {
  padding: 16px;
  border-top: 1px solid var(--border);
}
.btn-cancel {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px;
  text-align: center;
  color: var(--text-dim);
  font-size: 14px;
  cursor: pointer;
}
</style>
