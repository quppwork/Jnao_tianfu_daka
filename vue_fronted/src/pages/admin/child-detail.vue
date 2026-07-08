<template>
  <view class="app">
    <view class="nav">
      <view class="nav-back" @click="goBack"><text>← 返回</text></view>
      <text class="nav-title">孩子详情</text>
      <view class="nav-btn" @click="showEdit = true"><text>管理</text></view>
    </view>

    <view v-if="loading" class="empty"><text>加载中...</text></view>

    <view v-else-if="detail" class="content">
      <view class="card">
        <text class="card-title">{{ detail.nickname }}</text>
        <view class="row-line"><text class="label">登录账号</text><text class="val">{{ detail.login_name || '—' }}</text></view>
        <view class="row-line"><text class="label">年级</text><text class="val">{{ detail.grade || '—' }}</text></view>
        <view class="row-line"><text class="label">天赋类型</text><text class="val">{{ detail.talent_display || detail.talent || '—' }}</text></view>
        <view class="row-line"><text class="label">综合等级</text><text class="val">Lv.{{ detail.overall_tier || 1 }}</text></view>
        <view class="row-line"><text class="label">绑定家长</text><text class="val">{{ detail.parent_nickname || '未绑定' }} {{ detail.parent_phone ? `(${detail.parent_phone})` : '' }}</text></view>
        <view class="row-line"><text class="label">注册时间</text><text class="val">{{ formatTime(detail.created_at) }}</text></view>
      </view>

      <view class="stats">
        <view class="stat"><text class="stat-num">{{ detail.training_days || 0 }}</text><text class="stat-label">训练天数</text></view>
        <view class="stat"><text class="stat-num">{{ detail.checkins || 0 }}</text><text class="stat-label">打卡次数</text></view>
        <view class="stat"><text class="stat-num">{{ detail.active_sessions?.length || 0 }}</text><text class="stat-label">在线设备</text></view>
      </view>

      <view v-if="detail.training_progress?.skills" class="section">
        <text class="section-title">训练进度</text>
        <view v-for="(sk, name) in detail.training_progress.skills" :key="name" class="mini-row">
          <text class="mini-name">{{ name }}</text>
          <text class="mini-sub">等级 Lv.{{ sk.tier }} · 连续通过 {{ sk.consecutive_pass || 0 }} 次</text>
        </view>
      </view>

      <view class="section">
        <text class="section-title">训练记录（按日）</text>
        <view v-if="!detail.training_history_days?.length" class="hint"><text>暂无打卡记录</text></view>
        <view v-for="day in detail.training_history_days" :key="day.date" class="day-block">
          <text class="day-title">{{ day.date }}</text>
          <view v-for="(rec, idx) in day.records" :key="idx" class="rec-row">
            <text class="rec-name">{{ rec.item_name || rec.training_name || '训练项' }}</text>
            <text class="rec-sub">{{ formatTime(rec.checkin_at) }} · {{ rec.duration_minutes || rec.minutes || '—' }} 分钟</text>
          </view>
        </view>
      </view>

      <view class="section">
        <text class="section-title">近期训练方案</text>
        <view v-if="!detail.recent_plans?.length" class="hint"><text>暂无方案</text></view>
        <view v-for="p in detail.recent_plans" :key="p.plan_id" class="mini-row">
          <text class="mini-name">{{ p.plan_date }} · {{ p.status }}</text>
          <text class="mini-sub">{{ p.item_count }} 项 · 计划 {{ p.planned_minutes || '—' }} 分钟</text>
        </view>
      </view>

      <view class="section">
        <text class="section-title">在线设备</text>
        <view v-if="!detail.active_sessions?.length" class="hint"><text>暂无活跃会话</text></view>
        <view v-for="s in detail.active_sessions" :key="s.id" class="mini-row">
          <text class="mini-name">{{ s.device_label || '设备' }}</text>
          <text class="mini-sub">最近活跃 {{ formatTime(s.last_active_at) }}</text>
        </view>
      </view>
    </view>

    <view v-if="showEdit" class="overlay" @click="showEdit = false">
      <view class="panel" @click.stop>
        <text class="panel-title">管理孩子</text>
        <view class="field"><input v-model="form.nickname" placeholder="昵称" class="inp" /></view>
        <view class="field"><input v-model="form.password" placeholder="新密码（留空不改）" type="password" class="inp" /></view>
        <view class="field"><input v-model="form.grade" placeholder="年级" class="inp" /></view>
        <view class="btn-primary" @click="save"><text>保存</text></view>
        <view v-if="detail?.parent_id" class="btn-warn" @click="doUnbind"><text>解绑家长</text></view>
        <view class="btn-danger" @click="confirmDelete"><text>删除孩子（归档账号）</text></view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import {
  requirePageAuth,
  fetchAdminChildDetail,
  updateAdminChild,
  deleteAdminChild,
  unbindAdminChild,
} from '@/utils/userApi.js'
import { formatDateTimeShanghai } from '@/utils/datetime.js'

const adminId = ref(null)
const childId = ref(null)
const loading = ref(true)
const detail = ref(null)
const showEdit = ref(false)
const form = ref({})

onLoad((q) => {
  childId.value = Number(q.id)
})

onMounted(async () => {
  if (!childId.value) {
    goBack()
    return
  }
  const auth = await requirePageAuth('admin')
  if (!auth.ok) return
  adminId.value = auth.userId
  await load()
})

async function load() {
  loading.value = true
  try {
    detail.value = await fetchAdminChildDetail(adminId.value, childId.value)
    form.value = { ...detail.value, password: '' }
  } catch (_) {
    uni.showToast({ title: '加载失败', icon: 'none' })
    goBack()
  } finally {
    loading.value = false
  }
}

function formatTime(iso) {
  return formatDateTimeShanghai(iso)
}

function goBack() {
  uni.navigateBack({ fail: () => uni.redirectTo({ url: '/pages/admin/index' }) })
}

async function save() {
  const c = form.value
  const body = { nickname: c.nickname, grade: c.grade || null }
  if (c.password) body.password = c.password
  try {
    await updateAdminChild(adminId.value, childId.value, body)
    showEdit.value = false
    await load()
    uni.showToast({ title: '已保存', icon: 'none' })
  } catch (_) {
    uni.showToast({ title: '保存失败', icon: 'none' })
  }
}

async function doUnbind() {
  uni.showModal({
    title: '解绑',
    content: '解绑后孩子将无法登录，直到重新绑定。确定？',
    success: async (r) => {
      if (!r.confirm) return
      try {
        await unbindAdminChild(adminId.value, childId.value)
        showEdit.value = false
        await load()
        uni.showToast({ title: '已解绑', icon: 'none' })
      } catch (_) {
        uni.showToast({ title: '操作失败', icon: 'none' })
      }
    },
  })
}

function confirmDelete() {
  uni.showModal({
    title: '危险操作',
    content: '将归档该孩子账号，训练等业务数据会清除。确定？',
    success: async (r) => {
      if (!r.confirm) return
      try {
        await deleteAdminChild(adminId.value, childId.value)
        uni.showToast({ title: '已删除', icon: 'none' })
        goBack()
      } catch (_) {
        uni.showToast({ title: '删除失败', icon: 'none' })
      }
    },
  })
}
</script>

<style scoped>
.app { min-height:100vh; background:var(--bg); max-width:480px; margin:0 auto; padding-bottom:40px; }
.nav { display:flex; align-items:center; justify-content:space-between; padding:16px; }
.nav-back text, .nav-btn text { color:var(--text-dim); font-size:13px; }
.nav-title { color:var(--text); font-size:17px; font-weight:700; }
.content { padding:0 16px; }
.card { background:var(--bg-card); border:1px solid var(--border); border-radius:14px; padding:16px; margin-bottom:16px; }
.card-title { display:block; font-size:18px; font-weight:700; color:var(--text); margin-bottom:12px; }
.row-line { display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--border); }
.row-line:last-child { border-bottom:none; }
.label { color:var(--text-dim); font-size:13px; }
.val { color:var(--text); font-size:13px; max-width:60%; text-align:right; }
.stats { display:flex; gap:8px; margin-bottom:16px; }
.stat { flex:1; background:var(--bg-card); border:1px solid var(--border); border-radius:12px; padding:12px; text-align:center; }
.stat-num { display:block; font-size:20px; font-weight:700; color:#f59e0b; }
.stat-label { display:block; font-size:11px; color:var(--text-dim); margin-top:4px; }
.section { margin-bottom:20px; }
.section-title { display:block; color:var(--text); font-size:15px; font-weight:600; margin-bottom:10px; }
.hint { color:var(--text-dim); font-size:12px; padding:8px 0; }
.progress-card { background:var(--bg-card); border:1px solid var(--border); border-radius:10px; padding:12px; }
.progress-text { display:block; color:var(--text); font-size:13px; }
.progress-sub { display:block; color:var(--text-dim); font-size:12px; margin-top:4px; }
.day-block { margin-bottom:12px; }
.day-title { display:block; color:#f59e0b; font-size:13px; font-weight:600; margin-bottom:6px; }
.rec-row { background:var(--bg-card); border:1px solid var(--border); border-radius:8px; padding:8px 10px; margin-bottom:4px; }
.rec-name { display:block; color:var(--text); font-size:13px; }
.rec-sub { display:block; color:var(--text-dim); font-size:11px; margin-top:2px; }
.mini-row { background:var(--bg-card); border:1px solid var(--border); border-radius:10px; padding:10px 12px; margin-bottom:6px; }
.mini-name { display:block; color:var(--text); font-size:13px; }
.mini-sub { display:block; color:var(--text-dim); font-size:11px; margin-top:2px; }
.empty { text-align:center; padding:40px; color:var(--text-dim); }
.overlay { position:fixed; inset:0; background:rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center; padding:20px; z-index:100; }
.panel { width:100%; max-width:340px; background:var(--bg-card); border-radius:14px; padding:20px; max-height:85vh; overflow-y:auto; }
.panel-title { display:block; text-align:center; font-weight:700; color:var(--text); margin-bottom:14px; }
.field { margin-bottom:10px; border:1px solid var(--border); border-radius:10px; padding:0 10px; }
.inp { width:100%; padding:12px 0; font-size:14px; color:var(--text); }
.btn-primary { background:#f59e0b; border-radius:10px; padding:12px; text-align:center; margin-top:8px; }
.btn-primary text { color:#fff; font-weight:600; }
.btn-warn { margin-top:8px; padding:12px; text-align:center; border-radius:10px; background:rgba(245,158,11,0.12); }
.btn-warn text { color:#d97706; font-size:13px; }
.btn-danger { margin-top:8px; padding:12px; text-align:center; border-radius:10px; background:rgba(220,38,38,0.1); }
.btn-danger text { color:#dc2626; font-size:13px; }
</style>
