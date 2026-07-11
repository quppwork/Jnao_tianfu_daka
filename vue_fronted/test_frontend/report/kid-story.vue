<template>
  <!-- ============================================ -->
  <!--  孩子版报告 — 日间童话风                    -->
  <!-- ============================================ -->
  <view class="app">
    <view class="nav">
      <view class="nav-back" @click="goBack">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#8b5cf6" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      </view>
      <text class="nav-title">天赋报告</text>
      <view class="nav-spacer"></view>
    </view>

    <scroll-view class="body" scroll-y>
      <view class="content">

        <!-- ===== 1. Hero ===== -->
        <view class="card hero-card">
          <image src="/static/学者.png" class="hero-bg-fig" mode="aspectFit" />
          <view class="hero-row">
            <image v-if="d.avatar" :src="d.avatar" class="hero-avatar" mode="aspectFill" />
            <view class="hero-text">
              <text class="hero-greet">🚀 嗨，小小探险家！</text>
              <text class="hero-name">{{ d.name }}</text>
              <text class="hero-tagline">{{ d.tagline }}</text>
            </view>
          </view>
        </view>

        <!-- ===== 2. 神奇能量 ===== -->
        <view class="card">
          <text class="sec-title">⭐ 你的神奇能量</text>
          <view v-for="a in d.energies" :key="a.name" class="eng-row">
            <view class="eng-top">
              <text class="eng-emoji">{{ a.emoji }}</text>
              <text class="eng-name">{{ a.name }}</text>
              <view class="eng-gems">
                <text v-for="g in 5" :key="g" class="eng-gem" :class="{ on: g<=a.stars }">{{ g<=a.stars ? '⭐' : '☆' }}</text>
              </view>
            </view>
            <view class="eng-bar"><view class="eng-fill" :style="{width:a.value+'%',background:a.color}"></view></view>
            <text class="eng-tip">{{ a.tip }}</text>
          </view>
        </view>

        <!-- ===== 3. 本月亮点 ===== -->
        <view class="card">
          <text class="sec-title">🏆 本月亮点时刻</text>
          <view class="ach-grid">
            <view v-for="a in d.achievements" :key="a.id" class="ach-item">
              <text class="ach-emoji">{{ a.emoji }}</text>
              <text class="ach-text">{{ a.text }}</text>
              <view class="ach-badge"><text>{{ a.badge }}</text></view>
            </view>
          </view>
        </view>

        <!-- ===== 4. 超能力雷达 ===== -->
        <view class="card">
          <text class="sec-title">🌟 你的超能力雷达</text>
          <view v-html="miniRadar" class="radar-wrap"></view>
        </view>

        <!-- ===== 5. 悄悄话 ===== -->
        <view class="card">
          <text class="sec-title">💬 老师悄悄对你说</text>
          <view v-for="(t,i) in d.bubbles" :key="i" class="bub" :class="i%2===0?'bub-l':'bub-r'">
            <text class="bub-t">{{ t }}</text>
          </view>
        </view>

        <view style="height:80px" />
      </view>
    </scroll-view>

    <view class="bbar">
      <view class="bbtn" @click="reTest"><text>🚀 开始新的探险</text></view>
    </view>
  </view>
</template>

<script setup>
import { reactive, computed } from 'vue'
const d = reactive({
  name:'小明', tagline:'你是一个充满好奇心的小天才！', avatar:'/static/xue.jpg',
  energies:[
    {name:'放大镜能量',emoji:'🔍',value:85,stars:5,color:'#8b5cf6',tip:'你能发现别人看不到的小细节'},
    {name:'合作小分队',emoji:'🤝',value:72,stars:4,color:'#3b82f6',tip:'和朋友一起让你更开心'},
    {name:'坚持不倒翁',emoji:'💪',value:68,stars:4,color:'#10b981',tip:'遇到困难也不放弃，真棒'},
    {name:'创意小火花',emoji:'✨',value:90,stars:5,color:'#f59e0b',tip:'脑子里有好多奇妙的想法'},
  ],
  achievements:[
    {id:1,emoji:'📚',text:'连续5天自己整理书包',badge:'收纳小能手 🧹'},
    {id:2,emoji:'🎨',text:'画了一幅超棒的太空画',badge:'小小艺术家 🖌️'},
    {id:3,emoji:'❤️',text:'主动帮同学解决难题',badge:'爱心小天使 👼'},
    {id:4,emoji:'🌱',text:'坚持给植物浇水7天',badge:'护花小使者 🌻'},
  ],
  bubbles:[
    '下次遇到难题时，深呼吸三次，然后像拆积木一样，一块一块解决它！',
    '每天睡前想一想今天做了什么，你会发现自己比想象中更厉害～',
  ],
})

const ro=[{x:110,y:12},{x:190,y:68},{x:162,y:158},{x:58,y:158},{x:30,y:68}]
const miniRadar = computed(()=>{
  const pts=d.energies.map((a,i)=>{const r=a.value/100,v=ro[i];return`${110+(v.x-110)*r},${110+(v.y-110)*r}`}).join(' ')
  const dots=d.energies.map((a,i)=>{const r=a.value/100,v=ro[i],x=110+(v.x-110)*r,y=110+(v.y-110)*r;return`<circle cx="${x}" cy="${y}" r="3" fill="${r>=0.6?'#8b5cf6':'#c4b5fd'}"/>`}).join('')
  const labs=[{x:110,y:4,a:'middle',n:'专注力'},{x:198,y:68,a:'start',n:'合作力'},{x:165,y:172,a:'middle',n:'坚持力'},{x:55,y:172,a:'middle',n:'想象力'},{x:20,y:68,a:'end',n:'好奇心'}]
  return `<svg viewBox="0 0 220 200" style="width:180px;height:160px;display:block;margin:0 auto;">
    <polygon points="${ro.map(v=>`${v.x},${v.y}`).join(' ')}" fill="none" stroke="#ede9fe" stroke-width="1.5"/>
    <polygon points="${pts}" fill="rgba(139,92,246,0.06)" stroke="#8b5cf6" stroke-width="1.5" stroke-linejoin="round"/>
    ${dots}${labs.map(l=>`<text x="${l.x}" y="${l.y}" font-size="10" fill="#7c6fa0" text-anchor="${l.a}" font-weight="700">${l.n}</text>`).join('')}</svg>`
})

function goBack(){}
function reTest(){}
</script>

<style scoped>
.app { min-height:100vh; max-width:480px; margin:0 auto; background:#faf8ff; font-family:PingFang SC,sans-serif; display:flex; flex-direction:column; }
.nav { display:flex; align-items:center; padding:14px 24px 0; }
.nav-back { width:36px; height:36px; border-radius:50%; background:#f3f0ff; border:1px solid #e8e0f8; display:flex; align-items:center; justify-content:center; cursor:pointer; }
.nav-title { flex:1; text-align:center; color:#1e1b2e; font-size:16px; font-weight:600; }
.nav-spacer { width:36px; }
.body { flex:1; overflow-y:auto; }
.content { padding:12px 16px 0; }

.card { background:#fff; border:1px solid #f0ebff; border-radius:20px; padding:20px; margin-bottom:12px; box-shadow:0 2px 16px rgba(139,92,246,0.04); }
.sec-title { font-size:16px; font-weight:700; color:#1e1b2e; display:block; margin-bottom:16px; }

/* Hero */
.hero-card { position:relative; overflow:hidden; }
.hero-bg-fig { position:absolute; right:-30px; top:-30px; width:170px; height:220px; opacity:0.06; pointer-events:none; object-fit:cover; object-position:top; }
.hero-row { display:flex; align-items:center; gap:14px; position:relative; z-index:1; }
.hero-avatar { width:60px; height:60px; border-radius:50%; border:3px solid #ede9fe; flex-shrink:0; }
.hero-text { flex:1; }
.hero-greet { font-size:13px; color:#8b7fbf; display:block; }
.hero-name { font-size:24px; font-weight:800; color:#1e1b2e; display:block; margin:2px 0; }
.hero-tagline { font-size:12px; color:#9089b0; line-height:1.5; display:block; }

/* Energy */
.eng-row { margin-bottom:16px; }
.eng-row:last-child { margin-bottom:0; }
.eng-top { display:flex; align-items:center; gap:8px; margin-bottom:6px; }
.eng-emoji { font-size:16px; }
.eng-name { font-size:13px; font-weight:600; color:#3d3766; flex:1; }
.eng-gems { display:flex; gap:3px; }
.eng-gem { font-size:14px; color:#ddd6f0; }
.eng-gem.on { color:#f59e0b; }
.eng-bar { height:8px; background:#f3f0ff; border-radius:4px; overflow:hidden; margin-bottom:3px; }
.eng-fill { height:100%; border-radius:4px; }
.eng-tip { font-size:11px; color:#9089b0; }

/* Achievements */
.ach-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.ach-item { background:#fdfbff; border:1px solid #f0ebff; border-radius:16px; padding:14px; text-align:center; }
.ach-emoji { font-size:28px; display:block; margin-bottom:6px; }
.ach-text { font-size:11px; color:#5b5580; line-height:1.5; display:block; }
.ach-badge { margin-top:6px; }
.ach-badge text { font-size:10px; color:#8b5cf6; font-weight:600; background:#f3f0ff; padding:2px 8px; border-radius:8px; }

/* Radar */
.radar-wrap { text-align:center; }

/* Bubbles */
.bub { max-width:82%; padding:12px 16px; border-radius:16px; margin-bottom:10px; }
.bub:last-child { margin-bottom:0; }
.bub-l { background:#f3f0ff; border-bottom-left-radius:4px; margin-right:auto; }
.bub-r { background:#fef9e7; border-bottom-right-radius:4px; margin-left:auto; }
.bub-t { font-size:13px; color:#4a4166; line-height:1.7; }

/* Bottom */
.bbar { padding:12px 20px; padding-bottom:max(12px,env(safe-area-inset-bottom)); }
.bbtn { padding:16px; text-align:center; border-radius:16px; background:linear-gradient(135deg,#8b5cf6,#6366f1); cursor:pointer; box-shadow:0 4px 20px rgba(139,92,246,0.2); }
.bbtn text { color:#fff; font-size:16px; font-weight:700; }
.bbtn:active { opacity:0.85; transform:scale(0.98); }
</style>
