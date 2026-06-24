<template>
  <view class="app">
    <view class="nav">
      <view class="nav-back" @click="goBack">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#8b949e" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      </view>
      <text class="nav-title">成长里程碑</text>
      <view class="nav-spacer"></view>
    </view>

    <scroll-view class="body" scroll-y>
      <!-- Badges -->
      <text class="sec-title">🏅 荣誉徽章</text>
      <view class="badge-row">
        <view v-for="b in badges" :key="b.name" class="badge-item" :class="{ locked: !b.earned }">
          <view class="badge-circle" :class="{ earned: b.earned }"><text>{{ b.icon }}</text></view>
          <text class="badge-name">{{ b.name }}</text>
          <text class="badge-cond">{{ b.cond }}</text>
        </view>
      </view>

      <!-- Timeline -->
      <text class="sec-title">📅 成长时间线</text>
      <view class="timeline">
        <view class="tl-line"></view>
        <view v-for="(e,i) in events" :key="i" class="tl-item" :class="{ future: !e.done }">
          <view class="tl-dot" :class="{ done: e.done }"></view>
          <view class="tl-card">
            <text class="tl-title">{{ e.title }}</text>
            <text class="tl-date">{{ e.date }} · {{ e.desc }}</text>
          </view>
        </view>
      </view>

      <!-- Share -->
      <view class="share-card">
        <text class="share-title">📤 一键分享</text>
        <text class="share-hint">分享你的成长成就到微信/朋友圈</text>
        <view class="share-btn" @click="shareToast"><text>生成分享卡片</text></view>
      </view>

      <view style="height:40px;"></view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref } from 'vue'

const badges = ref([
  { name:'首次测评', icon:'🌟', cond:'完成天赋测试', earned:true },
  { name:'初露锋芒', icon:'🔥', cond:'连续打卡7天', earned:true },
  { name:'持之以恒', icon:'⚡', cond:'连续打卡30天', earned:false },
  { name:'百炼成钢', icon:'🏆', cond:'累计100次打卡', earned:false },
  { name:'全能王者', icon:'👑', cond:'完成全部能力训练', earned:false },
  { name:'知识达人', icon:'💎', cond:'累计提问100次', earned:false },
])

const events = ref([
  { title:'连续打卡 7 天', date:'06-28', desc:'获得「初露锋芒」徽章', done:true },
  { title:'完成首次天赋测评', date:'06-22', desc:'主导天赋：学者型', done:true },
  { title:'第 10 次打卡', date:'06-30', desc:'累计完成10天训练', done:true },
  { title:'首次学科答疑', date:'06-25', desc:'提出第一个学科问题', done:true },
  { title:'连续打卡 30 天', date:'未来', desc:'解锁「持之以恒」徽章', done:false },
  { title:'累计 100 次打卡', date:'未来', desc:'解锁「百炼成钢」金徽章', done:false },
])

function goBack() { uni.navigateBack({ delta: 1 }) }
function shareToast() { uni.showToast({ title: '分享功能开发中', icon: 'none' }) }
</script>

<style scoped>
.app { height:100vh; max-width:480px; margin:0 auto; background:var(--bg); font-family:-apple-system,"PingFang SC",sans-serif; display:flex; flex-direction:column; position:relative; overflow:hidden; }
.nav { display:flex; align-items:center; padding:14px 14px 0; }
.nav-back { width:36px; height:36px; border-radius:50%; background:var(--bg-card); display:flex; align-items:center; justify-content:center; cursor:pointer; }
.nav-title { flex:1; text-align:center; color:var(--text); font-size:16px; font-weight:600; }
.nav-spacer { width:36px; }
.body { flex:1; overflow-y:auto; padding:12px 16px 0; scrollbar-width:none; }
.body::-webkit-scrollbar { display:none; }
.sec-title { color:var(--text); font-size:15px; font-weight:700; display:block; margin:0 0 12px; }

.badge-row { display:flex; flex-wrap:wrap; gap:14px; margin-bottom:20px; }
.badge-item { text-align:center; width:calc(33.33% - 10px); }
.badge-item.locked { opacity:0.35; }
.badge-circle { width:50px; height:50px; border-radius:50%; margin:0 auto 4px; display:flex; align-items:center; justify-content:center; font-size:22px; }
.badge-circle.earned { background:var(--accent-bg); }
.badge-circle.locked { background:var(--bg-card); }
.badge-name { color:var(--text); font-size:11px; font-weight:600; display:block; }
.badge-cond { color:var(--text-dim); font-size:9px; display:block; margin-top:1px; }

.timeline { position:relative; padding-left:20px; margin-bottom:20px; }
.tl-line { position:absolute; left:6px; top:4px; bottom:4px; width:2px; background:var(--border); }
.tl-item { position:relative; margin-bottom:14px; }
.tl-item.future { opacity:0.35; }
.tl-dot { position:absolute; left:-18px; top:4px; width:10px; height:10px; border-radius:50%; background:var(--bg-card); border:2px solid var(--border); }
.tl-dot.done { background:var(--accent); border-color:var(--accent); }
.tl-card { }
.tl-title { color:var(--text); font-size:13px; font-weight:600; display:block; }
.tl-date { color:var(--text-dim); font-size:11px; display:block; margin-top:2px; }

.share-card { background:var(--bg-card); border-radius:16px; padding:20px; text-align:center; margin-bottom:20px; border:1px dashed var(--border); }
.share-title { color:var(--text); font-size:15px; font-weight:700; display:block; margin-bottom:4px; }
.share-hint { color:var(--text-dim); font-size:12px; display:block; margin-bottom:12px; }
.share-btn { background:var(--accent); border-radius:12px; padding:12px; display:inline-block; cursor:pointer; }
.share-btn text { color:#fff; font-size:14px; font-weight:600; }
.share-btn:active { opacity:0.85; }
</style>
