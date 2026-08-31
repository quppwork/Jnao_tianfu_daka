<template>
  <!-- ============================================ -->
  <!-- 版本3: 活泼 — 大色块 · 趣味插图 · 游戏化   -->
  <!-- ============================================ -->
  <view class="app">
    <view class="nav">
      <view class="nav-back" @tap="goBack">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#6b7280" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      </view>
      <view class="nav-spacer"></view>
    </view>

    <scroll-view class="body" scroll-y>

      <!-- ===== HERO: 大色块 + 大图 ===== -->
      <view class="v3-hero" :style="{ background: 'linear-gradient(135deg,'+d.color+', '+d.color2+')' }">
        <text class="v3-label">天赋报告</text>
        <image class="v3-img" :src="d.image" mode="aspectFit" />
        <text class="v3-name">{{ d.name }}</text>
        <view class="v3-pills">
          <view class="v3-pill"><text>{{ d.type }}</text></view>
          <view class="v3-pill v3-pill-out"><text>Lv.{{ d.level }}</text></view>
        </view>
        <view class="v3-hero-stats">
          <view class="v3-hs">
            <text class="v3-hsv">{{ d.score }}</text>
            <text class="v3-hsl">天赋值</text>
          </view>
          <view class="v3-hs">
            <text class="v3-hsv">{{ d.stage }}</text>
            <text class="v3-hsl">阶段</text>
          </view>
          <view class="v3-hs">
            <text class="v3-hsv">{{ d.energy }}</text>
            <text class="v3-hsl">状态</text>
          </view>
        </view>
      </view>

      <!-- ===== CIRCLE 特质轮盘 ===== -->
      <view class="v3-section">
        <text class="v3-sec-title">⚡ 天赋特质</text>
        <view class="v3-wheel">
          <view v-for="(t,i) in d.traits" :key="t.id" class="v3-witem" :style="{ transform:'rotate('+(i*72)+'deg) translateY(-12px)' }">
            <view class="v3-winner" :style="{ transform:'rotate(-'+(i*72)+'deg)', background: d.color+'18', borderColor: d.color }">
              <text class="v3-wemoji">{{ t.emoji }}</text>
              <text class="v3-wname">{{ t.name }}</text>
              <text class="v3-wlvl">Lv.{{ t.level }}</text>
            </view>
          </view>
        </view>
      </view>

      <!-- ===== 能力进度: 粗条 + 大数字 ===== -->
      <view class="v3-section">
        <text class="v3-sec-title">📊 综合能力</text>
        <view v-for="a in d.abilities" :key="a.n" class="v3-ab">
          <view class="v3-ab-head">
            <text class="v3-abn">{{ a.n }}</text>
            <text class="v3-abv" :style="{ color: a.v>=70?d.color:a.v>=50?'#f59e0b':'#ef4444' }">{{ a.v }}</text>
          </view>
          <view class="v3-abt"><view class="v3-abf" :style="{ width:a.v+'%', background:a.v>=70?d.color:a.v>=50?'#f59e0b':'#ef4444' }"></view></view>
        </view>
      </view>

      <!-- ===== 解读: 气泡卡 ===== -->
      <view class="v3-section">
        <text class="v3-sec-title">💡 天赋解读</text>
        <view class="v3-bubble">
          <text class="v3-bt">{{ d.oneliner }}</text>
        </view>
      </view>

      <!-- ===== 建议: 2x2 网格 ===== -->
      <view class="v3-section">
        <text class="v3-sec-title">📝 给你的建议</text>
        <view class="v3-grid">
          <view class="v3-gitem" style="background:#eff6ff">
            <text class="v3-gemoji">🏆</text>
            <text class="v3-gttl">事业方向</text>
            <text class="v3-gt">{{ d.adviceCareer }}</text>
          </view>
          <view class="v3-gitem" style="background:#fef3c7">
            <text class="v3-gemoji">❤️</text>
            <text class="v3-gttl">情感关系</text>
            <text class="v3-gt">{{ d.adviceEmotion }}</text>
          </view>
          <view class="v3-gitem v3-gitem-wide" style="background:#f0fdf4">
            <text class="v3-gemoji">💪</text>
            <text class="v3-gttl">成长要点</text>
            <text class="v3-gt">{{ d.adviceGrowth }}</text>
          </view>
        </view>
      </view>

      <!-- ===== 黄金建议 ===== -->
      <view class="v3-section">
        <text class="v3-sec-title">⭐ 黄金建议</text>
        <view v-for="(t,i) in d.tips" :key="i" class="v3-tip" :style="{ borderLeftColor: d.color }">
          <text class="v3-tipnum" :style="{ color: d.color }">0{{ i+1 }}</text>
          <text class="v3-tipt">{{ t }}</text>
        </view>
      </view>

      <view style="height:80px" />
    </scroll-view>

    <view class="v3-bbar">
      <view class="v3-bbtn" :style="{ background: 'linear-gradient(135deg,'+d.color+','+d.color2+')' }" @tap="reTest">
        <text>🔄 重新测试</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { reactive } from 'vue'
const d = reactive({
  type:'学者', name:'智求者', level:5, score:85, stage:'潜力期', energy:'平稳',
  color:'#2563eb', color2:'#7c3aed',
  image:'/static/xue.jpg',
  traits:[
    { id:'A',emoji:'🧠',name:'智慧',level:5 },{ id:'B',emoji:'💭',name:'思辨',level:4 },
    { id:'C',emoji:'🎯',name:'专注',level:4 },{ id:'D',emoji:'🔍',name:'洞察',level:3 },{ id:'E',emoji:'📖',name:'求知',level:5 }
  ],
  abilities:[{ n:'逻辑力',v:92 },{ n:'专注力',v:85 },{ n:'记忆力',v:78 },{ n:'创造力',v:65 },{ n:'表达力',v:55 }],
  oneliner:'你拥有卓越的逻辑分析能力和对新知识的强烈渴求。学习不是任务，而是你探索世界的本能。',
  adviceCareer:'适合科研、教育、技术分析等需要深度思考的工作。',
  adviceEmotion:'擅长理解他人，需学习更主动地表达情感。',
  adviceGrowth:'多做"先试再说"的小练习，平衡思考与行动的比例。',
  tips:['每天留出30分钟进行深度阅读','把学到的东西讲给别人听','每周完成一件不需过度思考的事'],
})
function goBack(){ uni.navigateBack() }
function reTest(){ uni.redirectTo({ url:'/pages/talent/index' }) }
</script>

<style scoped>
.app { min-height:100vh; max-width:480px; margin:0 auto; background:#fafafa; font-family:-apple-system,"PingFang SC",sans-serif; display:flex; flex-direction:column; }
.nav { position:absolute; top:0; left:0; right:0; z-index:10; display:flex; align-items:center; padding:14px 24px 0; max-width:480px; margin:0 auto; }
.nav-back { width:36px; height:36px; border-radius:50%; background:rgba(255,255,255,0.9); display:flex; align-items:center; justify-content:center; cursor:pointer; }
.nav-spacer { flex:1; }
.body { flex:1; overflow-y:auto; }

/* Hero */
.v3-hero { padding:60px 24px 32px; text-align:center; }
.v3-label { font-size:12px; color:rgba(255,255,255,0.7); letter-spacing:2px; display:block; }
.v3-img { width:100px; height:100px; border-radius:50%; border:3px solid rgba(255,255,255,0.4); margin:14px auto; display:block; background:rgba(255,255,255,0.2); }
.v3-name { font-size:26px; font-weight:800; color:#fff; display:block; }
.v3-pills { display:flex; gap:8px; justify-content:center; margin-top:10px; }
.v3-pill { padding:3px 14px; border-radius:20px; background:rgba(255,255,255,0.2); }
.v3-pill text { color:#fff; font-size:12px; font-weight:600; }
.v3-pill-out { border:1px solid rgba(255,255,255,0.3); background:transparent; }
.v3-hero-stats { display:flex; margin-top:20px; background:rgba(255,255,255,0.15); border-radius:14px; padding:12px 0; }
.v3-hs { flex:1; text-align:center; }
.v3-hsv { font-size:22px; font-weight:800; color:#fff; }
.v3-hsl { font-size:11px; color:rgba(255,255,255,0.6); display:block; margin-top:2px; }

/* Section */
.v3-section { padding:20px 20px 0; }
.v3-sec-title { font-size:16px; font-weight:700; color:#1f2937; display:block; margin-bottom:14px; }

/* Wheel */
.v3-wheel { width:200px; height:200px; border-radius:50%; border:2px dashed #e5e7eb; margin:0 auto; position:relative; display:flex; align-items:center; justify-content:center; }
.v3-witem { position:absolute; }
.v3-winner { padding:8px 12px; border-radius:12px; border:1.5px solid; text-align:center; min-width:64px; }
.v3-wemoji { font-size:18px; display:block; }
.v3-wname { font-size:11px; font-weight:700; color:#1f2937; display:block; }
.v3-wlvl { font-size:10px; color:#9ca3af; display:block; }

/* Abilities */
.v3-ab { margin-bottom:12px; }
.v3-ab-head { display:flex; justify-content:space-between; margin-bottom:4px; }
.v3-abn { font-size:13px; font-weight:600; color:#374151; }
.v3-abv { font-size:13px; font-weight:800; }
.v3-abt { height:8px; background:#f3f4f6; border-radius:4px; overflow:hidden; }
.v3-abf { height:100%; border-radius:4px; }

/* Bubble */
.v3-bubble { background:#f8fafc; border-radius:18px; padding:18px; border:1px solid #f1f5f9; }
.v3-bt { font-size:14px; color:#374151; line-height:1.7; }

/* Grid */
.v3-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.v3-gitem { border-radius:16px; padding:14px; }
.v3-gitem-wide { grid-column:span 2; }
.v3-gemoji { font-size:22px; display:block; margin-bottom:6px; }
.v3-gttl { font-size:13px; font-weight:700; color:#1f2937; display:block; margin-bottom:4px; }
.v3-gt { font-size:12px; color:#4b5563; line-height:1.5; }

/* Tips */
.v3-tip { padding:10px 0 10px 14px; border-left:3px solid; margin-bottom:8px; }
.v3-tipnum { font-size:14px; font-weight:800; display:block; }
.v3-tipt { font-size:13px; color:#374151; line-height:1.5; display:block; margin-top:2px; }

.v3-bbar { padding:12px 20px; padding-bottom:max(12px, env(safe-area-inset-bottom)); }
.v3-bbtn { padding:16px; text-align:center; border-radius:16px; cursor:pointer; }
.v3-bbtn text { color:#fff; font-size:16px; font-weight:700; }
</style>
