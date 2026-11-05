<template>
  <view class="app">
    <view class="card">
      <view class="logo-row">
        <text class="logo-j">J</text><text class="logo-nao">nao</text><text class="logo-ai">AI</text>
      </view>
      <text class="subtitle">{{ fromWechat ? '微信登录 · 验证码注册' : '注册家长账户' }}</text>

      <view class="form">
        <view class="input-wrap"><input v-model="form.realName" class="inp" placeholder="真实姓名（必填）" :disabled="loginBusy" /></view>
        <view class="input-wrap"><input v-model="form.nickname" class="inp" placeholder="昵称（必填）" :disabled="loginBusy" /></view>
        <view class="input-wrap">
          <input
            v-model="form.phone"
            class="inp"
            placeholder="手机号"
            type="number"
            maxlength="11"
            :disabled="loginBusy"
          />
        </view>
        <view class="input-wrap sms-row">
          <input v-model="form.smsCode" class="inp" placeholder="短信验证码" type="number" maxlength="6" :disabled="loginBusy" />
          <view class="sms-btn" :class="{ off: smsCooldown > 0 || loginBusy }" @click="openCaptchaModal">
            <text>{{ smsCooldown > 0 ? `${smsCooldown}s` : '获取验证码' }}</text>
          </view>
        </view>
        <view class="input-wrap"><input v-model="form.password" class="inp" placeholder="登录密码（8-32位，含大小写+数字）" type="password" :disabled="loginBusy" /></view>
        <view class="input-wrap"><input v-model="form.confirm" class="inp" placeholder="确认密码" type="password" :disabled="loginBusy" /></view>

        <view class="agree"><text>注册即代表您同意《用户协议》和《隐私政策》</text></view>

        <view class="btn-primary" :class="{ off: loginBusy }" @click="doRegister">
          <text>{{ loginBusy ? '注册中...' : '注册并登录' }}</text>
        </view>
        <view class="btn-back" @click="goBack"><text>← 返回登录</text></view>
      </view>
    </view>

    <view v-if="showCaptcha" class="overlay" @click="showCaptcha = false">
      <view class="captcha-panel" @click.stop>
        <text class="captcha-title">安全验证</text>
        <image v-if="captchaImage" class="captcha-img" :src="captchaImage" mode="aspectFit" @click="loadCaptcha" />
        <view class="input-wrap"><input v-model="captchaCode" class="inp" placeholder="图形验证码" maxlength="6" /></view>
        <view class="captcha-actions">
          <view class="btn-ghost" @click="loadCaptcha"><text>换一张</text></view>
          <view class="btn-confirm" @click="confirmSendSms"><text>{{ sendingSms ? '发送中...' : '确认发送' }}</text></view>
        </view>
      </view>
    </view>

    <view v-if="loginBusy" class="login-overlay">
      <view class="login-spinner"></view>
      <text class="login-overlay-text">{{ overlayText || '请稍候…' }}</text>
    </view>
  </view>
</template>

<script setup>
import { ref, onUnmounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import {
  registerParentSms,
  fetchCaptcha,
  sendParentSmsCode,
  saveAuthSession,
  parentNeedsProfileComplete,
  parentNeedsAccountReady,
  resolveParentAuthTarget,
} from '@/utils/userApi.js'
import { clearLoginGuard } from '@/utils/loginGuard.js'
import { useLoginFlow, hasValidSession, inferHomeFromSession } from '@/utils/useLoginFlow.js'
import { validatePasswordClient } from '@/utils/passwordPolicy.js'
import { validateRealNameClient, validateNicknameClient } from '@/utils/namePolicy.js'

const { overlayText, loginBusy, resetPhase, runAuthenticating, completeAfterAuth } = useLoginFlow()

const form = ref({ realName: '', nickname: '', phone: '', smsCode: '', password: '', confirm: '' })
const showCaptcha = ref(false)
const captchaId = ref('')
const captchaCode = ref('')
const captchaImage = ref('')
const sendingSms = ref(false)
const smsCooldown = ref(0)
const fromWechat = ref(false)
const bindTicket = ref('')
let cooldownTimer = null

onLoad((opts) => {
  if (opts?.phone) form.value.phone = String(opts.phone)
  if (opts?.from === 'wechat') fromWechat.value = true
  if (opts?.bind_ticket) bindTicket.value = String(opts.bind_ticket)
})

async function loadCaptcha() {
  const data = await fetchCaptcha()
  captchaId.value = data.captcha_id
  captchaImage.value = `data:image/${data.image_format || 'png'};base64,${data.image_base64}`
  captchaCode.value = ''
}

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

function validateRegisterFields() {
  const nameErr = validateRealNameClient(form.value.realName.trim())
  if (nameErr) return nameErr
  const nickErr = validateNicknameClient(form.value.nickname.trim())
  if (nickErr) return nickErr
  if (!form.value.phone.trim() || form.value.phone.trim().length < 11) {
    return '请输入正确的手机号'
  }
  return null
}

async function openCaptchaModal() {
  if (smsCooldown.value > 0 || loginBusy.value) return
  const err = validateRegisterFields()
  if (err) { uni.showToast({ title: err, icon: 'none' }); return }
  await loadCaptcha()
  showCaptcha.value = true
}

function goLogin(phone = '') {
  const q = phone ? `?phone=${encodeURIComponent(phone)}` : ''
  uni.redirectTo({ url: `/pages/login/index${q}` })
}

async function confirmSendSms() {
  if (!captchaCode.value.trim()) {
    uni.showToast({ title: '请输入图形验证码', icon: 'none' }); return
  }
  sendingSms.value = true
  try {
    const phone = form.value.phone.trim()
    const res = await sendParentSmsCode(phone, 'register', {
      captchaId: captchaId.value,
      captchaCode: captchaCode.value.trim(),
    })
    showCaptcha.value = false
    if (res.sent !== true) {
      if (res.hint === 'already_registered') {
        uni.showToast({ title: '该手机号已注册，请直接登录', icon: 'none' })
        setTimeout(() => goLogin(phone), 800)
      } else {
        uni.showToast({ title: res.message || '发送失败', icon: 'none' })
      }
      return
    }
    startCooldown(60)
    uni.showToast({ title: '验证码已发送', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '发送失败', icon: 'none' })
    await loadCaptcha()
  } finally {
    sendingSms.value = false
  }
}

function resolveParentTarget(data) {
  const target = resolveParentAuthTarget(data)
  if (target === '__bind_phone__') {
    return '/pages/login/register-parent'
  }
  return target
}

async function routeAfterRegister(data) {
  clearLoginGuard()
  saveAuthSession(data)
  uni.showToast({ title: '注册成功！', icon: 'none' })
  uni.redirectTo({ url: resolveParentTarget(data) })
}

async function doRegister() {
  if (loginBusy.value) return
  const fieldErr = validateRegisterFields()
  if (fieldErr) { uni.showToast({ title: fieldErr, icon: 'none' }); return }
  if (!form.value.smsCode.trim()) { uni.showToast({ title: '请输入短信验证码', icon: 'none' }); return }
  if (!form.value.password.trim()) { uni.showToast({ title: '请设置登录密码', icon: 'none' }); return }
  const pwdErr = validatePasswordClient(form.value.password.trim())
  if (pwdErr) { uni.showToast({ title: pwdErr, icon: 'none' }); return }
  if (form.value.password.trim() !== form.value.confirm.trim()) {
    uni.showToast({ title: '两次密码不一致', icon: 'none' }); return
  }

  try {
    const result = await runAuthenticating(async () => {
      const data = await registerParentSms({
        phone: form.value.phone.trim(),
        smsCode: form.value.smsCode.trim(),
        realName: form.value.realName.trim(),
        nickname: form.value.nickname.trim(),
        password: form.value.password.trim(),
        bindTicket: bindTicket.value || undefined,
      })
      await completeAfterAuth(() => routeAfterRegister(data), { busyText: '正在进入…' })
      return data
    }, { busyText: '正在注册…' })
    if (result?._sessionFallback) {
      await completeAfterAuth(() => uni.reLaunch({ url: inferHomeFromSession() }))
    }
  } catch (e) {
    resetPhase()
    if (hasValidSession()) {
      uni.reLaunch({ url: inferHomeFromSession() })
      return
    }
    if (e.status === 409) {
      uni.showToast({ title: e.message || '该手机号已注册，请登录', icon: 'none' })
      setTimeout(() => goLogin(form.value.phone.trim()), 800)
    } else {
      uni.showToast({ title: e.message || '注册失败', icon: 'none' })
    }
  }
}

function goBack() {
  uni.navigateBack({ fail: () => uni.redirectTo({ url: '/pages/login/index' }) })
}

onUnmounted(() => {
  if (cooldownTimer) clearInterval(cooldownTimer)
})
</script>

<style scoped>
.app { min-height:100vh; background:var(--bg); max-width:480px; margin:0 auto; padding:40px 20px; position:relative; }
.card { background:var(--bg-card); border:1px solid var(--border); border-radius:16px; padding:24px 20px; }
.logo-row { display:flex; justify-content:center; gap:4px; margin-bottom:8px; }
.logo-j { color:#dc2626; font-size:40px; font-weight:800; }
.logo-nao, .logo-ai { font-size:30px; font-weight:700; color:var(--text); }
.subtitle { display:block; text-align:center; font-size:16px; font-weight:600; color:var(--text); margin-bottom:20px; }
.input-wrap { border:1px solid var(--border); border-radius:10px; padding:0 12px; margin-bottom:10px; }
.sms-row { display:flex; align-items:center; padding-right:4px; }
.inp { width:100%; padding:12px 0; font-size:15px; color:var(--text); }
.sms-btn { flex-shrink:0; padding:8px 10px; border-radius:8px; background:rgba(88,166,255,0.15); }
.sms-btn.off { opacity:0.5; }
.sms-btn text { color:var(--accent); font-size:12px; }
.agree { margin:8px 0 16px; }
.agree text { font-size:11px; color:var(--text-dim); }
.btn-primary { background:linear-gradient(135deg, #58a6ff, #7c3aed); border-radius:12px; padding:14px; text-align:center; }
.btn-primary.off { opacity:0.55; }
.btn-primary text { color:#fff; font-weight:600; }
.btn-back { margin-top:14px; text-align:center; }
.btn-back text { color:var(--text-dim); font-size:13px; }
.overlay { position:fixed; inset:0; background:rgba(0,0,0,0.55); display:flex; align-items:center; justify-content:center; padding:24px; z-index:200; }
.captcha-panel { width:100%; max-width:320px; background:var(--bg-card); border-radius:16px; padding:20px; border:1px solid var(--border); }
.captcha-title { display:block; text-align:center; font-weight:700; color:var(--text); margin-bottom:12px; }
.captcha-img { width:100%; height:48px; margin-bottom:10px; border-radius:8px; background:#f3f4f6; }
.captcha-actions { display:flex; gap:10px; margin-top:12px; }
.btn-ghost { flex:1; padding:12px; text-align:center; border-radius:10px; border:1px solid var(--border); }
.btn-ghost text { color:var(--text-dim); }
.btn-confirm { flex:1; padding:12px; text-align:center; border-radius:10px; background:#58a6ff; }
.btn-confirm text { color:#fff; font-weight:600; }
.login-overlay {
  position: fixed; inset: 0; z-index: 9999;
  background: rgba(0,0,0,0.45);
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 14px;
}
.login-spinner {
  width: 36px; height: 36px; border-radius: 50%;
  border: 3px solid rgba(255,255,255,0.25);
  border-top-color: #58a6ff;
  animation: loginSpin 0.8s linear infinite;
}
.login-overlay-text { color: #fff; font-size: 14px; }
@keyframes loginSpin { to { transform: rotate(360deg); } }
</style>
