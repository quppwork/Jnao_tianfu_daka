<template>
  <view class="app">
    <view class="nav">
      <view class="nav-back" @click="goBack"><text>← 返回</text></view>
      <text class="nav-title">孩子详情</text>
      <view class="nav-btn" @click="showEdit = true"><text>管理</text></view>
    </view>

    <view v-if="loading" class="empty"><text>加载中...</text></view>

    <view v-else-if="detail" class="content">
      <view class="card">
        <text class="card-title">{{ detail.nickname }}</text>
        <view v-if="detail.account_status && detail.account_status !== 'active'" class="status-banner">
          <text>已从生产环境移出 · {{ formatTime(detail.removed_at) }}</text>
        </view>
        <view class="row-line"><text class="label">登录账号</text><text class="val">{{ detail.login_name || '—' }}</text></view>
        <view class="row-line"><text class="label">年级</text><text class="val">{{ detail.grade || '—' }}</text></view>
        <view class="row-line"><text class="label">天赋类型</text><text class="val">{{ detail.talent_display || detail.talent || '—' }}</text></view>
        <view class="row-line"><text class="label">综合等级</text><text class="val">Lv.{{ detail.overall_tier || 1 }}</text></view>
        <view class="row-line"><text class="label">绑定家长</text><text class="val">{{ detail.parent_nickname || '未绑定' }} {{ detail.parent_phone ? `(${detail.parent_phone})` : '' }}</text></view>
        <view class="row-line"><text class="label">注册时间</text><text class="val">{{ formatTime(detail.created_at) }}</text></view>
      </view>

      <view class="stats">
        <view class="stat"><text class="stat-num">{{ detail.training_days || 0 }}</text><text class="stat-label">训练天数</text></view>
        <view class="stat"><text class="stat-num">{{ detail.checkins || 0 }}</text><text class="stat-label">打卡次数</text></view>
        <view class="stat"><text class="stat-num">{{ detail.active_sessions?.length || 0 }}</text><text class="stat-label">在线设备</text></view>
      </view>

      <view class="card" style="margin-top:12px;">
        <view class="row-line" style="justify-content:space-between;">
          <text class="label">🧪 天赋测试配额</text>
          <view style="display:flex;align-items:center;gap:8px;">
            <text class="val" style="font-weight:700;">剩余 {{ quotaInfo.remaining }} 次</text>
            <text class="val" style="font-size:11px;color:var(--text-dim);">(总额 {{ quotaInfo.quota }} / 已用 {{ quotaInfo.used }})</text>
          </view>
        </view>
        <view style="margin-top:10px;display:flex;align-items:center;gap:8px;">
          <text style="font-size:12px;color:var(--text-dim);white-space:nowrap;">调整：</text>
          <input v-model.number="quotaForm.add" type="number" placeholder="+加 / -减" class="inp" style="flex:1;min-width:0;" />
          <view class="btn-save" @click="addQuota"><text>确认</text></view>
        </view>
        <text style="font-size:11px;color:var(--text-dim);margin-top:4px;">正数增加，负数减少（最低 {{ Math.max(2, quotaInfo.used) }} 次）</text>
        <text v-if="quotaForm.msg" class="hint" style="margin-top:4px;">{{ quotaForm.msg }}</text>
      </view>

      <view v-if="assessments.length" class="card" style="margin-top:12px;">
        <text class="card-title">📋 天赋测评记录</text>
        <view v-for="a in assessments" :key="a.id" class="mini-row" style="padding:6px 0;border-bottom:1px solid var(--border);">
          <text class="mini-name" :style="{ color: a.is_valid ? 'var(--text)' : '#f59e0b' }">{{ a.talent_primary }}</text>
          <text class="mini-sub">{{ a.is_valid ? '✅ 有效' : '🌀 迷者不计' }} · {{ a.assessed_at || a.created_at || '—' }}</text>
        </view>
      </view>

      <view v-if="detail.training_progress?.skills" class="section">
        <text class="section-title">训练进度</text>
        <view v-for="(sk, name) in detail.training_progress.skills" :key="name" class="mini-row">
          <text class="mini-name">{{ name }}</text>
          <text class="mini-sub">等级 Lv.{{ sk.tier }} · 连续通过 {{ sk.consecutive_pass || 0 }} 次</text>
        </view>
      </view>

      <view class="section">
        <text class="section-title">训练记录（按日）</text>
        <text class="section-hint">点击条目可查看打卡明细（用时、字数、配合度等）</text>
        <view v-if="!detail.training_history_days?.length" class="hint"><text>暂无打卡记录</text></view>
        <view v-for="day in detail.training_history_days" :key="day.date" class="day-block">
          <text class="day-title">{{ day.date }}</text>
          <view
            v-for="(rec, idx) in day.records"
            :key="rec.id || idx"
            class="rec-row clickable"
            @click="openRecordDetail(rec)"
          >
            <view class="rec-main">
              <view class="rec-head">
                <text class="rec-name">{{ recordTitle(rec) }}</text>
                <view v-if="rec.attitude_pct != null" class="rec-att">
                  <text>{{ attitudeEmoji(rec.attitude_pct) }} {{ rec.attitude_pct }}%</text>
                </view>
              </view>
              <text class="rec-sub">{{ formatTime(rec.checkin_at) }} · {{ recordSummary(rec) }}</text>
            </view>
            <text class="act">详情</text>
          </view>
        </view>
      </view>

      <view class="section">
        <text class="section-title">近期训练方案</text>
        <view v-if="!detail.recent_plans?.length" class="hint"><text>暂无方案</text></view>
        <view
          v-for="p in detail.recent_plans"
          :key="p.plan_id"
          class="rec-row clickable"
          @click="openPlanDetail(p)"
        >
          <view class="rec-main">
            <text class="rec-name">{{ p.plan_date }} · {{ planStatusLabel(p.status) }}</text>
            <text class="rec-sub">{{ p.item_count || 0 }} 项 · 计划 {{ p.planned_minutes || '—' }} 分钟 · 点击查看各项</text>
          </view>
          <text class="act">详情</text>
        </view>
      </view>

      <view class="section">
        <text class="section-title">在线设备</text>
        <view v-if="!detail.active_sessions?.length" class="hint"><text>暂无活跃会话</text></view>
        <view v-for="s in detail.active_sessions" :key="s.id" class="mini-row">
          <text class="mini-name">{{ s.device_label || '设备' }}</text>
          <text class="mini-sub">最近活跃 {{ formatTime(s.last_active_at) }}</text>
        </view>
      </view>
    </view>

    <view v-if="detail?.account_status && detail.account_status !== 'active'" class="content">
      <view class="btn-restore" @click="doRestore"><text>恢复孩子账号</text></view>
    </view>

    <view v-if="showEdit" class="overlay" @click="showEdit = false">
      <view class="panel" @click.stop>
        <text class="panel-title">管理孩子</text>
        <view class="field"><input v-model="form.nickname" placeholder="昵称" class="inp" /></view>
        <view class="field"><input v-model="form.password" placeholder="新密码（留空不改）" type="password" class="inp" /></view>
        <view class="field"><input v-model="form.grade" placeholder="年级" class="inp" /></view>
        <view class="btn-primary" @click="save"><text>保存</text></view>
        <view v-if="detail?.parent_id" class="btn-warn" @click="doUnbind"><text>解绑家长</text></view>
        <view class="btn-danger" @click="confirmDelete"><text>移出生产环境</text></view>
      </view>
    </view>

    <!-- 打卡详情（复用学员历史页字段与 cardsFromRecord） -->
    <view v-if="showCheckinDetail" class="overlay" @click="closeRecordDetail">
      <view class="panel detail-panel" @click.stop>
        <view class="detail-header">
          <text class="panel-title" style="margin-bottom:0;">打卡详情</text>
          <text class="detail-close" @click="closeRecordDetail">✕</text>
        </view>
        <view v-if="detailAttitude != null" class="detail-attitude">
          <text>配合度 {{ attitudeEmoji(detailAttitude) }} {{ detailAttitude }}%</text>
        </view>
        <view v-for="(c, ci) in detailCards" :key="ci" class="detail-card-item">
          <text class="detail-card-name">{{ c.name }}{{ c.phaseBlock ? ` · 训练${c.phaseBlock}` : '' }}</text>
          <view class="detail-fields">
            <view v-if="c.time" class="detail-field"><text class="dfl">用时</text><text class="dfv">{{ c.time }}分钟</text></view>
            <view v-if="c.wordCount" class="detail-field"><text class="dfl">完成</text><text class="dfv">{{ c.wordCount }}字</text></view>
            <view v-if="c.count" class="detail-field"><text class="dfl">题数</text><text class="dfv">{{ c.count }}题</text></view>
            <view v-if="c.accuracy" class="detail-field"><text class="dfl">正确率</text><text class="dfv">{{ c.accuracy }}%</text></view>
            <view v-if="c.tool" class="detail-field"><text class="dfl">工具</text><text class="dfv">{{ c.tool }}</text></view>
            <view v-if="c.completed" class="detail-field"><text class="dfl">状态</text><text class="dfv">{{ c.completed }}</text></view>
            <view v-if="c.materialType" class="detail-field"><text class="dfl">材料</text><text class="dfv">{{ c.materialType }}</text></view>
            <view v-if="c.materialName" class="detail-field"><text class="dfl">名称</text><text class="dfv">《{{ c.materialName }}》</text></view>
            <view v-if="c.result" class="detail-field"><text class="dfl">效果</text><text class="dfv">{{ c.result }}</text></view>
            <view v-if="c.note" class="detail-field"><text class="dfl">备注</text><text class="dfv">{{ c.note }}</text></view>
            <view v-if="c.content" class="detail-field"><text class="dfl">内容</text><text class="dfv">{{ c.content }}</text></view>
          </view>
        </view>
        <view v-if="!detailCards.length" class="hint"><text>暂无卡片明细</text></view>
        <view class="btn-primary" @click="closeRecordDetail"><text>关闭</text></view>
      </view>
    </view>

    <!-- 方案详情：当日训练项列表 -->
    <view v-if="showPlanDetail" class="overlay" @click="closePlanDetail">
      <view class="panel detail-panel" @click.stop>
        <view class="detail-header">
          <text class="panel-title" style="margin-bottom:0;">方案详情</text>
          <text class="detail-close" @click="closePlanDetail">✕</text>
        </view>
        <view v-if="planDetail" class="detail-attitude">
          <text>{{ planDetail.plan_date }} · {{ planStatusLabel(planDetail.status) }} · 计划 {{ planDetail.planned_minutes || '—' }} 分钟</text>
        </view>
        <view v-for="(it, ii) in (planDetail?.items || [])" :key="it.id || ii" class="detail-card-item">
          <text class="detail-card-name">{{ it.sort_order != null ? `${it.sort_order}. ` : '' }}{{ it.title || '训练项' }}</text>
          <view class="detail-fields">
            <view v-if="it.ability_type" class="detail-field"><text class="dfl">类型</text><text class="dfv">{{ it.ability_type }}</text></view>
            <view class="detail-field"><text class="dfl">时长</text><text class="dfv">{{ it.duration_min != null ? `${it.duration_min} 分钟` : '—' }}</text></view>
            <view class="detail-field"><text class="dfl">打卡</text><text class="dfv">{{ planItemCheckinLabel(it.checkin_status) }}</text></view>
          </view>
        </view>
        <view v-if="!(planDetail?.items || []).length" class="hint"><text>该日方案暂无训练项</text></view>
        <view class="btn-primary" @click="closePlanDetail"><text>关闭</text></view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import {
  requirePageAuth,
  fetchAdminChildDetail,
  updateAdminChild,
  deleteAdminChild,
  unbindAdminChild,
  restoreAdminChild,
  fetchChildTalentQuota,
  updateChildTalentQuota,
  fetchAdminChildAssessments,
} from '@/utils/userApi.js'
import { formatDateTimeShanghai } from '@/utils/datetime.js'
import { miniCardSummary, cardsFromRecord, attitudeEmoji } from '@/utils/trainingCardDisplay.js'

const adminId = ref(null)
const childId = ref(null)
const loading = ref(true)
const detail = ref(null)
const showEdit = ref(false)
const form = ref({})
const quotaInfo = ref({ quota: 2, used: 0, remaining: 2 })
const quotaForm = ref({ add: 1, msg: '' })
const assessments = ref([])
const showCheckinDetail = ref(false)
const detailCards = ref([])
const detailAttitude = ref(null)
const showPlanDetail = ref(false)
const planDetail = ref(null)

function recordTitle(rec) {
  const cards = cardsFromRecord(rec)
  if (cards.length === 1) return cards[0].name || '训练打卡'
  if (cards.length > 1) return cards.map(c => c.name).filter(Boolean).join('、') || '训练打卡'
  return rec.ability_type || rec.item_name || rec.training_name || '训练打卡'
}

function recordSummary(rec) {
  const cards = cardsFromRecord(rec)
  if (cards.length) {
    return cards.map(c => miniCardSummary(c)).filter(Boolean).join(' · ')
  }
  if (rec.time_spent) return String(rec.time_spent)
  return '点击查看打卡明细'
}

function openRecordDetail(rec) {
  detailCards.value = cardsFromRecord(rec)
  detailAttitude.value = rec?.attitude_pct ?? null
  showCheckinDetail.value = true
}

function closeRecordDetail() {
  showCheckinDetail.value = false
  detailCards.value = []
  detailAttitude.value = null
}

function planStatusLabel(status) {
  const s = String(status || '').toLowerCase()
  if (s === 'completed') return '已完成'
  if (s === 'pending') return '进行中'
  if (s === 'stale') return '已过期'
  return status || '—'
}

function planItemCheckinLabel(status) {
  const s = String(status || '').toLowerCase()
  if (s === 'done' || s === 'completed' || s === 'checked') return '已打卡'
  if (s === 'pending') return '未打卡'
  if (s === 'skipped') return '已跳过'
  return status || '未打卡'
}

function openPlanDetail(plan) {
  planDetail.value = plan || null
  showPlanDetail.value = true
}

function closePlanDetail() {
  showPlanDetail.value = false
  planDetail.value = null
}

async function loadQuota() {
  if (!childId.value || !adminId.value) return
  try {
    const [info, hist] = await Promise.all([
      fetchChildTalentQuota(adminId.value, childId.value),
      fetchAdminChildAssessments(adminId.value, childId.value).catch(() => []),
    ])
    quotaInfo.value = info
    assessments.value = hist
  } catch (_) { /* ignore */ }
}

async function addQuota() {
  const n = parseInt(quotaForm.value.add, 10)
  if (isNaN(n) || n < 1) {
    quotaForm.value.msg = '请输入有效次数（≥1）'
    return
  }
  try {
    const res = await updateChildTalentQuota(adminId.value, childId.value, n)
    quotaInfo.value = res
    quotaForm.value.msg = `已增加 ${n} 次，剩余 ${res.remaining} 次`
  } catch (e) {
    quotaForm.value.msg = e.message || '操作失败'
  }
}

onLoad((q) => {
  childId.value = Number(q.id)
})

onMounted(async () => {
  if (!childId.value) {
    goBack()
    return
  }
  const auth = await requirePageAuth('admin')
  if (!auth.ok) return
  adminId.value = auth.userId
  await load()
})

async function load() {
  loading.value = true
  try {
    detail.value = await fetchAdminChildDetail(adminId.value, childId.value)
    form.value = { ...detail.value, password: '' }
    loadQuota()
  } catch (_) {
    uni.showToast({ title: '加载失败', icon: 'none' })
    goBack()
  } finally {
    loading.value = false
  }
}

function formatTime(iso) {
  return formatDateTimeShanghai(iso)
}

function goBack() {
  uni.navigateBack({ fail: () => uni.redirectTo({ url: '/pages/admin/index' }) })
}

async function save() {
  const c = form.value
  const body = { nickname: c.nickname, grade: c.grade || null }
  if (c.password) body.password = c.password
  try {
    await updateAdminChild(adminId.value, childId.value, body)
    showEdit.value = false
    await load()
    uni.showToast({ title: '已保存', icon: 'none' })
  } catch (_) {
    uni.showToast({ title: '保存失败', icon: 'none' })
  }
}

async function doUnbind() {
  uni.showModal({
    title: '解绑',
    content: '解绑后孩子将无法登录，直到重新绑定。确定？',
    success: async (r) => {
      if (!r.confirm) return
      try {
        await unbindAdminChild(adminId.value, childId.value)
        showEdit.value = false
        await load()
        uni.showToast({ title: '已解绑', icon: 'none' })
      } catch (_) {
        uni.showToast({ title: '操作失败', icon: 'none' })
      }
    },
  })
}

async function doRestore() {
  try {
    await restoreAdminChild(adminId.value, childId.value)
    uni.showToast({ title: '已恢复', icon: 'none' })
    await load()
  } catch (e) {
    uni.showToast({ title: e.message || '恢复失败', icon: 'none' })
  }
}

function confirmDelete() {
  uni.showModal({
    title: '移出确认',
    content: '将从生产环境移出该孩子（数据保留，可再次登录）。确定？',
    success: async (r) => {
      if (!r.confirm) return
      try {
        await deleteAdminChild(adminId.value, childId.value)
        uni.showToast({ title: '已删除', icon: 'none' })
        goBack()
      } catch (_) {
        uni.showToast({ title: '删除失败', icon: 'none' })
      }
    },
  })
}
</script>

<style scoped>
.app { min-height:100vh; background:var(--bg); max-width:480px; margin:0 auto; padding-bottom:40px; }
.nav { display:flex; align-items:center; justify-content:space-between; padding:16px; }
.nav-back text, .nav-btn text { color:var(--text-dim); font-size:13px; }
.nav-title { color:var(--text); font-size:17px; font-weight:700; }
.content { padding:0 16px; }
.card { background:var(--bg-card); border:1px solid var(--border); border-radius:14px; padding:16px; margin-bottom:16px; }
.card-title { display:block; font-size:18px; font-weight:700; color:var(--text); margin-bottom:12px; }
.row-line { display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--border); }
.row-line:last-child { border-bottom:none; }
.label { color:var(--text-dim); font-size:13px; }
.val { color:var(--text); font-size:13px; max-width:60%; text-align:right; }
.stats { display:flex; gap:8px; margin-bottom:16px; }
.stat { flex:1; background:var(--bg-card); border:1px solid var(--border); border-radius:12px; padding:12px; text-align:center; }
.stat-num { display:block; font-size:20px; font-weight:700; color:#f59e0b; }
.stat-label { display:block; font-size:11px; color:var(--text-dim); margin-top:4px; }
.section { margin-bottom:20px; }
.section-title { display:block; color:var(--text); font-size:15px; font-weight:600; margin-bottom:6px; }
.section-hint { display:block; color:var(--text-dim); font-size:11px; margin-bottom:10px; }
.hint { color:var(--text-dim); font-size:12px; padding:8px 0; }
.progress-card { background:var(--bg-card); border:1px solid var(--border); border-radius:10px; padding:12px; }
.progress-text { display:block; color:var(--text); font-size:13px; }
.progress-sub { display:block; color:var(--text-dim); font-size:12px; margin-top:4px; }
.day-block { margin-bottom:12px; }
.day-title { display:block; color:#f59e0b; font-size:13px; font-weight:600; margin-bottom:6px; }
.rec-row { display:flex; align-items:center; gap:8px; background:var(--bg-card); border:1px solid var(--border); border-radius:8px; padding:10px 12px; margin-bottom:6px; }
.rec-row.clickable { cursor:pointer; }
.rec-row.clickable:active { opacity:0.85; background:var(--accent-bg); }
.rec-main { flex:1; min-width:0; }
.rec-head { display:flex; align-items:center; justify-content:space-between; gap:8px; }
.rec-name { display:block; color:var(--text); font-size:13px; font-weight:600; }
.rec-att { flex-shrink:0; }
.rec-att text { color:#f59e0b; font-size:11px; }
.rec-sub { display:block; color:var(--text-dim); font-size:11px; margin-top:4px; line-height:1.4; }
.act { color:#f59e0b; font-size:12px; flex-shrink:0; }
.detail-panel { max-height:80vh; overflow-y:auto; }
.detail-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
.detail-close { color:var(--text-dim); font-size:16px; padding:4px 8px; cursor:pointer; }
.detail-attitude { margin-bottom:12px; padding:8px 10px; border-radius:8px; background:rgba(245,158,11,0.12); }
.detail-attitude text { color:#d97706; font-size:13px; font-weight:600; }
.detail-card-item { border:1px solid var(--border); border-radius:10px; padding:12px; margin-bottom:10px; }
.detail-card-name { display:block; color:var(--text); font-size:14px; font-weight:600; margin-bottom:8px; }
.detail-fields { display:flex; flex-direction:column; gap:6px; }
.detail-field { display:flex; align-items:flex-start; gap:8px; }
.dfl { color:var(--text-dim); font-size:12px; width:48px; flex-shrink:0; }
.dfv { color:var(--text); font-size:13px; flex:1; word-break:break-word; }
.mini-row { background:var(--bg-card); border:1px solid var(--border); border-radius:10px; padding:10px 12px; margin-bottom:6px; }
.mini-name { display:block; color:var(--text); font-size:13px; }
.mini-sub { display:block; color:var(--text-dim); font-size:11px; margin-top:2px; }
.empty { text-align:center; padding:40px; color:var(--text-dim); }
.overlay { position:fixed; inset:0; background:rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center; padding:20px; z-index:100; }
.panel { width:100%; max-width:340px; background:var(--bg-card); border-radius:14px; padding:20px; max-height:85vh; overflow-y:auto; }
.panel-title { display:block; text-align:center; font-weight:700; color:var(--text); margin-bottom:14px; }
.field { margin-bottom:10px; border:1px solid var(--border); border-radius:10px; padding:0 10px; }
.inp { width:100%; padding:12px 0; font-size:14px; color:var(--text); }
.btn-primary { background:#f59e0b; border-radius:10px; padding:12px; text-align:center; margin-top:8px; }
.btn-primary text { color:#fff; font-weight:600; }
.btn-primary:active { opacity:0.8; transform:scale(0.97); }
.btn-save { background:var(--accent); border-radius:8px; padding:7px 16px; cursor:pointer; flex-shrink:0; transition:all 0.15s; }
.btn-save text { color:#fff; font-size:13px; font-weight:600; }
.btn-save:active { opacity:0.75; transform:scale(0.96); background:#2563eb; }
.btn-warn { margin-top:8px; padding:12px; text-align:center; border-radius:10px; background:rgba(245,158,11,0.12); }
.btn-warn text { color:#d97706; font-size:13px; }
.btn-danger { margin-top:8px; padding:12px; text-align:center; border-radius:10px; background:rgba(220,38,38,0.1); }
.btn-danger text { color:#dc2626; font-size:13px; }
.status-banner { background:rgba(220,38,38,0.08); border-radius:8px; padding:8px 10px; margin-bottom:10px; }
.status-banner text { color:#dc2626; font-size:12px; }
.btn-restore { background:#f59e0b; border-radius:10px; padding:12px; text-align:center; margin:0 16px 20px; }
.btn-restore text { color:#fff; font-weight:600; font-size:14px; }
</style>
