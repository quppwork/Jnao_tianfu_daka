/* 频道页：海报、播放、解锁、讨论。不管剧情长卷和课程。 */
(function (root) {
  var ns = root.JnaoAcademy
  if (!ns) return
  var $ = ns.$

  /** 开房结果预取：看片过程中就请求，点「加入讨论」时不再等网络 */
  var openWarm = { id: '', live: false, promise: null, data: null }

  function showEndOverlay() {
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

  function markUnlocked(data, ep, opts) {
    if (!data || !data.unlocked) return
    ep.unlocked = true
    warmOpenRoom(ep)
    if (opts && opts.showEnd) showEndOverlay()
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
      if (percent >= 72) warmOpenRoom(ep)
      if (percent < 100) return
      clearInterval(timer)
      root.__academyPlaying = false
      ns.api('/api/academy/episodes/' + ep.id + '/progress', { percent: 100 })
        .then(function (data) { markUnlocked(data, ep, { showEnd: true }) })
        .catch(function () {
          ep.unlocked = true
          warmOpenRoom(ep)
          showEndOverlay()
          ns.toast('进度没记上，再看一遍')
        })
    }, 90)
  }

  function roomKey(id) {
    return 'jnao_academy_room_' + id
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
      localStorage.setItem(roomKey(id), JSON.stringify((turns || []).slice(-40)))
    } catch (e) { /* 隐私模式写不进也不影响这一次 */ }
  }

  function clearOpenWarm() {
    openWarm = { id: '', live: false, promise: null, data: null }
  }

  function viewKey(id) {
    return 'jnao_academy_view_' + id
  }

  function rememberChatView(id) {
    if (!id) return
    try { sessionStorage.setItem(viewKey(id), 'chat') } catch (e) { /* ignore */ }
  }

  function wantsChatView(ep) {
    if (!ep || !ep.id) return false
    if (ep.unlocked) return true
    try {
      if (sessionStorage.getItem(viewKey(ep.id)) === 'chat') return true
    } catch (e) { /* ignore */ }
    var cached = readRoom(ep.id)
    return !!(cached && cached.length)
  }

  function unlockChatShell() {
    joined = true
    try { clearTimeout(teaserTm) } catch (e) { /* ignore */ }
    var ep = ns.state && ns.state.episode
    if (ep && ep.id) {
      rememberChatView(ep.id)
      ep.unlocked = true
    }
    if ($('chatroom')) $('chatroom').classList.remove('locked-teaser')
    if ($('stage')) $('stage').classList.add('on')
    if ($('inp')) {
      $('inp').disabled = false
      $('inp').placeholder = '说点什么，可以 @ 人或按住引用'
    }
    // 解锁后先停在学院页（图一），下滑标题条进入全屏讨论
    var phone = document.querySelector('.phone')
    if (phone) phone.classList.add('qq-peek')
    if (typeof syncChatDock === 'function') syncChatDock()
  }

  function lockChatShell() {
    if ($('chatroom')) $('chatroom').classList.add('locked-teaser')
    if ($('stage')) $('stage').classList.remove('on')
    if ($('inp')) {
      $('inp').disabled = true
      $('inp').placeholder = '看完正片即可加入讨论'
    }
    if ($('replies')) {
      $('replies').innerHTML = ''
      $('replies').style.display = 'none'
    }
    if (typeof syncChatDock === 'function') syncChatDock()
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
    var roomMark = (live ? 'live:' : 'fake:') + ep.id
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
      // 后台预热 open，失败也不清本地对话
      warmOpenRoom(ep).catch(function () { /* ignore */ })
      return
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
    if (live) {
      return ns.api('/api/academy/episodes/' + ep.id + '/open', {})
    }
    if (ns.fakeOpen) return Promise.resolve(ns.fakeOpen(ep.id))
    return ns.api('/api/academy/episodes/' + ep.id + '/open', {})
  }

  function warmOpenRoom(ep) {
    if (!ep || !ep.id) return openWarm.promise
    var live = !!(ns.userId && ns.userId())
    if (openWarm.id === ep.id && openWarm.live === live && openWarm.promise) {
      return openWarm.promise
    }
    openWarm.id = ep.id
    openWarm.live = live
    openWarm.data = null
    openWarm.promise = fetchOpenPayload(ep, live).then(function (data) {
      if (openWarm.id === ep.id) openWarm.data = data
      if (data && data.turns) writeRoom(ep.id, data.turns)
      return data
    }).catch(function (err) {
      // 预取失败不清 promise，join 时再走兜底
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
    var live = !!(ns.userId && ns.userId())
    var req = live
      ? ns.api('/api/academy/sector?episode_id=' + encodeURIComponent(eid))
      : Promise.resolve((ns.fakeSectorFor && ns.fakeSectorFor(eid)) || (ns.fakeSector && ns.fakeSector()) || null)
    req.then(function (data) {
      if (!data || !data.episode) {
        ns.toast('这一集还没准备好')
        return
      }
      if (!data.switchable || !data.switchable.length) {
        data.switchable = defaultSwitchable(data.episode.id)
      }
      resetChannelView()
      ns.state = data
      try { localStorage.setItem('jnao_academy_sector', JSON.stringify(data)) } catch (e) { /* ignore */ }
      if (ns.paintChannel) ns.paintChannel(data)
      try {
        if (root.parent && root.parent !== root) {
          root.parent.postMessage({ type: 'dayu-academy', academy: data }, '*')
          root.parent.postMessage({ type: 'dayu-nav', path: '/pages/hub/academy?ep=' + encodeURIComponent(data.episode.id) }, '*')
        }
      } catch (e) { /* ignore */ }
    }).catch(function () {
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
      if (item.unlocked === false && item.id !== currentId) {
        btn.disabled = true
        btn.textContent += '（未解锁）'
      }
      btn.onclick = function (e) {
        e.preventDefault()
        e.stopPropagation()
        box.classList.remove('open')
        if (item.id === currentId) return
        loadEpisode(item.id)
      }
      box.appendChild(btn)
    })
    name.onclick = function (e) {
      e.preventDefault()
      e.stopPropagation()
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
    if (wantsChatView(ep)) {
      // 已进过讨论 / 本地有对话：切回学院时直接恢复，不必再走「看完解锁」
      unlockChatShell()
      restoreRoomQuiet(ep)
    } else {
      lockChatShell()
      var box = $('replies')
      if (box) {
        box.innerHTML = ''
        box.style.display = 'none'
      }
    }
    // 切集后刷新底部提示词（按剧情）
    if (typeof showChips === 'function' && wantsChatView(ep)) {
      try { showChips() } catch (e) { /* ignore */ }
    }
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
            if (!cur || !video.duration) return
            if ($('vprogI')) $('vprogI').style.width = Math.min(100, video.currentTime / video.duration * 100) + '%'
            var ratio = video.currentTime / video.duration
            // 过半就预取讨论，不必等播完再点
            if (ratio >= 0.55 || cur.unlocked) warmOpenRoom(cur)
            if (Date.now() - lastSent < 4000) return
            lastSent = Date.now()
            // 中途只记进度/解锁讨论，不弹出「已看完」
            ns.api('/api/academy/episodes/' + cur.id + '/progress', {
              position_sec: video.currentTime,
              duration_sec: video.duration,
            }).then(function (data) { markUnlocked(data, cur) }).catch(function () {})
          })
          video.addEventListener('ended', function () {
            var cur = ns.state && ns.state.episode
            if (!cur) return
            var already = !!cur.unlocked
            warmOpenRoom(cur)
            ns.api('/api/academy/episodes/' + cur.id + '/progress', { percent: 100 })
              .then(function (data) {
                // 重看同一集：仍可点进讨论，但不必再挡在「解锁」态
                markUnlocked(data || { unlocked: true }, cur, { showEnd: !already })
                if (already) {
                  unlockChatShell()
                  showEndOverlay()
                }
              })
              .catch(function () {
                cur.unlocked = true
                warmOpenRoom(cur)
                unlockChatShell()
                showEndOverlay()
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
      if (!ep.unlocked) {
        ns.toast('看完正片才能加入讨论')
        return
      }
      hideEndOverlay()
      prefetchChatAssets()
      unlockChatShell()
      var live = !!(ns.userId && ns.userId())
      var roomMark = (live ? 'live:' : 'fake:') + ep.id
      // 已进过房：只滚到最新消息，不弹键盘
      if (shownRoom === roomMark && $('msgs') && $('msgs').children.length) {
        focusChatroom()
        return
      }
      shownRoom = roomMark
      if ($('msgs')) $('msgs').innerHTML = ''
      focusChatroom()

      var cached = readRoom(ep.id)
      var warmReady = openWarm.id === ep.id && openWarm.data
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
