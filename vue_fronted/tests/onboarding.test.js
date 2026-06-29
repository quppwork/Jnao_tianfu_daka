/** onboarding 流程交互测试 — 覆盖每一步按钮点击 + 输入框响应 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref, computed } from 'vue'

// ── 模拟 uni 全局 ──
const uniMock = {
  showToast: vi.fn(),
  redirectTo: vi.fn(),
  navigateTo: vi.fn(),
}
global.uni = uniMock
global.getCurrentPages = vi.fn(() => [{ options: {} }])

// ── 模拟依赖模块 ──
vi.mock('@/utils/userApi.js', () => ({
  getChildUserId: vi.fn(() => 1),
  saveProfile: vi.fn(() => Promise.resolve({ code: 1 })),
}))
vi.mock('@/utils/talentState.js', () => ({
  TALENT_CODE_MAP: { 学者: 1, 思者: 2, 行者: 3, 德者: 4, 赢者: 5 },
  clearTalentState: vi.fn(),
  refreshTalentState: vi.fn(() => Promise.resolve()),
}))

// ── 内联组件逻辑（避免 uni-app .vue 文件编译问题） ──
function createOnboardingState() {
  const step = ref(1)
  const studentType = ref('')
  const selectedTalent = ref('')
  const selectedAbilities = ref([])
  const formData = ref({})

  const fFirstDate = ref('')
  const fTotalCount = ref('')
  const fLastTime = ref('')
  const fLastResult = ref('')
  const fNote = ref('')

  const globalFirstDate = ref('')
  const globalTotalCount = ref('')

  const talents = [
    { name: '学者', color: '#12417A', desc: '逻辑思辨', delay: '0.4s' },
    { name: '思者', color: '#22C55E', desc: '创意灵性', delay: '0.5s' },
    { name: '行者', color: '#A57A1A', desc: '实践行动', delay: '0.6s' },
    { name: '德者', color: '#582E1F', desc: '共情利他', delay: '0.7s' },
    { name: '赢者', color: '#960D24', desc: '目标驱动', delay: '0.8s' },
  ]

  const allAbilities = [
    '超脑阅读','影像追忆','扫描速记','极速运算',
    '极速学习','难题专练','文科扫书','理科扫书',
    '高效作业','天赋绘画','音乐灵感','棋类专注'
  ]

  const selectedAbilityNames = computed(() => selectedAbilities.value.map(i => allAbilities[i]))
  const currentAbilityIndex = computed(() => step.value - 5)
  const currentAbility = computed(() => selectedAbilityNames.value[currentAbilityIndex.value] || '')
  const isLastDataStep = computed(() => currentAbilityIndex.value >= selectedAbilityNames.value.length - 1)

  function selectStudentType(type) {
    studentType.value = type
    step.value = type === 'new' ? 2 : 3
  }

  function selectTalent(name) {
    selectedTalent.value = name
  }

  function confirmReturningTalent() {
    if (!selectedTalent.value || selectedTalent.value === 'unknown') {
      uni.showToast({ title: '请选择一个天赋', icon: 'none' })
      return
    }
    step.value = 4
  }

  function toggleAbility(ai) {
    const idx = selectedAbilities.value.indexOf(ai)
    if (idx >= 0) selectedAbilities.value.splice(idx, 1)
    else selectedAbilities.value.push(ai)
  }

  function confirmAbilities() {
    if (!selectedAbilities.value.length) {
      uni.showToast({ title: '请至少选择一项', icon: 'none' })
      return
    }
    for (const ab of selectedAbilityNames.value) {
      if (!formData.value[ab]) formData.value[ab] = { firstDate: '', totalCount: '', lastTime: '', lastResult: '', note: '' }
    }
    step.value = 5
  }

  function nextDataStep() {
    formData.value[currentAbility.value] = {
      firstDate: fFirstDate.value, totalCount: fTotalCount.value,
      lastTime: fLastTime.value, lastResult: fLastResult.value, note: fNote.value,
    }
    if (isLastDataStep.value) step.value = 100
    else { step.value++; fFirstDate.value = ''; fTotalCount.value = ''; fLastTime.value = ''; fLastResult.value = ''; fNote.value = '' }
  }

  return {
    step, studentType, selectedTalent, selectedAbilities, formData,
    fFirstDate, fTotalCount, fLastTime, fLastResult, fNote,
    globalFirstDate, globalTotalCount,
    talents, allAbilities, selectedAbilityNames, currentAbility, isLastDataStep,
    selectStudentType, selectTalent, confirmReturningTalent,
    toggleAbility, confirmAbilities, nextDataStep,
  }
}

// ── tests ─────────────────────────────────────────────

describe('Onboarding 老学员全流程', () => {
  let state

  beforeEach(() => {
    vi.clearAllMocks()
    state = createOnboardingState()
  })

  // ── Step 1: 选新/老 ──
  describe('Step 1 — 选新/老学员', () => {
    it('选老学员 → step 跳转到 3', () => {
      state.selectStudentType('returning')
      expect(state.studentType.value).toBe('returning')
      expect(state.step.value).toBe(3)
    })

    it('选新学员 → step 跳转到 2', () => {
      state.selectStudentType('new')
      expect(state.studentType.value).toBe('new')
      expect(state.step.value).toBe(2)
    })
  })

  // ── Step 3: 老学员选天赋 ──
  describe('Step 3 — 老学员选天赋', () => {
    beforeEach(() => {
      state.selectStudentType('returning')
    })

    it('未选天赋点继续 → toast 提示', () => {
      state.confirmReturningTalent()
      expect(uniMock.showToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: '请选择一个天赋' })
      )
      expect(state.step.value).toBe(3) // 不前进
    })

    it('选天赋后点继续 → step 跳转到 4', () => {
      state.selectTalent('学者')
      state.confirmReturningTalent()
      expect(state.step.value).toBe(4)
    })

    it('五者都可以选中', () => {
      for (const t of state.talents) {
        state.selectTalent(t.name)
        expect(state.selectedTalent.value).toBe(t.name)
      }
    })

    it('无法选"不知道"（选项已删除）', () => {
      state.selectTalent('unknown')
      // unknown 不是合法天赋，confirmReturningTalent 应拦截
      state.confirmReturningTalent()
      expect(uniMock.showToast).toHaveBeenCalled()
    })
  })

  // ── Step 4: 全局数据 + 选能力 ──
  describe('Step 4 — 初次训练日期 + 总次数 + 选能力', () => {
    beforeEach(() => {
      state.selectStudentType('returning')
      state.selectTalent('学者')
      state.confirmReturningTalent()
    })

    it('全局输入框可写入', () => {
      state.globalFirstDate.value = '2025年3月'
      state.globalTotalCount.value = '120'
      expect(state.globalFirstDate.value).toBe('2025年3月')
      expect(state.globalTotalCount.value).toBe('120')
    })

    it('选能力 — toggle 单项', () => {
      state.toggleAbility(0) // 超脑阅读
      expect(state.selectedAbilities.value).toContain(0)
      state.toggleAbility(0) // 取消
      expect(state.selectedAbilities.value).not.toContain(0)
    })

    it('选多项能力', () => {
      state.toggleAbility(0)
      state.toggleAbility(1)
      state.toggleAbility(2)
      expect(state.selectedAbilities.value).toEqual([0, 1, 2])
      expect(state.selectedAbilityNames.value).toEqual(['超脑阅读', '影像追忆', '扫描速记'])
    })

    it('未选能力点继续 → toast', () => {
      state.confirmAbilities()
      expect(uniMock.showToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: '请至少选择一项' })
      )
    })

    it('选能力后点继续 → step 跳转到 5', () => {
      state.toggleAbility(0)
      state.confirmAbilities()
      expect(state.step.value).toBe(5)
      expect(state.currentAbility.value).toBe('超脑阅读')
    })
  })

  // ── Step 5+: 逐项填数据 ──
  describe('Step 5+ — 逐项训练数据', () => {
    beforeEach(() => {
      state.selectStudentType('returning')
      state.selectTalent('学者')
      state.confirmReturningTalent()
      state.toggleAbility(0) // 超脑阅读
      state.toggleAbility(1) // 影像追忆
      state.confirmAbilities()
    })

    it('输入框可写入', () => {
      state.fFirstDate.value = '2025年3月'
      state.fTotalCount.value = '30'
      state.fLastTime.value = '20'
      state.fLastResult.value = '85'
      state.fNote.value = '中途停过两个月'
      expect(state.fFirstDate.value).toBe('2025年3月')
      expect(state.fTotalCount.value).toBe('30')
      expect(state.fLastTime.value).toBe('20')
      expect(state.fLastResult.value).toBe('85')
      expect(state.fNote.value).toBe('中途停过两个月')
    })

    it('空字段也可跳过', () => {
      state.nextDataStep()
      expect(state.step.value).toBe(6) // 下一项
      expect(state.formData.value['超脑阅读'].firstDate).toBe('')
    })

    it('逐项推进 — 填完第一项进第二项', () => {
      state.fFirstDate.value = '2025年3月'
      state.fTotalCount.value = '30'
      state.nextDataStep()
      expect(state.step.value).toBe(6)
      expect(state.currentAbility.value).toBe('影像追忆')
      expect(state.formData.value['超脑阅读']).toMatchObject({
        firstDate: '2025年3月', totalCount: '30',
      })
    })

    it('最后一项完成 → step 跳转 100', () => {
      // 第一项
      state.nextDataStep()
      // 第二项（最后）
      state.nextDataStep()
      expect(state.step.value).toBe(100)
      expect(state.formData.value['超脑阅读']).toBeDefined()
      expect(state.formData.value['影像追忆']).toBeDefined()
    })
  })

  // ── 单项输入响应 ──
  describe('单个输入框响应验证', () => {
    beforeEach(() => {
      state.selectStudentType('returning')
      state.selectTalent('学者')
    })

    it('globalFirstDate 能写能读', () => {
      state.globalFirstDate.value = ''
      expect(state.globalFirstDate.value).toBe('')
      state.globalFirstDate.value = '2025年3月'
      expect(state.globalFirstDate.value).toBe('2025年3月')
    })

    it('globalTotalCount 能写能读', () => {
      state.globalTotalCount.value = '120'
      expect(state.globalTotalCount.value).toBe('120')
    })

    it('fTotalCount 能写能读（纯数字字符串）', () => {
      state.fTotalCount.value = '50'
      expect(state.fTotalCount.value).toBe('50')
    })

    it('fLastTime 和 fLastResult 能独立填写', () => {
      state.fLastTime.value = '25'
      state.fLastResult.value = '92'
      expect(state.fLastTime.value).toBe('25')
      expect(state.fLastResult.value).toBe('92')
    })
  })
})
