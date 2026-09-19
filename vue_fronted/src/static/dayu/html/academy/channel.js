/* 频道页：海报、播放、解锁、讨论。不管剧情长卷和课程。 */
(function (root) {
  var ns = root.JnaoAcademy
  if (!ns) return
  var $ = ns.$

  function markUnlocked(data, ep) {
    if (!data || !data.unlocked) return
    ep.unlocked = true
    if ($('vend')) $('vend').style.display = 'flex'
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
    video.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:2;background:#000;display:none'
    box.insertBefore(video, box.firstChild)
    return video
  }

  function simulateWatch(ep) {
    if (root.__academyPlaying) return
    root.__academyPlaying = true
    $('vbox').classList.add('playing')
    if (typeof startDanmaku === 'function') startDanmaku()
    var percent = 0
    var timer = setInterval(function () {
      percent += 4
      if ($('vprogI')) $('vprogI').style.width = Math.min(100, percent) + '%'
      if (percent < 100) return
      clearInterval(timer)
      root.__academyPlaying = false
      $('vbox').classList.remove('playing')
      if ($('dmk')) $('dmk').innerHTML = ''
      ns.api('/api/academy/episodes/' + ep.id + '/progress', { percent: 100 })
        .then(function (data) { markUnlocked(data, ep) })
        .catch(function () { ns.toast('进度没记上，再看一遍') })
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

  ns.paintChannel = function (sector) {
    var ep = sector && sector.episode
    if (!ep || !$('chanName')) return
    var badge = $('ac-lv') || document.querySelector('.ac-lv')
    if (badge && sector.badge) badge.textContent = sector.badge
    $('chanName').textContent = ep.channel_name || ''
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
    if (ep.unlocked && $('vend')) $('vend').style.display = 'flex'
    if (ep.unlocked && typeof root.joinChat === 'function') root.joinChat()
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
      node.innerHTML = '<div class="ng1">⏰</div><p>' + text + '</p><a href="train.html">去打卡</a>'
      if ($('msgs')) $('msgs').appendChild(node)
      if (typeof scrollChat === 'function') scrollChat()
    }
    root.playEp = function () {
      var ep = ns.state && ns.state.episode
      if (!ep) {
        ns.toast('频道加载中')
        return
      }
      if (ep.play_url) {
        var video = ensureVideo()
        if (!video) return
        video.style.display = 'block'
        if (video.dataset.bound !== '1') {
          video.dataset.bound = '1'
          video.src = ep.play_url
          var lastSent = 0
          video.addEventListener('timeupdate', function () {
            if (!video.duration) return
            if ($('vprogI')) $('vprogI').style.width = Math.min(100, video.currentTime / video.duration * 100) + '%'
            if (Date.now() - lastSent < 4000) return
            lastSent = Date.now()
            ns.api('/api/academy/episodes/' + ep.id + '/progress', {
              position_sec: video.currentTime,
              duration_sec: video.duration,
            }).then(function (data) { markUnlocked(data, ep) }).catch(function () {})
          })
          video.addEventListener('ended', function () {
            ns.api('/api/academy/episodes/' + ep.id + '/progress', { percent: 100 })
              .then(function (data) { markUnlocked(data, ep) }).catch(function () {})
          })
        }
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
      var live = !!(ns.userId && ns.userId())
      var roomMark = (live ? 'live:' : 'fake:') + ep.id
      if (shownRoom === roomMark) return
      shownRoom = roomMark
      joined = true
      try { clearTimeout(teaserTm) } catch (e) { /* ignore */ }
      if ($('vend')) $('vend').style.display = 'none'
      if ($('msgs')) $('msgs').innerHTML = ''
      if ($('chatroom')) $('chatroom').classList.remove('locked-teaser')
      if ($('stage')) $('stage').classList.add('on')
      if ($('inp')) {
        $('inp').disabled = false
        $('inp').placeholder = '说点什么，可以 @ 人或按住引用'
      }
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
      }).catch(function (err) {
        if (err && err.status && err.status < 500) {
          if (typeof addSys === 'function') addSys(err.message || '讨论没打开')
          return
        }
        var data = cached
          ? { replay: true, turns: cached, nudge: ep.nudge }
          : (ns.fakeOpen ? ns.fakeOpen() : { turns: [] })
        if (typeof addSys === 'function') addSys(data.replay ? '回到 #' + ep.channel_name : '接口没通，先用本地假对话')
        return paintSaved(ep, data)
      })
    }
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
        return ns.renderTurns(data.turns || [], true).then(function () {
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
