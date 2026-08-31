<template>
  <!-- ============================================ -->
  <!-- 版本2: 极简 — 大留白 · 字体层次 · 精致克制 -->
  <!-- ============================================ -->
  <view class="app">
    <view class="nav">
      <view class="nav-back" @tap="goBack">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#6b7280" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      </view>
      <view class="nav-spacer"></view>
    </view>

    <scroll-view class="body" scroll-y>
      <view class="content">

        <!-- HERO: 纯文字 + 大数字 -->
        <view class="v2-hero">
          <text class="v2-label">天赋报告</text>
          <text class="v2-name" :style="{ color: d.color }">{{ d.name }}</text>
          <view class="v2-divider" :style="{ background: d.color }"></view>
          <text class="v2-tagline">{{ d.tagline }}</text>
          <view class="v2-stats">
            <view class="v2-stat">
              <text class="v2-snum" :style="{ color: d.color }">{{ d.score }}</text>
              <text class="v2-slbl">核心天赋值</text>
            </view>
            <view class="v2-stat">
              <text class="v2-snum">{{ d.stage }}</text>
              <text class="v2-slbl">成长阶段</text>
            </view>
          </view>
        </view>

        <!-- 特质: 字号变化 -->
        <view class="v2-block">
          <text class="v2-sec">天赋特质</text>
          <view class="v2-traits">
            <view v-for="t in d.traits" :key="t.id" class="v2-trait">
              <text class="v2-tlvl" :style="{ color: d.color }">0{{ t.level }}</text>
              <text class="v2-tname">{{ t.name }}</text>
            </view>
          </view>
        </view>

        <!-- 能力: 细线进度 -->
        <view class="v2-block">
          <text class="v2-sec">综合能力</text>
          <view v-for="a in d.abilities" :key="a.n" class="v2-ab">
            <text class="v2-an">{{ a.n }}</text>
            <view class="v2-abt"><view class="v2-abf" :style="{ width: a.v+'%', background: d.color }"></view></view>
          </view>
        </view>

        <!-- 解读: 引用式 -->
        <view class="v2-block">
          <text class="v2-sec">天赋解读</text>
          <view class="v2-quote">
            <text class="v2-quotemark">"</text>
            <text class="v2-qt">{{ d.oneliner }}</text>
          </view>
        </view>

        <!-- 建议: 极简列表 -->
        <view class="v2-block">
          <text class="v2-sec">给你的建议</text>
          <view class="v2-tips">
            <view v-for="(t,i) in d.tips" :key="i" class="v2-tip">
              <text class="v2-tnum" :style="{ color: d.color }">{{ String(i+1).padStart(2,'0') }}</text>
              <text class="v2-tt">{{ t }}</text>
            </view>
          </view>
        </view>

        <view style="height:60px" />
      </view>
    </scroll-view>

    <view class="v2-bbar">
      <view class="v2-bbtn" @tap="reTest"><text>重新测试</text></view>
    </view>
  </view>
</template>

<script setup>
import { reactive } from 'vue'
const d = reactive({
  color: '#1a1a2e', name: '智求者', tagline: '天生的思考者，用知识照亮前路',
  score: 85, stage: '潜力期',
  traits: [
    { id:'A', name:'智慧', level:5 }, { id:'B', name:'思辨', level:4 },
    { id:'C', name:'专注', level:4 }, { id:'D', name:'洞察', level:3 }, { id:'E', name:'求知', level:5 }
  ],
  abilities: [{ n:'逻辑力',v:92 },{ n:'专注力',v:85 },{ n:'记忆力',v:78 },{ n:'创造力',v:65 },{ n:'表达力',v:55 }],
  oneliner: '你拥有卓越的逻辑分析能力和对新知识的强烈渴求。学习不是任务，而是你探索世界的本能。',
  tips: ['每天留出30分钟深度阅读，自由探索感兴趣的知识领域','把学到的东西讲给别人听，教是最好的学','每周完成一件无需过度思考的事，培养行动直觉'],
})
function goBack(){ uni.navigateBack() }
function reTest(){ uni.redirectTo({ url:'/pages/talent/index' }) }
</script>

<style scoped>
.app { min-height:100vh; max-width:480px; margin:0 auto; background:#fafafa; font-family:-apple-system,"PingFang SC",sans-serif; display:flex; flex-direction:column; }
.nav { display:flex; align-items:center; padding:14px 24px 0; }
.nav-back { width:36px; height:36px; border-radius:50%; background:#fff; display:flex; align-items:center; justify-content:center; cursor:pointer; border:1px solid #e5e7eb; }
.nav-spacer { flex:1; }
.body { flex:1; overflow-y:auto; }
.content { padding:0 28px; }

/* Hero */
.v2-hero { padding:32px 0 40px; }
.v2-label { font-size:11px; color:#9ca3af; letter-spacing:2px; text-transform:uppercase; display:block; }
.v2-name { font-size:48px; font-weight:200; display:block; margin-top:8px; letter-spacing:-1px; }
.v2-divider { width:32px; height:2px; margin-top:16px; border-radius:1px; }
.v2-tagline { font-size:14px; color:#6b7280; line-height:1.6; display:block; margin-top:16px; }
.v2-stats { display:flex; gap:40px; margin-top:28px; }
.v2-snum { font-size:36px; font-weight:200; display:block; }
.v2-slbl { font-size:12px; color:#9ca3af; display:block; margin-top:2px; }

/* Blocks */
.v2-block { padding:24px 0; border-top:1px solid #f3f4f6; }
.v2-sec { font-size:11px; color:#9ca3af; letter-spacing:1.5px; text-transform:uppercase; display:block; margin-bottom:16px; }

/* Traits */
.v2-traits { display:flex; gap:20px; }
.v2-trait { text-align:center; }
.v2-tlvl { font-size:32px; font-weight:200; display:block; }
.v2-tname { font-size:12px; color:#6b7280; display:block; margin-top:4px; }

/* Abilities */
.v2-ab { display:flex; align-items:center; gap:12px; padding:6px 0; }
.v2-an { width:48px; font-size:12px; color:#374151; }
.v2-abt { flex:1; height:2px; background:#f3f4f6; border-radius:1px; }
.v2-abf { height:100%; border-radius:1px; }

/* Quote */
.v2-quote { position:relative; padding-left:20px; }
.v2-quotemark { font-size:48px; color:#e5e7eb; position:absolute; left:0; top:-10px; line-height:1; font-family:Georgia,serif; }
.v2-qt { font-size:15px; color:#374151; line-height:1.8; }

/* Tips */
.v2-tip { display:flex; gap:14px; align-items:flex-start; padding:10px 0; }
.v2-tnum { font-size:18px; font-weight:300; width:24px; flex-shrink:0; }
.v2-tt { font-size:14px; color:#374151; line-height:1.6; }

.v2-bbar { padding:12px 28px; padding-bottom:max(12px, env(safe-area-inset-bottom)); }
.v2-bbtn { padding:12px; text-align:center; border:1px solid #e5e7eb; border-radius:8px; cursor:pointer; }
.v2-bbtn text { font-size:14px; color:#374151; }
</style>
