<template>
  <report-talent-chat :assessment-id="assessmentId" as-page />
</template>

<script setup>
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import ReportTalentChat from '@/components/report-talent-chat/report-talent-chat.vue'

const assessmentId = ref(0)

onLoad((opts) => {
  assessmentId.value = parseInt(opts?.assessment_id || '', 10) || 0
})
</script>
