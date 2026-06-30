<template>
  <view class="app">
    <view class="card">
      <view class="logo-row">
        <text class="logo-j">J</text><text class="logo-nao">nao</text><text class="logo-ai">AI</text>
      </view>
      <text class="subtitle">孩子账号说明</text>

      <view class="info-block">
        <text class="info-title">账号由家长分配</text>
        <text class="info-text">孩子登录账号和密码由家长在「家长中心」创建。请联系家长获取账号后，在登录页选择「学生」并使用账号密码登录。</text>
      </view>

      <view class="btn-login" @click="goLogin">
        <text>返回登录</text>
      </view>

      <view class="btn-back" @click="goParentRegister">
        <text>我是家长，去注册</text>
      </view>
    </view>
  </view>
</template>

<script setup>
function goLogin() {
  uni.navigateBack()
}

function goParentRegister() {
  uni.navigateTo({ url: '/pages/login/register-parent' })
}
</script>

<style scoped>
.app { height:100vh; max-width:480px; margin:0 auto; background:var(--bg); display:flex; align-items:center; justify-content:center; padding:30px; font-family:-apple-system,"PingFang SC",sans-serif; }
.card { width:100%; }
.logo-row { display:flex; align-items:baseline; justify-content:center; gap:6px; margin-bottom:6px; }
.logo-j { color:#dc2626; font-size:44px; font-weight:800; }
.logo-nao { color:var(--text); font-size:34px; font-weight:700; }
.logo-ai { color:var(--text); font-size:34px; font-weight:300; }
.subtitle { color:var(--text-dim); font-size:13px; text-align:center; display:block; margin-bottom:24px; }
.info-block { background:var(--bg-card); border:1px solid var(--border); border-radius:14px; padding:18px; margin-bottom:24px; }
.info-title { color:var(--text); font-size:15px; font-weight:700; display:block; margin-bottom:8px; }
.info-text { color:var(--text-dim); font-size:13px; line-height:1.6; display:block; }
.btn-login { background:linear-gradient(135deg,var(--accent),#3b8bff); border-radius:14px; padding:15px; text-align:center; cursor:pointer; }
.btn-login text { color:#fff; font-size:16px; font-weight:700; }
.btn-back { border:1.5px solid var(--border); border-radius:14px; padding:13px; text-align:center; cursor:pointer; margin-top:10px; }
.btn-back text { color:var(--text-dim); font-size:14px; }
</style>
