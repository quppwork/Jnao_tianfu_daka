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

/** 顶区 chips */
export const HOME_CHIPS = [
  { key: 'talent', label: '天赋测试', path: '/pages/talent/hub' },
  { key: 'story', label: '历史剧情', path: '/pages/hub/story' },
  { key: 'course', label: '天赋课程', path: '/pages/hub/courses' },
]

export function switchMainTab(path) {
  const full = String(path || '')
  if (!full) return
  const target = full.split('?')[0]
  const pages = getCurrentPages()
  const cur = pages.length ? `/${pages[pages.length - 1].route}` : ''
  if (cur === target && !full.includes('?')) return
  uni.reLaunch({ url: full.startsWith('/') ? full : `/${full}` })
}
