<template>
  <view class="app">
    <view class="card">
      <text class="title">{{ isWechat ? '设置登录密码' : '完善家长资料' }}</text>
      <text class="hint">{{ isWechat ? '设置密码后可在任意设备使用手机号+密码登录' : '还差一步即可进入家长中心' }}</text>

      <view v-if="missing.includes('real_name')" class="field">
        <text class="label">真实姓名</text>
        <input v-model="form.realName" class="inp" placeholder="请输入真实姓名" />
      </view>
      <view v-if="missing.includes('nickname')" class="field">
        <text class="label">昵称</text>
        <input v-model="form.nickname" class="inp" placeholder="请输入昵称" />
      </view>

      <view v-if="missing.includes('password') || isWechat" class="field">
        <text class="label">{{ isWechat ? '登录密码（必填）' : '登录密码（可选）' }}</text>
        <input v-model="form.password" class="inp" placeholder="至少6位" type="password" />
      </view>
      <view v-if="(missing.includes('password') || isWechat) && isWechat" class="field">
        <input v-model="form.confirm" class="inp" placeholder="确认密码" type="password" />
      </view>

      <view class="btn-primary" @click="submit">
        <text>{{ submitting ? '保存中...' : '进入家长中心' }}</text>
      </view>
      <view v-if="!isWechat" class="skip" @click="skipPassword">
        <text>暂不设置密码</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getChildUserId, fetchParentProfile, updateParentProfile } from '@/utils/userApi.js'

const parentId = ref(null)
const missing = ref([])
const isWechat = ref(false)
const form = ref({ realName: '', nickname: '', password: '', confirm: '' })
const submitting = ref(false)

onMounted(async () => {
  try {
    const params = new URLSearchParams(window.location.search)
    isWechat.value = params.get('from') === 'wechat'
  } catch (_) {}

  parentId.value = getChildUserId()
  if (!parentId.value) {
    uni.redirectTo({ url: '/pages/login/index' })
    return
  }
  try {
    const p = await fetchParentProfile(parentId.value)
    if (p.login_channel === 'wechat') isWechat.value = true
    missing.value = p.missing_fields || []
    form.value.realName = p.real_name || ''
    form.value.nickname = p.nickname || ''
    if (p.account_ready || (p.profile_complete && !isWechat.value)) {
      uni.redirectTo({ url: '/pages/parent/index' })
    }
  } catch (_) {
    uni.redirectTo({ url: '/pages/login/index' })
  }
})

async function submit() {
  const body = { require_password: isWechat.value }
  if (missing.value.includes('real_name') || form.value.realName.trim()) {
    if (!form.value.realName.trim()) {
      uni.showToast({ title: '请填写真实姓名', icon: 'none' }); return
    }
    body.real_name = form.value.realName.trim()
  }
  if (missing.value.includes('nickname') || form.value.nickname.trim()) {
    if (!form.value.nickname.trim()) {
      uni.showToast({ title: '请填写昵称', icon: 'none' }); return
    }
    body.nickname = form.value.nickname.trim()
  }
  if (isWechat.value || form.value.password.trim()) {
    const pwd = form.value.password.trim()
    if (isWechat.value && pwd.length < 6) {
      uni.showToast({ title: '密码至少6位', icon: 'none' }); return
    }
    if (isWechat.value && pwd !== form.value.confirm.trim()) {
      uni.showToast({ title: '两次密码不一致', icon: 'none' }); return
    }
    if (pwd) body.password = pwd
  }
  submitting.value = true
  try {
    const p = await updateParentProfile(parentId.value, body)
    if (isWechat.value && !p.account_ready) {
      missing.value = p.missing_fields || []
      uni.showToast({ title: '请补全必填项', icon: 'none' })
      return
    }
    if (!p.profile_complete && !isWechat.value) {
      missing.value = p.missing_fields
      uni.showToast({ title: '请补全必填项', icon: 'none' })
      return
    }
    uni.redirectTo({ url: '/pages/parent/index' })
  } catch (e) {
    uni.showToast({ title: e.message || '保存失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

function skipPassword() {
  if (isWechat.value) return
  form.value.password = ''
  submit()
}
</script>

<style scoped>
.app { min-height:100vh; background:var(--bg); max-width:480px; margin:0 auto; padding:40px 20px; }
.card { background:var(--bg-card); border:1px solid var(--border); border-radius:16px; padding:24px; }
.title { display:block; font-size:20px; font-weight:700; color:var(--text); text-align:center; }
.hint { display:block; text-align:center; color:var(--text-dim); font-size:13px; margin:8px 0 24px; }
.field { margin-bottom:14px; }
.label { display:block; color:var(--text-dim); font-size:12px; margin-bottom:6px; }
.inp { width:100%; padding:12px; border:1px solid var(--border); border-radius:10px; font-size:15px; color:var(--text); background:var(--bg); box-sizing:border-box; }
.btn-primary { margin-top:20px; background:linear-gradient(135deg, #58a6ff, #7c3aed); border-radius:12px; padding:14px; text-align:center; }
.btn-primary text { color:#fff; font-weight:600; }
.skip { margin-top:14px; text-align:center; }
.skip text { color:var(--text-dim); font-size:13px; }
</style>
