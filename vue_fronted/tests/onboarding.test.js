/** onboarding 流程 — 登录后引导，天赋统一走测评 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref, computed } from 'vue'

const uniMock = {
  showToast: vi.fn(),
  redirectTo: vi.fn(),
  navigateTo: vi.fn(),
}
global.uni = uniMock
global.getCurrentPages = vi.fn(() => [{ options: {} }])

function createOnboardingState() {
  const step = ref(1)
  const studentType = ref('')
  const selectedAbilities = ref([])
  const formData = ref({})
  const fFirstDate = ref('')
  const fTotalCount = ref('')
  const fLastTime = ref('')
  const fLastResult = ref('')
  const fNote = ref('')
  const globalFirstDate = ref('')
  const globalTotalCount = ref('')

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
    step.value = 2
  }

  function startTalentTest() {
    uni.navigateTo({
      url: `/pages/talent/index?from=onboarding&student_type=${studentType.value || 'new'}`,
    })
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
    step, studentType, selectedAbilities, formData,
    fFirstDate, fTotalCount, fLastTime, fLastResult, fNote,
    globalFirstDate, globalTotalCount,
    allAbilities, selectedAbilityNames, currentAbility, isLastDataStep,
    selectStudentType, startTalentTest, toggleAbility, confirmAbilities, nextDataStep,
  }
}

describe('Onboarding 登录后引导', () => {
  let state

  beforeEach(() => {
    vi.clearAllMocks()
    state = createOnboardingState()
  })

  describe('Step 1 — 选新/老学员', () => {
    it('选老学员 → step 2（天赋测试）', () => {
      state.selectStudentType('returning')
      expect(state.studentType.value).toBe('returning')
      expect(state.step.value).toBe(2)
    })

    it('选新学员 → step 2（天赋测试）', () => {
      state.selectStudentType('new')
      expect(state.studentType.value).toBe('new')
      expect(state.step.value).toBe(2)
    })
  })

  describe('Step 2 — 天赋测试入口', () => {
    it('新学员点击测试 → 跳转天赋页', () => {
      state.selectStudentType('new')
      state.startTalentTest()
      expect(uniMock.navigateTo).toHaveBeenCalledWith({
        url: '/pages/talent/index?from=onboarding&student_type=new',
      })
    })

    it('老学员点击测试 → 跳转天赋页并带 student_type', () => {
      state.selectStudentType('returning')
      state.startTalentTest()
      expect(uniMock.navigateTo).toHaveBeenCalledWith({
        url: '/pages/talent/index?from=onboarding&student_type=returning',
      })
    })
  })

  describe('老学员 Step 4+ — 训练数据', () => {
    beforeEach(() => {
      state.selectStudentType('returning')
      state.step.value = 4
    })

    it('选能力后进入逐项填写', () => {
      state.toggleAbility(0)
      state.confirmAbilities()
      expect(state.step.value).toBe(5)
      expect(state.currentAbility.value).toBe('超脑阅读')
    })

    it('最后一项完成 → step 100', () => {
      state.toggleAbility(0)
      state.confirmAbilities()
      state.nextDataStep()
      expect(state.step.value).toBe(100)
    })
  })
})
