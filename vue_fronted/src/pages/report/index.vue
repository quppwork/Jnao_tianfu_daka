<template>
  <view class="app" v-if="loadError && !report">
    <view class="nav"><view class="nav-back" @click="goBack"><text class="nav-back-text">← 首页</text></view><text class="nav-title">天赋报告</text><view class="nav-spacer"></view></view>
    <view style="padding:40px 20px;text-align:center;color:#888;">{{ loadError }}</view>
  </view>
  <view class="app" v-else-if="report">
    <!-- Nav -->
    <view class="nav"><view class="nav-back" @click="goBack"><text class="nav-back-text">← 首页</text></view><text class="nav-title">天赋报告</text><view class="nav-spacer"></view></view>

    <scroll-view class="body" scroll-y>
      <view class="content">

        <!-- ══ 迷者警告 ══ -->
        <view v-if="isMizhe" class="card mizhe-warn">
          <view class="mizhe-icon">⚠️</view>
          <text class="mizhe-title">测评结果不明确</text>
          <text class="mizhe-desc">本次天赋测评未得出明确的五者天赋归属，建议重新测试以获得准确的训练方案。</text>
          <view class="btn-solid mizhe-btn" @tap="reTestFromMizhe">
            <text>🔄 重新测试</text>
          </view>
        </view>

        <!-- ══ 天赋冲突弹窗 ══ -->
        <view v-if="talentConflict" class="card conflict-warn">
          <view class="conflict-icon">🔄</view>
          <text class="conflict-title">天赋结果不一致</text>
          <text class="conflict-desc">您之前设置的天赋是「{{ currentTalent }}」，本次测评结果为「{{ report?.talent || '--' }}」。是否用新结果替换？</text>
          <view class="conflict-actions">
            <view class="btn-outline conflict-btn" @tap="handleConflictResolve('keep_old')">
              <text>保留「{{ currentTalent }}」</text>
            </view>
            <view class="btn-solid conflict-btn-new" @tap="handleConflictResolve('use_new')">
              <text>使用「{{ report?.talent || '--' }}」</text>
            </view>
          </view>
          <text v-if="resolving" class="conflict-hint">处理中...</text>
        </view>

        <!-- ══ 天赋锁定提示 ══ -->
        <view v-if="talentLocked" class="card mizhe-warn">
          <view class="mizhe-icon">🔒</view>
          <text class="mizhe-title">天赋已锁定</text>
          <text class="mizhe-desc">{{ lockMessage }}</text>
        </view>

        <!-- ══ 1. Hero ══ -->
        <view class="card hero-row">
          <view class="hero-logo">
            <image v-if="talentLogo" :src="talentLogo" mode="aspectFit" class="hero-logo-img" />
            <text v-else class="hero-logo-text">{{ report.check_talent?.[0] || report.talent?.[0] || '?' }}</text>
          </view>
          <view class="hero-info">
            <text class="hero-label">天赋者</text>
            <text class="hero-name">{{ talentDisplay }}</text>
            <text class="hero-desc">{{ attrShort }}</text>
          </view>
        </view>

        <!-- ══ 2. Stats Row ══ -->
        <view class="card stats-row">
          <view class="stat"><text class="stat-val">{{ talentVal }}</text><text class="stat-label">核心天赋值</text></view>
          <view class="stat"><text class="stat-val" :style="{ color: talentColor }">{{ talentDisplay }}</text><text class="stat-label">天赋类型</text></view>
          <view class="stat"><text class="stat-val">{{ stateName }}</text><text class="stat-label">能量状态</text></view>
        </view>

        <!-- ══ 3. Traits ══ -->
        <view class="card" v-if="traits.length">
          <text class="sec-title">天赋特质</text>
          <view class="traits-row">
            <view v-for="t in traits" :key="t.id" class="trait">
              <text class="trait-name">{{ t.name }}求{{ traitSuffix(t.name) }}</text>
              <text class="trait-grade">Lv.{{ t.grade }} · 值 {{ t.value }}</text>
            </view>
          </view>
        </view>

        <!-- ══ 4. 双重属性 ══ -->
        <view class="card" v-if="suppDesp">
          <text class="card-label">{{ talentDisplay }} · 双重属性详解</text>
          <view class="collapse-wrap" :class="{ clamped: !collapseOpen['supp'] && suppDesp.length > 120 }" v-html="suppDesp"></view>
          <text v-if="stripHtml(suppDesp).length > 120" class="collapse-btn" @tap="collapseOpen['supp']=!collapseOpen['supp']">{{ collapseOpen['supp'] ? '收起' : '展示更多' }}</text>
        </view>

        <!-- ══ 5. 天赋能力 ══ -->
        <view class="card" v-if="abilityDesc || wordsForYou">
          <text class="sec-title">天赋能力</text>
          <text class="card-label">天赋能力解读</text>
          <view v-if="abilityDesc" class="collapse-wrap" :class="{ clamped: !collapseOpen['ab'] && stripHtml(abilityDesc).length > 120 }" v-html="abilityDesc"></view>
          <text v-if="stripHtml(abilityDesc).length > 120" class="collapse-btn" @tap="collapseOpen['ab']=!collapseOpen['ab']">{{ collapseOpen['ab'] ? '收起' : '展示更多' }}</text>
          <view v-if="wordsForYou" class="words-block">
            <text class="card-label">想对你说的话</text>
            <view v-html="cleanWords"></view>
          </view>
        </view>

        <!-- ══ 6. 综合能力 + Radar ══ -->
        <view class="card" v-if="Ability.length">
          <text class="sec-title">综合能力</text>
          <!-- Radar SVG -->
          <view v-html="radarSvgHtml" class="radar-wrap"></view>
          <view v-for="ab in Ability" :key="ab.abilityID" class="ab-row">
            <text class="ab-name">{{ ab.abilityName }}</text>
            <view class="ab-bar"><view class="ab-fill" :style="{ width: Math.min(ab.value||0,100) + '%', background: talentColor }"></view></view>
            <text class="ab-val">{{ ab.value }}</text>
            <text class="ab-rating" :class="ab.value>70?'':'ab-warn'">{{ ab.value>70?'良好':ab.value>=50?'正常':'待提升' }}</text>
          </view>
          <view v-if="Ability.some(a=>a.desp)" class="ab-desp-block">
            <text class="card-label">综合能力解读</text>
            <view v-for="ab in Ability.filter(a=>a.desp)" :key="ab.abilityID" class="ab-desp">
              <text class="ab-desp-name">-{{ ab.abilityName }}-</text>
              <view v-html="cleanDesp(ab.desp, ab.abilityName)"></view>
            </view>
          </view>
        </view>

        <!-- ══ 7. 当前状态 ══ -->
        <view class="card" v-if="stateSummary">
          <text class="sec-title">当前状态</text>
          <view v-if="report.StateIcon" class="state-icon-wrap">
            <image :src="report.StateIcon" mode="heightFix" style="height:44px;" />
          </view>
          <!-- Mood SVG -->
          <view v-html="moodSvgHtml" class="mood-wrap"></view>
          <view class="state-labels">
            <text v-for="l in STATE_LABELS" :key="l" class="state-label" :style="l===stateName?{color:talentColor}:{}">{{ l }}</text>
          </view>
          <view class="collapse-wrap" :class="{ clamped: !collapseOpen['st'] && stripHtml(stateSummary).length > 120 }" v-html="stateSummary"></view>
          <text v-if="stripHtml(stateSummary).length > 120" class="collapse-btn" @tap="collapseOpen['st']=!collapseOpen['st']">{{ collapseOpen['st'] ? '收起' : '展示更多' }}</text>
        </view>

        <!-- ══ 8. 给你的建议 ══ -->
        <view class="card" v-if="advice">
          <text class="sec-title">给你的建议</text>
          <view v-if="advice.career" class="advice-item">
            <text class="card-label">事业建议</text>
            <text class="advice-text">{{ advice.career }}</text>
          </view>
          <view v-if="advice.emotion" class="advice-item">
            <text class="card-label">情感建议</text>
            <text class="advice-text">{{ advice.emotion }}</text>
          </view>
        </view>

        <!-- ══ 9. 三条黄金建议 ══ -->
        <view class="card" v-if="goldenAdvice.length">
          <text class="sec-title">三条黄金建议</text>
          <view v-for="(item,i) in goldenAdvice" :key="i" class="golden-item">
            <text class="golden-text">{{ i+1 }}. {{ item }}</text>
          </view>
        </view>

        <!-- ══ Meta ══ -->
        <view class="meta">
          <text>记录 #{{ report.id }} · {{ report.create_time }}</text>
          <text class="meta-link" @tap="openOldReport">旧版报告</text>
        </view>

        <!-- ══ Actions ══ -->
        <view class="actions">
          <view v-if="testType==='孩子' && !isBackup" class="btn-outline" @tap="reTest">深度校准（备用卷）</view>
          <view class="btn-solid" :style="{ background: talentColor }" @tap="goBack">重新测试</view>
        </view>

        <view style="height:40px;"></view>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ensureChildUser, fetchAssessmentReport } from '@/utils/userApi.js'

const STATE_LABELS = ["相争","难辨","牵制","双生","本命","孤显","无向","无神"]
const TALENT_COLORS = { "学者":"#12417A","思者":"#22C55E","行者":"#A57A1A","赢者":"#960D24","德者":"#582E1F","迷者":"#9CA3AF" }
const TALENT_LOGOS = { "学者":"/static/xue.jpg","思者":"/static/si.jpg","赢者":"/static/ying.jpg","德者":"/static/de.jpg","行者":"/static/xing.jpg" }

const report = ref(null)
const testType = ref('成人')
const isBackup = ref(false)
const collapseOpen = ref({})
const loadError = ref('')

onMounted(async () => {
  try {
    const pages = getCurrentPages()
    const page = pages[pages.length - 1]
    const assessmentId = page?.options?.assessment_id
    const uid = await ensureChildUser()

    // 冲突检测
    if (page?.options?.talent_conflict === '1') {
      talentConflict.value = true
      currentTalent.value = decodeURIComponent(page?.options?.current_talent || '')
    }
    if (page?.options?.talent_locked === '1') {
      talentLocked.value = true
      lockMessage.value = decodeURIComponent(page?.options?.lock_message || '天赋已锁定')
    }

    if (!assessmentId) {
      loadError.value = '缺少测评记录 ID'
      return
    }
    const json = await fetchAssessmentReport(uid, assessmentId)
    if (json.code !== 1) throw new Error('报告加载失败')
    report.value = json.data
  } catch (e) {
    loadError.value = e.message || '报告加载失败'
    console.error('报告加载失败:', e)
  }
})

const talentConflict = ref(false)
const currentTalent = ref('')
const talentLocked = ref(false)
const lockMessage = ref('')
const resolving = ref(false)

async function handleConflictResolve(action) {
  resolving.value = true
  try {
    const uid = await ensureChildUser()
    const { resolveTalentConflict } = await import('@/utils/userApi.js')
    await resolveTalentConflict(uid, action)
    talentConflict.value = false
    uni.showToast({ title: action === 'use_new' ? '已更新天赋' : '已保留原天赋', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '操作失败', icon: 'none' })
  }
  resolving.value = false
}

function reTestFromMizhe() {
  uni.redirectTo({ url: '/pages/talent/index' })
}
function goBack() {
  uni.redirectTo({ url: '/pages/index' })
}

// Computed
const isMizhe = computed(() => {
  const t = report.value?.talent || report.value?.talent_primary || ''
  return t === '迷者'
})
const talentColor = computed(() => TALENT_COLORS[report.value?.talent] || '#171717')
const talentLogo = computed(() => TALENT_LOGOS[report.value?.talent] || '')
const talentDisplay = computed(() => {
  const ct = report.value?.check_talent
  if (ct && ct.length >= 2) return ct[0] + '偏' + ct[1]
  return report.value?.talent || '--'
})
const stateName = computed(() => report.value?.results?.State?.name || '--')
const talentVal = computed(() => report.value?.results?.Talent?.value || report.value?.results?.State?.id || '--')
const attrShort = computed(() => stripHtml(report.value?.results?.Attribute?.desp || '').slice(0, 80))
const suppDesp = computed(() => report.value?.results?.Attribute?.SupplementDesp || '')
const Ability = computed(() => Array.isArray(report.value?.results?.Ability) ? report.value.results.Ability : [])

const traits = computed(() => {
  const A = report.value?.results?.Attribute
  if (!A?.attributeList) return []
  const list = [...A.attributeList]
  if (A.attribute && !list.find(a=>a.id===A.attribute.id)) list.push(A.attribute)
  return list.sort((a,b)=>["A","B","C","D","E"].indexOf(a.id)-["A","B","C","D","E"].indexOf(b.id))
})

function traitSuffix(name) {
  const m = {"学者":"智","思者":"思","行者":"行","赢者":"赢","德者":"德","迷者":"知"}
  return m[name]||'知'
}

// Parse talent.desp
const parsedTalent = computed(() => {
  const html = report.value?.results?.Talent?.desp || ''
  if (!html) return { abilityDesc:'', wordsForYou:'', goldenAdvice:[] }
  const wordsIdx = html.search(/想对你说的话/)
  const goldenIdx = html.search(/三条黄金建议/)
  let abilityDesc = '', wordsForYou = ''
  const goldenAdvice = []
  if (wordsIdx >= 0) {
    abilityDesc = html.slice(0, wordsIdx).replace(/<p[^>]*>\s*<strong>【?天赋能力解读】?<\/strong>\s*<\/p>/gi,'').trim()
    if (goldenIdx >= 0) {
      wordsForYou = html.slice(wordsIdx, goldenIdx).replace(/<[^>]*>\s*想对你说的话\s*<\/[^>]*>/gi,'').trim()
      const goldenBlock = stripHtml(html.slice(goldenIdx)).replace(/三条黄金建议[：:]?/g,'').trim()
      goldenBlock.split(/(?=\d+\.)/).filter(Boolean).forEach(item => {
        const c = item.replace(/^\d+\.\s*/,'').trim()
        if (c) goldenAdvice.push(c)
      })
    } else {
      wordsForYou = html.slice(wordsIdx).replace(/<p[^>]*>\s*<strong>想对你说的话<\/strong>\s*<\/p>/gi,'').trim()
    }
  } else {
    abilityDesc = html.replace(/<p[^>]*>\s*<strong>【?天赋能力解读】?<\/strong>\s*<\/p>/gi,'').trim()
  }
  return { abilityDesc, wordsForYou, goldenAdvice }
})
const abilityDesc = computed(() => parsedTalent.value.abilityDesc)
const wordsForYou = computed(() => parsedTalent.value.wordsForYou)
const goldenAdvice = computed(() => parsedTalent.value.goldenAdvice)
const cleanWords = computed(() => stripHtml(wordsForYou.value).replace(/\n/g,'<br>'))

// Parse state
const stateSummary = computed(() => {
  const d = report.value?.results?.State?.desp || ''
  if (!d) return ''
  const idx = d.search(/给你的建议|事业建议|情感建议/)
  return idx > 0 ? d.slice(0, idx).trim() : d
})
const advice = computed(() => {
  const d = report.value?.results?.State?.desp || ''
  if (!d) return null
  const t = stripHtml(d)
  const cm = t.match(/事业建议[：:]\s*(.+?)(?=情感建议|给你的建议|$)/s)
  const em = t.match(/情感建议[：:]\s*(.+?)(?=事业建议|给你的建议|$)/s)
  return { career: cm?.[1]?.trim()||'', emotion: em?.[1]?.trim()||'' }
})

function stripHtml(h) {
  if (!h) return ''
  return h.replace(/<[^>]+>/g,'').replace(/&nbsp;/g,' ').replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').trim()
}
function cleanDesp(desp, name) {
  const plain = stripHtml(desp)
  return plain.replace(new RegExp(`^(\\s*-?\\s*${name}\\s*-?\\s*)+`,'i'),'').trim().replace(/\n/g,'<br>')
}

// ── Radar Chart SVG ──
const RADAR_OUTER = [{x:65,y:8},{x:118,y:45},{x:98,y:105},{x:32,y:105},{x:12,y:45}]
const RADAR_CX = 65, RADAR_CY = 61.6
const RADAR_LABELS = ['协调力','执行力','公信力','领导力','创新力']
const RADAR_LABEL_POS = [{x:65,y:3,a:'middle'},{x:128,y:48,a:'start'},{x:100,y:113,a:'middle'},{x:30,y:113,a:'middle'},{x:-2,y:48,a:'end'}]
function radarVertices(scale) {
  return RADAR_OUTER.map(v => `${RADAR_CX+(v.x-RADAR_CX)*scale},${RADAR_CY+(v.y-RADAR_CY)*scale}`).join(' ')
}

// ── Mood SVG ──
const radarSvgHtml = computed(() => {
  const sorted = RADAR_LABELS.map(name => Ability.value.find(d => d.abilityName === name) || { abilityName: name, value: 0 })
  const dataPts = sorted.map((d,i) => {
    const r = Math.min(100,Math.max(0,d.value))/100
    const v = RADAR_OUTER[i]
    return `${RADAR_CX+(v.x-RADAR_CX)*r},${RADAR_CY+(v.y-RADAR_CY)*r}`
  }).join(' ')
  const dots = sorted.map((d,i) => {
    const r = Math.min(100,Math.max(0,d.value))/100
    const v = RADAR_OUTER[i]
    const x = RADAR_CX+(v.x-RADAR_CX)*r, y = RADAR_CY+(v.y-RADAR_CY)*r
    return `<circle cx="${x}" cy="${y}" r="3" fill="${r>=0.5?'#c9d1d9':'#8b949e'}"/>`
  }).join('')
  const labels = RADAR_LABEL_POS.map((l,i) =>
    `<text x="${l.x}" y="${l.y}" font-size="10" fill="#1f2937" text-anchor="${l.a}" font-weight="600">${RADAR_LABELS[i]}</text>`
  ).join('')
  return `<svg viewBox="-10 -5 150 130" style="display:block;width:220px;height:auto;margin:0 auto;overflow:visible;">
    <polygon points="${radarVertices(1)}" fill="none" stroke="#30363d" stroke-width="1"/>
    <polygon points="${radarVertices(0.75)}" fill="none" stroke="#30363d" stroke-width="1"/>
    <polygon points="${radarVertices(0.5)}" fill="none" stroke="#30363d" stroke-width="1"/>
    <polygon points="${dataPts}" fill="rgba(128,128,128,0.06)" stroke="#8b949e" stroke-width="1.5" stroke-linejoin="round"/>
    ${dots}${labels}</svg>`
})

const moodSvgHtml = computed(() => {
  const px = moodPx(stateName.value)
  return `<svg width="180" height="44" viewBox="0 0 180 44" style="display:block;margin:0 auto;">
    <rect x="10" y="30" width="160" height="4" rx="2" fill="#30363d"/>
    <rect x="10" y="30" width="50" height="4" rx="2" fill="#5c4030"/>
    <rect x="90" y="30" width="50" height="4" rx="2" fill="#3a4a5c"/>
    <rect x="140" y="30" width="30" height="4" rx="2" fill="#3a5c3a"/>
    <circle cx="${px}" cy="32" r="6" fill="#a07050" stroke="#fff" stroke-width="2"/>
    <text x="35" y="22" font-size="7" fill="#8b949e" text-anchor="middle">低迷</text>
    <text x="90" y="14" font-size="7" fill="#8b949e" text-anchor="middle">平稳</text>
    <text x="140" y="22" font-size="7" fill="#8b949e" text-anchor="middle">高涨</text>
  </svg>`
})

function moodPx(name) {
  const idx = STATE_LABELS.indexOf(name)
  return idx >= 0 ? 155 - idx * (110/7) : 100
}

function reTest() { goBack() }
function openOldReport() {
  const id = report.value?.id
  if (id) {
    // #ifdef H5
    window.open(`https://m.jnao.com/h5/parent_test_result.html?id=${id}`, '_blank')
    // #endif
  }
}
</script>

<style scoped>
.app { min-height:100vh; max-width:480px; margin:0 auto; background:#fafafa; font-family:-apple-system,"PingFang SC",sans-serif; display:flex; flex-direction:column; }
.nav { display:flex; align-items:center; padding:14px 24px 0; }
.nav-back { padding:6px 12px; border-radius:18px; background:var(--bg-card); display:flex; align-items:center; cursor:pointer; }
.nav-back-text { color:var(--accent); font-size:13px; }
.nav-title { flex:1; text-align:center; color:var(--text); font-size:16px; font-weight:600; }
.nav-spacer { width:36px; }
.body { flex:1; overflow-y:auto; }
.content { padding:16px 20px 0; }

.card { background:var(--bg-card); border-radius:16px; padding:16px; margin-bottom:10px; border-bottom:1px solid var(--border); }

/* Hero */
.hero-row { display:flex; gap:12px; align-items:center; }
.hero-logo { width:80px; height:80px; flex-shrink:0; }
.hero-logo-img { width:100%; height:100%; }
.hero-logo-text { font-size:32px; font-weight:700; color:#9ca3af; }
.hero-info { flex:1; min-width:0; }
.hero-label { font-size:11px; color:var(--text-dim); display:block; margin-bottom:2px; }
.hero-name { font-size:20px; font-weight:700; color:var(--text); display:block; }
.hero-desc { font-size:12px; color:var(--text-dim); line-height:1.5; display:block; margin-top:4px; }

/* Stats */
.stats-row { display:flex; }
.stat { flex:1; text-align:center; padding:10px 0; border-right:1px solid var(--border); }
.stat:last-child { border-right:none; }
.stat-val { font-size:20px; font-weight:700; color:var(--text); display:block; }
.stat-label { font-size:11px; color:var(--text-dim); display:block; margin-top:2px; }

/* Traits */
.sec-title { font-size:15px; font-weight:700; color:var(--text); display:block; margin-bottom:10px; }
.traits-row { display:flex; }
.trait { flex:1; text-align:center; padding:8px 2px; border-right:1px solid var(--border); }
.trait:last-child { border-right:none; }
.trait-name { font-size:11px; font-weight:600; color:var(--text); display:block; }
.trait-grade { font-size:9px; color:var(--text-dim); display:block; margin-top:2px; }

.card-label { font-size:12px; font-weight:600; color:var(--text-dim); text-transform:uppercase; letter-spacing:0.4px; display:block; margin-bottom:6px; }
.words-block { margin-top:12px; }

/* Ability */
.ab-row { display:flex; align-items:center; gap:8px; padding:4px 0; }
.ab-name { width:52px; font-size:12px; font-weight:600; color:var(--text); flex-shrink:0; }
.ab-bar { flex:1; height:4px; background:var(--bg-input); border-radius:2px; overflow:hidden; }
.ab-fill { height:100%; border-radius:2px; transition:width 0.5s; }
.ab-val { width:24px; text-align:right; font-size:12px; font-weight:600; color:var(--text); }
.ab-rating { width:36px; text-align:right; font-size:10px; color:var(--text-dim); }
.ab-warn { color:#c06040; }
.ab-desp-block { margin-top:12px; }
.ab-desp { margin-bottom:8px; }
.ab-desp-name { font-size:12px; font-weight:600; color:var(--text); display:block; margin-bottom:2px; }

/* State */
.state-labels { display:flex; justify-content:space-between; padding:8px 0; }
.state-label { font-size:12px; font-weight:600; color:var(--text-dim); }

/* Advice */
.advice-item { padding:10px 0; border-top:1px solid var(--border); }
.advice-text { font-size:13px; color:var(--text); line-height:1.6; display:block; }

/* Golden */
.golden-item { padding:8px 0; border-bottom:1px solid var(--border); }
.golden-item:last-child { border-bottom:none; }
.golden-text { font-size:13px; font-weight:600; color:var(--text); line-height:1.5; display:block; }

/* Meta */
.meta { text-align:center; padding:12px; font-size:12px; color:var(--text-dim); display:flex; align-items:center; justify-content:center; gap:12px; }
.meta-link { color:var(--accent); text-decoration:underline; cursor:pointer; }

/* Actions */
.actions { display:flex; flex-direction:column; gap:10px; padding:0 0 40px; align-items:center; }
.btn-outline { width:100%; max-width:300px; padding:12px; text-align:center; border:1px solid #fbbf24; border-radius:14px; background:rgba(251,191,36,0.06); color:#f59e0b; font-size:15px; font-weight:500; cursor:pointer; }
.btn-solid { width:100%; max-width:300px; padding:12px; text-align:center; border-radius:14px; color:#fff; font-size:15px; font-weight:500; cursor:pointer; }
.btn-outline:active, .btn-solid:active { opacity:0.8; }

.radar-wrap, .state-icon-wrap { text-align:center; padding-bottom:8px; }
.mood-wrap { text-align:center; }

/* Collapsible HTML text styles */
.collapse-wrap { font-size:12px; color:var(--text-dim); line-height:1.7; }
.collapse-wrap.clamped { display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
.collapse-btn { width:100%; text-align:center; font-size:12px; color:var(--text-dim); padding:6px 0; cursor:pointer; display:block; }

/* Conflict dialog */
.conflict-warn { background:linear-gradient(135deg,rgba(88,166,255,0.08),rgba(99,102,241,0.05)); border:1.5px solid rgba(88,166,255,0.35); text-align:center; padding:20px 16px; }
.conflict-icon { font-size:36px; display:block; margin-bottom:8px; }
.conflict-title { color:#3b82f6; font-size:18px; font-weight:700; display:block; margin-bottom:6px; }
.conflict-desc { color:var(--text-dim); font-size:13px; line-height:1.6; display:block; margin-bottom:16px; }
.conflict-actions { display:flex; gap:10px; justify-content:center; }
.conflict-btn { width:auto; padding:10px 20px; border:1px solid var(--border); border-radius:14px; cursor:pointer; }
.conflict-btn text { color:var(--text); font-size:14px; }
.conflict-btn-new { width:auto; padding:10px 20px; background:linear-gradient(135deg,var(--accent),#3b8bff); }
.conflict-hint { color:var(--text-dim); font-size:12px; margin-top:10px; display:block; }

/* Mizhe (迷者) warning */
.mizhe-warn { background:linear-gradient(135deg,rgba(255,193,7,0.08),rgba(255,152,0,0.05)); border:1.5px solid rgba(255,152,0,0.35); text-align:center; padding:20px 16px; }
.mizhe-icon { font-size:36px; display:block; margin-bottom:8px; }
.mizhe-title { color:#e67e00; font-size:18px; font-weight:700; display:block; margin-bottom:6px; }
.mizhe-desc { color:var(--text-dim); font-size:13px; line-height:1.6; display:block; margin-bottom:14px; }
.mizhe-btn { background:linear-gradient(135deg,#f59e0b,#e67e00); display:inline-block; width:auto; padding:10px 28px; margin:0 auto; }
</style>
