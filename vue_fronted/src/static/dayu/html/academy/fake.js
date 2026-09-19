/* 接口失败时的假目录和假对话。真实接口成功就不用这份。 */
(function (root) {
  var ns = root.JnaoAcademy = root.JnaoAcademy || {}
  var LINES = {
    jiahui: ['膝盖不过脚尖，重心落涌泉。笔记我整理好了。', '先站3分钟标准桩，比10分钟歪桩有用。'],
    yuchen: ['十桩功我连起来看懂了，就是腿还没看懂。', '先站5分钟再想原理，我认了。'],
    dani: ['我已经拉钩了，谁也不许偷懒。', '你打卡了我就打。'],
    limo: ['站一分钟是一分钟的功夫。', '今晚我陪你站。站完一起打卡。'],
    chenxue: ['看完就一个想法：我也要打到那个境界。', '你敢站上来就已经赢了一半。'],
    shanyu: ['今晚的任务记牢，到大宇智能体打卡。桩上见。', '聊得热闹。聊完，心别跑。']
  }
  var ORDER = ['jiahui', 'yuchen', 'dani', 'limo', 'chenxue']

  function line(who, salt) {
    var pool = LINES[who] || LINES.dani
    return { who: who, bot_id: 'bot_' + who, text: pool[Math.abs(salt) % pool.length] }
  }

  ns.fakeOpen = function () {
    return {
      replay: false,
      turns: [line('jiahui', 1), line('yuchen', 2), line('dani', 3), line('shanyu', 0)],
      nudge: {
        text: '善雨导师提醒：聊完记得完成今晚训练——站桩5分钟，到大宇智能体打卡。',
        href: 'train.html'
      }
    }
  }

  ns.fakeReply = function (payload) {
    var body = typeof payload === 'string' ? { text: payload } : (payload || {})
    var text = body.text || ''
    var salt = text.length || 1
    var first = body.mention || (body.quote && body.quote.who) || ORDER[salt % ORDER.length]
    if (!LINES[first]) first = ORDER[salt % ORDER.length]
    var turn = line(first, salt)
    turn.text = turn.text.replace(/。$/, '呀')
    if (body.quote && body.quote.text) turn.quote = body.quote
    if (body.sticker) turn.text = '哈哈看到了 ' + body.sticker
    var turns = [turn]
    if (!body.mention && !(body.quote && body.quote.who) && salt % 3 === 0) turns.push(line('shanyu', salt))
    return { turns: turns, nudge: salt % 3 === 0 ? ns.fakeOpen().nudge : null }
  }
  ns.fakeSector = function () {
    return {
      fake: true,
      user_id: 0,
      badge: '学者 · Lv.2',
      episode: {
        id: 'E13',
        title: '五兽桩',
        topic: '站桩 · 专注力修炼',
        task: '站桩5分钟',
        channel_name: 'E13 · 五兽桩讨论组',
        online_count: 6,
        notice: '频道公告：今晚站桩5分钟。——善雨导师',
        poster: '/static/dayu/assets/miji/mj-tfsd.jpg',
        duration_label: '模拟正片',
        media: 'demo',
        playable: true,
        unlocked: true,
        chips: ['这集你印象最深的是什么？', '今晚站桩谁跟我一组？', '我觉得我站不住怎么办？'],
        nudge: ns.fakeOpen().nudge,
        cast: []
      },
      acts: [{
        no: '第三幕', name: '唤醒基本功', range: 'E08-E14',
        poster: '/static/dayu/assets/hall/study2.png',
        core: '闹市静坐、石头开花、书道三部曲。',
        tag: '含 7 集',
        locked: false, status: 'ing', watched: 5, total: 7,
        episodes: [
          { id: 'E13', title: '五兽桩', topic: '站桩', status: 'watched', media: 'demo', playable: true, unlocked: true }
        ]
      }],
      courses: {
        camp: { enrolled: 183, seats_left: 7, seats_total: 190, open: false, note: '报名通道尚未开通' },
        mine: {
          done: 2, total: 4, percent: 50,
          chapters: [
            { title: '第 3 讲 · 五兽桩 · 站桩定力', episode_id: 'E13', status: 'now' }
          ]
        },
        miji: [
          { name: '太极神功', cover: '/static/dayu/assets/miji/mj-jsys.jpg', episode_id: 'E12' }
        ]
      }
    }
  }
})(window)
