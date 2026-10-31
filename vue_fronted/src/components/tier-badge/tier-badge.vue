<template>
  <view class="tier-badge" @click.stop="goGrowth">
    <view class="tb-ic" v-html="zapSvg"></view>
    <text class="tb-txt">{{ text }}</text>
  </view>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  // 后端 /api/growth/tier 返回的对象：{ overall_tier, tier_percent, honor_level, title, next_title, need }
  tier: { type: Object, default: null },
})

// 与全站一致的线性 SVG（24 视窗、currentColor）
const zapSvg = '<svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>'

const text = computed(() => {
  const t = props.tier
  const tier = t?.overall_tier || 1
  const title = t?.title || t?.honor_level || '新学员'
  return `第${tier}段 · ${title}`
})

function goGrowth() {
  uni.navigateTo({ url: '/pages/growth/index' })
}
</script>

<style scoped>
.tier-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: var(--accent-bg, rgba(37, 99, 235, 0.12));
  border: 1px solid var(--accent, #2563eb);
  border-radius: 999px;
  padding: 4px 10px;
  cursor: pointer;
  box-sizing: border-box;
}
.tier-badge:active { opacity: 0.8; }
.tb-ic { display: flex; align-items: center; color: var(--accent, #2563eb); }
.tb-txt { font-size: 11px; font-weight: 600; color: var(--accent, #2563eb); white-space: nowrap; }
</style>
