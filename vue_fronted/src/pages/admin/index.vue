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
      <view class="toolbar">
        <input v-model="parentSearch" class="search-inp" placeholder="搜索昵称或手机号" @confirm="loadParents" />
        <view class="toolbar-row">
          <view class="sub-tab" :class="{ on: parentSubTab === 'active' }" @click="switchParentSub('active')"><text>在用</text></view>
          <view class="sub-tab" :class="{ on: parentSubTab === 'removed' }" @click="switchParentSub('removed')"><text>已移出</text></view>
          <view class="btn-sm" @click="openParentCreate"><text>+ 新建家长</text></view>
          <view v-if="parentSubTab === 'removed'" class="btn-sm" @click="openRestoreByPhone"><text>按手机号恢复</text></view>
        </view>
      </view>
      <view v-if="parentSubTab === 'removed' && !removedParents.length" class="empty">
        <text>暂无已移出家长</text>
        <view class="btn-sm restore-quick" @click="openRestoreByPhone"><text>按手机号恢复</text></view>
      </view>
      <view v-for="p in displayParents" :key="p.id" class="row" @click="goParent(p.id)">
        <view class="main">
          <view class="name-row">
            <text class="name">{{ p.nickname }}</text>
            <text v-if="p.account_status && p.account_status !== 'active'" class="badge">{{ statusLabel(p.account_status) }}</text>
          </view>
          <text class="sub">{{ p.display_phone || p.parent_phone }} · 名额 {{ p.children_count }}/{{ p.child_quota }}</text>
        </view>
        <text v-if="parentSubTab === 'removed'" class="act" @click.stop="doRestoreParent(p)">恢复</text>
        <text v-else class="act">详情</text>
      </view>
    </view>

    <view v-else-if="tab === 'children'" class="list">
      <view class="toolbar">
        <input v-model="childSearch" class="search-inp" placeholder="搜索昵称或账号" @confirm="loadChildren" />
        <view class="btn-sm" @click="openChildCreate"><text>+ 新建孩子</text></view>
      </view>
      <view class="toolbar" style="margin-top:6px;padding:8px 10px;background:var(--bg-card);border-radius:8px;display:flex;align-items:center;gap:8px;">
        <text style="font-size:12px;color:var(--text-dim);white-space:nowrap;">🧪 批量调整测试次数</text>
        <view class="btn-sm" @click="applyBatchQuota(1)" style="flex-shrink:0;"><text>全部 +1</text></view>
        <view class="btn-sm" @click="applyBatchQuota(-1)" style="flex-shrink:0;"><text>全部 -1</text></view>
        <view class="btn-sm" @click="applyBatchQuota(3)" style="flex-shrink:0;"><text>全部 +3</text></view>
        <view class="btn-sm" @click="applyBatchQuota(5)" style="flex-shrink:0;"><text>全部 +5</text></view>
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

    <!-- 家长新建 -->
    <view v-if="showParentForm" class="overlay" @click="showParentForm = false">
      <view class="panel" @click.stop>
        <text class="panel-title">新建家长</text>
        <view class="field-inp"><input v-model="parentForm.parent_phone" placeholder="手机号" class="inp" /></view>
        <view class="field-inp"><input v-model="parentForm.nickname" placeholder="昵称" class="inp" /></view>
        <view class="field-inp"><input v-model="parentForm.password" placeholder="密码（可选）" type="password" class="inp" /></view>
        <view class="field-inp"><input v-model.number="parentForm.child_quota" placeholder="孩子名额" type="number" class="inp" /></view>
        <view class="btn-primary" @click="saveParent"><text>创建</text></view>
      </view>
    </view>

    <!-- 按手机号恢复 -->
    <view v-if="showRestoreForm" class="overlay" @click="showRestoreForm = false">
      <view class="panel" @click.stop>
        <text class="panel-title">恢复家长</text>
        <text class="panel-hint">输入手机号或昵称，找回已移出/归档账号</text>
        <view class="field-inp"><input v-model="restoreForm.phone" placeholder="手机号" class="inp" /></view>
        <view class="field-inp"><input v-model="restoreForm.nickname" placeholder="昵称（可选）" class="inp" /></view>
        <view class="btn-primary" @click="saveRestore"><text>恢复</text></view>
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
import { ref, computed, onMounted, watch } from 'vue'
import {
  clearAdminSession,
  logoutAdminAndGoLogin,
  requirePageAuth,
  fetchAdminParents,
  fetchAdminRemovedParents,
  fetchAdminChildren,
  createAdminParent,
  createAdminChild,
  restoreAdminParent,
  restoreAdminParentByPhone,
  fetchAdminSettings,
  updateAdminSettings,
  fetchAdminBlacklist,
  removeAdminBlacklist,
  batchUpdateTalentQuota,
} from '@/utils/userApi.js'

const adminId = ref(null)
const tab = ref('parents')
const parentSubTab = ref('active')
const parentSearch = ref('')
const childSearch = ref('')
const loading = ref(true)
const parents = ref([])
const removedParents = ref([])
const children = ref([])
const showChildForm = ref(false)
const showParentForm = ref(false)
const showRestoreForm = ref(false)
const childForm = ref({})
const parentForm = ref({ child_quota: 5 })
const restoreForm = ref({ phone: '', nickname: '' })
const createParentId = ref(null)
const settingsForm = ref({ admin_max_devices: 3, parent_max_devices: 1, student_max_devices: 1 })
const settingsLoaded = ref(false)
const blacklist = ref({ ips: [], phones: [], devices: [] })
const blacklistLoaded = ref(false)

const parentOptions = computed(() =>
  parents.value.map(p => ({ id: p.id, label: `${p.nickname} (${p.display_phone || p.parent_phone})` }))
)
const displayParents = computed(() =>
  parentSubTab.value === 'removed' ? removedParents.value : parents.value
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
    await Promise.all([loadParents(), loadChildren()])
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

async function loadParents() {
  const q = parentSearch.value.trim()
  parents.value = await fetchAdminParents(adminId.value, q)
  removedParents.value = await fetchAdminRemovedParents(adminId.value, q)
}

async function loadChildren() {
  children.value = await fetchAdminChildren(adminId.value, { q: childSearch.value.trim() })
}

function switchParentSub(sub) {
  parentSubTab.value = sub
}

function statusLabel(s) {
  if (s === 'removed') return ' 已移出'
  if (s === 'deleted') return ' 已归档'
  return ''
}

function openParentCreate() {
  parentForm.value = { parent_phone: '', nickname: '', password: '', child_quota: 5 }
  showParentForm.value = true
}

function openRestoreByPhone() {
  restoreForm.value = { phone: '', nickname: '' }
  showRestoreForm.value = true
}

async function saveParent() {
  const p = parentForm.value
  if (!p.parent_phone || !p.nickname) {
    uni.showToast({ title: '手机号和昵称必填', icon: 'none' })
    return
  }
  try {
    await createAdminParent(adminId.value, {
      parent_phone: p.parent_phone.trim(),
      nickname: p.nickname.trim(),
      password: p.password || null,
      child_quota: p.child_quota || 5,
    })
    showParentForm.value = false
    parentSubTab.value = 'active'
    await loadParents()
    uni.showToast({ title: '已创建', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '创建失败', icon: 'none' })
  }
}

async function saveRestore() {
  const r = restoreForm.value
  if (!r.phone && !r.nickname) {
    uni.showToast({ title: '请填写手机号或昵称', icon: 'none' })
    return
  }
  try {
    await restoreAdminParentByPhone(adminId.value, {
      phone: r.phone?.trim() || null,
      nickname: r.nickname?.trim() || null,
    })
    showRestoreForm.value = false
    parentSubTab.value = 'active'
    await loadParents()
    uni.showToast({ title: '已恢复', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '未找到账号', icon: 'none' })
  }
}

async function doRestoreParent(p) {
  uni.showModal({
    title: '恢复家长',
    content: `恢复 ${p.nickname}（${p.display_phone || p.parent_phone}）？`,
    success: async (r) => {
      if (!r.confirm) return
      try {
        await restoreAdminParent(adminId.value, p.id)
        parentSubTab.value = 'active'
        await loadParents()
        uni.showToast({ title: '已恢复', icon: 'none' })
      } catch (e) {
        uni.showToast({ title: e.message || '恢复失败', icon: 'none' })
      }
    },
  })
}

let searchTimer = null
watch(parentSearch, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => loadParents().catch(() => {}), 300)
})
watch(childSearch, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => loadChildren().catch(() => {}), 300)
})

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

async function applyBatchQuota(n) {
  const ids = children.value.map(c => c.id)
  if (!ids.length) {
    uni.showToast({ title: '暂无孩子可操作', icon: 'none' })
    return
  }
  uni.showModal({
    title: '批量增加测试次数',
    content: `确定为当前列表中 ${ids.length} 个孩子各增加 ${n} 次天赋测试机会吗？`,
    confirmText: '确定',
    success: async (res) => {
      if (!res.confirm) return
      try {
        const result = await batchUpdateTalentQuota(adminId.value, { childIds: ids, add: n })
        uni.showToast({ title: `已为 ${result.updated} 个孩子增加 ${n} 次`, icon: 'none' })
      } catch (e) {
        uni.showToast({ title: e.message || '操作失败', icon: 'none' })
      }
    },
  })
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
.toolbar-row { display:flex; gap:8px; align-items:center; margin-top:8px; flex-wrap:wrap; }
.search-inp { width:100%; padding:10px 12px; border:1px solid var(--border); border-radius:10px; font-size:14px; color:var(--text); background:var(--bg-card); margin-bottom:8px; }
.sub-tab { padding:6px 12px; border-radius:8px; background:var(--bg-card); border:1px solid var(--border); }
.sub-tab.on { border-color:#f59e0b; background:rgba(245,158,11,0.1); }
.sub-tab text { color:var(--text-dim); font-size:12px; }
.sub-tab.on text { color:#f59e0b; font-weight:600; }
.badge { color:#dc2626; font-size:11px; font-weight:400; }
.restore-quick { margin-top:12px; }
.panel-hint { display:block; text-align:center; color:var(--text-dim); font-size:12px; margin:-8px 0 12px; }
.row { display:flex; align-items:center; background:var(--bg-card); border:1px solid var(--border); border-radius:12px; padding:14px; margin-bottom:8px; }
.main { flex:1; }
.name { display:block; color:var(--text); font-size:15px; font-weight:600; }
.name-row { display:flex; align-items:center; gap:6px; }
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
