<template>
  <view class="app">
    <view class="top-bar">
      <view class="back-btn" @click="goBack">
        <text>← 返回登录</text>
      </view>
    </view>
    <view class="card">
      <text class="title">绑定手机号</text>
      <text class="hint">验证手机号后即可继续设置密码</text>

      <view class="field">
        <view class="input-wrap">
          <input v-model="phone" class="inp" placeholder="手机号" type="number" maxlength="11" />
        </view>
      </view>
      <view class="field sms-row">
        <view class="input-wrap flex-1">
          <input v-model="smsCode" class="inp" placeholder="短信验证码" type="number" maxlength="6" />
        </view>
        <view class="sms-btn" :class="{ off: smsCooldown > 0 }" @click="sendSms">
          <text>{{ smsCooldown > 0 ? `${smsCooldown}s` : '获取验证码' }}</text>
        </view>
      </view>

      <view class="btn-primary" @click="submit">
        <text>{{ submitting ? '提交中...' : '确认绑定' }}</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { wechatBindPhone, sendWechatBindSms, logoutAndGoLogin } from '@/utils/userApi.js'

const phone = ref('')
const smsCode = ref('')
const bindTicket = ref('')
const submitting = ref(false)
const smsCooldown = ref(0)
let cooldownTimer = null

function goBack() {
  logoutAndGoLogin()
}

onMounted(() => {
  const pages = getCurrentPages()
  const cur = pages[pages.length - 1]
  bindTicket.value = cur?.options?.bind_ticket || ''
  if (!bindTicket.value) {
    try {
      bindTicket.value = new URLSearchParams(window.location.search).get('bind_ticket') || ''
    } catch (_) {}
  }
  if (!bindTicket.value) {
    uni.showToast({ title: '请从微信重新进入', icon: 'none' })
    setTimeout(() => uni.redirectTo({ url: '/pages/login/index?from=mp' }), 1500)
  }
})

onUnmounted(() => {
  if (cooldownTimer) clearInterval(cooldownTimer)
})

function startCooldown(sec = 60) {
  smsCooldown.value = sec
  if (cooldownTimer) clearInterval(cooldownTimer)
  cooldownTimer = setInterval(() => {
    smsCooldown.value -= 1
    if (smsCooldown.value <= 0) {
      clearInterval(cooldownTimer)
      cooldownTimer = null
    }
  }, 1000)
}

async function sendSms() {
  if (smsCooldown.value > 0) return
  if (!phone.value.trim()) {
    uni.showToast({ title: '请输入手机号', icon: 'none' })
    return
  }
  try {
    await sendWechatBindSms({ bindTicket: bindTicket.value, phone: phone.value.trim() })
    startCooldown()
    uni.showToast({ title: '验证码已发送', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '发送失败', icon: 'none' })
  }
}

async function submit() {
  if (!phone.value.trim() || !smsCode.value.trim()) {
    uni.showToast({ title: '请填写手机号和验证码', icon: 'none' })
    return
  }
  submitting.value = true
  try {
    const data = await wechatBindPhone({
      bindTicket: bindTicket.value,
      phone: phone.value.trim(),
      smsCode: smsCode.value.trim(),
    })
    if (data.next_step === 'complete-profile' || !data.account_ready) {
      uni.redirectTo({ url: '/pages/login/complete-parent?from=wechat' })
    } else {
      uni.redirectTo({ url: '/pages/parent/index' })
    }
  } catch (e) {
    uni.showToast({ title: e.message || '绑定失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.app { min-height:100vh; min-height:100dvh; background:var(--bg); max-width:480px; margin:0 auto; padding:16px 20px 40px; }
.top-bar { margin-bottom:12px; }
.back-btn { display:inline-block; padding:8px 4px; }
.back-btn text { color:var(--accent); font-size:14px; }
.card { background:var(--bg-card); border:1px solid var(--border); border-radius:16px; padding:24px; position:relative; z-index:1; }
.title { display:block; font-size:20px; font-weight:700; color:var(--text); text-align:center; }
.hint { display:block; text-align:center; color:var(--text-dim); font-size:13px; margin:8px 0 24px; }
.field { margin-bottom:14px; }
.input-wrap {
  display:flex; align-items:center;
  background:var(--bg); border:1px solid var(--border);
  border-radius:10px; padding:0 12px;
  position:relative; z-index:2;
}
.flex-1 { flex:1; }
.inp {
  flex:1; width:100%; min-height:48px;
  padding:12px 0; font-size:16px; line-height:1.4;
  color:var(--text); background:transparent; border:none;
  box-sizing:border-box; -webkit-user-select:text; user-select:text;
}
.sms-row { display:flex; gap:8px; align-items:center; }
.sms-btn { flex-shrink:0; padding:10px 12px; background:rgba(88,166,255,0.15); border-radius:10px; }
.sms-btn.off { opacity:0.5; }
.sms-btn text { color:var(--accent); font-size:12px; }
.btn-primary { margin-top:20px; background:linear-gradient(135deg, #58a6ff, #7c3aed); border-radius:12px; padding:14px; text-align:center; }
.btn-primary text { color:#fff; font-weight:600; }
</style>
