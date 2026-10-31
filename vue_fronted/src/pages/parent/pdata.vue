<template>
  <dayu-frame :page="framePage" />
</template>
<script setup>
import { computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { ref } from 'vue'
import DayuFrame from '@/components/dayu-frame/dayu-frame.vue'

const childId = ref('')
onLoad((q) => {
  const id = q && (q.child_id || q.childId)
  if (id) childId.value = String(id)
})

const framePage = computed(() => {
  const base = 'pdata.html?v=dash5'
  return childId.value ? `${base}&child_id=${encodeURIComponent(childId.value)}` : base
})
</script>
