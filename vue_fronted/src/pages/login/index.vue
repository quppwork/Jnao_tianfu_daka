<template>
  <view class="app">
    <view class="glow glow-top"></view>

    <view class="card">
      <view class="logo-row">
        <text class="logo-j">J</text><text class="logo-nao">nao</text><text class="logo-ai">AI</text>
      </view>
      <text class="subtitle">天赋成长平台</text>

      <!-- 微信内：仅家长一键登录，不展示短信/密码表单 -->
      <view v-if="wechatParentOnly" class="wechat-only">
        <view v-if="loginBlocked" class="blocked-hint">
          <text>登录尝试过于频繁，请 {{ blockRemain }} 秒后再试</text>
        </view>
        <view v-if="wechatLoading" class="wechat-loading">
          <text>正在跳转微信登录…</text>
        </view>
        <view
          class="btn-wechat"
          :class="{ off: loginBlocked || wechatLoading }"
          @click="doWechatLogin"
        >
          <text>{{ wechatLoading ? '跳转中…' : '微信家长一键登录' }}</text>
        </view>
        <text class="wechat-hint">已绑定手机号的家长点击后直接进入</text>
        <view class="link-row" @click="openBrowserLogin">
          <text>使用手机号 / 密码登录</text>
        </view>
      </view>

      <!-- 非微信，或微信内主动选择手机号登录 -->
      <view v-else class="form">
        <view v-if="loginBlocked" class="blocked-hint">
          <text>登录尝试过于频繁，请 {{ blockRemain }} 秒后再试</text>
        </view>

        <template v-if="form.role === 'student'">
          <view class="input-wrap">
            <input class="login-input" v-model="form.loginName" placeholder="孩子账号" />
          </view>
          <view class="input-wrap">
            <input class="login-input" v-model="form.password" placeholder="密码" type="password" />
          </view>
        </template>

        <template v-else-if="parentMode === 'sms'">
          <view class="input-wrap">
            <input class="login-input" v-model="form.phone" placeholder="手机号" type="text" maxlength="11" confirm-type="done" />
          </view>
          <view class="input-wrap sms-row">
            <input class="login-input" v-model="form.smsCode" placeholder="短信验证码" type="text" maxlength="6" confirm-type="done" />
            <view class="sms-btn" :class="{ off: smsCooldown > 0 || loginBlocked }" @click="requestLoginSms">
              <text>{{ smsCooldown > 0 ? `${smsCooldown}s` : '获取验证码' }}</text>
            </view>
          </view>
        </template>

        <template v-else>
          <view class="input-wrap">
            <input class="login-input" v-model="form.phone" placeholder="手机号" type="text" maxlength="11" confirm-type="done" />
          </view>
          <view class="input-wrap">
            <input class="login-input" v-model="form.password" placeholder="密码" type="password" maxlength="64" confirm-type="done" />
          </view>
        </template>

        <view class="role-row">
          <view class="role-item" :class="{ active: form.role === 'student' }" @click="form.role = 'student'">
            <text class="ri-label">学生</text>
          </view>
          <view class="role-item" :class="{ active: form.role === 'parent' }" @click="form.role = 'parent'">
            <text class="ri-label">家长</text>
          </view>
        </view>

        <view class="btn-login" :class="{ off: loginBlocked }" @click="doLogin">
          <text>{{ submitting ? '登录中...' : '登录' }}</text>
        </view>

        <view v-if="form.role === 'student'" class="sub-actions">
          <text class="hint-text">孩子账号由家长在家长中心分配</text>
          <view class="hint-admin" @click="goAdminLogin"><text>管理员入口</text></view>
        </view>
        <view v-else class="sub-actions">
          <view class="link-row" @click="toggleParentMode">
            <text>{{ parentMode === 'sms' ? '使用密码登录' : '使用验证码登录' }}</text>
          </view>
          <view class="link-row" @click="goRegister"><text>注册家长账户</text></view>
          <view v-if="inWechat" class="link-row" @click="backToWechatLogin">
            <text>返回微信一键登录</text>
          </view>
        </view>
      </view>
    </view>

    <view class="glow glow-bottom"></view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  loginParent,
  loginStudent,
  loginParentSms,
  sendParentSmsCode,
  parentNeedsProfileComplete,
  parentNeedsAccountReady,
  saveAuthSession,
  exchangeWechatLogin,
  fetchParentProfile,
  fetchWechatOAuthUrl,
  fetchWechatConfig,
  studentNeedsOnboarding,
  getLoggedInUserId,
  getSessionToken,
} from '@/utils/userApi.js'
import {
  isLoginBlocked,
  recordLoginFail,
  clearLoginGuard,
} from '@/utils/loginGuard.js'
import {
  readWechatCallbackParams,
  clearWechatQueryFromUrl,
  redirectParentNextStep,
  isWeChatBrowser,
  skipWechatAutoLogin,
  startWechatOAuth,
  readWechatError,
  markWechatOAuthFailed,
  clearWechatOAuthCooldown,
} from '@/utils/wechatAuth.js'

const form = ref({ phone: '', loginName: '', password: '', smsCode: '', role: 'student' })
const parentMode = ref('sms')
const submitting = ref(false)
const wechatLoading = ref(false)
const inWechat = ref(false)
/** 微信内是否展示浏览器短信/密码表单（默认 false，仅一键登录） */
const browserLogin = ref(false)
const smsCooldown = ref(0)
const blockRemain = ref(0)
let cooldownTimer = null
let blockTimer = null

const loginBlocked = computed(() => blockRemain.value > 0)
const wechatParentOnly = computed(() => inWechat.value && !browserLogin.value)

function refreshBlockState() {
  const s = isLoginBlocked()
  blockRemain.value = s.blocked ? s.remainSec : 0
}

function cleanLandingQuery() {
  try {
    const url = new URL(window.location.href)
    const hasWxCb = url.searchParams.get('wx') === '1'
    const hasWxErr = url.searchParams.get('wx_error')
    if (!hasWxCb && !hasWxErr && url.searchParams.get('from') === 'mp') {
      url.searchParams.delete('from')
      window.history.replaceState({}, '', url.pathname + (url.search || ''))
    }
  } catch (_) { /* ignore */ }
}

function openBrowserLogin() {
  skipWechatAutoLogin()
  browserLogin.value = true
  wechatLoading.value = false
  form.value.role = 'parent'
}

function backToWechatLogin() {
  browserLogin.value = false
  form.value.role = 'parent'
}

function tryRedirectIfLoggedIn() {
  try {
    if (localStorage.getItem('jnao_logged_in') !== '1') return false
    const uid = getLoggedInUserId()
    if (!uid || !getSessionToken()) return false
    const raw = localStorage.getItem('jnao_user')
    const role = raw ? JSON.parse(raw).role : null
    if (role === 'parent') {
      uni.reLaunch({ url: '/pages/parent/index' })
      return true
    }
    if (role === 'student') {
      uni.reLaunch({ url: '/pages/index' })
      return true
    }
  } catch (_) { /* ignore */ }
  return false
}

onMounted(async () => {
  refreshBlockState()
  blockTimer = setInterval(refreshBlockState, 1000)
  inWechat.value = isWeChatBrowser()
  cleanLandingQuery()

  if (inWechat.value) {
    form.value.role = 'parent'
    browserLogin.value = false
  } else {
    browserLogin.value = true
  }

  const wxErr = readWechatError()
  if (wxErr) {
    wechatLoading.value = false
    markWechatOAuthFailed()
    clearWechatQueryFromUrl()
    uni.showModal({
      title: '微信登录失败',
      content: wxErr,
      showCancel: false,
    })
  }

  const wxCb = readWechatCallbackParams()
  if (wxCb?.loginTicket) {
    clearWechatQueryFromUrl()
    try {
      await exchangeWechatLogin(wxCb.loginTicket)
      const [profile, cfg] = await Promise.all([
        fetchParentProfile(getLoggedInUserId()),
        fetchWechatConfig().catch(() => ({})),
      ])
      redirectParentNextStep(profile.next_step || wxCb.nextStep, wxCb.bindTicket, cfg?.bind_mobile_url)
    } catch (e) {
      markWechatOAuthFailed()
      uni.showModal({
        title: '微信登录失败',
        content: e.message || '登录凭证已过期，请重新进入',
        showCancel: false,
      })
    }
    return
  }
  if (wxCb?.nextStep === 'bind-phone') {
    clearWechatQueryFromUrl()
    try {
      const cfg = await fetchWechatConfig()
      redirectParentNextStep('bind-phone', wxCb.bindTicket, cfg?.bind_mobile_url)
    } catch (_) {
      redirectParentNextStep('bind-phone', wxCb.bindTicket)
    }
    return
  }

  if (tryRedirectIfLoggedIn()) return
})

async function doWechatLogin() {
  if (wechatLoading.value || submitting.value || loginBlocked.value) return
  clearWechatOAuthCooldown()
  wechatLoading.value = true
  try {
    const ok = await startWechatOAuth(fetchWechatOAuthUrl)
    if (!ok) {
      wechatLoading.value = false
      markWechatOAuthFailed()
      uni.showToast({ title: '微信登录暂不可用', icon: 'none' })
    }
  } catch (e) {
    wechatLoading.value = false
    markWechatOAuthFailed()
    uni.showModal({
      title: '微信登录失败',
      content: e.message || '请稍后重试',
      showCancel: false,
    })
  }
}

function saveSession(data) {
  saveAuthSession(data)
}

function toggleParentMode() {
  parentMode.value = parentMode.value === 'sms' ? 'password' : 'sms'
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

async function requestLoginSms() {
  if (loginBlocked.value || smsCooldown.value > 0) return
  if (!form.value.phone.trim() || form.value.phone.trim().length < 11) {
    uni.showToast({ title: '请输入正确的手机号', icon: 'none' }); return
  }
  try {
    await sendParentSmsCode(form.value.phone.trim(), 'login')
    startCooldown(60)
    uni.showToast({ title: '验证码已发送', icon: 'none' })
  } catch (e) {
    if (e.status === 404) {
      uni.showModal({
        title: '尚未注册',
        content: '该手机号未注册，是否前往注册？',
        success: (r) => { if (r.confirm) goRegister() },
      })
    } else {
      uni.showToast({ title: e.message || '发送失败', icon: 'none' })
    }
    if (e.status === 403 || e.status === 429) recordLoginFail()
    refreshBlockState()
  }
}

async function routeParentHome(data) {
  clearLoginGuard()
  saveSession(data)
  uni.showToast({ title: '欢迎，' + data.nickname + '！', icon: 'none' })
  let target = '/pages/parent/index'
  if (parentNeedsAccountReady(data)) {
    if (data.next_step === 'bind-phone') {
      try {
        const cfg = await fetchWechatConfig()
        if (cfg.use_external_bind_mobile && cfg.bind_mobile_url) {
          window.location.href = cfg.bind_mobile_url
          return
        }
      } catch (_) { /* fallback */ }
      if (data.bind_ticket) {
        target = `/pages/login/bind-phone?bind_ticket=${encodeURIComponent(data.bind_ticket)}`
      } else {
        target = '/pages/login/index'
      }
    } else {
      target = '/pages/login/complete-parent' + (data.login_channel === 'wechat' ? '?from=wechat' : '')
    }
  } else if (parentNeedsProfileComplete(data)) {
    target = '/pages/login/complete-parent'
  }
  setTimeout(() => { uni.redirectTo({ url: target }) }, 500)
}

async function routeStudentHome(data) {
  clearLoginGuard()
  saveSession(data)
  uni.showToast({ title: '欢迎，' + data.nickname + '！', icon: 'none' })
  let target = '/pages/index'
  try {
    if (await studentNeedsOnboarding(data.child_user_id)) target = '/pages/login/onboarding/index'
  } catch (e) {
    console.error('[login] studentNeedsOnboarding 检查失败，默认走引导:', e?.message || e)
    target = '/pages/login/onboarding/index'
  }
  setTimeout(() => { uni.redirectTo({ url: target }) }, 500)
}

function handleLoginError(e) {
  submitting.value = false
  if (e.status === 403) {
    uni.showToast({ title: e.message || '访问受限', icon: 'none', duration: 3000 })
  } else if (e.status === 404) {
    uni.showModal({
      title: '尚未注册',
      content: '该手机号未注册，是否前往注册？',
      success: (r) => { if (r.confirm) goRegister() },
    })
  } else if (e.status === 401) {
    uni.showToast({ title: '账号或密码错误', icon: 'none' })
  } else if (e.status === 429) {
    uni.showToast({ title: e.message || '操作太频繁', icon: 'none' })
  } else {
    uni.showToast({ title: e.message || '登录失败', icon: 'none' })
  }
  if ([400, 401, 403, 404, 429].includes(e.status)) {
    recordLoginFail()
    refreshBlockState()
  }
}

async function doLogin() {
  if (loginBlocked.value) {
    uni.showToast({ title: `请 ${blockRemain.value} 秒后再试`, icon: 'none' }); return
  }
  submitting.value = true
  try {
    if (form.value.role === 'parent') {
      if (parentMode.value === 'sms') {
        if (!form.value.smsCode.trim()) {
          uni.showToast({ title: '请输入短信验证码', icon: 'none' }); submitting.value = false; return
        }
        const data = await loginParentSms({
          phone: form.value.phone.trim(),
          smsCode: form.value.smsCode.trim(),
        })
        await routeParentHome(data)
        return
      }
      if (!form.value.phone.trim() || form.value.phone.trim().length < 11) {
        uni.showToast({ title: '请输入正确的手机号', icon: 'none' }); submitting.value = false; return
      }
      if (!form.value.password.trim() || form.value.password.trim().length < 6) {
        uni.showToast({ title: '密码至少6位', icon: 'none' }); submitting.value = false; return
      }
      const data = await loginParent(form.value.phone.trim(), form.value.password.trim())
      await routeParentHome(data)
      return
    }

    if (!form.value.password.trim() || form.value.password.trim().length < 6) {
      uni.showToast({ title: '密码至少6位', icon: 'none' }); submitting.value = false; return
    }
    if (!form.value.loginName.trim()) {
      uni.showToast({ title: '请输入孩子账号', icon: 'none' }); submitting.value = false; return
    }
    const data = await loginStudent(form.value.loginName.trim(), form.value.password.trim())
    await routeStudentHome(data)
  } catch (e) {
    handleLoginError(e)
  }
}

function goRegister() {
  uni.navigateTo({ url: '/pages/login/register-parent' })
}

function goAdminLogin() {
  uni.navigateTo({ url: '/pages/admin/login' })
}

onUnmounted(() => {
  if (cooldownTimer) clearInterval(cooldownTimer)
  if (blockTimer) clearInterval(blockTimer)
})
</script>

<style scoped>
.app { height:100vh;height:100dvh; max-width:480px; margin:0 auto; background:var(--bg); display:flex; align-items:flex-start; justify-content:center; padding:30px; padding-top:12vh; position:relative; overflow:hidden; }
.glow { position:absolute; width:260px; height:260px; border-radius:50%; pointer-events:none; z-index:0; }
.glow-top { top:-80px; right:-60px; background:radial-gradient(circle, rgba(88,166,255,0.18) 0%, transparent 70%); }
.glow-bottom { bottom:-100px; left:-50px; background:radial-gradient(circle, rgba(139,92,246,0.14) 0%, transparent 70%); }
.card { width:100%; position:relative; z-index:1; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08); border-radius:20px; padding:36px 22px 28px; }
.logo-row { display:flex; align-items:baseline; justify-content:center; gap:6px; margin-bottom:4px; }
.logo-j { color:#dc2626; font-size:48px; font-weight:800; }
.logo-nao, .logo-ai { color:var(--text); font-size:36px; font-weight:700; }
.logo-ai { font-weight:300; }
.subtitle { color:var(--text-dim); font-size:12px; text-align:center; display:block; margin-bottom:20px; }
.blocked-hint { background:rgba(220,38,38,0.12); border-radius:10px; padding:10px; margin-bottom:12px; text-align:center; }
.blocked-hint text { color:#f87171; font-size:12px; }
.wechat-only { padding-top:8px; }
.btn-wechat { background:linear-gradient(135deg, #07c160, #06ad56); border-radius:14px; padding:16px; text-align:center; margin-top:8px; }
.btn-wechat.off { opacity:0.5; }
.btn-wechat text { color:#fff; font-size:17px; font-weight:700; }
.wechat-hint { display:block; text-align:center; color:var(--text-dim); font-size:12px; margin-top:14px; }
.wechat-loading { text-align:center; padding:10px 0 4px; }
.wechat-loading text { color:var(--accent); font-size:13px; }
.input-wrap { display:flex; align-items:center; background:var(--bg-card); border-radius:12px; padding:0 14px; margin-bottom:12px; border:1.5px solid var(--border); position:relative; z-index:2; }
.sms-row { padding-right:4px; }
.sms-btn { flex-shrink:0; padding:8px 10px; border-radius:8px; background:rgba(88,166,255,0.15); }
.sms-btn.off { opacity:0.5; }
.sms-btn text { color:var(--accent); font-size:12px; }
.login-input { flex:1; width:100%; min-height:48px; padding:14px 0; font-size:16px; line-height:1.4; color:var(--text); background:transparent; border:none; box-sizing:border-box; -webkit-user-select:text; user-select:text; }
.role-row { display:flex; gap:10px; margin-bottom:22px; }
.role-item { flex:1; padding:14px; text-align:center; border-radius:12px; border:1.5px solid var(--border); }
.role-item.active { border-color:var(--accent); background:var(--accent-bg); }
.ri-label { color:var(--text-dim); font-size:13px; }
.role-item.active .ri-label { color:var(--accent); font-weight:600; }
.btn-login { background:linear-gradient(135deg, #58a6ff, #7c3aed); border-radius:14px; padding:15px; text-align:center; }
.btn-login.off { opacity:0.5; }
.btn-login text { color:#fff; font-size:16px; font-weight:700; }
.sub-actions { text-align:center; margin-top:12px; }
.hint-text { color:var(--text-dim); font-size:12px; }
.link-row { margin-top:12px; text-align:center; }
.link-row text { color:#a78bfa; font-size:13px; }
.hint-admin { margin-top:8px; }
.hint-admin text { color:var(--text-dim); font-size:11px; text-decoration:underline; }
</style>
