import { describe, it, expect, beforeEach, vi } from 'vitest'
import { shuffle, requeueAtBack, getOrCreateUid, encodeAnswers } from '../src/utils/testHelpers.js'

describe('shuffle', () => {
  it('returns same-length array', () => {
    const input = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    expect(shuffle(input)).toHaveLength(input.length)
  })

  it('contains all original elements', () => {
    const input = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    const result = shuffle(input)
    expect([...result].sort((a, b) => a - b)).toEqual([...input].sort((a, b) => a - b))
  })

  it('does not mutate original', () => {
    const input = [1, 2, 3, 4, 5]
    const copy = [...input]
    shuffle(input)
    expect(input).toEqual(copy)
  })

  it('handles empty array', () => {
    expect(shuffle([])).toEqual([])
  })

  it('handles single element', () => {
    expect(shuffle([42])).toEqual([42])
  })

  it('produces different orderings (100 trials)', () => {
    const input = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    let sameCount = 0
    for (let i = 0; i < 100; i++) {
      const result = shuffle(input)
      if (result.every((v, idx) => v === input[idx])) sameCount++
    }
    expect(sameCount).toBeLessThan(5)
  })
})

describe('requeueAtBack', () => {
  it('moves qid to latter half', () => {
    const remaining = [10, 20, 30, 40, 50, 60, 70, 80]
    const result = requeueAtBack(remaining, 10)
    expect(result).toHaveLength(8)
    expect(result).toContain(10)
    const pos = result.indexOf(10)
    expect(pos).toBeGreaterThanOrEqual(Math.floor(result.length / 2) - 1)
  })

  it('does not lose elements', () => {
    const remaining = [5, 10, 15, 20, 25]
    const result = requeueAtBack(remaining, 15)
    expect([...result].sort((a, b) => a - b)).toEqual([...remaining].sort((a, b) => a - b))
  })

  it('handles single element', () => {
    expect(requeueAtBack([7], 7)).toEqual([7])
  })
})

describe('encodeAnswers', () => {
  it('完全符合→1, 有差异→0, sorted by qid', () => {
    const order = [5, 1, 3, 2, 4]
    const answers = { 1: '完全符合', 2: '有差异', 3: '完全符合', 4: '有差异', 5: '完全符合' }
    expect(encodeAnswers(order, answers)).toBe('10101')
  })

  it('missing answers → 0', () => {
    expect(encodeAnswers([1, 2, 3], { 1: '完全符合' })).toBe('100')
  })

  it('empty answers → all zeros', () => {
    expect(encodeAnswers([1, 2, 3], {})).toBe('000')
  })

  it('all 完全符合 → all ones', () => {
    const answers = { 1: '完全符合', 2: '完全符合', 3: '完全符合' }
    expect(encodeAnswers([2, 1, 3], answers)).toBe('111')
  })

  it('produces exactly 35 chars for full test', () => {
    const order = Array.from({ length: 35 }, (_, i) => i + 1)
    const answers = {}
    for (let i = 1; i <= 35; i++) answers[i] = i % 2 === 0 ? '完全符合' : '有差异'
    expect(encodeAnswers(order, answers)).toHaveLength(35)
  })
})

describe('getOrCreateUid', () => {
  let store
  beforeEach(() => {
    store = {}
    vi.stubGlobal('localStorage', {
      getItem: vi.fn((key) => store[key] ?? null),
      setItem: vi.fn((key, val) => { store[key] = val }),
    })
  })

  it('generates a number between 100000 and 1000000', () => {
    const uid = getOrCreateUid()
    expect(uid).toBeGreaterThanOrEqual(100000)
    expect(uid).toBeLessThan(1000000)
  })

  it('returns same uid on second call', () => {
    const first = getOrCreateUid()
    const second = getOrCreateUid()
    expect(second).toBe(first)
  })

  it('stores uid under jnao_uid key', () => {
    getOrCreateUid()
    expect(store['jnao_uid']).toBeTruthy()
  })
})
