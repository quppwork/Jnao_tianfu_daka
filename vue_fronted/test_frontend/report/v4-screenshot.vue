<template>
  <view class="app">
    <!-- Header -->
    <view class="header">
      <view class="back-btn" @tap="goBack">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#666" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      </view>
      <text class="header-title">天赋报告</text>
    </view>

    <scroll-view class="body" scroll-y>
      <view class="container">

        <!-- 1. Profile Card -->
        <view class="card profile-card">
          <image src="https://cdn.screenshottocode.com/zIdnxxtZ_pPfItdQJja-1.png" class="profile-art" mode="aspectFit" />
          <view class="profile-section">
            <image src="/static/xue.jpg" class="avatar" mode="aspectFill" />
            <view class="profile-info">
              <text class="profile-label">天赋者</text>
              <text class="profile-name">思者</text>
              <text class="profile-desc">大脑袋里装着10万个想法，脑洞不开则已，一开便无限大，创造力与创新力都超强。</text>
            </view>
          </view>
        </view>

        <!-- 2. Stats Grid -->
        <view class="stats-grid">
          <view class="stat-card">
            <text class="stat-value">41</text>
            <text class="stat-label">核心天赋值</text>
          </view>
          <view class="stat-card">
            <text class="stat-value stat-green">思者</text>
            <text class="stat-label">天赋类型</text>
          </view>
          <view class="stat-card">
            <text class="stat-value">孤显</text>
            <text class="stat-label">能量状态</text>
          </view>
        </view>

        <!-- 3. Talent Wheel -->
        <view class="card talent-wheel-card">
          <view class="wheel-container">
            <text class="wheel-label label-tl">思者</text>
            <text class="wheel-label label-tr">赢者</text>
            <text class="wheel-label label-bl">学者</text>
            <text class="wheel-label label-br">德者</text>
            <text class="wheel-label label-bc">行者</text>
            <svg class="wheel-svg" viewBox="0 0 200 200">
              <circle cx="100" cy="100" r="80" fill="none" stroke="#f0f0f0" stroke-width="2"/>
              <circle cx="100" cy="100" r="60" fill="none" stroke="#f0f0f0" stroke-width="2"/>
              <circle cx="100" cy="100" r="40" fill="none" stroke="#f0f0f0" stroke-width="2"/>
              <circle cx="100" cy="100" r="20" fill="none" stroke="#f0f0f0" stroke-width="2"/>
              <path d="M 100 100 L 43.4 43.4 A 80 80 0 0 1 100 20 Z" fill="#fff9c4" opacity="0.4"/>
              <path d="M 100 100 L 57.6 57.6 A 60 60 0 0 1 100 40 Z" fill="#fff176" opacity="0.6"/>
              <path d="M 100 100 L 71.7 71.7 A 40 40 0 0 1 100 60 Z" fill="#fbc02d"/>
              <circle cx="100" cy="100" r="20" fill="#fbc02d" opacity="0.8"/>
              <line x1="100" y1="20" x2="100" y2="100" stroke="#eee" stroke-width="1"/>
              <line x1="100" y1="180" x2="100" y2="100" stroke="#eee" stroke-width="1"/>
              <line x1="20" y1="100" x2="100" y2="100" stroke="#eee" stroke-width="1"/>
              <line x1="180" y1="100" x2="100" y2="100" stroke="#eee" stroke-width="1"/>
            </svg>
          </view>
        </view>

        <!-- 4. Talent Ability -->
        <view class="card">
          <text class="sec-title">天赋能力</text>
          <text class="sub-title">天赋能力解读</text>
          <view class="ability-row">
            <view class="ability-text">
              <text>你是一名充满激情与梦想的思者，天赋是创新力，在这方面你表现的更务实并注重目标。</text>
              <text style="margin-top:8px;">你善于创意创新，精于捕捉事物的关键信息。</text>
            </view>
            <view class="video-box"><text>视频</text></view>
          </view>
          <view class="ability-text" style="margin-top:14px;">
            <text class="sub-title">想对你说的话</text>
            <text>目前你表现出思者优秀的天赋，提升自己的关键是要有明确的目标，你的天赋是创造更多的可能性，虽然你表现出很强的领导力与业务能力，要时刻警惕思者的惰性会爆发。</text>
          </view>
        </view>

        <!-- 5. Detailed Attributes -->
        <view class="card">
          <view class="detail-header">
            <text class="detail-title">思者 · 双重属性详解</text>
            <image src="/static/思者.png" style="width:80px;height:100px;opacity:0.8;" mode="aspectFit" />
          </view>
          <view class="detail-body">
            <text class="detail-p">你是个机智应变型(思偏赢)的思者，正义率真、自信美感，乐观有梦想，有眼光、不服输。</text>
            <text class="detail-p">你相信正义、相信公平、相信付出必有回报，这也使你内心充满着正义感而愿意相信别人。你的右脑比左脑更发达，犹如植物一样生生不息的想法与创意是你生命中最宝贵的力量！</text>
            <text class="detail-sub">思者求仁</text>
            <text class="detail-p">追求仁义道德、品行仁慈，有同理心。</text>
            <text class="detail-sub">正木善变</text>
            <text class="detail-p">正直有爱、耿直真诚，思维灵活善于变通。</text>
            <text class="detail-sub">心无设限</text>
            <text class="detail-p">思者善长谋略，不受限制的思考方式从不相信世上只有一条道。</text>
            <text class="detail-sub">不韧需行</text>
            <text class="detail-p">思者身上缺乏坚韧不拔的毅力，因此需要更多的行动力与执行力来克服缺点。</text>
            <view class="collapse-btn" @tap="showDetail=!showDetail">
              <text>{{ showDetail ? '收起' : '展示更多' }}</text>
            </view>
          </view>
        </view>

        <!-- 6. Comprehensive Ability + Radar -->
        <view class="card">
          <text class="sec-title">综合能力</text>
          <text style="text-align:center;color:#666;font-size:14px;font-weight:700;display:block;">协调力</text>
          <view class="radar-wrap">
            <svg viewBox="0 0 200 200" style="width:100%;height:200px;">
              <polygon points="100,20 180,78 150,172 50,172 20,78" fill="none" stroke="#e0e0e0" stroke-width="1"/>
              <polygon points="100,50 156,91 135,152 65,152 44,91" fill="none" stroke="#e0e0e0" stroke-width="1"/>
              <polygon points="100,80 128,100 118,131 82,131 72,100" fill="none" stroke="#e0e0e0" stroke-width="1"/>
              <line x1="100" y1="100" x2="100" y2="20" stroke="#e0e0e0"/>
              <line x1="100" y1="100" x2="180" y2="78" stroke="#e0e0e0"/>
              <line x1="100" y1="100" x2="150" y2="172" stroke="#e0e0e0"/>
              <line x1="100" y1="100" x2="50" y2="172" stroke="#e0e0e0"/>
              <line x1="100" y1="100" x2="20" y2="78" stroke="#e0e0e0"/>
              <text x="5" y="65" font-size="12" font-weight="700" fill="#333">创新力</text>
              <text x="168" y="65" font-size="12" font-weight="700" fill="#333">执行力</text>
              <text x="48" y="195" font-size="12" font-weight="700" fill="#333">领导力</text>
              <text x="135" y="195" font-size="12" font-weight="700" fill="#333">公信力</text>
              <polygon points="100,40 140,85 130,140 85,150 55,100" fill="rgba(69,90,100,0.2)" stroke="#455a64" stroke-width="2"/>
              <circle cx="100" cy="40" r="3" fill="#455a64"/><circle cx="140" cy="85" r="3" fill="#455a64"/>
              <circle cx="130" cy="140" r="3" fill="#455a64"/><circle cx="85" cy="150" r="3" fill="#455a64"/>
              <circle cx="55" cy="100" r="3" fill="#455a64"/>
            </svg>
          </view>
          <view v-for="m in metrics" :key="m.name" class="metric-row">
            <text class="metric-label">{{ m.name }}</text>
            <view class="metric-bar"><view class="metric-fill" :style="{ width: m.pct+'%', background: m.pct>=70?'#52c41a':'#f26d5f' }"></view></view>
            <text class="metric-val">{{ m.value }}</text>
            <text class="metric-status" :class="m.pct>=70?'s-good':'s-normal'">{{ m.pct>=70?'良好':'正常' }}</text>
          </view>
        </view>

        <!-- 7. Current Status -->
        <view class="card status-card">
          <text class="sec-title">当前状态</text>
          <view class="lightbulb-wrap">
            <svg viewBox="0 0 40 40" width="40" height="40"><circle cx="20" cy="16" r="8" fill="#fbc02d"/><rect x="16" y="24" width="8" height="4" rx="1" fill="#ccc"/><rect x="15" y="28" width="10" height="3" rx="1" fill="#ccc"/></svg>
          </view>
          <view class="status-track-wrap">
            <view class="status-labels-top">
              <text>低迷</text><text>平稳</text><text>高涨</text>
            </view>
            <view class="status-track">
              <view class="status-dot"></view>
              <view class="status-dot active"></view>
              <view class="status-dot"></view>
            </view>
          </view>
          <view class="state-grid">
            <text v-for="s in states" :key="s" class="state-item" :class="{ active: s==='孤显' }">{{ s }}</text>
          </view>
          <text class="status-desc">综合能量显示你的内心状态略有低迷，但是对于生活稳定、无欲无求的人来说这是很平和自然的生活状态，当然这也可能只是暂时的低沉精神状态。</text>
          <view class="collapse-btn"><text>展示更多</text></view>
        </view>

        <!-- 8. Advice -->
        <view class="card">
          <text class="sec-title">给你的建议</text>
          <view class="advice-block">
            <text class="advice-title">事业建议</text>
            <view class="advice-row">
              <text class="advice-text">目前的状态对于一个有更高要求的人来说这代表一种低迷状态，因为这种状态若向上渴求突破人会显得无力，向下低沉则人会渐渐麻木。所以快乐与痛苦都没有那么强烈，人生会在既定的轨道上相对平稳地向前行。面对压力与风险要敢于挑战并乐于尝试，唯有更多的体验与磨砺才能令自己不断积淀人生的阅历与能力。</text>
              <view class="video-box"><text>视频</text></view>
            </view>
          </view>
          <view class="advice-block">
            <text class="advice-title">情感建议</text>
            <text class="advice-text">正视自己的优点长处，让自己更自信勇敢、乐观积极才能影响身边的亲人。综合能力的修炼则是自己需要承担更多的责任，敢于试错的勇气，拥有客观认知自己的正能量。</text>
          </view>
        </view>

        <!-- 9. Three Golden Rules -->
        <view class="card">
          <text class="sec-title">三条黄金建议</text>
          <view class="golden-item" v-for="(r,i) in goldenRules" :key="i">
            <text class="golden-num">{{ i+1 }}.</text>
            <text class="golden-text">{{ r }}</text>
          </view>
        </view>

      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, reactive } from 'vue'
const showDetail = ref(true)
const states = ["相争","难辨","牵制","双生","本命","孤显","无向","无神"]
const metrics = reactive([
  { name:'领导力', value:63, pct:63 }, { name:'公信力', value:114, pct:85 },
  { name:'执行力', value:57, pct:57 }, { name:'协调力', value:65, pct:65 },
])
const goldenRules = [
  '别太坚信相信未来可能要发生的事情',
  '别自信过度，过于理想化会令你看不到危机',
  '聪明人最大的敌人就是骄傲善妒的自己',
]
function goBack(){}
</script>

<style scoped>
.app { min-height:100vh; max-width:480px; margin:0 auto; background:#f7f8fa; font-family:-apple-system,"PingFang SC",sans-serif; }
.header { display:flex; align-items:center; justify-content:center; padding:15px; position:relative; background:#fff; border-bottom:1px solid #eee; }
.back-btn { position:absolute; left:15px; width:32px; height:32px; background:#f0f0f0; border-radius:50%; display:flex; align-items:center; justify-content:center; }
.header-title { font-size:18px; font-weight:600; color:#333; }
.body { flex:1; }
.container { padding:12px; }

.card { background:#fff; border-radius:12px; padding:20px; margin-bottom:12px; box-shadow:0 2px 8px rgba(0,0,0,0.05); }

/* Profile */
.profile-card { position:relative; overflow:hidden; }
.profile-art { position:absolute; right:-10px; top:6px; width:135px; height:150px; opacity:0.22; pointer-events:none; }
.profile-section { position:relative; z-index:1; display:flex; align-items:flex-start; gap:15px; }
.avatar { width:70px; height:70px; border-radius:15px; }
.profile-label { font-size:12px; color:#999; display:block; }
.profile-name { font-size:20px; font-weight:700; color:#333; display:block; }
.profile-desc { font-size:13px; color:#666; line-height:1.5; display:block; margin-top:4px; }

/* Stats */
.stats-grid { display:flex; gap:10px; margin-bottom:12px; }
.stat-card { flex:1; background:#fff; border-radius:12px; padding:15px 10px; text-align:center; box-shadow:0 2px 8px rgba(0,0,0,0.05); }
.stat-value { font-size:20px; font-weight:700; color:#333; display:block; }
.stat-green { color:#4caf50; }
.stat-label { font-size:12px; color:#999; display:block; margin-top:4px; }

/* Wheel */
.talent-wheel-card { text-align:center; padding:30px 20px; }
.wheel-container { position:relative; width:240px; height:240px; margin:0 auto; }
.wheel-label { position:absolute; font-size:16px; font-weight:600; color:#333; }
.label-tl { top:8px; left:8px; color:#fbc02d; }
.label-tr { top:8px; right:8px; color:#666; }
.label-bl { bottom:8px; left:8px; color:#666; }
.label-br { bottom:8px; right:8px; color:#666; }
.label-bc { bottom:-20px; left:50%; transform:translateX(-50%); color:#666; }

/* Ability */
.sec-title { font-size:18px; font-weight:700; color:#333; display:block; margin-bottom:12px; }
.sub-title { font-size:14px; color:#666; display:block; margin-bottom:8px; }
.ability-row { display:flex; gap:15px; }
.ability-text { flex:1; font-size:13px; color:#666; line-height:1.6; }
.video-box { width:120px; height:80px; background:#c4c4c4; border-radius:8px; display:flex; align-items:center; justify-content:center; flex-shrink:0; font-size:12px; color:#333; }

/* Detail */
.detail-header { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:15px; }
.detail-title { font-size:15px; font-weight:700; color:#555; }
.detail-p { font-size:13px; color:#666; line-height:1.6; display:block; margin-bottom:10px; }
.detail-sub { font-weight:700; color:#444; display:block; margin-bottom:5px; font-size:14px; }
.collapse-btn { text-align:center; color:#999; font-size:12px; margin-top:10px; }

/* Radar */
.radar-wrap { margin-bottom:15px; }

/* Metrics */
.metric-row { display:flex; align-items:center; margin-bottom:10px; }
.metric-label { width:60px; font-size:13px; color:#333; }
.metric-bar { flex:1; height:6px; background:#f0f0f0; border-radius:3px; margin:0 10px; }
.metric-fill { height:100%; border-radius:3px; }
.metric-val { width:30px; text-align:right; font-size:13px; font-weight:700; }
.metric-status { width:40px; text-align:right; margin-left:10px; font-size:12px; }
.s-good { color:#52c41a; }
.s-normal { color:#f26d5f; }

/* Status */
.status-card { text-align:center; }
.lightbulb-wrap { margin:20px 0; }
.status-track-wrap { margin:20px 0; }
.status-labels-top { display:flex; justify-content:space-between; width:60%; margin:0 auto 5px; font-size:10px; color:#999; }
.status-track { display:flex; align-items:center; justify-content:space-between; width:80%; margin:0 auto; height:3px; background:#e0e0e0; position:relative; }
.status-dot { width:10px; height:10px; background:#999; border-radius:50%; }
.status-dot.active { width:14px; height:14px; background:#8d6e63; }
.state-grid { display:flex; flex-wrap:wrap; justify-content:center; gap:15px; margin-top:20px; }
.state-item { font-size:13px; color:#999; }
.state-item.active { color:#4caf50; font-weight:700; }
.status-desc { font-size:13px; color:#666; line-height:1.6; display:block; margin-top:15px; text-align:left; }

/* Advice */
.advice-block { padding-bottom:15px; margin-bottom:15px; border-bottom:1px solid #f0f0f0; }
.advice-block:last-child { border-bottom:none; margin-bottom:0; padding-bottom:0; }
.advice-title { font-size:14px; font-weight:700; color:#444; display:block; margin-bottom:8px; }
.advice-row { display:flex; gap:15px; }
.advice-text { flex:1; font-size:13px; color:#666; line-height:1.6; }

/* Golden */
.golden-item { display:flex; padding:12px 0; border-bottom:1px solid #f9f9f9; }
.golden-item:last-child { border-bottom:none; }
.golden-num { margin-right:8px; font-size:13px; font-weight:700; }
.golden-text { font-size:13px; color:#333; line-height:1.5; }
</style>
