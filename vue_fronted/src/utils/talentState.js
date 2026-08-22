/** 全局有效天赋状态 — 引导自选 / JNAO 测评 / profile 同步字段统一入口 */

import { fetchProfile, fetchTrainingEntry } from '@/utils/userApi.js'

const TALENT_CODE_MAP = { 学者: 1, 思者: 2, 行者: 3, 德者: 4, 赢者: 5 }

/** 五者头像 / 主题色：训练、成长、报告、测评共用，禁止页面再抄一份 */
export const TALENT_AVATAR = {
  学者: '/static/talent-xuezhe.png',
  思者: '/static/talent-sizhe.png',
  行者: '/static/talent-xingzhe.png',
  德者: '/static/talent-dezhe.png',
  赢者: '/static/talent-yingzhe.png',
}

export const TALENT_COLOR = {
  学者: '#12417A',
  思者: '#22C55E',
  行者: '#A57A1A',
  德者: '#582E1F',
  赢者: '#960D24',
  迷者: '#9CA3AF',
}

const TALENT_COLOR_FALLBACK = '#3b82f6'
const DUAN_CN = ['一', '二', '三', '四', '五', '六', '七', '八', '九']

export const HONOR_BADGE = {
  会员: '💳',
  VIP会员: '💎',
  导师子女: '🎓',
  传承特使: '🏅',
  劲脑学神: '🧠',
  专利精英: '💡',
}

/** /tier 未返回 path 时的展示兜底；晋级门槛以接口为准 */
export const HONOR_PATH = [
  { name: '会员', identity: true },
  { name: 'VIP会员', identity: true },
  { name: '导师子女', identity: true },
  { name: '传承特使', identity: false, from_duan: 1 },
  { name: '劲脑学神', identity: false, from_duan: 5 },
  { name: '专利精英', identity: false, from_duan: 8 },
]

export function talentAvatarUrl(name) {
  return TALENT_AVATAR[name] || TALENT_AVATAR['学者']
}

export function talentThemeColor(name, fallback = TALENT_COLOR_FALLBACK) {
  return TALENT_COLOR[name] || fallback
}

export function duanCN(n) {
  const i = Math.min(9, Math.max(1, Number(n) || 1)) - 1
  return DUAN_CN[i]
}

/** 用户可见段位文案：第3段，不用 Tier / Lv */
export function duanText(n) {
  return `第${Number(n) || 1}段`
}

export function decorateHonorPath(path) {
  const steps = path?.length ? path : HONOR_PATH
  return steps.map((s) => ({
    ...s,
    identity: !!s.identity,
    badge: HONOR_BADGE[s.name] || '🏅',
  }))
}

export function honorPathIndex(honorName, path) {
  const steps = decorateHonorPath(path)
  const idx = steps.findIndex((s) => s.name === honorName)
  if (idx >= 0) return idx
  const firstSkill = steps.findIndex((s) => !s.identity)
  return firstSkill >= 0 ? firstSkill : 0
}

export function honorStepTag(step) {
  if (!step) return ''
  if (step.identity) return '身份'
  if (step.from_duan) return `${duanText(step.from_duan)}起`
  return '训练称号'
}

export function duanNineSteps() {
  return DUAN_CN.map((num, i) => ({
    num,
    group: i < 3 ? 1 : i < 6 ? 2 : 3,
  }))
}

let _state = null

export function getTalentState() {
  return _state
}

export function clearTalentState() {
  _state = null
}

function fromOnboarding(profileJson) {
  const ob = profileJson?.onboarding
  if (!ob || ob.talent_unknown) return null
  const name = ob.self_reported_talent
  if (!name) return null
  const code = ob.self_reported_talent_code || TALENT_CODE_MAP[name] || null
  return { talent_primary: name, talent_code: code, talent_source: 'onboarding' }
}

function mergeTalent(profile, entry) {
  const pj = profile?.profile_json || {}
  const ob = fromOnboarding(pj)
  const talent = {
    userId: profile?.child_user_id || null,
    talent_primary:
      profile?.talent_primary
      || pj.talent_primary
      || ob?.talent_primary
      || entry?.talent_primary
      || null,
    talent_code:
      profile?.talent_code
      || pj.talent_code
      || ob?.talent_code
      || entry?.talent_code
      || null,
    talent_tag:
      profile?.talent_tag
      || pj.talent_tag
      || entry?.talent_tag
      || null,
    talent_source:
      profile?.talent_source
      || pj.talent_source
      || ob?.talent_source
      || entry?.talent_source
      || null,
    has_assessment: !!(entry?.has_assessment || profile?.talent_code || ob?.talent_code || profile?.talent_primary || ob?.talent_primary),
    needs_assessment: entry?.needs_assessment ?? !(profile?.talent_code || ob?.talent_code || profile?.talent_primary || ob?.talent_primary),
    onboarding_completed: profile?.onboarding_completed ?? !!pj.onboarding?.completed_at,
  }
  if (talent.talent_primary && !talent.talent_code) {
    talent.talent_code = TALENT_CODE_MAP[talent.talent_primary] || null
  }
  if (talent.talent_code && !talent.needs_assessment) {
    talent.has_assessment = true
  }
  return talent
}

export function hasEffectiveTalent(state = _state) {
  if (!state) return false
  if (state.needs_assessment === false && state.has_assessment) return true
  return !!(state.talent_code || state.talent_primary)
}

export function applyTalentFromProfile(profile, entry = null) {
  if (!profile) return _state
  _state = mergeTalent(profile, entry)
  _state.userId = profile.child_user_id || _state?.userId || null
  return _state
}

/** 从 profile + training/entry 刷新全局天赋（各页面进入时调用） */
export async function refreshTalentState(userId, profileHint = null) {
  const [profile, entry] = await Promise.all([
    profileHint ? Promise.resolve(profileHint) : fetchProfile(userId),
    fetchTrainingEntry(userId).catch(() => null),
  ])
  const state = applyTalentFromProfile(profile, entry)
  if (state) state.userId = userId
  return state
}

export async function ensureTalentState(userId) {
  if (_state?.userId === userId && hasEffectiveTalent(_state)) {
    return _state
  }
  return refreshTalentState(userId)
}

export { TALENT_CODE_MAP }
