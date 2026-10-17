<template>
  <dayu-frame :page="htmlPage" :back-path="backPath" />
</template>
<script setup>
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import DayuFrame from '@/components/dayu-frame/dayu-frame.vue'
import { studentHomeUrl } from '@/utils/uiSkin.js'
import {
  ensureReportUser,
  fetchAssessmentReport,
  fetchLatestAssessment,
  fetchProfile,
} from '@/utils/userApi.js'

/** 满 18 岁看成人巨幕报告，未满 18 岁看儿童报告 */
const htmlPage = ref('report-kid.html?lock=1&v=rpt2')
const backPath = ref('')

const TALENT_KEY = {
  学者: 'study',
  思者: 'think',
  行者: 'act',
  德者: 'virtue',
  赢者: 'win',
}

function resolveBackPath(from, isAdult) {
  const f = String(from || '').toLowerCase()
  if (f === 'training') return '/pages/training/dayu'
  if (f === 'onboarding') return studentHomeUrl()
  if (f === 'hub' || f === 'talent') return '/pages/talent/hub'
  return isAdult ? '/pages/talent/hub' : '/pages/training/dayu'
}

function readAge(profile) {
  const pj = profile?.profile_json && typeof profile.profile_json === 'object'
    ? profile.profile_json
    : {}
  const learner = pj.learner && typeof pj.learner === 'object' ? pj.learner : {}
  const raw = profile?.age ?? pj.age ?? learner.age
  const n = parseInt(raw, 10)
  return Number.isFinite(n) && n > 0 ? n : null
}

function modeFromQuery(opts) {
  const mode = String(opts?.mode || '').toLowerCase()
  const type = String(opts?.type ?? '')
  if (mode === 'adult' || mode === 'adu' || mode === '0' || type === '0') return true
  if (mode === 'kid' || mode === 'child' || mode === '1' || type === '1') return false
  return null
}

onLoad(async (opts) => {
  let isAdult = modeFromQuery(opts)
  let talent = ''
  let name = ''
  let date = ''
  let assessmentId = 0
  try {
    const uid = await ensureReportUser()
    const profile = await fetchProfile(uid).catch(() => null)
    const age = readAge(profile)
    if (age != null) isAdult = age >= 18
    name = String(profile?.nickname || profile?.real_name || '').trim()
    const aid = parseInt(opts?.assessment_id || '', 10)
    const report = aid
      ? await fetchAssessmentReport(uid, aid).catch(() => null)
      : await fetchLatestAssessment(uid).catch(() => null)
    talent = String(report?.talent_primary || report?.data?.talent || '').trim()
    const testedAt = report?.assessed_at || ''
    if (testedAt) date = String(testedAt).slice(0, 10)
    if (age == null && isAdult == null && report && report.test_type != null) {
      isAdult = Number(report.test_type) === 0
    }
    assessmentId = Number(report?.assessment_id || report?.id || aid || 0)
  } catch (_) { /* 拉不到档案时按入口参数 */ }
  if (isAdult == null) isAdult = false
  const key = TALENT_KEY[talent] || talent || ''
  const q = new URLSearchParams({ lock: '1', v: 'rpt3' })
  if (key) q.set('talent', key)
  if (name) q.set('name', name)
  if (date) q.set('date', date)
  if (assessmentId > 0) q.set('assessment_id', String(assessmentId))
  htmlPage.value = `${isAdult ? 'report-v3.html' : 'report-kid.html'}?${q.toString()}`
  backPath.value = resolveBackPath(opts?.from, isAdult)
})
</script>
