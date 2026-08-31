<template>
  <view class="app">
    <view class="nav">
      <view class="nav-back" @click="goBack">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#8b5cf6" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      </view>
      <text class="nav-title">我的报告</text>
      <view class="nav-spacer"></view>
    </view>

    <!-- 加载中 -->
    <view v-if="loading" class="loading-wrap">
      <view class="loading-spinner"></view>
      <text class="loading-text">报告加载中...</text>
    </view>

    <!-- 加载失败 -->
    <view v-else-if="loadError" style="padding:40px 20px;text-align:center;color:#9089b0;">{{ loadError }}</view>

    <!-- 报告内容 -->
    <scroll-view v-else-if="report" class="body" scroll-y>
      <view class="content">

        <!-- 迷者/冲突/锁 提示 -->
        <view v-if="isMizhe" class="card" style="background:#fef3c7;border-color:#fde68a;text-align:center;">
          <text style="font-size:32px;display:block;">⚠️</text>
          <text style="font-size:15px;font-weight:700;color:#92400e;display:block;margin:8px 0;">结果不太明确哦</text>
          <text style="font-size:12px;color:#a16207;">重新测一次吧，会更准确！</text>
        </view>

        <!-- ===== 1. Hero ===== -->
        <view class="card hero-card">
          <image src="/static/学者.png" mode="aspectFit" style="position:absolute;right:8px;top:-20px;width:140px;height:200px;opacity:0.3;pointer-events:none;z-index:0;" />
          <view class="hero-row">
            <image v-if="talentLogo" :src="talentLogo" class="hero-avatar" mode="aspectFill" />
            <view class="hero-text">
              <text class="hero-greet">🚀 嗨，小小探险家！</text>
              <text class="hero-name">{{ talentDisplay }}</text>
              <text class="hero-tagline">{{ kidTagline }}</text>
            </view>
          </view>
        </view>

        <!-- ===== 2. 神奇能量 ===== -->
        <view class="card" v-if="Ability.length">
          <text class="sec-title">⭐ 你的神奇能量</text>
          <view v-for="a in kidAbilities" :key="a.id" class="eng-row">
            <view class="eng-top">
              <text class="eng-emoji">{{ a.emoji }}</text>
              <text class="eng-name">{{ a.label }}</text>
              <view class="eng-gems">
                <text v-for="g in 5" :key="g" class="eng-gem" :class="{ on: g <= a.stars }">{{ g <= a.stars ? '⭐' : '☆' }}</text>
              </view>
            </view>
            <view class="eng-bar"><view class="eng-fill" :style="{ width: Math.min(a.value||0,100) + '%', background: a.color }"></view></view>
            <text class="eng-tip">{{ a.tip }}</text>
          </view>
        </view>

        <!-- ===== 3. 超能力雷达 ===== -->
        <view class="card" v-if="Ability.length">
          <text class="sec-title">🌟 超能力雷达</text>
          <view v-html="kidRadarSvg" class="radar-wrap"></view>
        </view>

        <!-- ===== 4. 悄悄话 ===== -->
        <view class="card" v-if="wordsForYou || goldenAdvice.length">
          <text class="sec-title">💬 老师悄悄对你说</text>
          <view class="bub bub-l">
            <text class="bub-t" v-html="cleanWords"></text>
          </view>
          <view v-for="(t,i) in goldenAdvice.slice(0,3)" :key="i" class="bub" :class="(i+1)%2===0?'bub-l':'bub-r'">
            <text class="bub-t">{{ t }}</text>
          </view>
        </view>

        <view style="height:80px" />
      </view>
    </scroll-view>

    <!-- 底部按钮 -->
    <view v-if="report" class="bbar">
      <view class="bbtn" @click="goBack"><text>🚀 开始新的探险</text></view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ensureChildUser, fetchAssessmentReport, fetchProfile, saveProfile } from '@/utils/userApi.js'

const STATE_LABELS = ["相争","难辨","牵制","双生","本命","孤显","无向","无神"]
const TALENT_COLORS = { "学者":"#12417A","思者":"#22C55E","行者":"#A57A1A","赢者":"#960D24","德者":"#582E1F","迷者":"#9CA3AF" }
const TALENT_LOGOS = { "学者":"/static/xue.jpg","思者":"/static/si.jpg","赢者":"/static/ying.jpg","德者":"/static/de.jpg","行者":"/static/xing.jpg" }
const TALENT_FIGS = { "学者":"/static/学者.png","思者":"/static/思者.png","赢者":"/static/赢者.png","德者":"/static/德者.png","行者":"/static/行者.png" }

const loading = ref(true), report = ref(null), testType = ref('成人')
const collapseOpen = ref({}), loadError = ref('')
const USE_MOCK = true
const fromOnboarding = ref(false), studentTypeFromOb = ref('new')
const themeVersion = ref(0)
const isLightTheme = computed(() => { void themeVersion.value; return document.documentElement.getAttribute('data-theme')==='white' })
let themeObserver = null, prevTheme = null

onMounted(async () => {
  prevTheme = document.documentElement.getAttribute('data-theme') || null
  document.documentElement.setAttribute('data-theme', 'white')
  try {
    const pages = getCurrentPages()
    const page = pages[pages.length - 1]
    const assessmentId = page?.options?.assessment_id
    fromOnboarding.value = page?.options?.from === 'onboarding'
    studentTypeFromOb.value = page?.options?.student_type || 'new'
    const uid = await ensureChildUser()
    if (page?.options?.talent_conflict === '1') { talentConflict.value = true; currentTalent.value = decodeURIComponent(page?.options?.current_talent || '') }
    if (page?.options?.talent_locked === '1') { talentLocked.value = true; lockMessage.value = decodeURIComponent(page?.options?.lock_message || '天赋已锁定') }
    if (USE_MOCK) { report.value = getMockData(); loading.value = false; return }
    if (!assessmentId) { loadError.value = '缺少测评记录 ID'; return }
    const json = await fetchAssessmentReport(uid, assessmentId)
    if (json.code !== 1) throw new Error('报告加载失败')
    report.value = json.data
    themeObserver = new MutationObserver(() => { themeVersion.value++ })
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
  } catch (e) { loadError.value = e.message || '报告加载失败' }
  finally { loading.value = false }
})

const talentConflict = ref(false), currentTalent = ref('')
const talentLocked = ref(false), lockMessage = ref(''), resolving = ref(false)
async function handleConflictResolve(action) {
  resolving.value = true
  try { const uid = await ensureChildUser(); const { resolveTalentConflict } = await import('@/utils/userApi.js'); await resolveTalentConflict(uid, action); talentConflict.value = false }
  catch (e) { uni.showToast({ title: e.message || '操作失败', icon: 'none' }) }
  resolving.value = false
}
function reTestFromMizhe() { uni.redirectTo({ url: '/pages/talent/index' }) }
async function goBack() {
  if (fromOnboarding.value) {
    const uid = await ensureChildUser()
    let ob = {}
    try { const p = await fetchProfile(uid); ob = p.profile_json?.onboarding || {} } catch (_) {}
    const st = studentTypeFromOb.value || ob.student_type || 'new'
    const patch = { ...ob, student_type: st, talent_test_done: true, talent_unknown: true }
    if (st !== 'returning') patch.completed_at = new Date().toISOString()
    try { await saveProfile(uid, { profile_json: { onboarding: patch } }) } catch (_) {}
    if (st === 'returning') { uni.redirectTo({ url: '/pages/login/onboarding/index?resume=4' }) }
    else { uni.redirectTo({ url: '/pages/index' }) }
    return
  }
  uni.redirectTo({ url: '/pages/index' })
}

// Computed
const isMizhe = computed(() => { const t = report.value?.talent || report.value?.talent_primary || ''; return t === '迷者' })
const talentColor = computed(() => TALENT_COLORS[report.value?.talent] || '#171717')
const talentLogo = computed(() => TALENT_LOGOS[report.value?.talent] || '')
const talentDisplay = computed(() => {
  const ct = report.value?.check_talent
  if (!ct) return report.value?.talent || '--'
  if (Array.isArray(ct) && ct.length >= 2) return String(ct[0]).replace(/者$/,'')+'偏'+String(ct[1]).replace(/者$/,'')
  if (typeof ct === 'string' && ct.includes('偏')) { const p=ct.split('偏'); return p[0].replace(/者$/,'')+'偏'+p[1].replace(/者$/,'') }
  return report.value?.talent || '--'
})
const stateName = computed(() => report.value?.results?.State?.name || '--')
const talentVal = computed(() => report.value?.results?.Talent?.value || report.value?.results?.State?.id || '--')
const attrShort = computed(() => stripHtml(report.value?.results?.Attribute?.desp || '').slice(0, 80))
const Ability = computed(() => Array.isArray(report.value?.results?.Ability) ? report.value.results.Ability : [])

const parsedTalent = computed(() => {
  const html = report.value?.results?.Talent?.desp || ''
  if (!html) return { abilityDesc:'', wordsForYou:'', goldenAdvice:[] }
  const wordsIdx = html.search(/想对你说的话/), goldenIdx = html.search(/三条黄金建议/)
  let abilityDesc='', wordsForYou=''; const goldenAdvice=[]
  if (wordsIdx >= 0) {
    abilityDesc = html.slice(0, wordsIdx).replace(/<p[^>]*>\s*<strong>【?天赋能力解读】?<\/strong>\s*<\/p>/gi,'').trim()
    if (goldenIdx >= 0) {
      wordsForYou = html.slice(wordsIdx, goldenIdx).replace(/<[^>]*>\s*想对你说的话\s*<\/[^>]*>/gi,'').trim()
      const goldenBlock = stripHtml(html.slice(goldenIdx)).replace(/三条黄金建议[：:]?/g,'').trim()
      goldenBlock.split(/(?=\d+\.)/).filter(Boolean).forEach(item => { const c = item.replace(/^\d+\.\s*/,'').trim(); if (c) goldenAdvice.push(c) })
    } else { wordsForYou = html.slice(wordsIdx).replace(/<p[^>]*>\s*<strong>想对你说的话<\/strong>\s*<\/p>/gi,'').trim() }
  } else { abilityDesc = html.replace(/<p[^>]*>\s*<strong>【?天赋能力解读】?<\/strong>\s*<\/p>/gi,'').trim() }
  return { abilityDesc, wordsForYou, goldenAdvice }
})
const wordsForYou = computed(() => parsedTalent.value.wordsForYou)
const goldenAdvice = computed(() => parsedTalent.value.goldenAdvice)
const cleanWords = computed(() => stripHtml(wordsForYou.value).replace(/\n/g,'<br>'))

function stripHtml(h) { if (!h) return ''; return h.replace(/<[^>]+>/g,'').replace(/&nbsp;/g,' ').replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').trim() }

// ── 孩子版专属 ──
const KID_LABELS = { '协调力':'🤝 合作力','执行力':'⚡ 行动力','公信力':'📢 表达力','领导力':'👑 领导力','创新力':'✨ 想象力' }
const KID_ENERGY_COLORS = ['#8b5cf6','#3b82f6','#10b981','#f59e0b','#ef4444']
const kidAbilities = computed(() => Ability.value.map((a,i) => {
  const v = a.value || 0
  return { ...a, label: KID_LABELS[a.abilityName]?.split(' ')[1] || a.abilityName, emoji: KID_LABELS[a.abilityName]?.split(' ')[0] || '⭐', stars: v>=90?5:v>=70?4:v>=50?3:v>=30?2:1, color: v>=80?'#10b981':v>=60?'#8b5cf6':v>=40?'#f59e0b':'#ef4444', tip: v>=80?'太厉害了！':v>=60?'继续保持哦！':v>=40?'加油，你可以的！':'多练练会更好！' }
}))
const kidTagline = computed(() => {
  const m = { '学者':'你是个爱思考的小天才！', '思者':'你脑子转得飞快，总有新点子！', '行者':'你是个行动派，做什么都很有干劲！', '赢者':'你天生就是小领袖，大家都愿意跟着你！', '德者':'你心地善良，总是为别人着想！' }
  return m[report.value?.talent] || attrShort.value
})
const kidBgFig = computed(() => TALENT_FIGS[report.value?.talent] || '')

// 雷达图
const ro2 = [{x:110,y:12},{x:190,y:68},{x:162,y:158},{x:58,y:158},{x:30,y:68}]
const kidRadarSvg = computed(() => {
  const items = kidAbilities.value.slice(0,5)
  const pts = items.map((a,i) => { const r=Math.min(100,Math.max(0,a.value||0))/100, v=ro2[i]; return `${110+(v.x-110)*r},${110+(v.y-110)*r}` }).join(' ')
  const dots = items.map((a,i) => { const r=Math.min(100,Math.max(0,a.value||0))/100, v=ro2[i], x=110+(v.x-110)*r, y=110+(v.y-110)*r; return `<circle cx="${x}" cy="${y}" r="3" fill="${r>=0.6?'#8b5cf6':'#c4b5fd'}"/>` }).join('')
  const labs = [{x:110,y:4,a:'middle'},{x:198,y:68,a:'start'},{x:165,y:172,a:'middle'},{x:55,y:172,a:'middle'},{x:20,y:68,a:'end'}]
  const names = items.map(a=>a.label)
  return `<svg viewBox="0 0 220 200" style="width:180px;height:160px;display:block;margin:0 auto;">
    <polygon points="${ro2.map(v=>`${v.x},${v.y}`).join(' ')}" fill="none" stroke="#ede9fe" stroke-width="1.5"/>
    <polygon points="${pts}" fill="rgba(139,92,246,0.06)" stroke="#8b5cf6" stroke-width="1.5" stroke-linejoin="round"/>
    ${dots}${labs.map((l,i)=>`<text x="${l.x}" y="${l.y}" font-size="10" fill="#7c6fa0" text-anchor="${l.a}" font-weight="700">${names[i]||''}</text>`).join('')}</svg>`
})

onBeforeUnmount(() => { if(themeObserver){themeObserver.disconnect();themeObserver=null}; if(prevTheme){document.documentElement.setAttribute('data-theme',prevTheme)}else{document.documentElement.removeAttribute('data-theme')} })

function getMockData() {
  return { id:1, talent:'学者', talent_primary:'学者', check_talent:['学者','德者'], create_time:'2026-07-01 12:00',
    results:{ Talent:{ value:85, desp:'<p><strong>天赋能力解读</strong></p><p>学者型的人天生对世界充满好奇，喜欢系统性思考。</p><p><strong>想对你说的话</strong></p><p>你的逻辑分析能力非常出色，继续保持好奇心！</p><p><strong>三条黄金建议</strong></p><p>1. 每天留出30分钟深度阅读</p><p>2. 把学到的知识讲给别人听</p><p>3. 每周做一件不需要过度思考的事</p>' },
    Attribute:{ desp:'拥有卓越的逻辑分析能力', SupplementDesp:'<p>学者偏德者，智德双修。</p>', attributeList:[{id:'A',name:'智慧',grade:5,value:92},{id:'B',name:'思辨',grade:4,value:85},{id:'C',name:'专注',grade:4,value:78},{id:'D',name:'洞察',grade:3,value:65},{id:'E',name:'求知',grade:5,value:90}] },
    State:{ name:'平稳', id:4, desp:'<p>当前状态平稳。</p>' },
    Ability:[{abilityID:1,abilityName:'协调力',value:78},{abilityID:2,abilityName:'执行力',value:65},{abilityID:3,abilityName:'公信力',value:55},{abilityID:4,abilityName:'领导力',value:85},{abilityID:5,abilityName:'创新力',value:92}] } }
}
</script>

<style scoped>
.app { min-height:100vh; max-width:480px; margin:0 auto; background:#faf8ff; font-family:PingFang SC,sans-serif; display:flex; flex-direction:column; }
.nav { display:flex; align-items:center; padding:14px 24px 0; }
.nav-back { width:36px; height:36px; border-radius:50%; background:#f3f0ff; border:1px solid #e8e0f8; display:flex; align-items:center; justify-content:center; cursor:pointer; }
.nav-title { flex:1; text-align:center; color:#1e1b2e; font-size:16px; font-weight:600; }
.nav-spacer { width:36px; }
.loading-wrap { flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:16px; }
.loading-spinner { width:36px; height:36px; border:3px solid #ede9fe; border-top-color:#8b5cf6; border-radius:50%; animation:spin 0.8s linear infinite; }
.loading-text { color:#9089b0; font-size:14px; }
@keyframes spin { to{transform:rotate(360deg)} }
.body { flex:1; overflow-y:auto; }
.content { padding:12px 16px 0; }

.card { background:#fff; border:1px solid #f0ebff; border-radius:20px; padding:20px; margin-bottom:12px; box-shadow:0 2px 16px rgba(139,92,246,0.04); }
.sec-title { font-size:16px; font-weight:700; color:#1e1b2e; display:block; margin-bottom:16px; }

/* Hero */
.hero-card { position:relative; overflow:visible; }
.hero-bg-fig { position:absolute; right:8px; top:-20px; width:140px; height:200px; opacity:0.3; pointer-events:none; z-index:0; }
.hero-row { display:flex; align-items:center; gap:14px; position:relative; z-index:1; }
.hero-avatar { width:60px; height:60px; border-radius:50%; border:3px solid #ede9fe; flex-shrink:0; }
.hero-text { flex:1; }
.hero-greet { font-size:13px; color:#8b7fbf; display:block; }
.hero-name { font-size:24px; font-weight:800; color:#1e1b2e; display:block; margin:2px 0; }
.hero-tagline { font-size:12px; color:#9089b0; line-height:1.5; display:block; }

/* Energy */
.eng-row { margin-bottom:14px; }
.eng-row:last-child { margin-bottom:0; }
.eng-top { display:flex; align-items:center; gap:8px; margin-bottom:6px; }
.eng-emoji { font-size:16px; }
.eng-name { font-size:13px; font-weight:600; color:#3d3766; flex:1; }
.eng-gems { display:flex; gap:3px; }
.eng-gem { font-size:14px; color:#ddd6f0; }
.eng-gem.on { color:#f59e0b; }
.eng-bar { height:8px; background:#f3f0ff; border-radius:4px; overflow:hidden; margin-bottom:3px; }
.eng-fill { height:100%; border-radius:4px; }
.eng-tip { font-size:11px; color:#9089b0; }

/* Radar */
.radar-wrap { text-align:center; }

/* Bubbles */
.bub { max-width:82%; padding:12px 16px; border-radius:16px; margin-bottom:10px; }
.bub:last-child { margin-bottom:0; }
.bub-l { background:#f3f0ff; border-bottom-left-radius:4px; margin-right:auto; }
.bub-r { background:#fef9e7; border-bottom-right-radius:4px; margin-left:auto; }
.bub-t { font-size:13px; color:#4a4166; line-height:1.7; }

/* Bottom */
.bbar { padding:12px 20px; padding-bottom:max(12px,env(safe-area-inset-bottom)); }
.bbtn { padding:16px; text-align:center; border-radius:16px; background:linear-gradient(135deg,#8b5cf6,#6366f1); cursor:pointer; box-shadow:0 4px 20px rgba(139,92,246,0.2); }
.bbtn text { color:#fff; font-size:16px; font-weight:700; }
.bbtn:active { opacity:0.85; transform:scale(0.98); }
</style>
