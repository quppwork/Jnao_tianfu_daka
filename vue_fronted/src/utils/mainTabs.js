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

/** 软切：优先 stack 回退，再 redirectTo。不用官方 tabBar，避免和页面自绘底栏叠两层。 */
function softNavigate(url) {
  const full = withSlash(url)
  const target = normalizeRoute(full)
  if (!target) return
  const cur = currentRoute()
  const hasQuery = String(full).includes('?')
  if (cur === target && !hasQuery) return

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
    if (!hasQuery) {
      for (let i = pages.length - 2; i >= 0; i -= 1) {
        if (String(pages[i].route || '') === target) {
          uni.navigateBack({ delta: pages.length - 1 - i })
          return
        }
      }
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

export function switchParentTab(path) {
  softNavigate(path)
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
