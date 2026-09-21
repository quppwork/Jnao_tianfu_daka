/* 接口失败时的假目录和假对话。真实接口成功就不用这份。 */
(function (root) {
  var ns = root.JnaoAcademy = root.JnaoAcademy || {}

  var LINES_BY_EP = {
    E13: {
      jiahui: ['膝盖不过脚尖，重心落涌泉。笔记我整理好了。', '先站3分钟标准桩，比10分钟歪桩有用。'],
      yuchen: ['十桩功我连起来看懂了，就是腿还没看懂。', '先站5分钟再想原理，我认了。'],
      dani: ['我已经拉钩了，谁也不许偷懒。', '你站我就站。'],
      limo: ['站一分钟是一分钟的功夫。', '今晚我陪你站。'],
      chenxue: ['看完就一个想法：我也要打到那个境界。', '你敢站上来就已经赢了一半。'],
      shanyu: ['心不定，这一下是空的。', '聊得热闹。聊完，心别跑。']
    },
    E14: {
      jiahui: ['红的粒子中间有个黑三角。我第一次听见自己的声音发颤。', '眼罩一戴，标准就只剩指尖了。'],
      yuchen: ['关了灯我想到绿，绿漫成一大片草地。不是卡片绿，是我想到了绿。', '眼睛关了，脑子反而更吵。'],
      dani: ['卡片是平的。我搓边却摸到棱。老师说是大脑把信号放大了。', '关灯那一下我抓住你袖子了，别笑。'],
      limo: ['黄的，方的。就是知道。为什么，我还说不清。', '摸到了。别问我怎么摸到的。'],
      chenxue: ['蓝的圆的，看得清楚。边上那点联想不重要，我掐了。', '别怕黑。黑只是把眼睛关了。'],
      shanyu: ['眼睛关了，世界不会关。', '聊得热闹。聊完，心别跑。']
    },
    EH01: {
      jiahui: ['我把那首诗抄进笔记：冲天香阵透长安，满城尽带黄金甲。', '种姓那面墙，我先把名字和顺序记下来了。'],
      yuchen: ['我盯着画问：黄巢最后当上皇帝了没有。老师说称帝四年就没了。', '榜上没有名字的时候，人会把整张榜烧掉吗？'],
      dani: ['他杀那么多人，里面也有孩子。老师说是榜和大旱先把他逼到墙角。', '听完我有点难受，但还想听完。'],
      limo: ['听到杀遍贵族，我的手自己握紧了。诗我没抄，拳头记得。', '油画里的甲，比字更沉。'],
      chenxue: ['中国为什么没有种姓？不赶尽杀绝，世家后代会不会报仇？', '这堂课不像讲故事，像在问我们站哪边。'],
      shanyu: ['历史课听完了。问完再离开。', '聊得热闹。聊完，心别跑。']
    }
  }
  var ORDER = ['jiahui', 'yuchen', 'dani', 'limo', 'chenxue']

  function epId(explicit) {
    var id = String(explicit || (ns.state && ns.state.episode && ns.state.episode.id) || 'E13').trim().toUpperCase()
    return id || 'E13'
  }

  function linesFor(id) {
    return LINES_BY_EP[epId(id)] || LINES_BY_EP.E13
  }

  function line(who, salt, id) {
    var pool = (linesFor(id)[who] || linesFor(id).dani || LINES_BY_EP.E13.dani)
    return { who: who, bot_id: 'bot_' + who, text: pool[Math.abs(salt) % pool.length] }
  }

  function turnsFitEpisode(id, turns) {
    var blob = (turns || []).map(function (t) { return t && t.text || '' }).join('')
    var eid = epId(id)
    var stake = /站桩|标准桩|十桩|涌泉|膝盖不过脚尖/.test(blob)
    var blind = /眼罩|卡片|关灯|摸到|草地|粒子|棱|田小静/.test(blob)
    var hist = /黄巢|种姓|博物馆|黄金甲|大齐|冲天香阵/.test(blob)
    if (eid === 'E14') return !(stake && !blind)
    if (eid === 'EH01') return !((stake || blind) && !hist)
    if (eid === 'E13') return !((blind && !stake) || (hist && !stake))
    return true
  }

  ns.turnsFitEpisode = turnsFitEpisode

  ns.fakeOpen = function (episodeId) {
    var id = epId(episodeId)
    var meta = EP_META[id] || EP_META.E13
    return {
      replay: false,
      turns: [line('jiahui', 1, id), line('yuchen', 2, id), line('dani', 3, id), line('shanyu', 0, id)],
      nudge: {
        text: '善雨导师提醒：聊完记得完成今晚训练——' + (meta.task || '看完这一集') + '，到大宇智能体打卡。',
        href: 'train.html'
      }
    }
  }

  ns.fakeReply = function (payload) {
    var body = typeof payload === 'string' ? { text: payload } : (payload || {})
    var text = body.text || ''
    var salt = text.length || 1
    var id = epId()
    var first = body.mention || (body.quote && body.quote.who) || ORDER[salt % ORDER.length]
    if (!linesFor(id)[first]) first = ORDER[salt % ORDER.length]
    var turn = line(first, salt, id)
    turn.text = turn.text.replace(/。$/, '呀')
    if (body.quote && body.quote.text) turn.quote = body.quote
    if (body.sticker) turn.text = '哈哈看到了 ' + body.sticker
    var turns = [turn]
    if (!body.mention && !(body.quote && body.quote.who) && salt % 3 === 0) turns.push(line('shanyu', salt, id))
    return { turns: turns, nudge: salt % 3 === 0 ? ns.fakeOpen(id).nudge : null }
  }
  var SWITCHABLE = [
    { id: 'E13', title: '五兽桩', channel_name: 'E13 · 五兽桩讨论组', unlocked: true },
    { id: 'E14', title: '蒙上眼睛之后', channel_name: 'E14 · 蒙上眼睛之后讨论组', unlocked: true },
    { id: 'EH01', title: '历史课·黄巢篇', channel_name: 'EH01 · 历史课·黄巢篇讨论组', unlocked: true },
  ]

  var EP_META = {
    E13: {
      title: '五兽桩',
      topic: '站桩 · 专注力修炼',
      task: '站桩5分钟',
      channel_name: 'E13 · 五兽桩讨论组',
      notice: '频道公告：今晚站桩5分钟。——善雨导师',
      chips: ['这集你印象最深的是什么？', '今晚站桩谁跟我一组？', '我觉得我站不住怎么办？'],
    },
    E14: {
      title: '蒙上眼睛之后',
      topic: '多元感知 · 圆形教室',
      task: '蒙眼认一张卡',
      channel_name: 'E14 · 蒙上眼睛之后讨论组',
      notice: '频道公告：今晚蒙眼认一张卡。——善雨导师',
      chips: ['戴上眼罩你怕不怕黑？', '你摸到卡片是什么感觉？', '五个世界里你最想问谁？'],
    },
    EH01: {
      title: '历史课·黄巢篇',
      topic: '博物馆 · 满城尽带黄金甲',
      task: '记住今天这节历史课',
      channel_name: 'EH01 · 历史课·黄巢篇讨论组',
      notice: '频道公告：记住今天这节历史课。——善雨导师',
      chips: ['中国为什么没有种姓？', '黄巢最后当上皇帝了吗？', '那首诗你记住哪一句？'],
    },
  }

  ns.fakeSectorFor = function (episodeId) {
    var focus = String(episodeId || 'E13').trim().toUpperCase() || 'E13'
    var meta = EP_META[focus] || {
      title: focus,
      topic: '模拟剧集',
      task: '看完这一集',
      channel_name: focus + ' · 讨论组',
      notice: '频道公告：看完这一集再聊。——善雨导师',
      chips: ['这集你印象最深的是什么？'],
    }
    return {
      fake: true,
      user_id: 0,
      badge: '学者 · Lv.2',
      episode: {
        id: focus,
        title: meta.title,
        topic: meta.topic,
        task: meta.task,
        channel_name: meta.channel_name,
        online_count: 6,
        notice: meta.notice,
        poster: '/static/dayu/assets/miji/mj-tfsd.jpg',
        duration_label: '模拟正片',
        media: 'demo',
        playable: true,
        unlocked: true,
        chips: meta.chips,
        nudge: ns.fakeOpen(focus).nudge,
        cast: []
      },
      switchable: SWITCHABLE.map(function (item) {
        return {
          id: item.id,
          title: item.title,
          channel_name: item.channel_name,
          unlocked: true,
          current: item.id === focus,
        }
      }),
      acts: [{
        no: '第三幕', name: '唤醒基本功', range: 'E08-E14',
        poster: '/static/dayu/assets/hall/study2.png',
        core: '闹市静坐、石头开花、书道三部曲。',
        tag: '含 7 集',
        locked: false, status: 'ing', watched: 5, total: 7,
        episodes: [
          { id: 'E13', title: '五兽桩', topic: '站桩', status: 'watched', media: 'demo', playable: true, unlocked: true },
          { id: 'E14', title: '蒙上眼睛之后', topic: '多元感知', status: 'open', media: 'demo', playable: true, unlocked: true }
        ]
      }],
      courses: {
        camp: { enrolled: 183, seats_left: 7, seats_total: 190, open: false, note: '报名通道尚未开通' },
        mine: {
          done: 2, total: 4, percent: 50,
          chapters: [
            { title: '第 3 讲 · 五兽桩 · 站桩定力', episode_id: 'E13', status: 'now' },
            { title: '第 4 讲 · 蒙上眼睛之后', episode_id: 'E14', status: 'todo' }
          ]
        },
        miji: [
          { name: '太极神功', cover: '/static/dayu/assets/miji/mj-jsys.jpg', episode_id: 'E12' }
        ]
      }
    }
  }

  ns.fakeSector = function () {
    return ns.fakeSectorFor('E13')
  }
})(window)
