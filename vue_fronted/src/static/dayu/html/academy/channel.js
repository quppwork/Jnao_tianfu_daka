/* 频道页：海报、播放、解锁、讨论。不管剧情长卷和课程。 */
(function (root) {
  var ns = root.JnaoAcademy
  if (!ns) return
  var $ = ns.$

  function showEndOverlay() {
    if ($('vend')) $('vend').style.display = 'flex'
    if ($('vbox')) $('vbox').classList.remove('playing')
    if ($('dmk')) $('dmk').innerHTML = ''
  }

  function hideEndOverlay() {
    if ($('vend')) $('vend').style.display = 'none'
  }

  function markUnlocked(data, ep, opts) {
    if (!data || !data.unlocked) return
    ep.unlocked = true
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
      if (percent < 100) return
      clearInterval(timer)
      root.__academyPlaying = false
      ns.api('/api/academy/episodes/' + ep.id + '/progress', { percent: 100 })
        .then(function (data) { markUnlocked(data, ep, { showEnd: true }) })
        .catch(function () {
          ep.unlocked = true
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
      return Array.isArray(raw) && raw.length ? raw : null
    } catch (e) {
      return null
    }
  }

  function writeRoom(id, turns) {
    try {
      localStorage.setItem(roomKey(id), JSON.stringify((turns || []).slice(-40)))
    } catch (e) { /* 隐私模式写不进也不影响这一次 */ }
  }

  var shownRoom = ''

  function paintSaved(ep, data, instant) {
    writeRoom(ep.id, data.turns || [])
    return ns.renderTurns(data.turns || [], !!instant || !!data.replay).then(function () {
      if (typeof showChips === 'function') showChips()
      if (data && data.nudge && typeof addNudge === 'function') addNudge()
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
    if (typeof root.stopDanmaku === 'function') root.stopDanmaku()
    else if (typeof stopDanmaku === 'function') stopDanmaku()
    if ($('msgs')) $('msgs').innerHTML = ''
    if ($('chatroom')) $('chatroom').classList.add('locked-teaser')
    if ($('vend')) $('vend').style.display = 'none'
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
    if ($('vbox')) $('vbox').classList.remove('playing')
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
    if (ep.unlocked) {
      hideEndOverlay()
      if (typeof root.joinChat === 'function') root.joinChat()
    } else {
      hideEndOverlay()
    }
  }

  ns.bindChannel = function () {
    if (!$('chanName')) return
    root.showChips = function () {
      var box = $('replies')
      var chips = (ns.state && ns.state.episode && ns.state.episode.chips) || []
      if (!box) return
      box.style.display = 'flex'
      box.innerHTML = ''
      chips.forEach(function (text) {
        var node = document.createElement('div')
        node.className = 'rp'
        node.textContent = text
        node.onclick = function () { if (typeof quickSay === 'function') quickSay(text) }
        box.appendChild(node)
      })
    }
    root.addNudge = function () {
      if (document.querySelector('#msgs .nudge')) return
      var ep = ns.state && ns.state.episode
      var node = document.createElement('div')
      node.className = 'nudge'
      var text = (ep && ep.nudge && ep.nudge.text) || ''
      node.innerHTML = '<div class="ng1">⏰</div><p>' + text + '</p>'
      var go = document.createElement('button')
      go.type = 'button'
      go.className = 'ngo'
      go.textContent = '去打卡'
      go.addEventListener('click', function (event) {
        event.preventDefault()
        event.stopPropagation()
        if (typeof root.goTodayTrain === 'function') root.goTodayTrain()
      })
      node.appendChild(go)
      if ($('msgs')) $('msgs').appendChild(node)
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
            ns.api('/api/academy/episodes/' + cur.id + '/progress', { percent: 100 })
              .then(function (data) {
                markUnlocked(data || { unlocked: true }, cur, { showEnd: true })
              })
              .catch(function () {
                cur.unlocked = true
                showEndOverlay()
              })
          })
          video.addEventListener('error', function () {
            $('vbox').classList.remove('playing')
            ns.toast('正片加载失败，稍后再试')
          })
        }
        try { video.currentTime = 0 } catch (e) { /* ignore */ }
        $('vbox').classList.add('playing')
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
      var room = $('chatroom')
      if (!room) return
      try {
        room.scrollIntoView({ behavior: 'smooth', block: 'start' })
      } catch (e) { /* ignore */ }
      setTimeout(function () {
        try {
          room.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
        } catch (e2) { /* ignore */ }
        var inp = $('inp')
        if (inp) {
          try { inp.focus() } catch (e3) { /* ignore */ }
        }
      }, 120)
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
      var live = !!(ns.userId && ns.userId())
      var roomMark = (live ? 'live:' : 'fake:') + ep.id
      // 已进过房：只滚到下方对话框
      if (shownRoom === roomMark) {
        if ($('chatroom')) $('chatroom').classList.remove('locked-teaser')
        if ($('stage')) $('stage').classList.add('on')
        focusChatroom()
        return
      }
      shownRoom = roomMark
      joined = true
      try { clearTimeout(teaserTm) } catch (e) { /* ignore */ }
      if ($('msgs')) $('msgs').innerHTML = ''
      if ($('chatroom')) $('chatroom').classList.remove('locked-teaser')
      if ($('stage')) $('stage').classList.add('on')
      if ($('inp')) {
        $('inp').disabled = false
        $('inp').placeholder = '说点什么，可以 @ 人或按住引用'
      }
      focusChatroom()
      var cached = readRoom(ep.id)
      var openTalk
      if (live) {
        if (typeof addSys === 'function') addSys('角色正在开口…')
        openTalk = ns.api('/api/academy/episodes/' + ep.id + '/open', {})
      } else if (ns.fakeOpen) {
        openTalk = Promise.resolve(cached
          ? { replay: true, turns: cached, nudge: ep.nudge }
          : ns.fakeOpen())
      } else {
        openTalk = ns.api('/api/academy/episodes/' + ep.id + '/open', {})
      }
      openTalk.then(function (data) {
        if (typeof addSys === 'function') {
          addSys(data.replay ? '回到 #' + ep.channel_name : '你加入了 #' + ep.channel_name)
        }
        return paintSaved(ep, data, live)
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
          : (ns.fakeOpen ? ns.fakeOpen() : { turns: [] })
        if (typeof addSys === 'function') addSys(data.replay ? '回到 #' + ep.channel_name : '接口没通，先用本地假对话')
        return paintSaved(ep, data).then(function () { focusChatroom() })
      })
    }
    ns._joinChat = root.joinChat
    root.__academyJoinChat = root.joinChat
    root.respond = function (payload) {
      var ep = ns.state && ns.state.episode
      if (!ep) return
      var body = typeof payload === 'string' ? { text: payload } : (payload || {})
      var userText = body.text || body.sticker || ''
      if (!userText) return
      var mine = { who: 'me', text: userText }
      if (body.mention) mine.mention = body.mention
      if (body.quote) mine.quote = body.quote
      if (body.sticker) mine.sticker = body.sticker
      var live = !!(ns.userId && ns.userId())
      var sendTalk = (!live && ns.fakeReply)
        ? Promise.resolve(ns.fakeReply(body))
        : ns.api('/api/academy/episodes/' + ep.id + '/chat', {
          text: userText,
          mention: body.mention || undefined,
          quote: body.quote || undefined,
          sticker: body.sticker || undefined
        })
      sendTalk.then(function (data) {
        var prev = readRoom(ep.id) || []
        writeRoom(ep.id, prev.concat([mine]).concat(data.turns || []))
        return ns.renderTurns(data.turns || [], false).then(function () {
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
  }
})(window)
