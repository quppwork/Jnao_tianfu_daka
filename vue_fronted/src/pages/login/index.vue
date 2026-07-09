<template>
  <view class="app">
    <view class="glow glow-top"></view>

    <view class="card">
      <view class="brand-head">
        <view class="logo-row">
          <text class="logo-j">J</text><text class="logo-nao">nao</text><text class="logo-ai">AI</text>
        </view>
        <text class="subtitle">欢迎来到天赋成长平台</text>
        <text class="sub-desc">天赋测评 · 每日训练 · 成长记录</text>
      </view>

      <!-- 微信内：家长主路径 -->
      <view v-if="wechatParentOnly" class="login-flow">
        <view v-if="loginBlocked" class="blocked-hint">
          <text>登录尝试过于频繁，请 {{ blockRemain }} 秒后再试</text>
        </view>
        <view v-if="wechatLoading" class="wechat-loading">
          <text>正在跳转微信登录…</text>
        </view>
        <view
          class="btn-wechat"
          :class="{ off: loginBlocked || loginBusy }"
          @click="doWechatLogin"
        >
          <text>{{ wechatLoading ? '跳转中…' : '微信一键登录' }}</text>
        </view>

        <view class="btn-phone-login" @click="openBrowserLogin">
          <text>手机号登录</text>
        </view>

        <view class="divider"><text>其他方式</text></view>

        <view class="alt-btns">
          <view class="btn-outline btn-outline-student" @click="openStudentLogin">
            <text class="btn-outline-title">孩子账号登录</text>
            <text class="btn-outline-sub">使用家长分配的训练账号</text>
          </view>
        </view>
      </view>

      <!-- 浏览器 / 已切换为表单登录 -->
      <view v-else class="login-main">
        <view class="form">
        <view v-if="loginBlocked" class="blocked-hint">
          <text>登录尝试过于频繁，请 {{ blockRemain }} 秒后再试</text>
        </view>

        <view class="role-row">
          <view class="role-item" :class="{ active: form.role === 'student' }" @click="form.role = 'student'">
            <text class="ri-label">学生</text>
          </view>
          <view class="role-item" :class="{ active: form.role === 'parent' }" @click="form.role = 'parent'">
            <text class="ri-label">家长</text>
          </view>
        </view>

        <template v-if="form.role === 'student'">
          <view class="input-wrap">
            <input class="login-input" v-model="form.loginName" placeholder="孩子账号" :disabled="loginBusy" />
          </view>
          <view class="input-wrap">
            <input class="login-input" v-model="form.password" placeholder="密码" type="password" :disabled="loginBusy" />
          </view>
        </template>

        <template v-else-if="parentMode === 'sms'">
          <view class="input-wrap">
            <input class="login-input" v-model="form.phone" placeholder="注册手机号（11位，非昵称）" type="text" maxlength="11" confirm-type="done" :disabled="loginBusy" />
          </view>
          <view class="input-wrap sms-row">
            <input class="login-input" v-model="form.smsCode" placeholder="短信验证码" type="text" maxlength="6" confirm-type="done" :disabled="loginBusy" />
            <view class="sms-btn" :class="{ off: smsCooldown > 0 || loginBlocked || loginBusy }" @click="requestLoginSms">
              <text>{{ smsCooldown > 0 ? `${smsCooldown}s` : '获取验证码' }}</text>
            </view>
          </view>
        </template>

        <template v-else>
          <view class="input-wrap">
            <input class="login-input" v-model="form.phone" placeholder="注册手机号（11位，非昵称）" type="text" maxlength="11" confirm-type="done" :disabled="loginBusy" />
          </view>
          <view class="input-wrap">
            <input class="login-input" v-model="form.password" placeholder="密码" type="password" maxlength="64" confirm-type="done" :disabled="loginBusy" />
          </view>
        </template>

        <!-- 家长：切换登录方式 / 返回微信 → 在登录按钮上方，左右对齐输入框 -->
        <view v-if="form.role === 'parent'" class="form-links-above">
          <text class="form-link form-link-left" @click="toggleParentMode">
            {{ parentMode === 'sms' ? '密码登录' : '验证码登录' }}
          </text>
          <text v-if="inWechat" class="form-link form-link-right" @click="backToWechatLogin">返回微信登录</text>
        </view>

        <!-- 学生：家长入口在登录按钮上方 -->
        <view v-if="form.role === 'student'" class="form-links-above">
          <text class="form-link" @click="switchToParent">我是家长，去注册 / 登录</text>
        </view>

        <view class="btn-login" :class="{ off: loginBlocked || loginBusy }" @click="doLogin">
          <text>{{ loginBusy ? '登录中...' : '登录' }}</text>
        </view>

        <view v-if="form.role === 'parent'" class="btn-register" @click="goRegister()">
          <text>新家长注册</text>
        </view>
        </view>

        <view class="page-footer">
          <text class="footer-link" @click="goAdminLogin">管理员后台</text>
          <text class="footer-dot">·</text>
          <text class="footer-link" @click="showLoginHelp">登录帮助</text>
        </view>
      </view>

      <view v-if="wechatParentOnly" class="page-footer">
        <text class="footer-link" @click="goAdminLogin">管理员后台</text>
        <text class="footer-dot">·</text>
        <text class="footer-link" @click="showLoginHelp">登录帮助</text>
      </view>
    </view>

    <view class="glow glow-bottom"></view>

    <view v-if="loginBusy" class="login-overlay">
      <view class="login-spinner"></view>
      <text class="login-overlay-text">{{ overlayText || '请稍候…' }}</text>
    </view>

    <view v-if="showCaptcha" class="overlay" @click="showCaptcha = false">
      <view class="captcha-panel" @click.stop>
        <text class="captcha-title">安全验证</text>
        <image v-if="captchaImage" class="captcha-img" :src="captchaImage" mode="aspectFit" @click="loadCaptcha" />
        <view class="input-wrap"><input v-model="captchaCode" class="login-input" placeholder="图形验证码" maxlength="6" /></view>
        <view class="captcha-actions">
          <view class="sms-btn" @click="loadCaptcha"><text>换一张</text></view>
          <view class="btn-login captcha-confirm" @click="confirmLoginSms"><text>{{ sendingSms ? '发送中…' : '发送验证码' }}</text></view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  loginParent,
  loginStudent,
  loginParentSms,
  sendParentSmsCode,
  fetchCaptcha,
  parentNeedsProfileComplete,
  parentNeedsAccountReady,
  saveAuthSession,
  exchangeWechatLogin,
  completeWechatExternalBind,
  fetchParentProfile,
  fetchWechatOAuthUrl,
  fetchWechatConfig,
  studentNeedsOnboarding,
  getLoggedInUserId,
  getSessionToken,
  resetLocalAuthCache,
} from '@/utils/userApi.js'
import {
  isLoginBlocked,
  recordLoginFail,
  clearLoginGuard,
} from '@/utils/loginGuard.js'
import {
  readWechatCallbackParams,
  readExternalBindReturn,
  clearWechatQueryFromUrl,
  redirectParentNextStep,
  isWeChatBrowser,
  skipWechatAutoLogin,
  startWechatOAuth,
  readWechatError,
  markWechatOAuthFailed,
  clearWechatOAuthCooldown,
} from '@/utils/wechatAuth.js'
import {
  useLoginFlow,
  hasValidSession,
  inferHomeFromSession,
  minDelay,
} from '@/utils/useLoginFlow.js'
import { consumePostLoginRoute, sanitizeAuthForLoginEntry } from '@/utils/appSession.js'

const { overlayText, loginBusy, setPhase, resetPhase, runAuthenticating, completeAfterAuth } = useLoginFlow()

const form = ref({ phone: '', loginName: '', password: '', smsCode: '', role: 'student' })
const parentMode = ref('sms')
const wechatLoading = ref(false)
const inWechat = ref(false)
const browserLogin = ref(false)
const smsCooldown = ref(0)
const blockRemain = ref(0)
const showCaptcha = ref(false)
const captchaId = ref('')
const captchaCode = ref('')
const captchaImage = ref('')
const sendingSms = ref(false)
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
    const hasExtBind = url.searchParams.get('from') === 'mp' && url.searchParams.get('bind_ticket')
    if (!hasWxCb && !hasWxErr && url.searchParams.get('from') === 'mp' && !hasExtBind) {
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
  parentMode.value = 'password'
}

function openStudentLogin() {
  skipWechatAutoLogin()
  browserLogin.value = true
  wechatLoading.value = false
  form.value.role = 'student'
}

function switchToParent() {
  form.value.role = 'parent'
  parentMode.value = 'sms'
}

function backToWechatLogin() {
  browserLogin.value = false
  form.value.role = 'parent'
}

function tryRedirectIfLoggedIn() {
  try {
    // 管理员 session 与用户登录页隔离，不在此自动跳转
    const adminRaw = localStorage.getItem('jnao_admin_user')
    const adminTok = localStorage.getItem('jnao_admin_token')
    if (adminRaw && adminTok && localStorage.getItem('jnao_logged_in') !== '1') {
      return false
    }
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

async function handleWechatCallback(wxCb) {
  clearWechatQueryFromUrl()
  setPhase('authenticating', '正在登录…')
  try {
    await exchangeWechatLogin(wxCb.loginTicket)
  } catch (e) {
    markWechatOAuthFailed()
    resetPhase()
    uni.showModal({
      title: '微信登录失败',
      content: e.message || '登录凭证已过期，请重新进入',
      showCancel: false,
    })
    return
  }
  setPhase('settling', '正在进入…')
  try {
    const [profile, cfg] = await Promise.all([
      fetchParentProfile(getLoggedInUserId()),
      fetchWechatConfig().catch(() => ({})),
    ])
    await minDelay(400)
    redirectParentNextStep(profile.next_step || wxCb.nextStep, wxCb.bindTicket, cfg?.bind_mobile_url)
  } catch (e) {
    console.warn('[login] wechat post-auth fallback', e?.message || e)
    await minDelay(400)
    redirectParentNextStep(wxCb.nextStep || 'home', wxCb.bindTicket)
  }
}

onMounted(async () => {
  sanitizeAuthForLoginEntry('/pages/login/index')
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
    await handleWechatCallback(wxCb)
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

  const extBind = readExternalBindReturn()
  if (extBind?.bindTicket) {
    setPhase('authenticating', '正在完成绑手机…')
    try {
      const data = await completeWechatExternalBind(extBind.bindTicket)
      clearWechatQueryFromUrl()
      await routeParentHome(data)
    } catch (e) {
      resetPhase()
      clearWechatQueryFromUrl()
      uni.showModal({
        title: '绑手机未完成',
        content: e.message || '请先在绑手机页完成操作后再返回',
        showCancel: false,
      })
    }
    return
  }

  if (tryRedirectIfLoggedIn()) return
})

async function doWechatLogin() {
  if (wechatLoading.value || loginBusy.value || loginBlocked.value) return
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

async function loadCaptcha() {
  const data = await fetchCaptcha()
  captchaId.value = data.captcha_id
  captchaImage.value = `data:image/svg+xml;base64,${data.image_base64}`
  captchaCode.value = ''
}

async function requestLoginSms() {
  if (loginBlocked.value || smsCooldown.value > 0 || loginBusy.value) return
  if (!form.value.phone.trim() || form.value.phone.trim().length < 11) {
    uni.showToast({ title: '请输入正确的手机号', icon: 'none' }); return
  }
  try {
    await loadCaptcha()
    showCaptcha.value = true
  } catch (e) {
    uni.showToast({ title: e.message || '验证码加载失败', icon: 'none' })
  }
}

async function confirmLoginSms() {
  if (!captchaCode.value.trim()) {
    uni.showToast({ title: '请输入图形验证码', icon: 'none' }); return
  }
  sendingSms.value = true
  try {
    await sendParentSmsCode(form.value.phone.trim(), 'login', {
      captchaId: captchaId.value,
      captchaCode: captchaCode.value.trim(),
    })
    showCaptcha.value = false
    startCooldown(60)
    uni.showToast({ title: '验证码已发送', icon: 'none' })
  } catch (e) {
    if (e.status === 404) {
      const msg = e.message || ''
      showCaptcha.value = false
      if (msg.includes('老系统') || msg.includes('微信')) {
        uni.showModal({
          title: '请使用微信登录',
          content: msg,
          showCancel: false,
        })
      } else {
        uni.showModal({
          title: '尚未注册',
          content: '该手机号未注册，是否前往注册？',
          success: (r) => { if (r.confirm) goRegister(form.value.phone.trim()) },
        })
      }
    } else {
      uni.showToast({ title: e.message || '发送失败', icon: 'none' })
      await loadCaptcha()
    }
    if (e.status === 403 || e.status === 429) recordLoginFail()
    refreshBlockState()
  } finally {
    sendingSms.value = false
  }
}

function resolveParentTarget(data) {
  let target = '/pages/parent/index'
  if (parentNeedsAccountReady(data)) {
    if (data.next_step === 'bind-phone') {
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
  return target
}

async function routeParentHome(data) {
  clearLoginGuard()
  saveAuthSession(data)
  uni.showToast({ title: '欢迎，' + data.nickname + '！', icon: 'none' })
  let target = resolveParentTarget(data)
  if (parentNeedsAccountReady(data) && data.next_step === 'bind-phone') {
    try {
      const cfg = await fetchWechatConfig()
      if (cfg.use_external_bind_mobile && cfg.bind_mobile_url) {
        window.location.href = cfg.bind_mobile_url
        return
      }
    } catch (_) { /* fallback local bind page */ }
  }
  if (target === '/pages/parent/index') target = consumePostLoginRoute(target, 'parent')
  uni.redirectTo({ url: target })
}

async function routeStudentHome(data) {
  clearLoginGuard()
  saveAuthSession(data)
  uni.showToast({ title: '欢迎，' + data.nickname + '！', icon: 'none' })
  let target = '/pages/index'
  try {
    if (await studentNeedsOnboarding(data.child_user_id)) target = '/pages/login/onboarding/index'
  } catch (e) {
    console.error('[login] studentNeedsOnboarding 检查失败，默认走引导:', e?.message || e)
    target = '/pages/login/onboarding/index'
  }
  if (target === '/pages/index') target = consumePostLoginRoute(target, 'student')
  uni.redirectTo({ url: target })
}

function handleLoginError(e) {
  resetPhase()
  if (hasValidSession()) {
    uni.reLaunch({ url: inferHomeFromSession() })
    return
  }
  if (e.status === 403) {
    uni.showToast({ title: e.message || '访问受限', icon: 'none', duration: 3000 })
  } else if (e.status === 404) {
    const msg = e.message || ''
    if (msg.includes('老系统') || msg.includes('微信')) {
      uni.showModal({ title: '请使用微信登录', content: msg, showCancel: false })
    } else {
      uni.showModal({
        title: '尚未注册',
        content: '该手机号未注册，是否前往注册？',
        success: (r) => { if (r.confirm) goRegister(form.value.phone.trim()) },
      })
    }
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
  if (loginBlocked.value || loginBusy.value) {
    if (loginBlocked.value) uni.showToast({ title: `请 ${blockRemain.value} 秒后再试`, icon: 'none' })
    return
  }
  try {
    const result = await runAuthenticating(async () => {
      if (form.value.role === 'parent') {
        if (parentMode.value === 'sms') {
          if (!form.value.smsCode.trim()) {
            uni.showToast({ title: '请输入短信验证码', icon: 'none' })
            resetPhase()
            return null
          }
          const data = await loginParentSms({
            phone: form.value.phone.trim(),
            smsCode: form.value.smsCode.trim(),
          })
          await completeAfterAuth(() => routeParentHome(data))
          return data
        }
        if (!form.value.phone.trim() || form.value.phone.trim().length < 11) {
          uni.showToast({ title: '请输入正确的手机号', icon: 'none' })
          resetPhase()
          return null
        }
        if (!form.value.password.trim() || form.value.password.trim().length < 6) {
          uni.showToast({ title: '密码至少6位', icon: 'none' })
          resetPhase()
          return null
        }
        const data = await loginParent(form.value.phone.trim(), form.value.password.trim())
        await completeAfterAuth(() => routeParentHome(data))
        return data
      }

      if (!form.value.password.trim() || form.value.password.trim().length < 6) {
        uni.showToast({ title: '密码至少6位', icon: 'none' })
        resetPhase()
        return null
      }
      if (!form.value.loginName.trim()) {
        uni.showToast({ title: '请输入孩子账号', icon: 'none' })
        resetPhase()
        return null
      }
      const data = await loginStudent(form.value.loginName.trim(), form.value.password.trim())
      await completeAfterAuth(() => routeStudentHome(data))
      return data
    })
    if (result?._sessionFallback) {
      await completeAfterAuth(() => uni.reLaunch({ url: inferHomeFromSession() }))
    }
  } catch (e) {
    handleLoginError(e)
  }
}

function goRegister(phone = '') {
  const q = phone ? `?phone=${encodeURIComponent(phone)}` : ''
  uni.navigateTo({ url: `/pages/login/register-parent${q}` })
}

function goAdminLogin() {
  uni.navigateTo({ url: '/pages/admin/login' })
}

function confirmClearCache() {
  uni.showModal({
    title: '清除登录状态',
    content: '仅清除本网站的登录信息（不影响微信），清除后需重新登录。确定？',
    success: (r) => {
      if (!r.confirm) return
      resetLocalAuthCache()
      uni.showToast({ title: '已清除，请重新登录', icon: 'none' })
    },
  })
}

function showLoginHelp() {
  uni.showActionSheet({
    itemList: ['清除本机登录状态', '家长登录说明', '孩子登录说明'],
    success: (r) => {
      if (r.tapIndex === 0) confirmClearCache()
      if (r.tapIndex === 1) {
        uni.showModal({
          title: '家长怎么登录',
          content: '微信内：点绿色「微信一键登录」。\n\n其它情况：选「家长」→ 输入注册时的11位手机号（不是昵称 pyx 这类名字）+ 密码或验证码。\n\n管理员请点底部「管理员后台」，不要在这里用管理员账号。',
          showCancel: false,
        })
      }
      if (r.tapIndex === 2) {
        uni.showModal({
          title: '孩子怎么登录',
          content: '选「学生」→ 输入家长创建的孩子账号和密码。\n\n首次使用需家长先注册，在家长中心添加孩子后再登录训练。',
          showCancel: false,
        })
      }
    },
  })
}

onUnmounted(() => {
  if (cooldownTimer) clearInterval(cooldownTimer)
  if (blockTimer) clearInterval(blockTimer)
})
</script>

<style scoped>
.app {
  height:100vh; height:100dvh; max-width:480px; margin:0 auto;
  background:var(--bg); display:flex; align-items:center; justify-content:center;
  padding:12px 20px; padding-top:max(12px, env(safe-area-inset-top));
  padding-bottom:max(12px, env(safe-area-inset-bottom));
  position:relative; overflow:hidden; box-sizing:border-box;
}
.glow { position:absolute; width:260px; height:260px; border-radius:50%; pointer-events:none; z-index:0; }
.glow-top { top:-80px; right:-60px; background:radial-gradient(circle, rgba(88,166,255,0.18) 0%, transparent 70%); }
.glow-bottom { bottom:-100px; left:-50px; background:radial-gradient(circle, rgba(139,92,246,0.14) 0%, transparent 70%); }
.card {
  width:100%; max-height:100%; position:relative; z-index:1;
  background:rgba(255,255,255,0.03); border:none;
  border-radius:20px; padding:24px 20px 18px; box-sizing:border-box;
}
.brand-head { margin-top:-40px; margin-bottom:0; }
.logo-row { display:flex; align-items:baseline; justify-content:center; gap:6px; margin-bottom:4px; }
.logo-j { color:#dc2626; font-size:48px; font-weight:800; line-height:1; }
.logo-nao, .logo-ai { color:var(--text); font-size:36px; font-weight:700; line-height:1; }
.logo-ai { font-weight:300; }
.subtitle { color:var(--text-dim); font-size:12px; text-align:center; display:block; line-height:1.4; margin-bottom:2px; }
.sub-desc { color:var(--text-dim); font-size:11px; text-align:center; display:block; line-height:1.4; margin-bottom:0; opacity:0.85; }
.login-main { margin-top:60px; }
.login-flow { margin-top:20px; padding-top:0; }
.divider { display:flex; align-items:center; gap:10px; margin:16px 0 12px; }
.divider::before, .divider::after { content:''; flex:1; height:1px; background:var(--border); }
.divider text { color:var(--text-dim); font-size:11px; flex-shrink:0; }
.alt-btns { display:flex; flex-direction:column; gap:10px; }
.btn-outline { border:1.5px solid var(--border); border-radius:12px; padding:14px 16px; background:var(--bg-card); }
.btn-outline-student { border-color:rgba(167,139,250,0.35); }
.btn-outline-title { display:block; color:var(--text); font-size:15px; font-weight:600; }
.btn-outline-sub { display:block; color:var(--text-dim); font-size:11px; margin-top:4px; line-height:1.4; }
.page-footer { display:flex; align-items:center; justify-content:center; gap:8px; margin-top:16px; padding-top:12px; border-top:1px solid rgba(255,255,255,0.06); }
.footer-link { color:var(--text-dim); font-size:11px; padding:4px 2px; }
.footer-link:active { opacity:0.6; }
.footer-dot { color:var(--text-dim); font-size:11px; opacity:0.5; }
.blocked-hint { background:rgba(220,38,38,0.12); border-radius:10px; padding:8px; margin-bottom:10px; text-align:center; }
.blocked-hint text { color:#f87171; font-size:12px; }
.btn-wechat { background:linear-gradient(135deg, #07c160, #06ad56); border-radius:14px; padding:14px; text-align:center; }
.btn-wechat.off { opacity:0.5; }
.btn-wechat text { color:#fff; font-size:16px; font-weight:700; }
.btn-phone-login {
  margin-top:10px; padding:13px; text-align:center; border-radius:14px;
  border:1.5px solid var(--border); background:var(--bg-card);
}
.btn-phone-login text { color:var(--text); font-size:15px; font-weight:600; }
.wechat-loading { text-align:center; padding:8px 0 4px; }
.wechat-loading text { color:var(--accent); font-size:13px; }
.input-wrap { display:flex; align-items:center; background:var(--bg-card); border-radius:12px; padding:0 14px; margin-bottom:10px; border:1.5px solid var(--border); position:relative; z-index:2; }
.sms-row { padding-right:4px; }
.sms-btn { flex-shrink:0; padding:8px 10px; border-radius:8px; background:rgba(88,166,255,0.15); }
.sms-btn.off { opacity:0.5; }
.sms-btn text { color:var(--accent); font-size:12px; }
.login-input { flex:1; width:100%; min-height:44px; padding:12px 0; font-size:16px; line-height:1.4; color:var(--text); background:transparent; border:none; box-sizing:border-box; -webkit-user-select:text; user-select:text; }
.role-row { display:flex; gap:0; margin-top:0; margin-bottom:12px; border-radius:14px; overflow:hidden; border:1.5px solid var(--border); background:var(--accent-bg); }
.role-item { flex:1; padding:12px; text-align:center; cursor:pointer; transition:all 0.25s; position:relative; }
.role-item:first-child { border-right:1.5px solid var(--border); }
.role-item.active { background:var(--bg-card); }
.role-item.active::after {
  content:''; position:absolute; bottom:0; left:20%; width:60%; height:2px;
  background:linear-gradient(90deg,#a78bfa,#60a5fa); border-radius:2px;
}
.ri-label { font-size:14px; font-weight:500; transition:all 0.25s; }
.role-item.active .ri-label { color:var(--accent); font-weight:700; }
.role-item:not(.active) .ri-label { color:var(--text-dim); }
.btn-login { background:linear-gradient(135deg, #58a6ff, #7c3aed); border-radius:14px; padding:13px; text-align:center; margin-top:4px; }
.btn-login.off { opacity:0.5; }
.btn-login text { color:#fff; font-size:16px; font-weight:700; }
.form-links-above {
  display:flex; align-items:center; justify-content:space-between;
  width:100%; margin:4px 0 10px; box-sizing:border-box;
}
.form-link { color:#a78bfa; font-size:13px; padding:4px 0; }
.form-link-left { text-align:left; flex:1; }
.form-link-right { text-align:right; flex:1; }
.btn-register {
  margin-top:10px; padding:13px; text-align:center; border-radius:14px;
  border:1.5px solid rgba(167,139,250,0.45); background:rgba(167,139,250,0.08);
}
.btn-register text { color:#c4b5fd; font-size:15px; font-weight:600; }
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
.overlay { position:fixed; inset:0; z-index:10000; background:rgba(0,0,0,0.55); display:flex; align-items:center; justify-content:center; padding:20px; }
.captcha-panel { width:100%; max-width:320px; background:var(--bg-card); border-radius:16px; padding:20px; border:1px solid var(--border); }
.captcha-title { display:block; text-align:center; font-weight:700; color:var(--text); margin-bottom:12px; }
.captcha-img { width:100%; height:48px; margin-bottom:10px; border-radius:8px; background:#f3f4f6; }
.captcha-actions { display:flex; gap:10px; margin-top:12px; align-items:center; }
.captcha-confirm { flex:1; padding:12px; }
</style>
