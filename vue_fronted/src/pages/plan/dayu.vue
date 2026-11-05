<template>
  <dayu-frame page="plan.html" />
</template>
<script setup>
import { onBeforeUnmount, onMounted } from 'vue'
import DayuFrame from '@/components/dayu-frame/dayu-frame.vue'
import { confirmAcademicPlan, ensureChildUser } from '@/utils/userApi.js'

let confirming = false

async function onMessage(ev) {
  const data = ev?.data
  if (!data || data.type !== 'dayu-plan-confirm') return
  if (confirming) return
  confirming = true
  try {
    uni.showLoading({ title: '确认中...', mask: true })
    const uid = await ensureChildUser()
    const res = await confirmAcademicPlan(uid)
    uni.hideLoading()
    if (res?.plan_gate?.ok || res?.ok) {
      uni.showToast({ title: '规划已确认，可开始学科引导', icon: 'none', duration: 2500 })
      try {
        window.parent?.postMessage?.({ type: 'dayu-toast', title: '规划已确认' }, '*')
      } catch (_) { /* ignore */ }
    } else {
      const hint = res?.plan_gate?.student_hint || '确认未完成，请稍后重试'
      uni.showToast({ title: hint, icon: 'none', duration: 3000 })
    }
  } catch (e) {
    uni.hideLoading()
    uni.showToast({ title: e?.message || '确认失败', icon: 'none' })
  } finally {
    confirming = false
  }
}

onMounted(() => {
  if (typeof window !== 'undefined') window.addEventListener('message', onMessage)
})
onBeforeUnmount(() => {
  if (typeof window !== 'undefined') window.removeEventListener('message', onMessage)
})
</script>
