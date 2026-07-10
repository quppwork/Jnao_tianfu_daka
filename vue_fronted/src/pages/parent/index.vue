<template>
  <view class="app">
    <view class="nav-bar">
      <view class="nav-back" @click="goToStudentLogin">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--text-dim)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
      </view>
      <text class="nav-center">家长中心</text>
      <view class="nav-actions">
        <view class="nav-icon-btn" @click="toggleTheme">
          <svg v-if="isLight" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--text-dim)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
          <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--text-dim)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
        </view>
        <view class="nav-icon-btn" @click="showSettings = true">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--text-dim)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        </view>
      </view>
    </view>

    <view class="hero">
      <view class="hero-avatar">{{ parentName.charAt(0) }}</view>
      <text class="hero-name">{{ parentName }}</text>
      <text class="hero-sub">已绑定 {{ children.length }} 个孩子 · 名额 {{ quota.used }}/{{ quota.limit }}</text>
    </view>

    <view class="children-section">
      <view class="section-header">
        <text class="section-title">我的孩子</text>
        <view class="btn-add" :class="{ disabled: !quota.can_add }" @click="openAddChild">
          <text>+ 添加孩子</text>
        </view>
      </view>

      <view v-if="loading" class="empty-state">
        <text class="empty-text">加载中...</text>
      </view>
      <view v-else-if="children.length === 0" class="empty-state">
        <text class="empty-icon">📋</text>
        <text class="empty-text">暂无孩子账号</text>
        <text class="empty-hint">点击「添加孩子」分配账号和密码</text>
      </view>
      <view v-for="child in children" :key="child.id" class="child-card" @click="openEditChild(child)">
        <view class="child-avatar">{{ (child.nickname || '?').charAt(0) }}</view>
        <view class="child-info">
          <text class="child-name">{{ child.nickname || '未命名' }}</text>
          <text class="child-detail">账号：{{ child.login_name || '—' }}</text>
          <text class="child-detail">天赋：{{ child.talent || '未测评' }} · 训练 {{ child.training_days || 0 }} 天</text>
        </view>
        <view class="child-arrow"><text>编辑</text></view>
      </view>
    </view>

    <!-- 添加/编辑孩子 -->
    <view v-if="showChildForm" class="overlay" @tap="closeChildForm">
      <view class="settings-panel form-panel" @tap.stop>
        <text class="settings-title">{{ editingChild ? '编辑孩子' : '添加孩子账号' }}</text>
        <view v-if="!editingChild" class="input-wrap">
          <input class="form-input" v-model="childForm.loginName" placeholder="登录账号（英文/数字，唯一）" />
        </view>
        <view class="input-wrap">
          <input class="form-input" v-model="childForm.nickname" placeholder="孩子姓名/昵称" />
        </view>
        <view class="input-wrap">
          <input class="form-input" v-model="childForm.password" :placeholder="editingChild ? '新密码（留空不改，8-32位含大小写+数字）' : '登录密码（8-32位，含大小写+数字）'" type="password" />
        </view>
        <view class="input-wrap">
          <input class="form-input" v-model="childForm.confirm" :placeholder="editingChild ? '确认新密码' : '确认密码'" type="password" />
        </view>
        <view class="input-wrap">
          <picker class="form-picker" :range="ageOptions" :value="ageIndex" @change="onAgeChange">
            <view class="form-picker-display" :class="{ placeholder: !childForm.age }">
              {{ childForm.age ? childForm.age + ' 岁' : '请选择年龄' }}
            </view>
          </picker>
        </view>
        <view class="input-wrap">
          <picker class="form-picker" :range="gradeOptions" :value="gradeIndex" @change="onGradeChange">
            <view class="form-picker-display" :class="{ placeholder: !childForm.grade }">
              {{ childForm.grade || '请选择年级' }}
            </view>
          </picker>
        </view>
        <!-- region 后端已建字段，前端暂不使用：profile_json.learner.region -->
        <view class="btn-save" @click="saveChild">
          <text>{{ saving ? '保存中...' : '保存' }}</text>
        </view>
        <view v-if="editingChild" class="form-hint">
          <text>如需注销或转移账号，请联系管理员</text>
        </view>
        <view class="settings-close" @tap="closeChildForm"><text>取消</text></view>
      </view>
    </view>

    <view v-if="showSettings" class="overlay" @tap="showSettings = false">
      <view class="settings-panel" @tap.stop>
        <text class="settings-title">设置</text>
        <view class="settings-item settings-item-normal" @tap="openProfileForm">
          <text class="settings-label-normal">我的资料</text>
        </view>
        <view class="settings-item" @tap="doLogout">
          <text class="settings-label">退出登录</text>
        </view>
        <view class="settings-close" @tap="showSettings = false"><text>关闭</text></view>
      </view>
    </view>

    <view v-if="showProfileForm" class="overlay" @tap="closeProfileForm">
      <view class="settings-panel form-panel" @tap.stop>
        <text class="settings-title">我的资料</text>
        <view class="input-wrap readonly">
          <text class="form-label">手机号</text>
          <text class="form-readonly">{{ profileForm.phone || '—' }}</text>
        </view>
        <view class="input-wrap">
          <input class="form-input" v-model="profileForm.realName" placeholder="真实姓名" />
        </view>
        <view class="input-wrap">
          <input class="form-input" v-model="profileForm.nickname" placeholder="昵称" />
        </view>
        <view v-if="profileHasPassword" class="input-wrap">
          <input class="form-input" v-model="profileForm.oldPassword" placeholder="原密码（改密必填）" type="password" />
        </view>
        <view class="input-wrap">
          <input class="form-input" v-model="profileForm.password" placeholder="新密码（留空不改）" type="password" />
        </view>
        <view class="input-wrap">
          <input class="form-input" v-model="profileForm.confirm" placeholder="确认新密码" type="password" />
        </view>
        <view class="btn-save" @click="saveProfile">
          <text>{{ savingProfile ? '保存中...' : '保存' }}</text>
        </view>
        <view class="settings-close" @tap="closeProfileForm"><text>取消</text></view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  requirePageAuth,
  logoutAndGoLogin,
  fetchParentChildren,
  fetchParentQuota,
  fetchParentProfile,
  updateParentProfile,
  createParentChild,
  updateParentChild,
  ensureParentAccountReady,
  invalidatePageAuthCache,
} from '@/utils/userApi.js'
import { prepareRoleLoginEntry } from '@/utils/appSession.js'
import { validatePasswordClient } from '@/utils/passwordPolicy.js'

const showSettings = ref(false)
const showProfileForm = ref(false)
const showChildForm = ref(false)
const parentName = ref('家长')
const parentId = ref(null)
const children = ref([])
const quota = ref({ limit: 5, used: 0, can_add: true })
const loading = ref(true)
const saving = ref(false)
const savingProfile = ref(false)
const isLight = ref(false)
const editingChild = ref(null)
const childForm = ref({ loginName: '', nickname: '', password: '', confirm: '', age: null, grade: '' })
const profileForm = ref({ phone: '', realName: '', nickname: '', oldPassword: '', password: '', confirm: '' })
const profileHasPassword = ref(false)

const ageOptions = Array.from({ length: 118 }, (_, i) => i + 3)  // 3 ~ 120，与后端校验一致
const ageIndex = computed(() => {
  const idx = ageOptions.indexOf(childForm.value.age)
  return idx >= 0 ? idx : 0
})
function onAgeChange(e) {
  childForm.value.age = ageOptions[e.detail.value] || null
}

const gradeOptions = ['一年级','二年级','三年级','四年级','五年级','六年级','初一','初二','初三','高一','高二','高三']
const gradeIndex = computed(() => {
  const idx = gradeOptions.indexOf(childForm.value.grade)
  return idx >= 0 ? idx : 0
})
function onGradeChange(e) {
  childForm.value.grade = gradeOptions[e.detail.value] || ''
}

onMounted(() => loadData())

async function loadData() {
  loading.value = true
  try {
    const auth = await requirePageAuth('parent')
    if (!auth.ok) return

    const raw = localStorage.getItem('jnao_user')
    if (raw) {
      const u = JSON.parse(raw)
      if (u.role !== 'parent') {
        logoutAndGoLogin()
        return
      }
      parentName.value = u.name || '家长'
      parentId.value = u.id || auth.userId
    } else {
      parentId.value = auth.userId
    }
    if (!parentId.value) {
      logoutAndGoLogin()
      return
    }
    const ready = await ensureParentAccountReady(parentId.value)
    if (!ready) return
    const [list, q] = await Promise.all([
      fetchParentChildren(parentId.value),
      fetchParentQuota(parentId.value),
    ])
    children.value = list
    quota.value = q
  } catch (_) {
    uni.showToast({ title: '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
  try {
    isLight.value = localStorage.getItem('jnao_theme') === 'white'
  } catch (_) {}
}

async function openAddChild() {
  if (!parentId.value) return
  const ready = await ensureParentAccountReady(parentId.value)
  if (!ready) return
  if (!quota.value.can_add) {
    uni.showToast({ title: '孩子名额已满', icon: 'none' })
    return
  }
  editingChild.value = null
  childForm.value = { loginName: '', nickname: '', password: '', confirm: '', age: null, grade: '' }
  showChildForm.value = true
}

function openEditChild(child) {
  editingChild.value = child
  childForm.value = { loginName: child.login_name || '', nickname: child.nickname || '', password: '', confirm: '', age: child.age || null, grade: child.grade || '' }
  showChildForm.value = true
}

function closeChildForm() {
  showChildForm.value = false
  editingChild.value = null
}

async function openProfileForm() {
  showSettings.value = false
  if (!parentId.value) return
  try {
    const p = await fetchParentProfile(parentId.value)
    profileForm.value = {
      phone: p.parent_phone || '',
      realName: p.real_name || '',
      nickname: p.nickname || '',
      oldPassword: '',
      password: '',
      confirm: '',
    }
    profileHasPassword.value = !!p.has_password
    showProfileForm.value = true
  } catch (_) {
    uni.showToast({ title: '加载资料失败', icon: 'none' })
  }
}

function closeProfileForm() {
  showProfileForm.value = false
}

async function saveProfile() {
  const realName = profileForm.value.realName.trim()
  const nickname = profileForm.value.nickname.trim()
  const pwd = profileForm.value.password.trim()
  const confirm = profileForm.value.confirm.trim()
  if (!realName) { uni.showToast({ title: '请填写真实姓名', icon: 'none' }); return }
  if (!nickname) { uni.showToast({ title: '请填写昵称', icon: 'none' }); return }
  if (pwd || confirm) {
    if (profileHasPassword.value && !profileForm.value.oldPassword.trim()) {
      uni.showToast({ title: '请输入原密码', icon: 'none' }); return
    }
    if (!pwd) { uni.showToast({ title: '请填写新密码', icon: 'none' }); return }
    const pwdErr = validatePasswordClient(pwd)
    if (pwdErr) { uni.showToast({ title: pwdErr, icon: 'none' }); return }
    if (pwd !== confirm) { uni.showToast({ title: '两次密码不一致', icon: 'none' }); return }
  }
  savingProfile.value = true
  try {
    const body = { real_name: realName, nickname }
    if (pwd) {
      body.password = pwd
      if (profileHasPassword.value) body.old_password = profileForm.value.oldPassword.trim()
    }
    const p = await updateParentProfile(parentId.value, body)
    parentName.value = p.nickname || parentName.value
    try {
      const raw = localStorage.getItem('jnao_user')
      if (raw) {
        const u = JSON.parse(raw)
        u.name = p.nickname
        localStorage.setItem('jnao_user', JSON.stringify(u))
      }
    } catch (_) {}
    closeProfileForm()
    uni.showToast({ title: '资料已更新', icon: 'none' })
  } catch (e) {
    if (e.status === 401) return
    uni.showToast({ title: e.message || '保存失败', icon: 'none' })
  } finally {
    savingProfile.value = false
  }
}

async function saveChild() {
  const nick = childForm.value.nickname.trim()
  const pwd = childForm.value.password.trim()
  const confirm = childForm.value.confirm.trim()
  if (!nick) { uni.showToast({ title: '请输入孩子姓名', icon: 'none' }); return }
  if (pwd || confirm) {
    if (!pwd) { uni.showToast({ title: '请填写密码', icon: 'none' }); return }
    const pwdErr = validatePasswordClient(pwd)
    if (pwdErr) { uni.showToast({ title: pwdErr, icon: 'none' }); return }
    if (pwd !== confirm) { uni.showToast({ title: '两次密码不一致', icon: 'none' }); return }
  }
  saving.value = true
  try {
    if (editingChild.value) {
      const body = { nickname: nick }
      if (childForm.value.grade) body.grade = childForm.value.grade
      if (childForm.value.age != null && childForm.value.age !== '') body.age = childForm.value.age
      if (pwd) body.password = pwd
      await updateParentChild(parentId.value, editingChild.value.id, body)
    } else {
      const loginName = childForm.value.loginName.trim()
      if (!loginName || loginName.length < 2) { uni.showToast({ title: '账号至少2位', icon: 'none' }); saving.value = false; return }
      if (!pwd) { uni.showToast({ title: '请设置登录密码', icon: 'none' }); saving.value = false; return }
      await createParentChild(parentId.value, {
        loginName, nickname: nick, password: pwd,
        grade: childForm.value.grade || null,
        age: childForm.value.age || null,
      })
    }
    closeChildForm()
    await loadData()
    uni.showToast({ title: '已保存', icon: 'none' })
  } catch (e) {
    if (e.status === 401) return
    if (e.status === 403) {
      uni.showToast({ title: e.message || '请先完善家长资料', icon: 'none' })
      return
    }
    if (e.status === 409) uni.showToast({ title: '账号已被使用', icon: 'none' })
    else uni.showToast({ title: e.message || '保存失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}

function toggleTheme() {
  isLight.value = !isLight.value
  try { localStorage.setItem('jnao_theme', isLight.value ? 'white' : 'dark') } catch (_) {}
  const html = document.documentElement
  if (isLight.value) html.setAttribute('data-theme', 'white')
  else html.removeAttribute('data-theme')
}

function doLogout() {
  showSettings.value = false
  logoutAndGoLogin()
}

function goToStudentLogin() {
  prepareRoleLoginEntry('student')
  invalidatePageAuthCache()
  uni.redirectTo({ url: '/pages/login/index?role=student' })
}
</script>

<style scoped>
.app { min-height: 100vh; min-height: 100dvh; height: 100dvh; max-width: var(--app-max-width, 480px); margin: 0 auto; background: var(--bg); font-family: -apple-system, "PingFang SC", sans-serif; display: flex; flex-direction: column; padding: 0 0 40px; }
.nav-bar { display:flex; align-items:center; padding:14px 14px 10px; }
.nav-back { width:34px; height:34px; border-radius:50%; background:var(--bg-card); border:1px solid var(--border); display:flex; align-items:center; justify-content:center; cursor:pointer; flex-shrink:0; }
.nav-center { flex:1; text-align:center; color:var(--text); font-size:16px; font-weight:600; }
.nav-actions { display:flex; gap:8px; }
.nav-icon-btn { width:34px; height:34px; border-radius:50%; background:var(--bg-card); border:1px solid var(--border); display:flex; align-items:center; justify-content:center; cursor:pointer; }
.hero { text-align:center; padding:24px 20px 20px; }
.hero-avatar { width:64px; height:64px; border-radius:50%; background:linear-gradient(135deg,var(--accent),#7c3aed); display:flex; align-items:center; justify-content:center; margin:0 auto 10px; color:#fff; font-size:28px; font-weight:700; }
.hero-name { color:var(--text); font-size:20px; font-weight:700; display:block; }
.hero-sub { color:var(--text-dim); font-size:13px; margin-top:4px; display:block; }
.children-section { padding:0 16px; }
.section-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
.section-title { color:var(--text); font-size:15px; font-weight:700; }
.btn-add { background:rgba(139,92,246,0.15); border:1px solid rgba(139,92,246,0.35); border-radius:10px; padding:6px 12px; cursor:pointer; }
.btn-add text { color:#a78bfa; font-size:12px; font-weight:600; }
.btn-add.disabled { opacity:0.4; pointer-events:none; }
.child-card { display:flex; align-items:center; background:var(--bg-card); border-radius:14px; padding:14px; margin-bottom:10px; border:1px solid var(--border); cursor:pointer; }
.child-avatar { width:44px; height:44px; border-radius:50%; background:var(--accent-bg); display:flex; align-items:center; justify-content:center; margin-right:12px; flex-shrink:0; color:var(--accent); font-size:18px; font-weight:700; }
.child-info { flex:1; min-width:0; }
.child-name { color:var(--text); font-size:15px; font-weight:600; display:block; }
.child-detail { color:var(--text-dim); font-size:11px; margin-top:2px; display:block; }
.child-arrow text { color:var(--text-dim); font-size:12px; }
.empty-state { text-align:center; padding:40px 20px; }
.empty-icon { font-size:40px; display:block; margin-bottom:10px; }
.empty-text { color:var(--text); font-size:15px; font-weight:600; display:block; }
.empty-hint { color:var(--text-dim); font-size:12px; margin-top:6px; display:block; }
.overlay { position:fixed; inset:0; z-index:500; background:rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center; padding:40px; }
.settings-panel { width:100%; max-width:300px; background:var(--bg-card); border-radius:16px; padding:24px 20px 20px; }
.form-panel { max-width:340px; }
.settings-title { color:var(--text); font-size:17px; font-weight:700; text-align:center; display:block; margin-bottom:16px; }
.input-wrap { background:var(--bg); border:1px solid var(--border); border-radius:12px; padding:0 12px; margin-bottom:10px; }
.form-input { width:100%; padding:12px 0; font-size:14px; color:var(--text); border:none; background:transparent; }
.form-picker { width:100%; padding:12px 0; }
.form-picker-display { font-size:14px; color:var(--text); }
.form-picker-display.placeholder { color:var(--text-dim); }
.btn-save { background:linear-gradient(135deg,#8b5cf6,#7c3aed); border-radius:12px; padding:13px; text-align:center; margin-top:8px; cursor:pointer; }
.btn-save text { color:#fff; font-weight:600; }
.form-hint { margin-top:12px; text-align:center; }
.form-hint text { color:var(--text-dim); font-size:12px; }
.settings-item { padding:14px; border-radius:12px; background:rgba(220,38,38,0.08); text-align:center; cursor:pointer; margin-bottom:12px; }
.settings-item-normal { background:rgba(88,166,255,0.1); border:1px solid rgba(88,166,255,0.25); }
.settings-label { color:#dc2626; font-size:15px; font-weight:500; }
.settings-label-normal { color:var(--accent); font-size:15px; font-weight:500; }
.input-wrap.readonly { display:flex; align-items:center; justify-content:space-between; padding:12px; }
.form-label { color:var(--text-dim); font-size:13px; }
.form-readonly { color:var(--text); font-size:14px; }
.settings-close { text-align:center; padding:10px; cursor:pointer; }
.settings-close text { color:var(--text-dim); font-size:13px; }
</style>
