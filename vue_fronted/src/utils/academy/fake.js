/** 学院三页在接口失败时用的假目录。讨论台词在 iframe 的 fake.js。 */

function episode(id, title, topic, unlocked) {
  return {
    id,
    title,
    topic,
    status: unlocked ? 'watched' : 'open',
    media: id <= 'E13' ? 'demo' : 'none',
    playable: id <= 'E13',
    unlocked,
  }
}

export function fakeAcademySector(episodeId) {
  const focus = (episodeId || 'E13').toUpperCase()
  return {
    fake: true,
    user_id: 0,
    badge: '学者 · Lv.2',
    talent_primary: '学者',
    overall_tier: 2,
    episode: {
      id: focus === 'E13' ? 'E13' : focus,
      title: focus === 'E13' ? '五兽桩' : focus === 'E14' ? '蒙上眼睛之后' : focus === 'EH01' ? '历史课·黄巢篇' : '模拟剧集',
      topic: focus === 'E14' ? '多元感知 · 圆形教室' : focus === 'EH01' ? '博物馆 · 满城尽带黄金甲' : '站桩 · 专注力修炼',
      task: focus === 'E14' ? '蒙眼认一张卡' : focus === 'EH01' ? '记住今天这节历史课' : '站桩5分钟',
      channel_name: focus === 'E13' ? 'E13 · 五兽桩讨论组' : focus === 'E14' ? 'E14 · 蒙上眼睛之后讨论组' : focus === 'EH01' ? 'EH01 · 历史课·黄巢篇讨论组' : `${focus} · 讨论组`,
      online_count: 6,
      notice: '频道公告：看完这一集再聊。——善雨导师',
      poster: '/static/dayu/assets/miji/mj-tfsd.jpg',
      duration_label: '模拟正片',
      play_url: '',
      media: 'demo',
      playable: true,
      unlocked: true,
      percent: 100,
      chips: focus === 'E14'
        ? ['戴上眼罩你怕不怕黑？', '你摸到卡片是什么感觉？', '五个世界里你最想问谁？']
        : focus === 'EH01'
          ? ['中国为什么没有种姓？', '黄巢最后当上皇帝了吗？', '那首诗你记住哪一句？']
          : ['这集你印象最深的是什么？', '今晚站桩谁跟我一组？', '我觉得我站不住怎么办？'],
      nudge: {
        text: '善雨导师提醒：聊完记得完成今晚训练，到大宇智能体打卡。',
        href: 'train.html',
      },
      cast: [
        { key: 'shanyu', name: '善雨', tag: '导师' },
        { key: 'jiahui', name: '王家慧', tag: '学者' },
      ],
    },
    switchable: [
      { id: 'E13', title: '五兽桩', channel_name: 'E13 · 五兽桩讨论组', unlocked: true, current: focus === 'E13' },
      { id: 'E14', title: '蒙上眼睛之后', channel_name: 'E14 · 蒙上眼睛之后讨论组', unlocked: true, current: focus === 'E14' },
      { id: 'EH01', title: '历史课·黄巢篇', channel_name: 'EH01 · 历史课·黄巢篇讨论组', unlocked: true, current: focus === 'EH01' },
    ],
    acts: [
      {
        no: '第三幕',
        name: '唤醒基本功',
        range: 'E08-E14',
        poster: '/static/dayu/assets/hall/study2.png',
        core: '闹市静坐、石头开花、书道三部曲。',
        tag: '含 7 集 · 专注 / 观察 / 记忆 / 书道',
        locked: false,
        status: 'ing',
        watched: 5,
        total: 7,
        episodes: [
          episode('E11', '眼中有太极', '书道Ⅰ', true),
          episode('E12', '心中有太极', '篆书开五窍', true),
          episode('E13', '五兽桩', '站桩 · 专注力修炼', true),
          episode('E14', '蒙上眼睛之后', '多元感知', false),
        ],
      },
    ],
    courses: {
      enrolled_count: 1,
      mine: {
        title: '大书道课程',
        subtitle: '进度跟书道剧集走；未看的讲次用模拟片',
        done: 2,
        total: 4,
        percent: 50,
        chapters: [
          { title: '第 1 讲 · 眼中有太极（书道Ⅰ）', episode_id: 'E11', status: 'done' },
          { title: '第 2 讲 · 心中有太极（篆书）', episode_id: 'E12', status: 'done' },
          { title: '第 3 讲 · 五兽桩 · 站桩定力', episode_id: 'E13', status: 'now' },
          { title: '第 4 讲 · 蒙上眼睛之后', episode_id: 'E14', status: 'todo' },
        ],
      },
      miji: [
        {
          name: '太极神功',
          cover: '/static/dayu/assets/miji/mj-jsys.jpg',
          desc: '思维太极',
          episode_id: 'E12',
          unlocked: true,
        },
      ],
      offers: [],
      camp: {
        enrolled: 183,
        seats_left: 7,
        seats_total: 190,
        open: false,
        note: '报名通道尚未开通',
      },
    },
  }
}
