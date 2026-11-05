<template>
  <!-- 占位：视觉底栏仍由各页自绘；此处仅启用 switchTab 保活 -->
  <view class="cg-tabbar-slot" />
</template>

<script setup>
</script>

<style scoped>
.cg-tabbar-slot {
  height: 0;
  width: 0;
  overflow: hidden;
  pointer-events: none;
}
</style>
