/** 主流程底栏路由（大宇改版壳 + 现有业务页） */

export const MAIN_TABS = [
  {
    key: 'guide',
    label: '大宇AI',
    path: '/pages/dayu/home',
    icon: '/static/dayu/assets/ic/robot.png',
  },
  {
    key: 'train',
    label: '今日修炼',
    path: '/pages/training/dayu',
    icon: '/static/dayu/assets/ic/map.png',
  },
  {
    key: 'qa',
    label: '学科答疑',
    path: '/pages/qa/dayu',
    icon: '/static/dayu/assets/ic/cap.png',
  },
  {
    key: 'academy',
    label: '天赋学院',
    path: '/pages/hub/academy',
    icon: '/static/dayu/assets/ic/bubble.png',
  },
  {
    key: 'console',
    label: '中央电脑',
    path: '/pages/hub/console',
    icon: '/static/dayu/assets/ic/computer.png',
  },
]

export const PARENT_TABS = [
  { key: 'dayu', label: '大宇', path: '/pages/parent/dayu', icon: '/static/dayu/assets/ic/robot.png' },
  { key: 'community', label: '天赋社区', path: '/pages/parent/community', icon: '/static/dayu/assets/ic/family.png' },
  { key: 'consult', label: '在线咨询', path: '/pages/parent/consult', icon: '/static/dayu/assets/ic/bubble.png' },
  { key: 'pdata', label: '数据分析', path: '/pages/parent/pdata', icon: '/static/dayu/assets/ic/target.png' },
  { key: 'pset', label: '我的', path: '/pages/parent/pset', icon: '/static/dayu/assets/ic/person.png' },
]

/** 顶区 chips */
export const HOME_CHIPS = [
  { key: 'talent', label: '天赋测试', path: '/pages/talent/hub' },
  { key: 'story', label: '历史剧情', path: '/pages/hub/story' },
  { key: 'course', label: '天赋课程', path: '/pages/hub/courses' },
]

const MAIN_TAB_ROUTES = new Set(MAIN_TABS.map((t) => normalizeRoute(t.path)))
const PARENT_TAB_ROUTES = new Set(PARENT_TABS.map((t) => normalizeRoute(t.path)))

function normalizeRoute(path) {
  return String(path || '').split('?')[0].replace(/^\//, '')
}

function withSlash(path) {
  const p = String(path || '')
  return p.startsWith('/') ? p : `/${p}`
}

function currentRoute() {
  try {
    const pages = getCurrentPages()
    if (!pages.length) return ''
    return String(pages[pages.length - 1].route || '')
  } catch (_) {
    return ''
  }
}

/**
 * 软切：仅「上一页就是目标」时 navigateBack（保留学院 iframe）；
 * 主底栏其它互切一律 redirectTo。
 * 禁止跨层 back——否则学院⇄中央电脑会偶发弹回大宇首页。
 */
const TAB_STACK_SOFT_MAX = 6
let _navLockUntil = 0

function softNavigate(url) {
  const full = withSlash(url)
  const target = normalizeRoute(full)
  if (!target) return
  const cur = currentRoute()
  const hasQuery = String(full).includes('?')
  if (cur === target && !hasQuery) return

  const now = Date.now()
  if (now < _navLockUntil) return
  _navLockUntil = now + 320

  // 同路由但带 ?ep= 等参数：必须 replace，navigateBack 会丢掉 query
  if (cur === target && hasQuery) {
    uni.redirectTo({
      url: full,
      fail: () => uni.reLaunch({ url: full }),
    })
    return
  }

  try {
    const pages = getCurrentPages()
    // 只允许相邻回退：刚从学院进中央电脑再点回来时，保留讨论区 DOM
    if (!hasQuery && pages.length >= 2) {
      const prev = String(pages[pages.length - 2].route || '')
      if (prev === target) {
        uni.navigateBack({ delta: 1 })
        return
      }
    }
    // 主底栏互切：redirectTo，避免栈越堆越深、跨层 back 弹回首页
    if (MAIN_TAB_ROUTES.has(target) && (!cur || MAIN_TAB_ROUTES.has(cur))) {
      uni.redirectTo({
        url: full,
        fail: () => uni.reLaunch({ url: full }),
      })
      return
    }
    if (pages.length < TAB_STACK_SOFT_MAX) {
      uni.navigateTo({
        url: full,
        fail: () => uni.redirectTo({
          url: full,
          fail: () => uni.reLaunch({ url: full }),
        }),
      })
      return
    }
  } catch (_) { /* ignore */ }

  uni.redirectTo({
    url: full,
    fail: () => uni.reLaunch({ url: full }),
  })
}

export function switchMainTab(path) {
  softNavigate(path)
}

/**
 * 家长五底栏互切：一律 redirectTo，禁止 navigateBack。
 * softNavigate 会在栈里找到更早的「大宇」并 pop 回去，表现为偶发弹回首页。
 * 家长页是 iframe 壳，不必用栈保留 DOM。
 */
export function switchParentTab(path) {
  const full = withSlash(path)
  const target = normalizeRoute(full)
  if (!target) return
  const cur = currentRoute()
  const hasQuery = String(full).includes('?')
  if (cur === target && !hasQuery) return
  uni.redirectTo({
    url: full,
    fail: () => uni.reLaunch({ url: full }),
  })
}

/** 通用页内跳转：Tab 走软切，其它 navigateTo */
export function goAppPage(path) {
  const full = withSlash(path)
  const route = normalizeRoute(full)
  if (MAIN_TAB_ROUTES.has(route)) {
    switchMainTab(full)
    return
  }
  if (PARENT_TAB_ROUTES.has(route)) {
    switchParentTab(full)
    return
  }
  uni.navigateTo({
    url: full,
    fail: () => uni.redirectTo({
      url: full,
      fail: () => uni.reLaunch({ url: full }),
    }),
  })
}
