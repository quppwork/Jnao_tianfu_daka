<template>
  <view class="app">
    <view class="nav">
      <view class="nav-back" @click="goBack"><text>← 返回</text></view>
      <text class="nav-title">家长详情</text>
      <view class="nav-btn" @click="showEdit = true"><text>编辑</text></view>
    </view>

    <view v-if="loading" class="empty"><text>加载中...</text></view>

    <view v-else-if="detail" class="content">
      <view class="card">
        <text class="card-title">{{ detail.nickname }}</text>
        <view class="row-line"><text class="label">手机号</text><text class="val">{{ detail.parent_phone }}</text></view>
        <view class="row-line"><text class="label">孩子名额</text><text class="val">{{ detail.children_count }} / {{ detail.child_quota }}</text></view>
        <view class="row-line"><text class="label">注册时间</text><text class="val">{{ formatTime(detail.created_at) }}</text></view>
      </view>

      <view v-if="detail.is_duplicate_account" class="warn-box">
        <text class="warn-title">重复家长账号</text>
        <text class="warn-text">该手机号存在多个家长账号，孩子列表已合并显示自主账号（ID {{ detail.canonical_parent_id }}）。</text>
      </view>

      <view v-if="detail.pending_unbound_count > 0" class="warn-box">
        <text class="warn-title">待绑定孩子（{{ detail.pending_unbound_count }}）</text>
        <text class="warn-text">同手机号下有孩子账号尚未绑定到该家长，需管理员确认后才会出现在列表中。</text>
        <view v-for="c in detail.unbound_children" :key="c.id" class="warn-row">
          <text class="warn-text">{{ c.nickname }} · {{ c.login_name }}</text>
        </view>
        <view class="btn-reconcile" @click="doReconcile"><text>确认绑定</text></view>
      </view>

      <view v-if="reconcileMsg" class="info-box">
        <text class="info-text">{{ reconcileMsg }}</text>
      </view>

      <view v-if="detail.duplicate_parents?.length" class="warn-box">
        <text class="warn-title">同手机号其他账号（{{ detail.duplicate_parents.length }}）</text>
        <view v-for="d in detail.duplicate_parents" :key="d.id" class="warn-row">
          <text class="warn-text">{{ d.nickname }} · ID {{ d.id }} · {{ d.children_count }} 个孩子</text>
          <text class="act" @click="goParent(d.id)">查看</text>
        </view>
      </view>

      <view class="section">
        <text class="section-title">在线设备（{{ detail.active_sessions?.length || 0 }}）</text>
        <view v-if="!detail.active_sessions?.length" class="hint"><text>暂无活跃会话</text></view>
        <view v-for="s in detail.active_sessions" :key="s.id" class="mini-row">
          <text class="mini-name">{{ s.device_label || '设备' }}</text>
          <text class="mini-sub">最近活跃 {{ formatTime(s.last_active_at) }}</text>
        </view>
      </view>

      <view class="section">
        <text class="section-title">名下孩子（{{ detail.children?.length || 0 }}）</text>
        <view v-if="!detail.children?.length" class="hint"><text>暂无孩子</text></view>
        <view
          v-for="c in detail.children"
          :key="c.id"
          class="row"
          @click="goChild(c.id)"
        >
          <view class="main">
            <text class="name">{{ c.nickname }}（{{ c.login_name || '—' }}）</text>
            <text class="sub">训练 {{ c.training_days || 0 }} 天 · 打卡 {{ c.checkins || 0 }} 次</text>
          </view>
          <text class="act">查看</text>
        </view>
      </view>
    </view>

    <view v-if="showEdit" class="overlay" @click="showEdit = false">
      <view class="panel" @click.stop>
        <text class="panel-title">编辑家长</text>
        <view class="field"><input v-model="form.nickname" placeholder="昵称" class="inp" /></view>
        <view class="field"><input v-model="form.parent_phone" placeholder="手机号" class="inp" /></view>
        <view class="field"><input v-model="form.password" placeholder="新密码（留空不改）" type="password" class="inp" /></view>
        <view class="field"><input v-model.number="form.child_quota" placeholder="孩子名额" type="number" class="inp" /></view>
        <view class="btn-primary" @click="save"><text>保存</text></view>
        <view class="btn-danger" @click="confirmDelete"><text>删除家长（归档账号）</text></view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import {
  requirePageAuth,
  fetchAdminParentDetail,
  reconcileAdminParent,
  updateAdminParent,
  deleteAdminParent,
} from '@/utils/userApi.js'
import { formatDateTimeShanghai } from '@/utils/datetime.js'

const adminId = ref(null)
const parentId = ref(null)
const loading = ref(true)
const detail = ref(null)
const showEdit = ref(false)
const form = ref({})
const reconcileMsg = ref('')

onLoad((q) => {
  parentId.value = Number(q.id)
})

onMounted(async () => {
  if (!parentId.value) {
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
    detail.value = await fetchAdminParentDetail(adminId.value, parentId.value)
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

function goChild(id) {
  uni.navigateTo({ url: `/pages/admin/child-detail?id=${id}` })
}

function goParent(id) {
  if (id === parentId.value) return
  uni.redirectTo({ url: `/pages/admin/parent-detail?id=${id}` })
}

async function doReconcile() {
  try {
    const res = await reconcileAdminParent(adminId.value, parentId.value)
    reconcileMsg.value = `已绑定 ${res.reconciled_count} 个孩子`
    await load()
    uni.showToast({ title: '绑定完成', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '绑定失败', icon: 'none' })
  }
}

async function save() {
  const p = form.value
  const body = { nickname: p.nickname, parent_phone: p.parent_phone, child_quota: p.child_quota }
  if (p.password) body.password = p.password
  try {
    await updateAdminParent(adminId.value, parentId.value, body)
    showEdit.value = false
    await load()
    uni.showToast({ title: '已保存', icon: 'none' })
  } catch (_) {
    uni.showToast({ title: '保存失败', icon: 'none' })
  }
}

function confirmDelete() {
  uni.showModal({
    title: '危险操作',
    content: '将归档该家长及名下孩子账号，业务数据会清除。确定？',
    success: async (r) => {
      if (!r.confirm) return
      try {
        await deleteAdminParent(adminId.value, parentId.value)
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
.val { color:var(--text); font-size:13px; }
.section { margin-bottom:20px; }
.section-title { display:block; color:var(--text); font-size:15px; font-weight:600; margin-bottom:10px; }
.hint { color:var(--text-dim); font-size:12px; padding:8px 0; }
.mini-row { background:var(--bg-card); border:1px solid var(--border); border-radius:10px; padding:10px 12px; margin-bottom:6px; }
.mini-name { display:block; color:var(--text); font-size:13px; }
.mini-sub { display:block; color:var(--text-dim); font-size:11px; margin-top:2px; }
.row { display:flex; align-items:center; background:var(--bg-card); border:1px solid var(--border); border-radius:12px; padding:14px; margin-bottom:8px; }
.main { flex:1; }
.name { display:block; color:var(--text); font-size:15px; font-weight:600; }
.sub { display:block; color:var(--text-dim); font-size:12px; margin-top:4px; }
.act { color:#f59e0b; font-size:12px; }
.empty { text-align:center; padding:40px; color:var(--text-dim); }
.overlay { position:fixed; inset:0; background:rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center; padding:20px; z-index:100; }
.panel { width:100%; max-width:340px; background:var(--bg-card); border-radius:14px; padding:20px; }
.panel-title { display:block; text-align:center; font-weight:700; color:var(--text); margin-bottom:14px; }
.field { margin-bottom:10px; border:1px solid var(--border); border-radius:10px; padding:0 10px; }
.inp { width:100%; padding:12px 0; font-size:14px; color:var(--text); }
.btn-primary { background:#f59e0b; border-radius:10px; padding:12px; text-align:center; margin-top:8px; }
.btn-primary text { color:#fff; font-weight:600; }
.btn-danger { margin-top:8px; padding:12px; text-align:center; border-radius:10px; background:rgba(220,38,38,0.1); }
.btn-danger text { color:#dc2626; font-size:13px; }
.warn-box { background:rgba(245,158,11,0.12); border:1px solid rgba(245,158,11,0.35); border-radius:12px; padding:12px; margin-bottom:12px; }
.warn-title { display:block; color:#f59e0b; font-size:13px; font-weight:600; margin-bottom:6px; }
.warn-text { display:block; color:var(--text-dim); font-size:12px; line-height:1.5; }
.warn-row { display:flex; align-items:center; justify-content:space-between; margin-top:6px; }
.info-box { background:rgba(34,197,94,0.1); border:1px solid rgba(34,197,94,0.3); border-radius:12px; padding:10px 12px; margin-bottom:12px; }
.btn-reconcile { margin-top:10px; background:#f59e0b; border-radius:10px; padding:10px; text-align:center; }
.btn-reconcile text { color:#fff; font-size:13px; font-weight:600; }
.info-text { color:#22c55e; font-size:12px; }
</style>
