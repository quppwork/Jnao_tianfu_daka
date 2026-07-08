<template>
  <view class="app">
    <view class="nav">
      <text class="nav-title">管理后台</text>
      <view class="nav-btn" @click="logout"><text>退出</text></view>
    </view>

    <view class="tabs">
      <view class="tab" :class="{ on: tab === 'parents' }" @click="tab = 'parents'"><text>家长</text></view>
      <view class="tab" :class="{ on: tab === 'children' }" @click="tab = 'children'"><text>孩子</text></view>
      <view class="tab" :class="{ on: tab === 'settings' }" @click="openSettings"><text>设置</text></view>
      <view class="tab" :class="{ on: tab === 'blacklist' }" @click="openBlacklist"><text>黑名单</text></view>
    </view>

    <view v-if="loading" class="empty"><text>加载中...</text></view>

    <view v-else-if="tab === 'parents'" class="list">
      <view v-for="p in parents" :key="p.id" class="row" @click="goParent(p.id)">
        <view class="main">
          <text class="name">{{ p.nickname }}</text>
          <text class="sub">{{ p.parent_phone }} · 名额 {{ p.children_count }}/{{ p.child_quota }}</text>
        </view>
        <text class="act">详情</text>
      </view>
    </view>

    <view v-else-if="tab === 'children'" class="list">
      <view class="toolbar">
        <view class="btn-sm" @click="openChildCreate"><text>+ 新建孩子</text></view>
      </view>
      <view v-for="c in children" :key="c.id" class="row" @click="goChild(c.id)">
        <view class="main">
          <text class="name">{{ c.nickname }}（{{ c.login_name || '—' }}）</text>
          <text class="sub">家长：{{ c.parent_nickname || '未绑定' }} · 训练{{ c.training_days || 0 }}天</text>
        </view>
        <text class="act">详情</text>
      </view>
    </view>

    <view v-else-if="tab === 'settings'" class="list settings">
      <text class="settings-hint">登录设备上限（后续接入更多登录方式时仍生效）</text>
      <view class="field">
        <text class="field-label">管理员最多设备数</text>
        <input v-model.number="settingsForm.admin_max_devices" type="number" class="inp" />
      </view>
      <view class="field">
        <text class="field-label">家长最多设备数</text>
        <input v-model.number="settingsForm.parent_max_devices" type="number" class="inp" />
      </view>
      <view class="field">
        <text class="field-label">孩子最多设备数</text>
        <input v-model.number="settingsForm.student_max_devices" type="number" class="inp" />
      </view>
      <view class="btn-primary" @click="saveSettings"><text>保存设置</text></view>
    </view>

    <view v-else-if="tab === 'blacklist'" class="list">
      <text class="settings-hint">登录异常自动拉黑，可在此解封避免误伤</text>
      <text class="bl-section">IP 地址</text>
      <view v-for="r in blacklist.ips" :key="'ip-' + r.value" class="bl-row">
        <view class="main">
          <text class="name">{{ r.value }}</text>
          <text class="sub">{{ r.reason }} · {{ r.created_at || '' }}</text>
        </view>
        <text class="act" @click="unban('ip', r.value)">解封</text>
      </view>
      <text class="bl-section">手机号</text>
      <view v-for="r in blacklist.phones" :key="'ph-' + r.value" class="bl-row">
        <view class="main">
          <text class="name">{{ r.value }}</text>
          <text class="sub">{{ r.reason }} · {{ r.created_at || '' }}</text>
        </view>
        <text class="act" @click="unban('phone', r.value)">解封</text>
      </view>
      <text class="bl-section">设备 ID</text>
      <view v-for="r in blacklist.devices" :key="'dv-' + r.value" class="bl-row">
        <view class="main">
          <text class="name">{{ r.value }}</text>
          <text class="sub">{{ r.reason }} · {{ r.created_at || '' }}</text>
        </view>
        <text class="act" @click="unban('device', r.value)">解封</text>
      </view>
      <view v-if="!blacklist.ips?.length && !blacklist.phones?.length && !blacklist.devices?.length" class="empty">
        <text>暂无黑名单记录</text>
      </view>
    </view>

    <!-- 孩子新建 -->
    <view v-if="showChildForm" class="overlay" @click="showChildForm = false">
      <view class="panel" @click.stop>
        <text class="panel-title">新建孩子</text>
        <view class="field-inp">
          <picker :range="parentOptions" range-key="label" @change="onParentPick">
            <view class="picker">{{ selectedParentLabel || '选择家长' }}</view>
          </picker>
        </view>
        <view class="field-inp"><input v-model="childForm.login_name" placeholder="登录账号" class="inp" /></view>
        <view class="field-inp"><input v-model="childForm.nickname" placeholder="昵称" class="inp" /></view>
        <view class="field-inp"><input v-model="childForm.password" placeholder="密码" type="password" class="inp" /></view>
        <view class="field-inp"><input v-model="childForm.grade" placeholder="年级" class="inp" /></view>
        <view class="btn-primary" @click="saveChild"><text>创建</text></view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  clearAdminSession,
  logoutAdminAndGoLogin,
  requirePageAuth,
  fetchAdminParents,
  fetchAdminChildren,
  createAdminChild,
  fetchAdminSettings,
  updateAdminSettings,
  fetchAdminBlacklist,
  removeAdminBlacklist,
} from '@/utils/userApi.js'

const adminId = ref(null)
const tab = ref('parents')
const loading = ref(true)
const parents = ref([])
const children = ref([])
const showChildForm = ref(false)
const childForm = ref({})
const createParentId = ref(null)
const settingsForm = ref({ admin_max_devices: 3, parent_max_devices: 1, student_max_devices: 1 })
const settingsLoaded = ref(false)
const blacklist = ref({ ips: [], phones: [], devices: [] })
const blacklistLoaded = ref(false)

const parentOptions = computed(() =>
  parents.value.map(p => ({ id: p.id, label: `${p.nickname} (${p.parent_phone})` }))
)
const selectedParentLabel = computed(() => {
  const p = parents.value.find(x => x.id === createParentId.value)
  return p ? `${p.nickname} (${p.parent_phone})` : ''
})

onMounted(async () => {
  const auth = await requirePageAuth('admin')
  if (!auth.ok) return
  adminId.value = auth.userId
  await loadAll()
})

async function loadAll() {
  loading.value = true
  try {
    parents.value = await fetchAdminParents(adminId.value)
    children.value = await fetchAdminChildren(adminId.value)
  } catch (e) {
    if (e?.status === 401) {
      logout()
      return
    }
    uni.showToast({ title: '加载失败，请稍后重试', icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function openSettings() {
  tab.value = 'settings'
  if (settingsLoaded.value) return
  try {
    const data = await fetchAdminSettings(adminId.value)
    settingsForm.value = { ...data.login_policy }
    settingsLoaded.value = true
  } catch (_) {
    uni.showToast({ title: '加载设置失败', icon: 'none' })
  }
}

async function openBlacklist() {
  tab.value = 'blacklist'
  if (blacklistLoaded.value) return
  try {
    blacklist.value = await fetchAdminBlacklist(adminId.value)
    blacklistLoaded.value = true
  } catch (_) {
    uni.showToast({ title: '加载黑名单失败', icon: 'none' })
  }
}

async function unban(kind, value) {
  uni.showModal({
    title: '解封确认',
    content: `确定解封 ${value} ？`,
    success: async (r) => {
      if (!r.confirm) return
      try {
        await removeAdminBlacklist(adminId.value, kind, value)
        blacklist.value = await fetchAdminBlacklist(adminId.value)
        uni.showToast({ title: '已解封', icon: 'none' })
      } catch (_) {
        uni.showToast({ title: '操作失败', icon: 'none' })
      }
    },
  })
}

async function saveSettings() {
  try {
    const data = await updateAdminSettings(adminId.value, {
      login_policy: { ...settingsForm.value },
    })
    settingsForm.value = { ...data.login_policy }
    uni.showToast({ title: '已保存', icon: 'none' })
  } catch (_) {
    uni.showToast({ title: '保存失败', icon: 'none' })
  }
}

function goParent(id) {
  uni.navigateTo({ url: `/pages/admin/parent-detail?id=${id}` })
}

function goChild(id) {
  uni.navigateTo({ url: `/pages/admin/child-detail?id=${id}` })
}

function openChildCreate() {
  childForm.value = { login_name: '', nickname: '', password: '', grade: '' }
  createParentId.value = parents.value[0]?.id || null
  showChildForm.value = true
}

function onParentPick(e) {
  const idx = e.detail.value
  createParentId.value = parentOptions.value[idx]?.id || null
}

async function saveChild() {
  const c = childForm.value
  if (!createParentId.value) { uni.showToast({ title: '请选择家长', icon: 'none' }); return }
  if (!c.login_name || !c.password) { uni.showToast({ title: '账号和密码必填', icon: 'none' }); return }
  try {
    await createAdminChild(adminId.value, {
      parent_id: createParentId.value,
      login_name: c.login_name.trim(),
      nickname: c.nickname.trim(),
      password: c.password,
      grade: c.grade || null,
    })
    showChildForm.value = false
    await loadAll()
    uni.showToast({ title: '已创建', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.status === 409 ? '账号已存在' : '创建失败', icon: 'none' })
  }
}

function logout() {
  logoutAdminAndGoLogin()
}
</script>

<style scoped>
.app { min-height:100vh; background:var(--bg); max-width:480px; margin:0 auto; padding-bottom:40px; }
.nav { display:flex; align-items:center; justify-content:space-between; padding:16px; }
.nav-title { color:var(--text); font-size:17px; font-weight:700; }
.nav-btn text { color:var(--text-dim); font-size:13px; }
.tabs { display:flex; gap:8px; padding:0 16px 12px; }
.tab { flex:1; text-align:center; padding:10px; border-radius:10px; background:var(--bg-card); border:1px solid var(--border); }
.tab.on { border-color:#f59e0b; background:rgba(245,158,11,0.1); }
.tab.on text { color:#f59e0b; font-weight:600; }
.tab text { color:var(--text-dim); font-size:14px; }
.list { padding:0 16px; }
.toolbar { margin-bottom:10px; }
.row { display:flex; align-items:center; background:var(--bg-card); border:1px solid var(--border); border-radius:12px; padding:14px; margin-bottom:8px; }
.main { flex:1; }
.name { display:block; color:var(--text); font-size:15px; font-weight:600; }
.sub { display:block; color:var(--text-dim); font-size:12px; margin-top:4px; }
.act { color:#f59e0b; font-size:12px; }
.empty { text-align:center; padding:40px; color:var(--text-dim); }
.settings-hint { display:block; color:var(--text-dim); font-size:12px; margin-bottom:16px; line-height:1.5; }
.field { margin-bottom:14px; }
.field-label { display:block; color:var(--text); font-size:13px; margin-bottom:6px; }
.field .inp { width:100%; padding:12px; border:1px solid var(--border); border-radius:10px; font-size:14px; color:var(--text); background:var(--bg-card); }
.overlay { position:fixed; inset:0; background:rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center; padding:20px; z-index:100; }
.panel { width:100%; max-width:340px; background:var(--bg-card); border-radius:14px; padding:20px; }
.panel-title { display:block; text-align:center; font-weight:700; color:var(--text); margin-bottom:14px; }
.field-inp { margin-bottom:10px; border:1px solid var(--border); border-radius:10px; padding:0 10px; }
.inp, .picker { width:100%; padding:12px 0; font-size:14px; color:var(--text); }
.btn-primary { background:#f59e0b; border-radius:10px; padding:12px; text-align:center; margin-top:8px; }
.btn-primary text { color:#fff; font-weight:600; }
.btn-sm { display:inline-block; padding:8px 12px; border-radius:8px; background:rgba(245,158,11,0.15); }
.btn-sm text { color:#d97706; font-size:12px; }
.bl-section { display:block; color:var(--text); font-size:14px; font-weight:600; margin:16px 0 8px; }
.bl-row { display:flex; align-items:center; background:var(--bg-card); border:1px solid var(--border); border-radius:12px; padding:12px; margin-bottom:8px; }
</style>
