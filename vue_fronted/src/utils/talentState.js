/** 全局有效天赋状态 — 引导自选 / JNAO 测评 / profile 同步字段统一入口 */

import { fetchProfile, fetchTrainingEntry } from '@/utils/userApi.js'

const TALENT_CODE_MAP = { 学者: 1, 思者: 2, 行者: 3, 德者: 4, 赢者: 5 }

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

/** 从 profile + training/entry 刷新全局天赋（各页面进入时调用） */
export async function refreshTalentState(userId) {
  const [profile, entry] = await Promise.all([
    fetchProfile(userId),
    fetchTrainingEntry(userId).catch(() => null),
  ])
  _state = mergeTalent(profile, entry)
  _state.userId = userId
  return _state
}

export async function ensureTalentState(userId) {
  if (_state?.userId === userId && hasEffectiveTalent(_state)) {
    return _state
  }
  return refreshTalentState(userId)
}

export { TALENT_CODE_MAP }
