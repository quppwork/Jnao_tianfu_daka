<template>
  <view class="app">
    <view class="card">
      <text class="title">完善家长资料</text>
      <text class="hint">还差一步即可进入家长中心</text>

      <view v-if="missing.includes('real_name')" class="field">
        <text class="label">真实姓名</text>
        <input v-model="form.realName" class="inp" placeholder="请输入真实姓名" />
      </view>
      <view v-if="missing.includes('nickname')" class="field">
        <text class="label">昵称</text>
        <input v-model="form.nickname" class="inp" placeholder="请输入昵称" />
      </view>

      <view class="field optional">
        <text class="label">登录密码（可选）</text>
        <input v-model="form.password" class="inp" placeholder="至少6位，可稍后在设置中修改" type="password" />
      </view>

      <view class="btn-primary" @click="submit">
        <text>{{ submitting ? '保存中...' : '进入家长中心' }}</text>
      </view>
      <view class="skip" @click="skipPassword">
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
const form = ref({ realName: '', nickname: '', password: '' })
const submitting = ref(false)

onMounted(async () => {
  parentId.value = getChildUserId()
  if (!parentId.value) {
    uni.redirectTo({ url: '/pages/login/index' })
    return
  }
  try {
    const p = await fetchParentProfile(parentId.value)
    missing.value = p.missing_fields || []
    form.value.realName = p.real_name || ''
    form.value.nickname = p.nickname || ''
    if (p.profile_complete) {
      uni.redirectTo({ url: '/pages/parent/index' })
    }
  } catch (_) {
    uni.redirectTo({ url: '/pages/login/index' })
  }
})

async function submit() {
  const body = {}
  if (missing.value.includes('real_name')) {
    if (!form.value.realName.trim()) {
      uni.showToast({ title: '请填写真实姓名', icon: 'none' }); return
    }
    body.real_name = form.value.realName.trim()
  }
  if (missing.value.includes('nickname')) {
    if (!form.value.nickname.trim()) {
      uni.showToast({ title: '请填写昵称', icon: 'none' }); return
    }
    body.nickname = form.value.nickname.trim()
  }
  if (form.value.password.trim()) {
    if (form.value.password.trim().length < 6) {
      uni.showToast({ title: '密码至少6位', icon: 'none' }); return
    }
    body.password = form.value.password.trim()
  }
  submitting.value = true
  try {
    const p = await updateParentProfile(parentId.value, body)
    if (!p.profile_complete && (p.missing_fields || []).length) {
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
.field.optional { margin-top:8px; }
.label { display:block; color:var(--text-dim); font-size:12px; margin-bottom:6px; }
.inp { width:100%; padding:12px; border:1px solid var(--border); border-radius:10px; font-size:15px; color:var(--text); background:var(--bg); box-sizing:border-box; }
.btn-primary { margin-top:20px; background:linear-gradient(135deg, #58a6ff, #7c3aed); border-radius:12px; padding:14px; text-align:center; }
.btn-primary text { color:#fff; font-weight:600; }
.skip { margin-top:14px; text-align:center; }
.skip text { color:var(--text-dim); font-size:13px; }
</style>
