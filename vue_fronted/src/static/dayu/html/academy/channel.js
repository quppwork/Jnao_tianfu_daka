/* 频道页：海报、播放、解锁、讨论。不管剧情长卷和课程。 */
(function (root) {
  var ns = root.JnaoAcademy
  if (!ns) return
  var $ = ns.$

  /** 开房结果预取：仅已解锁才打 /open；403 后冻结，禁止空转重试刷屏 */
  var openWarm = { id: '', uid: '', live: false, promise: null, data: null, blocked: false }

  function showEndOverlay() {
    // 播完正片后才允许 joinChat 补报 progress；「同步中」条不可走此旁路
    root.__academyAllowProgressUnlock = true
    var box = $('vbox')
    if (box) {
      box.classList.remove('playing')
      box.classList.add('ended')
    }
    var video = $('vvideo')
    if (video) {
      try { video.pause() } catch (e) { /* ignore */ }
      video.removeAttribute('controls')
    }
    if ($('vend')) $('vend').style.display = 'flex'
    if ($('dmk')) $('dmk').innerHTML = ''
  }

  function hideEndOverlay() {
    if ($('vend')) $('vend').style.display = 'none'
    var box = $('vbox')
    if (box) box.classList.remove('ended')
    var video = $('vvideo')
    if (video) video.setAttribute('controls', '')
  }

  function syncUnlockedToParent(ep) {
    if (!ep || !ep.id || !ns.state) return
    try {
      var payload = ns.state
      if (payload.episode && payload.episode.id === ep.id) {
        payload.episode.unlocked = true
        payload.episode.percent = Math.max(Number(payload.episode.percent) || 0, 100)
      }
      localStorage.removeItem('jnao_academy_sector')
      localStorage.setItem(sectorCacheKey(), JSON.stringify(payload))
      if (root.parent && root.parent !== root) {
        root.parent.postMessage({ type: 'dayu-academy-sync', academy: payload }, '*')
      }
    } catch (e) { /* ignore */ }
  }

  /** 未知 ≠ 未解锁：pending 显示同步中，避免首屏先闪锁定再变讨论组 */
  function unlockPhase(ep) {
    if (!ep) return 'pending'
    if (ep.unlocked) return 'unlocked'
    var liveId = String(ns.sectorLiveId || '')
    var epId = String(ep.id || '')
    if (ns.sectorLiveOk && liveId && epId && liveId === epId) return 'locked'
    return 'pending'
  }

  function markSectorLive(ep) {
    if (!ep || !ep.id) return
    ns.sectorLiveOk = true
    ns.sectorLiveId = String(ep.id)
  }

  function refreshUnlockChrome(ep) {
    if (!ep) return
    var phase = unlockPhase(ep)
    var unlocked = phase === 'unlocked'
    var pending = phase === 'pending'
    var locked = phase === 'locked'
    if ($('inp')) {
      $('inp').disabled = !joined
      if (!joined) {
        $('inp').placeholder = unlocked
          ? '点击加入讨论'
          : pending
            ? '正在同步本集进度…'
            : '看完正片即可加入讨论'
      }
    }
    var lk2 = document.querySelector('#chatroom .lk2')
    var lk3 = document.querySelector('#chatroom .lk3')
    if (lk2) {
      lk2.textContent = unlocked
        ? '本集已解锁，点「加入频道讨论」进入'
        : pending
          ? '正在同步本集进度…'
          : '看完正片，即可加入讨论'
    }
    if (lk3) {
      lk3.textContent = unlocked
        ? '加入频道讨论 →'
        : pending
          ? '同步进度中…'
          : '看完正片即可加入讨论'
      lk3.style.cursor = unlocked ? 'pointer' : 'default'
      lk3.style.pointerEvents = unlocked ? '' : 'none'
      lk3.onclick = unlocked
        ? function (ev) {
            try { if (ev) { ev.preventDefault(); ev.stopPropagation() } } catch (e0) { /* ignore */ }
            if (typeof root.joinChat === 'function') root.joinChat()
            else if (typeof joinChat === 'function') joinChat()
          }
        : null
    }
    var browseJoin = $('browseJoin')
    if (browseJoin) {
      var phone = document.querySelector('.phone')
      var inBrowse = !!(phone && phone.classList.contains('browse-mode'))
      var show = inBrowse && !joined
      browseJoin.classList.toggle('is-on', unlocked && show)
      browseJoin.classList.toggle('is-pending', pending && show)
      browseJoin.classList.toggle('is-locked', locked && show)
      try {
        if (unlocked) {
          browseJoin.innerHTML = '进入讨论组 →<small>本集已解锁，点这里和角色聊</small>'
        } else if (pending) {
          browseJoin.innerHTML = '同步进度中…<small>正在确认本集是否已解锁</small>'
        } else {
          browseJoin.innerHTML = '看完正片即可加入讨论<small>看完正片后再来聊</small>'
        }
      } catch (eBj2) { /* ignore */ }
      // 仅后端确认已解锁时可点；pending / locked 一律不可进
      if (unlocked) {
        browseJoin.setAttribute('role', 'button')
        browseJoin.setAttribute('aria-disabled', 'false')
        browseJoin.onclick = function (ev) {
          try { if (ev) { ev.preventDefault(); ev.stopPropagation() } } catch (e4) { /* ignore */ }
          if (joinGateBlocked()) return
          if (typeof root.joinChat === 'function') root.joinChat()
          else if (typeof joinChat === 'function') joinChat()
        }
      } else {
        browseJoin.removeAttribute('role')
        browseJoin.setAttribute('aria-disabled', 'true')
        browseJoin.onclick = null
      }
    }
  }

  function markUnlocked(data, ep, opts) {
    if (!ep) return
    var pct = data && data.percent != null ? Number(data.percent) : NaN
    var unlocked = !!(data && (data.unlocked || pct >= 90))
    if (!unlocked) return
    ep.unlocked = true
    if (isFinite(pct) && pct > Number(ep.percent || 0)) ep.percent = pct
    else if (!ep.percent || ep.percent < 90) ep.percent = 100
    // 刚解锁：清掉此前 403 冻结；仅预热，不展开讨论
    if (openWarm.id === ep.id || !openWarm.id) {
      openWarm.blocked = false
      if (openWarm.id === ep.id) {
        openWarm.promise = null
        openWarm.data = null
      }
    }
    syncUnlockedToParent(ep)
    refreshUnlockChrome(ep)
    warmOpenRoom(ep).catch(function () { /* ignore */ })
    if (opts && opts.showEnd) showEndOverlay()
  }

  /** 同集陈旧 hydrate 不得把已解锁打回锁定（否则播完「进入讨论组」会消失） */
  function preserveLocalUnlock(nextEp) {
    var prev = ns.state && ns.state.episode
    if (!prev || !nextEp || prev.id !== nextEp.id) return nextEp
    if (prev.unlocked && !nextEp.unlocked) {
      nextEp.unlocked = true
      nextEp.percent = Math.max(Number(nextEp.percent) || 0, Number(prev.percent) || 0, 100)
    }
    return nextEp
  }

  function resolvePlaySrc(playUrl) {
    if (!playUrl) return ''
    if (/^(https?:|blob:|data:)/i.test(playUrl)) return playUrl
    var origin = ''
    try { origin = root.location.origin } catch (e) { /* ignore */ }
    var url = String(playUrl)
    var uid = ns.userId && ns.userId()
    if (uid && url.indexOf('user_id=') < 0) {
      url += (url.indexOf('?') >= 0 ? '&' : '?') + 'user_id=' + encodeURIComponent(uid)
    }
    return origin ? (origin + url) : url
  }

  function ensureVideo() {
    var box = $('vbox')
    if (!box) return null
    box.style.position = 'relative'
    var video = $('vvideo')
    if (video) return video
    video = document.createElement('video')
    video.id = 'vvideo'
    video.setAttribute('playsinline', '')
    video.setAttribute('webkit-playsinline', '')
    video.setAttribute('controls', '')
    video.preload = 'auto'
    video.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:2;background:#000;display:none'
    box.insertBefore(video, box.firstChild)
    return video
  }

  function simulateWatch(ep) {
    if (root.__academyPlaying) return
    root.__academyPlaying = true
    hideEndOverlay()
    $('vbox').classList.add('playing')
    if (typeof startDanmaku === 'function') startDanmaku()
    var percent = 0
    var timer = setInterval(function () {
      percent += 4
      if ($('vprogI')) $('vprogI').style.width = Math.min(100, percent) + '%'
      // 未解锁时 open 会 403，等 progress 落库后再 warm
      if (percent < 100) return
      clearInterval(timer)
      root.__academyPlaying = false
      ns.api('/api/academy/episodes/' + ep.id + '/progress', { percent: 100 })
        .then(function (data) { markUnlocked(data, ep, { showEnd: true }) })
        .catch(function () {
          showEndOverlay()
          ns.toast('进度没记上，再看一遍')
        })
    }, 90)
  }

  function storageUid() {
    var uid = (ns.userId && ns.userId()) || ''
    return uid || 'guest'
  }

  function roomKey(id) {
    // 按孩子隔离；旧版 jnao_academy_room_<ep> 无 uid，换号会串历史
    return 'jnao_academy_room_' + storageUid() + '_' + id
  }

  function dropLegacyRoom(id) {
    if (!id) return
    try { localStorage.removeItem('jnao_academy_room_' + id) } catch (e) { /* ignore */ }
  }

  function readRoom(id) {
    try {
      var raw = JSON.parse(localStorage.getItem(roomKey(id)) || 'null')
      if (!Array.isArray(raw) || !raw.length) return null
      if (ns.turnsFitEpisode && !ns.turnsFitEpisode(id, raw)) {
        try { localStorage.removeItem(roomKey(id)) } catch (e2) { /* ignore */ }
        return null
      }
      return raw
    } catch (e) {
      return null
    }
  }

  function writeRoom(id, turns) {
    try {
      dropLegacyRoom(id)
      localStorage.setItem(roomKey(id), JSON.stringify((turns || []).slice(-40)))
    } catch (e) { /* 隐私模式写不进也不影响这一次 */ }
  }

  function clearOpenWarm() {
    openWarm = { id: '', uid: '', live: false, promise: null, data: null, blocked: false }
  }

  function viewKey(id) {
    return 'jnao_academy_view_' + storageUid() + '_' + id
  }

  function sectorCacheKey() {
    return 'jnao_academy_sector_' + storageUid()
  }

  function rememberChatView(id) {
    if (!id) return
    try { sessionStorage.setItem(viewKey(id), 'chat') } catch (e) { /* ignore */ }
  }

  function wantsChatView(ep) {
    // 仅表示本集已解锁可进讨论；不自动弹出讨论页
    return !!(ep && ep.id && ep.unlocked)
  }

  // 切集后短时忽略「加入讨论」，避免下拉点选集的点击穿透到蒙层按钮
  var joinGateUntil = 0

  function armJoinGate(ms) {
    joinGateUntil = Date.now() + (ms || 600)
  }

  function joinGateBlocked() {
    return Date.now() < joinGateUntil
  }

  /** 切集 / 进页：隐藏整块讨论区，仅播完条「加入讨论」或 joinChat 可打开 */
  function collapseToAcademyView(ep) {
    armJoinGate(800)
    joined = false
    shownRoom = ''
    try { clearTimeout(teaserTm) } catch (e) { /* ignore */ }
    if ($('msgs')) $('msgs').innerHTML = ''
    if ($('nudgeSlot')) $('nudgeSlot').innerHTML = ''
    if ($('replies')) {
      $('replies').innerHTML = ''
      $('replies').style.display = 'none'
    }
    if (typeof root.clearNudgeUi === 'function') {
      try { root.clearNudgeUi(false) } catch (e0) { /* ignore */ }
    }
    if ($('stage')) $('stage').classList.remove('on')
    if ($('chatroom')) $('chatroom').classList.add('locked-teaser')
    var phone = document.querySelector('.phone')
    if (phone) {
      phone.classList.add('browse-mode')
      phone.classList.remove('qq-chat', 'qq-peek', 'qq-sliding')
    }
    try { document.documentElement.style.removeProperty('--qq-top') } catch (e2) { /* ignore */ }
    refreshUnlockChrome(ep)
    if (typeof syncChatDock === 'function') syncChatDock()
    // 切集 / 点换集：绝不在这里 warm/open，避免异步回调把讨论又拉起来
  }

  function unlockChatShell() {
    joined = true
    try { clearTimeout(teaserTm) } catch (e) { /* ignore */ }
    var ep = ns.state && ns.state.episode
    if (ep && ep.id && ep.unlocked) {
      rememberChatView(ep.id)
    }
    if ($('chatroom')) $('chatroom').classList.remove('locked-teaser')
    if ($('stage')) $('stage').classList.add('on')
    if ($('inp')) {
      $('inp').disabled = false
      $('inp').placeholder = '说点什么，可以 @ 人或按住引用'
    }
    // 加入讨论 → 直接全屏讨论页（上滑标题条可回到学院页）
    var phone = document.querySelector('.phone')
    if (phone) {
      phone.classList.remove('browse-mode', 'qq-peek')
    }
    var browseJoin = $('browseJoin')
    if (browseJoin) {
      browseJoin.classList.remove('is-on', 'is-pending', 'is-locked')
      browseJoin.onclick = null
    }
    try { document.documentElement.style.setProperty('--qq-top', '0px') } catch (e) { /* ignore */ }
    if (typeof syncChatDock === 'function') syncChatDock()
    if (typeof showChips === 'function') {
      try { showChips() } catch (e) { /* ignore */ }
    }
    setTimeout(function () {
      if (typeof scrollChat === 'function') scrollChat()
    }, 60)
  }

  function lockChatShell() {
    collapseToAcademyView(ns.state && ns.state.episode)
  }

  /** 滚到讨论区，并让消息列表停在最新一条。不 focus 输入框，避免弹出键盘。 */
  function scrollToLatestChat() {
    var room = $('chatroom')
    if (room) {
      try { room.scrollIntoView({ behavior: 'smooth', block: 'start' }) } catch (e) { /* ignore */ }
    }
    function pinBottom() {
      if (typeof syncChatDock === 'function') syncChatDock()
      if (typeof scrollChat === 'function') {
        scrollChat()
        return
      }
      var wrap = $('msgwrap')
      if (wrap) wrap.scrollTop = wrap.scrollHeight
    }
    pinBottom()
    setTimeout(pinBottom, 80)
    setTimeout(pinBottom, 280)
  }

  function restoreRoomQuiet(ep) {
    if (!ep || !ep.id) return
    var live = !!(ns.userId && ns.userId())
    var roomMark = (live ? 'live:' : 'fake:') + storageUid() + ':' + ep.id
    if (shownRoom === roomMark && $('msgs') && $('msgs').children.length) {
      scrollToLatestChat()
      return
    }
    var cached = readRoom(ep.id)
    if (cached && cached.length) {
      shownRoom = roomMark
      if ($('msgs')) $('msgs').innerHTML = ''
      paintSaved(ep, { replay: true, turns: cached, nudge: ep.nudge }, true)
        .then(function () { scrollToLatestChat() })
      // 后台校验/补全服务端房间，失败也不清本地对话
      warmOpenRoom(ep).catch(function () { /* ignore */ })
      return
    }
    // 已解锁但无本地缓存：先进讨论壳，后台开房，避免卡在二次看片
    if (typeof addSys === 'function') {
      try { addSys('角色正在开口…') } catch (e) { /* ignore */ }
    }
    warmOpenRoom(ep).then(function (data) {
      if (!data || !ns.state || !ns.state.episode || ns.state.episode.id !== ep.id) return
      if (!wantsChatView(ep)) return
      shownRoom = roomMark
      if ($('msgs')) $('msgs').innerHTML = ''
      return paintSaved(ep, data, true).then(function () { scrollToLatestChat() })
    }).catch(function () { /* 进页预取失败，点讨论时再开 */ })
  }

  function prefetchChatAssets() {
    var chars = root.CHARS || {}
    var urls = {}
    Object.keys(chars).forEach(function (key) {
      var c = chars[key]
      if (!c) return
      ;[c.av, c.bg, c.sp].forEach(function (u) {
        if (u) urls[u] = true
      })
    })
    ;[
      '/static/dayu/assets/bg-dorm.png',
      '/static/dayu/assets/bg-study.png',
      '/static/dayu/assets/ip/sizhe.png?v=nobg',
      '/static/dayu/assets/ip/dezhe.png?v=nobg',
      '/static/dayu/assets/ip/xingzhe.png?v=nobg',
      '/static/dayu/assets/ip/xuezhe.png?v=nobg',
      '/static/dayu/assets/ip/yingzhe.png?v=nobg',
      '/static/dayu/assets/avatar_teacher.jpg',
      '/static/dayu/assets/avatar-mind.jpg',
      '/static/dayu/assets/gif/mentor-mind.gif',
    ].forEach(function (u) { urls[u] = true })
    Object.keys(urls).forEach(function (src) {
      try {
        var img = new Image()
        img.decoding = 'async'
        img.src = src
      } catch (e) { /* ignore */ }
    })
  }

  function fetchOpenPayload(ep, live) {
    if (!ep || !ep.unlocked) {
      var locked = new Error('看完正片才能加入讨论')
      locked.status = 403
      return Promise.reject(locked)
    }
    var cached = readRoom(ep.id)
    // 本地已有对话：切回学院直接用缓存，避免重复 open（失败会刷红、还会冲界面）
    if (cached && cached.length) {
      return Promise.resolve({
        replay: true,
        turns: cached,
        nudge: ep.nudge || null,
        training_done: !!ep.training_done,
        unlocked: true,
      })
    }
    var eid = String(ep.id || '').toUpperCase()
    if (live) {
      return ns.api('/api/academy/episodes/' + eid + '/open', {})
    }
    if (ns.fakeOpen) return Promise.resolve(ns.fakeOpen(eid))
    return ns.api('/api/academy/episodes/' + eid + '/open', {})
  }

  function warmOpenRoom(ep) {
    if (!ep || !ep.id) return Promise.resolve(null)
    // 未看完：绝不打 /open（后端 403；旧逻辑清空 promise 会空转刷屏）
    if (!ep.unlocked) return Promise.resolve(null)
    var live = !!(ns.userId && ns.userId())
    var uid = storageUid()
    if (openWarm.id === ep.id && openWarm.uid === uid && openWarm.live === live) {
      if (openWarm.blocked) {
        var blocked = new Error('看完正片才能加入讨论')
        blocked.status = 403
        return Promise.reject(blocked)
      }
      if (openWarm.promise) return openWarm.promise
    }
    openWarm.id = ep.id
    openWarm.uid = uid
    openWarm.live = live
    openWarm.data = null
    openWarm.blocked = false
    openWarm.promise = fetchOpenPayload(ep, live).then(function (data) {
      if (openWarm.id === ep.id && openWarm.uid === uid) openWarm.data = data
      if (data && data.turns) writeRoom(ep.id, data.turns)
      return data
    }).catch(function (err) {
      if (err && Number(err.status) === 403) {
        // 冻结本集预热，直到 markUnlocked 清掉 blocked
        openWarm.blocked = true
        var frozen = Promise.reject(err)
        frozen.catch(function () { /* 避免 Uncaught (in promise) */ })
        openWarm.promise = frozen
        throw err
      }
      openWarm.promise = null
      throw err
    })
    return openWarm.promise
  }

  var shownRoom = ''

  function paintSaved(ep, data, instant) {
    writeRoom(ep.id, data.turns || [])
    if (typeof data.training_done !== 'undefined') ep.training_done = !!data.training_done
    if (data && data.nudge) ep.nudge = data.nudge
    else if (data && data.training_done) ep.nudge = null
    return ns.renderTurns(data.turns || [], !!instant || !!data.replay).then(function () {
      if (typeof showChips === 'function') showChips()
      if (ep.training_done) {
        try { sessionStorage.removeItem('jnao_nudge_dismiss_' + ep.id) } catch (e) { /* ignore */ }
        if (typeof root.clearNudgeUi === 'function') root.clearNudgeUi(false)
      } else if (data && data.nudge && typeof addNudge === 'function') {
        addNudge()
      } else if (typeof root.clearNudgeUi === 'function') {
        root.clearNudgeUi(false)
      }
      if ($('chatroom') && $('chatroom').scrollIntoView) {
        $('chatroom').scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    })
  }

  var SWITCHABLE = [
    { id: 'E13', title: '五兽桩', channel_name: 'E13 · 五兽桩讨论组', unlocked: true },
    { id: 'E14', title: '蒙上眼睛之后', channel_name: 'E14 · 蒙上眼睛之后讨论组', unlocked: true },
    { id: 'EH01', title: '历史课·黄巢篇', channel_name: 'EH01 · 历史课·黄巢篇讨论组', unlocked: true },
  ]

  function defaultSwitchable(currentId) {
    return SWITCHABLE.map(function (item) {
      return {
        id: item.id,
        title: item.title,
        channel_name: item.channel_name,
        unlocked: true,
        current: item.id === currentId,
      }
    })
  }

  function resetChannelView() {
    shownRoom = ''
    clearOpenWarm()
    if (typeof root.stopDanmaku === 'function') root.stopDanmaku()
    else if (typeof stopDanmaku === 'function') stopDanmaku()
    if ($('msgs')) $('msgs').innerHTML = ''
    if ($('chatroom')) $('chatroom').classList.add('locked-teaser')
    hideEndOverlay()
    if ($('stage')) $('stage').classList.remove('on')
    if ($('replies')) {
      $('replies').innerHTML = ''
      $('replies').style.display = 'none'
    }
    var video = $('vvideo')
    if (video) {
      try { video.pause() } catch (e) { /* ignore */ }
      video.removeAttribute('src')
      video.dataset.src = ''
      video.style.display = 'none'
    }
    if ($('vbox')) {
      $('vbox').classList.remove('playing')
      $('vbox').classList.remove('ended')
    }
    if ($('vprogI')) $('vprogI').style.width = '0%'
    if ($('dmk')) $('dmk').innerHTML = ''
  }

  function loadEpisode(id) {
    var eid = String(id || '').trim()
    if (!eid) return
    var box = $('epPick')
    if (box) box.classList.remove('open')
    // 快速连点切集时丢弃过期 sector 响应
    var seq = (loadEpisode._seq = (loadEpisode._seq || 0) + 1)
    clearOpenWarm()
    var live = !!(ns.userId && ns.userId())
    var req = live
      ? ns.api('/api/academy/sector?episode_id=' + encodeURIComponent(eid))
      : Promise.resolve((ns.fakeSectorFor && ns.fakeSectorFor(eid)) || (ns.fakeSector && ns.fakeSector()) || null)
    req.then(function (data) {
      if (seq !== loadEpisode._seq) return
      if (!data || !data.episode) {
        ns.toast('这一集还没准备好')
        return
      }
      preserveLocalUnlock(data.episode)
      if (!data.switchable || !data.switchable.length) {
        data.switchable = defaultSwitchable(data.episode.id)
      }
      resetChannelView()
      ns.state = data
      markSectorLive(data.episode)
      try {
        localStorage.removeItem('jnao_academy_sector')
        localStorage.setItem(sectorCacheKey(), JSON.stringify(data))
        var uidEp = storageUid()
        if (uidEp && uidEp !== 'guest' && data.episode && data.episode.id) {
          localStorage.setItem('jnao_academy_last_ep_' + uidEp, String(data.episode.id).toUpperCase())
        }
      } catch (e) { /* ignore */ }
      if (ns.paintChannel) ns.paintChannel(data)
      try {
        if (root.parent && root.parent !== root) {
          // 只同步父页 hydrate，勿 dayu-nav 重进学院（会 remount iframe 丢掉播放进度）
          root.parent.postMessage({ type: 'dayu-academy-sync', academy: data }, '*')
        }
      } catch (e) { /* ignore */ }
    }).catch(function () {
      if (seq !== loadEpisode._seq) return
      ns.toast('切集失败，稍后再试')
    })
  }

  function paintEpisodePick(list, currentId) {
    var box = $('epPick')
    var name = $('chanName')
    if (!box || !name) return
    var rows = (list && list.length) ? list : defaultSwitchable(currentId)
    box.innerHTML = ''
    rows.forEach(function (item) {
      var btn = document.createElement('button')
      btn.type = 'button'
      btn.textContent = item.channel_name || (item.id + ' · ' + item.title)
      if (item.id === currentId || item.current) btn.className = 'on'
      // 测试集始终可切，不在下拉里标锁；讨论门禁只看本集 episode.unlocked
      btn.onclick = function (e) {
        e.preventDefault()
        e.stopPropagation()
        box.classList.remove('open')
        armJoinGate(800)
        if (item.id === currentId) return
        loadEpisode(item.id)
      }
      box.appendChild(btn)
    })
    name.onclick = function (e) {
      e.preventDefault()
      e.stopPropagation()
      armJoinGate(800)
      // 换集按钮：只开/关下拉，绝不触发讨论区逻辑
      box.classList.toggle('open')
      try { name.blur && name.blur() } catch (err) { /* ignore */ }
      try { if (window.getSelection) window.getSelection().removeAllRanges() } catch (err) { /* ignore */ }
    }
    if (!root._epPickBound) {
      root._epPickBound = true
      document.addEventListener('click', function () {
        box.classList.remove('open')
      })
    }
  }

  ns.paintChannel = function (sector) {
    var ep = sector && sector.episode
    if (!ep || !$('chanName')) return
    preserveLocalUnlock(ep)
    if (!sector.switchable || !sector.switchable.length) {
      sector.switchable = defaultSwitchable(ep.id)
    }
    var badge = $('ac-lv') || document.querySelector('.ac-lv')
    if (badge && sector.badge) badge.textContent = sector.badge
    $('chanName').textContent = ep.channel_name || ''
    paintEpisodePick(sector.switchable, ep.id)
    var online = document.querySelector('.online')
    if (online) online.textContent = (ep.online_count || 0) + '人在线'
    if ($('notice')) $('notice').textContent = ep.notice || ''
    if ($('crTitle')) $('crTitle').textContent = '# ' + (ep.channel_name || '')
    if ($('vt')) $('vt').textContent = ep.id + ' ' + ep.title
    if ($('vs')) $('vs').textContent = ep.topic || ''
    var dur = document.querySelector('.vdur')
    if (dur) dur.textContent = ep.duration_label || ''
    if ($('vposter') && ep.poster) $('vposter').src = ep.poster
    if (root.EP) {
      root.EP.task = ep.task || root.EP.task
      root.EP.title = ep.title
      root.EP.id = ep.id
    }
    prefetchChatAssets()
    hideEndOverlay()
    // 切集 / 进页：始终停在学院页，讨论组由用户手动点进
    collapseToAcademyView(ep)
  }

  ns.collapseChannel = function () {
    collapseToAcademyView(ns.state && ns.state.episode)
  }

  ns.bindChannel = function () {
    if (!$('chanName')) return
    root.showChips = function () {
      var box = $('replies')
      if (!box) return
      var chips = (ns.state && ns.state.episode && ns.state.episode.chips) || []
      if (!chips.length && typeof currentChips === 'function') {
        try { chips = currentChips() } catch (e) { chips = [] }
      }
      box.style.display = chips.length ? 'flex' : 'none'
      box.innerHTML = ''
      chips.forEach(function (text) {
        var node = document.createElement('div')
        node.className = 'rp'
        node.textContent = text
        node.onclick = function () { if (typeof quickSay === 'function') quickSay(text) }
        box.appendChild(node)
      })
      if (typeof syncChatDock === 'function') syncChatDock()
    }
    root.clearNudgeUi = function (persistDismiss) {
      var slot = $('nudgeSlot')
      if (slot) slot.innerHTML = ''
      document.querySelectorAll('#msgs .nudge').forEach(function (node) { node.remove() })
      if (persistDismiss) {
        try {
          var ep0 = ns.state && ns.state.episode
          if (ep0 && ep0.id) sessionStorage.setItem('jnao_nudge_dismiss_' + ep0.id, '1')
        } catch (e) { /* ignore */ }
      }
      if (typeof syncChatDock === 'function') syncChatDock()
    }
    root.dismissNudge = function () {
      root.clearNudgeUi(true)
    }
    root.addNudge = function () {
      if (document.querySelector('#nudgeSlot .nudge') || document.querySelector('#msgs .nudge')) return
      var ep = ns.state && ns.state.episode
      if (!ep) return
      if (ep.training_done) return
      try {
        if (ep.id && sessionStorage.getItem('jnao_nudge_dismiss_' + ep.id) === '1') return
      } catch (e) { /* ignore */ }
      if (!ep.nudge || !ep.nudge.text) return
      var node = document.createElement('div')
      node.className = 'nudge'
      node.innerHTML = '<div class="ng1">⏰</div><p>' + ep.nudge.text + '</p>'
      var go = document.createElement('button')
      go.type = 'button'
      go.className = 'ngo'
      go.textContent = '去打卡'
      go.addEventListener('click', function (event) {
        event.preventDefault()
        event.stopPropagation()
        root.dismissNudge()
        if (typeof root.goTodayTrain === 'function') root.goTodayTrain()
      })
      node.appendChild(go)
      var close = document.createElement('button')
      close.type = 'button'
      close.className = 'ngx'
      close.setAttribute('aria-label', '关闭提醒')
      close.textContent = '×'
      close.addEventListener('click', function (event) {
        event.preventDefault()
        event.stopPropagation()
        root.dismissNudge()
      })
      node.appendChild(close)
      var slot = $('nudgeSlot') || $('msgs')
      if (slot) slot.appendChild(node)
      if (typeof syncChatDock === 'function') syncChatDock()
      if (typeof scrollChat === 'function') scrollChat()
    }
    root.playEp = function () {
      var ep = ns.state && ns.state.episode
      if (!ep) {
        ns.toast('频道加载中')
        return
      }
      hideEndOverlay()
      if (ep.play_url) {
        var video = ensureVideo()
        if (!video) return
        var src = resolvePlaySrc(ep.play_url)
        video.style.display = 'block'
        if (video.dataset.src !== src) {
          video.dataset.src = src
          video.src = src
          try { video.load() } catch (e) { /* ignore */ }
        }
        if (video.dataset.bound !== '1') {
          video.dataset.bound = '1'
          var lastSent = 0
          video.addEventListener('timeupdate', function () {
            var cur = ns.state && ns.state.episode
            var dur = Number(video.duration)
            if (!cur || !isFinite(dur) || dur <= 0) return
            var pct = Math.min(100, (Number(video.currentTime) / dur) * 100)
            if ($('vprogI')) $('vprogI').style.width = pct + '%'
            if (Date.now() - lastSent < 4000) return
            lastSent = Date.now()
            // 必须带 percent：duration=Infinity 时 JSON 会变成 null，后端会 400
            ns.api('/api/academy/episodes/' + cur.id + '/progress', {
              percent: pct,
              position_sec: video.currentTime,
              duration_sec: dur,
            }).then(function (data) { markUnlocked(data, cur) }).catch(function () {})
          })
          video.addEventListener('ended', function () {
            var cur = ns.state && ns.state.episode
            if (!cur) return
            var already = !!cur.unlocked
            // 先记进度解锁，成功后再 warm；禁止未解锁抢打 /open
            ns.api('/api/academy/episodes/' + cur.id + '/progress', { percent: 100 })
              .then(function (data) {
                // 播完只出「加入讨论」按钮，不自动弹讨论组
                markUnlocked(data || { unlocked: true, percent: 100 }, cur, { showEnd: true })
                if (already) showEndOverlay()
              })
              .catch(function () {
                // 网络抖动：再试一次 percent=100（不依赖 duration）
                ns.api('/api/academy/episodes/' + cur.id + '/progress', { percent: 100 })
                  .then(function (data) {
                    markUnlocked(data || { unlocked: true, percent: 100 }, cur, { showEnd: true })
                  })
                  .catch(function () {
                    showEndOverlay()
                    ns.toast('进度没记上，点「加入讨论」会再试一次，或再播一遍')
                  })
              })
          })
          video.addEventListener('error', function () {
            $('vbox').classList.remove('playing')
            $('vbox').classList.remove('ended')
            ns.toast('正片加载失败，稍后再试')
          })
        }
        try { video.currentTime = 0 } catch (e) { /* ignore */ }
        $('vbox').classList.add('playing')
        $('vbox').classList.remove('ended')
        if (typeof startDanmaku === 'function') startDanmaku()
        video.play().catch(function () { ns.toast('点一下画面再播放') })
        return
      }
      if (ep.media === 'demo') {
        simulateWatch(ep)
        return
      }
      ns.toast('这一集正片还没上传')
    }
    ns._playEp = root.playEp
    root.__academyPlayEp = root.playEp
    function focusChatroom() {
      scrollToLatestChat()
    }

    root.joinChat = function () {
      var ep = ns.state && ns.state.episode
      if (!ep) {
        ns.toast('频道加载中')
        return
      }
      if (joinGateBlocked()) return
      var phase = unlockPhase(ep)
      // 未与后端对齐前禁止进房，也不允许偷报 progress=100 绕过
      if (phase === 'pending') {
        ns.toast('正在同步本集进度…')
        return
      }
      if (!ep.unlocked || phase === 'locked') {
        // 仅播完正片后的补记（由播放结束路径置位）；禁止点条「同步中」自行解锁
        if (!root.__academyAllowProgressUnlock) {
          ns.toast('看完正片才能加入讨论')
          return
        }
        if (root.__academyJoinUnlocking) return
        root.__academyJoinUnlocking = true
        ns.api('/api/academy/episodes/' + ep.id + '/progress', { percent: 100 })
          .then(function (data) {
            root.__academyJoinUnlocking = false
            root.__academyAllowProgressUnlock = false
            if (data && (data.unlocked || Number(data.percent) >= 90)) {
              markUnlocked(data, ep)
              root.joinChat()
              return
            }
            ns.toast('看完正片才能加入讨论')
          })
          .catch(function () {
            root.__academyJoinUnlocking = false
            root.__academyAllowProgressUnlock = false
            ns.toast('看完正片才能加入讨论')
          })
        return
      }
      hideEndOverlay()
      prefetchChatAssets()
      unlockChatShell()
      // 已解锁进房：清掉历史 403 冻结，避免 warm 一直 reject
      if (openWarm.id === ep.id) {
        openWarm.blocked = false
        if (openWarm.promise && !openWarm.data) openWarm.promise = null
      }
      var live = !!(ns.userId && ns.userId())
      var roomMark = (live ? 'live:' : 'fake:') + storageUid() + ':' + ep.id
      // 已进过房：只滚到最新消息，不弹键盘
      if (shownRoom === roomMark && $('msgs') && $('msgs').children.length) {
        focusChatroom()
        return
      }
      shownRoom = roomMark
      if ($('msgs')) $('msgs').innerHTML = ''
      focusChatroom()

      var cached = readRoom(ep.id)
      var warmReady = openWarm.id === ep.id && openWarm.uid === storageUid() && openWarm.data && !openWarm.blocked
      var openTalk = warmReady
        ? Promise.resolve(openWarm.data)
        : warmOpenRoom(ep)

      if (!warmReady && !cached && live && typeof addSys === 'function') {
        addSys('角色正在开口…')
      }

      openTalk.then(function (data) {
        if (typeof addSys === 'function') {
          addSys(data.replay ? '回到 #' + ep.channel_name : '你加入了 #' + ep.channel_name)
        }
        var instant = !!(warmReady || data.replay || cached)
        return paintSaved(ep, data, instant)
      }).then(function () {
        focusChatroom()
      }).catch(function (err) {
        if (err && err.status && err.status < 500) {
          if (typeof addSys === 'function') addSys(err.message || '讨论没打开')
          focusChatroom()
          return
        }
        var data = cached
          ? { replay: true, turns: cached, nudge: ep.nudge }
          : (ns.fakeOpen ? ns.fakeOpen(ep.id) : { turns: [] })
        if (typeof addSys === 'function') addSys(data.replay ? '回到 #' + ep.channel_name : '接口没通，先用本地假对话')
        return paintSaved(ep, data, true).then(function () { focusChatroom() })
      })
    }
    ns._joinChat = root.joinChat
    root.__academyJoinChat = root.joinChat
    root.respond = function (payload) {
      var ep = ns.state && ns.state.episode
      if (!ep) return
      var body = typeof payload === 'string' ? { text: payload } : (payload || {})
      var sticker = body.sticker || ''
      var userText = (body.text || '').trim()
      if (!userText && !sticker) return
      // 大表情：正文可空，仅走 sticker；小表情是普通 text，不要抬成大图
      if (sticker && userText === sticker) {
        userText = ''
      }
      var mine = { who: 'me', text: userText || sticker }
      if (body.mention) mine.mention = body.mention
      if (body.quote) mine.quote = body.quote
      if (sticker) mine.sticker = sticker
      var live = !!(ns.userId && ns.userId())
      var sendTalk = (!live && ns.fakeReply)
        ? Promise.resolve(ns.fakeReply(body))
        : ns.api('/api/academy/episodes/' + ep.id + '/chat', {
          text: userText || (sticker ? '' : ''),
          mention: body.mention || undefined,
          quote: body.quote || undefined,
          sticker: sticker || undefined
        })
      sendTalk.then(function (data) {
        var prev = readRoom(ep.id) || []
        var botTurns = data.turns || []
        writeRoom(ep.id, prev.concat([mine]).concat(botTurns))
        if (!botTurns.length && typeof addSys === 'function') {
          addSys('这句角色没接上，再发一次或换个问法')
        }
        return ns.renderTurns(botTurns, false).then(function () {
          if (data && data.nudge && typeof addNudge === 'function') addNudge()
        })
      }).catch(function (err) {
        if (err && err.status && err.status < 500) {
          if (typeof addSys === 'function') addSys(err.message || '这句没送出去')
          return
        }
        var data = ns.fakeReply ? ns.fakeReply(body) : { turns: [] }
        var prev = readRoom(ep.id) || []
        writeRoom(ep.id, prev.concat([mine]).concat(data.turns || []))
        if (typeof addSys === 'function') addSys('接口没通，这一句先记在本地')
        return ns.renderTurns(data.turns || [], false).then(function () {
          if (data.nudge && typeof addNudge === 'function') addNudge()
        })
      })
    }

    // 进页即预热舞台与角色图
    prefetchChatAssets()
  }
})(window)
