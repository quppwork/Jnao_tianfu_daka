<template>
  <view class="app">
    <!-- ===== 导航栏 ===== -->
    <view class="nav">
      <view class="nav-back" @tap="goBack">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#6b7280" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      </view>
      <text class="nav-title">天赋报告</text>
      <view class="nav-spacer"></view>
    </view>

    <scroll-view class="body" scroll-y>

      <!-- ===== 1. HERO C位 ===== -->
      <view class="hero">
        <image class="hero-img" :src="tData.image" mode="aspectFit" />
        <view class="hero-badge" :style="{ background: tData.color }">
          <text>{{ tData.type }}</text>
        </view>
        <text class="hero-name">{{ tData.name }}</text>
        <text class="hero-tagline">{{ tData.tagline }}</text>
        <view class="hero-stats">
          <view class="hs"><text class="hs-val" :style="{ color: tData.color }">{{ tData.score }}</text><text class="hs-lbl">天赋值</text></view>
          <view class="hs"><text class="hs-val">{{ tData.stage }}</text><text class="hs-lbl">成长阶段</text></view>
          <view class="hs"><text class="hs-val">{{ tData.energy }}</text><text class="hs-lbl">能量状态</text></view>
        </view>
      </view>

      <!-- ===== 2. 天赋特质 徽章 ===== -->
      <view class="card">
        <text class="sec-title">天赋特质</text>
        <view class="trait-tags">
          <view v-for="t in tData.traits" :key="t.id" class="ttag" :style="{ borderColor: tData.color+'40', background: tData.color+'08' }">
            <text class="ttag-emoji">{{ t.emoji }}</text>
            <text class="ttag-name">{{ t.name }}</text>
            <text class="ttag-lv">Lv.{{ t.level }}</text>
          </view>
        </view>
      </view>

      <!-- ===== 3. 综合能力 雷达图 ===== -->
      <view class="card">
        <text class="sec-title">综合能力</text>
        <view class="radar-wrap">
          <svg viewBox="0 0 200 180" style="width:200px;height:180px;display:block;margin:0 auto;">
            <polygon points="100,15 170,65 145,145 55,145 30,65" fill="none" stroke="#e5e7eb" stroke-width="1"/>
            <polygon points="100,40 155,68 135,120 65,120 45,68" fill="none" stroke="#e5e7eb" stroke-width="1"/>
            <polygon points="100,65 140,82 125,95 75,95 60,82" fill="none" stroke="#e5e7eb" stroke-width="1"/>
            <polygon :points="rdPts" fill="rgba(37,99,235,0.1)" stroke="#2563eb" stroke-width="1.5" stroke-linejoin="round"/>
            <circle v-for="(d,i) in rdDots" :key="i" :cx="d.x" :cy="d.y" r="3" :fill="d.v>=70?'#2563eb':'#94a3b8'"/>
            <text v-for="l in rdLabels" :key="l.n" :x="l.x" :y="l.y" font-size="10" fill="#374151" :text-anchor="l.a" font-weight="600">{{ l.n }}</text>
          </svg>
        </view>
        <view v-for="a in tData.abilities" :key="a.n" class="ab-row">
          <text class="ab-n">{{ a.n }}</text>
          <view class="ab-track"><view class="ab-fill" :style="{ width: a.v+'%', background: a.v>=70?tData.color:a.v>=50?'#f59e0b':'#94a3b8' }"></view></view>
          <text class="ab-v">{{ a.v }}</text>
        </view>
      </view>

      <!-- ===== 4. 天赋解读 折叠 ===== -->
      <view class="card">
        <text class="sec-title">天赋解读</text>
        <view class="oneline">
          <text>💬</text>
          <text class="oneline-t">{{ tData.oneliner }}</text>
        </view>
        <view v-if="!open.detail" class="expand" @tap="open.detail=true"><text>展开完整解读 ↓</text></view>
        <view v-else class="detail">
          <text class="detail-t">{{ tData.detail }}</text>
          <view class="expand" @tap="open.detail=false"><text>收起 ↑</text></view>
        </view>
      </view>

      <!-- ===== 5. 给你的建议 图标卡 ===== -->
      <view class="card">
        <text class="sec-title">给你的建议</text>
        <view class="advice-list">
          <view class="adv-item" style="background:#eff6ff"><text class="adv-emoji">🏆</text><text class="adv-ttl">事业方向</text><text class="adv-t">{{ tData.adviceCareer }}</text></view>
          <view class="adv-item" style="background:#fef3c7"><text class="adv-emoji">❤️</text><text class="adv-ttl">情感关系</text><text class="adv-t">{{ tData.adviceEmotion }}</text></view>
          <view class="adv-item" style="background:#f0fdf4"><text class="adv-emoji">💪</text><text class="adv-ttl">成长要点</text><text class="adv-t">{{ tData.adviceGrowth }}</text></view>
        </view>
      </view>

      <!-- ===== 6. 黄金建议 ===== -->
      <view class="card">
        <text class="sec-title">三条黄金建议</text>
        <view v-for="(t,i) in tData.tips" :key="i" class="tip-row">
          <view class="tip-num" :style="{ background: tData.color }"><text>{{ i+1 }}</text></view>
          <text class="tip-t">{{ t }}</text>
        </view>
      </view>

      <view style="height:80px" />
    </scroll-view>

    <!-- ===== 固定底栏 ===== -->
    <view class="bbar">
      <view class="bbar-btn" @tap="reTest"><text>🔄 重新测试</text></view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, reactive } from 'vue'

const open = reactive({ detail: false })

// ========= 原型数据 =========
const tData = reactive({
  type: '学者', name: '智求者',
  tagline: '天生的思考者，用知识照亮前路',
  color: '#2563eb', score: 85, stage: '潜力期', energy: '平稳',
  image: '/static/xue.jpg',
  oneliner: '你拥有卓越的逻辑分析能力和对新知识的强烈渴求。学习不是任务，而是探索世界的本能。',
  detail: '学者型的人天生对世界充满好奇，喜欢系统性思考。在学习中偏好深度阅读和独立思考。\n\n逻辑推理能力会越来越强，尤其适合需要深度分析的领域。注意平衡思考与行动的比例。\n\nAI 平台为你定制：强化逻辑推理、知识迁移、批判性思维，同时补充行动力训练。',
  traits: [
    { id:'A', emoji:'🧠', name:'智慧', level:5 },
    { id:'B', emoji:'💭', name:'思辨', level:4 },
    { id:'C', emoji:'🎯', name:'专注', level:4 },
    { id:'D', emoji:'🔍', name:'洞察', level:3 },
    { id:'E', emoji:'📖', name:'求知', level:5 },
  ],
  abilities: [
    { n:'逻辑力', v:92 }, { n:'专注力', v:85 }, { n:'记忆力', v:78 }, { n:'创造力', v:65 }, { n:'表达力', v:55 }
  ],
  adviceCareer: '适合科研、教育、技术分析、编程等需要深度思考的工作。',
  adviceEmotion: '擅长理解他人，需学习更主动地表达情感。',
  adviceGrowth: '多做"先试再说"的小练习，平衡思考与行动。',
  tips: [
    '每天留出 30 分钟深度阅读，自由探索感兴趣的知识领域。',
    '尝试把学到的东西讲给别人听，教是最好的学。',
    '每周完成一件不需要"想太多"的事，培养行动直觉。',
  ],
})

// 雷达图
const ro = [{x:100,y:15},{x:170,y:65},{x:145,y:145},{x:55,y:145},{x:30,y:65}]
const rdLabels = [
  { n:'逻辑力',x:100,y:8,a:'middle' },{ n:'专注力',x:178,y:65,a:'start' },
  { n:'记忆力',x:148,y:158,a:'middle' },{ n:'创造力',x:52,y:158,a:'middle' },{ n:'表达力',x:18,y:65,a:'end' }
]
const rdPts = computed(() => tData.abilities.map((a,i) => { const v=ro[i]; const r=a.v/100; return `${100+(v.x-100)*r},${100+(v.y-100)*r}` }).join(' '))
const rdDots = computed(() => tData.abilities.map((a,i) => { const v=ro[i]; const r=a.v/100; return { x:100+(v.x-100)*r, y:100+(v.y-100)*r, v:a.v } }))

function goBack(){ uni.navigateBack({ delta:1 }) }
function reTest(){ uni.redirectTo({ url:'/pages/talent/index' }) }
</script>

<style scoped>
.app { min-height:100vh; max-width:480px; margin:0 auto; background:#fafafa; font-family:-apple-system,"PingFang SC",sans-serif; display:flex; flex-direction:column; position:relative; }
.nav { display:flex; align-items:center; padding:14px 24px 0; }
.nav-back { width:36px; height:36px; border-radius:50%; background:#fff; display:flex; align-items:center; justify-content:center; cursor:pointer; flex-shrink:0; border:1px solid #e5e7eb; }
.nav-title { flex:1; text-align:center; color:#1f2937; font-size:16px; font-weight:600; }
.nav-spacer { width:36px; flex-shrink:0; }
.body { flex:1; overflow-y:auto; }

/* Hero */
.hero { display:flex; flex-direction:column; align-items:center; padding:24px 20px 28px; }
.hero-img { width:140px; height:140px; border-radius:24px; background:#f8fafc; }
.hero-badge { margin-top:14px; padding:4px 16px; border-radius:20px; }
.hero-badge text { color:#fff; font-size:12px; font-weight:600; }
.hero-name { margin-top:8px; font-size:28px; font-weight:800; color:#1f2937; }
.hero-tagline { margin-top:6px; font-size:14px; color:#6b7280; }
.hero-stats { display:flex; align-items:center; margin-top:18px; padding:14px 20px; background:#fff; border-radius:16px; border:1px solid #e5e7eb; width:100%; }
.hs { flex:1; text-align:center; }
.hs-val { font-size:20px; font-weight:800; }
.hs-lbl { font-size:11px; color:#9ca3af; display:block; margin-top:2px; }

/* Card */
.card { background:#fff; border:1px solid #e5e7eb; border-radius:16px; padding:20px; margin:0 20px 12px; }
.sec-title { font-size:16px; font-weight:700; color:#1f2937; display:block; margin-bottom:14px; }

/* Traits */
.trait-tags { display:flex; flex-wrap:wrap; gap:8px; }
.ttag { display:flex; align-items:center; gap:6px; padding:8px 14px; border-radius:12px; border:1.5px solid; }
.ttag-emoji { font-size:16px; }
.ttag-name { font-size:13px; font-weight:600; color:#1f2937; }
.ttag-lv { font-size:11px; color:#9ca3af; background:rgba(0,0,0,0.05); padding:1px 6px; border-radius:6px; }

/* Abilities */
.radar-wrap { margin-bottom:12px; }
.ab-row { display:flex; align-items:center; gap:10px; padding:4px 0; }
.ab-n { width:52px; font-size:12px; font-weight:600; color:#374151; flex-shrink:0; }
.ab-track { flex:1; height:6px; background:#f3f4f6; border-radius:3px; overflow:hidden; }
.ab-fill { height:100%; border-radius:3px; }
.ab-v { width:24px; text-align:right; font-size:12px; font-weight:700; color:#1f2937; }

/* Detail */
.oneline { display:flex; gap:10px; align-items:flex-start; padding:12px; background:#f8fafc; border-radius:12px; }
.oneline-t { font-size:13px; color:#374151; line-height:1.6; }
.expand { text-align:center; padding:10px 0; cursor:pointer; }
.expand text { font-size:13px; color:#2563eb; font-weight:500; }
.detail { margin-top:8px; padding:14px; background:#f8fafc; border-radius:12px; }
.detail-t { font-size:13px; color:#4b5563; line-height:1.8; white-space:pre-wrap; }

/* Advice */
.advice-list { display:flex; flex-direction:column; gap:10px; }
.adv-item { border-radius:14px; padding:14px; border:1px solid rgba(0,0,0,0.04); }
.adv-emoji { font-size:22px; display:block; margin-bottom:6px; }
.adv-ttl { font-size:14px; font-weight:700; color:#1f2937; display:block; margin-bottom:4px; }
.adv-t { font-size:13px; color:#4b5563; line-height:1.6; }

/* Tips */
.tip-row { display:flex; gap:12px; align-items:flex-start; padding:10px 0; border-bottom:1px solid #f3f4f6; }
.tip-row:last-child { border-bottom:none; }
.tip-num { width:24px; height:24px; border-radius:8px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.tip-num text { color:#fff; font-size:12px; font-weight:700; }
.tip-t { font-size:13px; color:#374151; line-height:1.5; flex:1; }

/* Bottom bar */
.bbar { position:fixed; bottom:0; left:50%; transform:translateX(-50%); width:100%; max-width:480px; padding:12px 20px; padding-bottom:max(12px, env(safe-area-inset-bottom)); background:rgba(255,255,255,0.92); backdrop-filter:blur(12px); border-top:1px solid #e5e7eb; }
.bbar-btn { width:100%; padding:14px; text-align:center; border-radius:14px; border:2px solid #2563eb; background:#fff; cursor:pointer; }
.bbar-btn text { color:#2563eb; font-size:15px; font-weight:600; }
.bbar-btn:active { opacity:0.85; transform:scale(0.98); }
</style>
