/**
 * 今日修炼（dayu）边界测试
 * 与 pages/training/dayu.vue 核心规则对齐的纯函数版，覆盖临界点。
 */
import { describe, it, expect } from 'vitest'

// ─── 倒计时格式 ───
function formatCountdown(totalSec) {
  const sec = Math.max(0, Math.floor(Number(totalSec) || 0))
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  if (h > 0) {
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function timerRemainPct(remaining, planned) {
  if (planned <= 0) return 0
  return Math.max(0, Math.min(100, (remaining / planned) * 100))
}

function remainingFromEndAt(endAtMs, nowMs = Date.now()) {
  if (!endAtMs) return 0
  return Math.max(0, Math.ceil((endAtMs - nowMs) / 1000))
}

// ─── 听音门槛 ───
function itemNeedsAudioListen(item) {
  if (!item) return false
  if (item.item_type === 'perception' || item.item_type === 'placeholder') return false
  return !!item.audio_url
}

function audioWatchPct(item) {
  const wp = item?.watch_progress
  if (!wp || typeof wp !== 'object') return 0
  const audio = wp.audio && typeof wp.audio === 'object' ? wp.audio : null
  if (audio) return Math.max(0, Math.min(100, Number(audio.pct || 0)))
  return Math.max(0, Math.min(100, Number(wp.pct || 0)))
}

function isListenReady(item) {
  if (!itemNeedsAudioListen(item)) return true
  return audioWatchPct(item) >= 90
}

function canOpenCheckin({ item, existingRecord, phase, devMode }) {
  if (!item || item._state === 'locked') return { ok: false, reason: 'locked' }
  if (!devMode && phase !== 'running' && phase !== 'expired') {
    return { ok: false, reason: 'phase' }
  }
  if (!existingRecord && !devMode && !isListenReady(item)) {
    return { ok: false, reason: 'listen' }
  }
  return { ok: true }
}

// ─── 音频续播 seek ───
function resolveAudioResumeSeek(pendingSec, durationSec) {
  if (pendingSec <= 0.5) return { seekTo: 0, clear: true }
  const target = durationSec > 0
    ? Math.min(pendingSec, Math.max(0, durationSec - 0.35))
    : pendingSec
  if (target <= 0.5) return { seekTo: 0, clear: true }
  return { seekTo: target, clear: true }
}

/** 停止：保留位置；结束：关面板，进度仍靠 watch_progress 续播 */
function afterStopAudio({ currentSec, peakSec }) {
  const cur = Number(currentSec || 0)
  return {
    playing: false,
    uiCurrent: cur > 0 ? cur : 0,
    peakSec: Math.max(peakSec || 0, cur),
    closed: false,
  }
}

function afterEndMedia({ currentSec, peakSec }) {
  const cur = Number(currentSec || 0)
  return {
    playing: false,
    closed: true,
    peakSec: Math.max(peakSec || 0, cur),
    uiCurrent: 0,
  }
}

// ─── 打卡回填 ───
function fillCheckinFormFromRecord(record, fallbackItem = {}) {
  const card = Array.isArray(record?.cards) && record.cards.length
    ? record.cards[0]
    : null
  const time = String(
    card?.time
    ?? record?.time_spent
    ?? (fallbackItem?.duration_min != null ? fallbackItem.duration_min : '')
    ?? '',
  )
  const wordCount = String(card?.wordCount ?? card?.word_count ?? '')
  const accuracy = String(card?.accuracy ?? '')
  const note = String(card?.note ?? record?.note ?? '')
  const att = Number(record?.attitude_pct)
  const attitude = Number.isFinite(att) && att > 0 ? att : 60
  return { time, wordCount, accuracy, note, attitude }
}

function resolveCheckinApi(existing) {
  return existing?.id ? 'update' : 'create'
}

// ─── 关卡解锁 ───
function itemDone(item) {
  if (!item) return false
  if (item.checkin_status === 'done') return true
  return false
}

function buildDisplayStates(items) {
  let firstActive = items.length - 1
  for (let i = 0; i < items.length; i++) {
    if (!itemDone(items[i])) {
      firstActive = i
      break
    }
  }
  return items.map((it, i) => {
    const done = itemDone(it)
    if (done) return 'done'
    if (i === firstActive) return 'active'
    if (i < firstActive) return 'done'
    return 'locked'
  })
}

// ─── 能量塔 ───
function clampTier(n) {
  const v = Number(n || 1)
  return Math.max(1, Math.min(9, Number.isFinite(v) ? v : 1))
}

function towerSegs(tier) {
  const cur = clampTier(tier)
  return Array.from({ length: 9 }, (_, i) => {
    const n = i + 1
    if (n < cur) return 'lit'
    if (n === cur) return 'half'
    return ''
  })
}

// ═══════════════════════════════════════════
describe('dayu 倒计时边界', () => {
  it('0 / 负数 → 00:00', () => {
    expect(formatCountdown(0)).toBe('00:00')
    expect(formatCountdown(-3)).toBe('00:00')
    expect(formatCountdown(NaN)).toBe('00:00')
  })

  it('刚好 59:59 不进小时位', () => {
    expect(formatCountdown(3599)).toBe('59:59')
  })

  it('刚好 3600 → 01:00:00', () => {
    expect(formatCountdown(3600)).toBe('01:00:00')
  })

  it('endAt 刚好过期 → remaining 0', () => {
    const now = 1_000_000
    expect(remainingFromEndAt(now - 1, now)).toBe(0)
    expect(remainingFromEndAt(now, now)).toBe(0)
  })

  it('endAt 还差 1 秒 → remaining 1', () => {
    const now = 1_000_000
    expect(remainingFromEndAt(now + 1000, now)).toBe(1)
  })

  it('planned=0 时进度条比例为 0（防除零）', () => {
    expect(timerRemainPct(100, 0)).toBe(0)
  })

  it('剩余 = 计划 → 100%；剩余 = 0 → 0%', () => {
    expect(timerRemainPct(600, 600)).toBe(100)
    expect(timerRemainPct(0, 600)).toBe(0)
  })
})

describe('dayu 听音 90% 打卡门槛', () => {
  const audioItem = (pct, extra = {}) => ({
    audio_url: '/a.mp3',
    watch_progress: { audio: { pct } },
    ...extra,
  })

  it('89.9% 不可打卡；90% 刚好可打卡', () => {
    expect(isListenReady(audioItem(89.9))).toBe(false)
    expect(isListenReady(audioItem(90))).toBe(true)
  })

  it('无 audio 子对象时回退顶层 pct', () => {
    const it = {
      audio_url: '/a.mp3',
      watch_progress: { video: { pct: 95 }, pct: 95 },
    }
    expect(audioWatchPct(it)).toBe(95)
    expect(isListenReady(it)).toBe(true)
  })

  it('完全无进度 → 0，不可打卡', () => {
    expect(audioWatchPct({ audio_url: '/a.mp3' })).toBe(0)
    expect(isListenReady({ audio_url: '/a.mp3' })).toBe(false)
  })

  it('有 audio 子进度时忽略顶层/视频进度', () => {
    const it = {
      audio_url: '/a.mp3',
      watch_progress: { audio: { pct: 40 }, video: { pct: 99 }, pct: 99 },
    }
    expect(audioWatchPct(it)).toBe(40)
    expect(isListenReady(it)).toBe(false)
  })

  it('无 audio_url → 不需要听音即可打卡', () => {
    expect(isListenReady({ video_url: '/v.mp4' })).toBe(true)
  })

  it('perception / placeholder → 跳过听音门槛', () => {
    expect(itemNeedsAudioListen({ item_type: 'perception', audio_url: '/a.mp3' })).toBe(false)
    expect(isListenReady({ item_type: 'perception', audio_url: '/a.mp3' })).toBe(true)
  })

  it('未达 90% 首次打开过关指导 → 拦截；已有打卡记录可再打开', () => {
    const item = { ...audioItem(50), _state: 'active' }
    expect(canOpenCheckin({
      item, existingRecord: null, phase: 'running', devMode: false,
    }).reason).toBe('listen')
    expect(canOpenCheckin({
      item, existingRecord: { id: 1 }, phase: 'running', devMode: false,
    }).ok).toBe(true)
  })

  it('locked / 未开挑战 → 不可打卡', () => {
    expect(canOpenCheckin({
      item: { ...audioItem(100), _state: 'locked' },
      existingRecord: null, phase: 'running', devMode: false,
    }).reason).toBe('locked')
    expect(canOpenCheckin({
      item: { ...audioItem(100), _state: 'active' },
      existingRecord: null, phase: 'confirm', devMode: false,
    }).reason).toBe('phase')
  })

  it('DEV 模式可跳过听音门槛', () => {
    expect(canOpenCheckin({
      item: { ...audioItem(10), _state: 'active' },
      existingRecord: null, phase: 'running', devMode: true,
    }).ok).toBe(true)
  })
})

describe('dayu 停止 / 结束 / 续播', () => {
  it('停止：不关面板，保留当前位置与峰值', () => {
    const r = afterStopAudio({ currentSec: 126, peakSec: 100 })
    expect(r.closed).toBe(false)
    expect(r.playing).toBe(false)
    expect(r.uiCurrent).toBe(126)
    expect(r.peakSec).toBe(126)
  })

  it('结束：关面板，UI 归零，峰值保留供再次进入续播', () => {
    const r = afterEndMedia({ currentSec: 200, peakSec: 180 })
    expect(r.closed).toBe(true)
    expect(r.uiCurrent).toBe(0)
    expect(r.peakSec).toBe(200)
  })

  it('续播 seek：pending≤0.5 不跳；正常跳到 pending', () => {
    expect(resolveAudioResumeSeek(0.4, 600).seekTo).toBe(0)
    expect(resolveAudioResumeSeek(120, 600).seekTo).toBe(120)
  })

  it('续播 seek：pending 贴近尾部时钳到 duration-0.35', () => {
    expect(resolveAudioResumeSeek(600, 600).seekTo).toBeCloseTo(599.65, 2)
  })
})

describe('dayu 打卡回填 / 修改', () => {
  it('有 cards 时回填字数/用时/态度', () => {
    const form = fillCheckinFormFromRecord({
      attitude_pct: 80,
      cards: [{ time: '8', wordCount: '1200', accuracy: '', note: 'ok' }],
    })
    expect(form.time).toBe('8')
    expect(form.wordCount).toBe('1200')
    expect(form.note).toBe('ok')
    expect(form.attitude).toBe(80)
  })

  it('无 cards 时用时回退 duration_min；态度缺省 60', () => {
    const form = fillCheckinFormFromRecord({}, { duration_min: 20 })
    expect(form.time).toBe('20')
    expect(form.attitude).toBe(60)
    expect(form.wordCount).toBe('')
  })

  it('已有 record.id → update；否则 create', () => {
    expect(resolveCheckinApi({ id: 9 })).toBe('update')
    expect(resolveCheckinApi(null)).toBe('create')
    expect(resolveCheckinApi({})).toBe('create')
  })
})

describe('dayu 关卡解锁链', () => {
  it('首关未完成 → 后续全锁', () => {
    const states = buildDisplayStates([
      { checkin_status: 'pending' },
      { checkin_status: 'pending' },
      { checkin_status: 'pending' },
    ])
    expect(states).toEqual(['active', 'locked', 'locked'])
  })

  it('第一关 done → 第二关 active', () => {
    const states = buildDisplayStates([
      { checkin_status: 'done' },
      { checkin_status: 'pending' },
      { checkin_status: 'pending' },
    ])
    expect(states).toEqual(['done', 'active', 'locked'])
  })

  it('全部 done → 最后一关仍为 done（无 locked）', () => {
    const states = buildDisplayStates([
      { checkin_status: 'done' },
      { checkin_status: 'done' },
    ])
    expect(states).toEqual(['done', 'done'])
  })
})

describe('dayu 能量塔九段边界', () => {
  it('tier 钳制到 1..9', () => {
    expect(clampTier(0)).toBe(1)
    expect(clampTier(99)).toBe(9)
    expect(clampTier('x')).toBe(1)
  })

  it('一段：仅第一格 half', () => {
    expect(towerSegs(1)).toEqual(['half', '', '', '', '', '', '', '', ''])
  })

  it('九段：前 8 lit，第 9 half', () => {
    const s = towerSegs(9)
    expect(s.filter((x) => x === 'lit')).toHaveLength(8)
    expect(s[8]).toBe('half')
  })
})

describe('dayu 计时结束后媒体锁 / 打卡仍可用', () => {
  function isMediaLocked({ phase, mediaExhausted, devMode }) {
    if (devMode) return false
    if (phase === 'expired') return true
    if (mediaExhausted) return true
    return false
  }

  function canOpenMedia({ phase, mediaExhausted, stageLocked, devMode }) {
    if (stageLocked) return { ok: false, reason: 'stage' }
    if (isMediaLocked({ phase, mediaExhausted, devMode })) {
      return { ok: false, reason: 'media' }
    }
    if (!devMode && phase !== 'running') return { ok: false, reason: 'phase' }
    return { ok: true }
  }

  function canOpenCheckinAfterExpire({ phase, stageLocked, listenReady, existing, devMode }) {
    if (stageLocked) return { ok: false, reason: 'locked' }
    if (!devMode && phase !== 'running' && phase !== 'expired') {
      return { ok: false, reason: 'phase' }
    }
    // 计时结束仍可打卡；仅卡听音门槛（已有记录可改）
    if (!existing && !devMode && !listenReady) return { ok: false, reason: 'listen' }
    return { ok: true }
  }

  it('expired / media_exhausted → 媒体锁定；DEV 可跳过', () => {
    expect(isMediaLocked({ phase: 'expired', mediaExhausted: false, devMode: false })).toBe(true)
    expect(isMediaLocked({ phase: 'running', mediaExhausted: true, devMode: false })).toBe(true)
    expect(isMediaLocked({ phase: 'running', mediaExhausted: false, devMode: false })).toBe(false)
    expect(isMediaLocked({ phase: 'expired', mediaExhausted: true, devMode: true })).toBe(false)
  })

  it('结束后不可开音视频', () => {
    expect(canOpenMedia({
      phase: 'expired', mediaExhausted: false, stageLocked: false, devMode: false,
    }).reason).toBe('media')
  })

  it('结束后仍可打开过关指导（补打卡）', () => {
    expect(canOpenCheckinAfterExpire({
      phase: 'expired', stageLocked: false, listenReady: true, existing: null, devMode: false,
    }).ok).toBe(true)
    expect(canOpenCheckinAfterExpire({
      phase: 'expired', stageLocked: false, listenReady: false, existing: { id: 1 }, devMode: false,
    }).ok).toBe(true)
  })
})
