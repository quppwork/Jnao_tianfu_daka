<template>
  <view class="tab-bar">
    <view
      v-for="tab in tabs"
      :key="tab.key"
      class="tab-item"
      :class="{ active: tab.key === active }"
      @tap="onTap(tab)"
    >
      <view class="tab-icon" :class="tab.key" aria-hidden="true"></view>
      <text class="tab-label">{{ tab.label }}</text>
    </view>
  </view>
</template>

<script setup>
import { MAIN_TABS, switchMainTab } from '../../utils/mainTabs.js'

defineProps({
  active: {
    type: String,
    required: true,
  },
})

const tabs = MAIN_TABS

function onTap(tab) {
  switchMainTab(tab.path)
}
</script>

<style scoped>
.tab-bar {
  flex-shrink: 0;
  display: flex;
  align-items: stretch;
  justify-content: space-around;
  gap: 2px;
  padding: 6px 4px calc(6px + env(safe-area-inset-bottom, 0px));
  background: var(--bg-card, #161b22);
  border-top: 1px solid var(--border, rgba(255, 255, 255, 0.08));
  max-width: var(--app-max-width, 480px);
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
  z-index: 200;
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
}
.tab-item {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  padding: 4px 2px;
  border-radius: 10px;
  cursor: pointer;
  opacity: 0.55;
  transition: opacity 0.15s, background 0.15s;
}
.tab-item.active {
  opacity: 1;
  background: var(--accent-bg, rgba(88, 166, 255, 0.12));
}
.tab-item:active {
  opacity: 0.9;
}
.tab-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-sub, #8b949e);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}
.tab-item.active .tab-label {
  color: var(--accent, #58a6ff);
}
.tab-icon {
  width: 22px;
  height: 22px;
  border-radius: 7px;
  background: var(--border, rgba(255, 255, 255, 0.12));
  position: relative;
}
.tab-item.active .tab-icon {
  background: var(--accent, #58a6ff);
}
.tab-icon::after {
  content: '';
  position: absolute;
  inset: 5px;
  border: 1.5px solid var(--bg-card, #161b22);
  border-radius: 3px;
  opacity: 0.85;
}
.tab-icon.guide::after {
  border-radius: 50%;
}
.tab-icon.train::after {
  border-left: none;
  border-top: none;
  transform: rotate(-45deg);
  inset: 6px 7px 4px;
}
.tab-icon.qa::after {
  border-radius: 2px 2px 2px 0;
}
.tab-icon.academy::after {
  inset: 4px 6px;
  border-radius: 2px;
}
.tab-icon.console::after {
  inset: 6px;
  border-radius: 1px;
  box-shadow: -3px -3px 0 -1px var(--bg-card, #161b22), 3px 3px 0 -1px var(--bg-card, #161b22);
}
[data-theme='white'] .tab-bar {
  background: #fff;
  border-top-color: #e5e7eb;
}
</style>
