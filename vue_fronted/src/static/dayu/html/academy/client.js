/* 学院壳共用：鉴权请求、提示、跳集。三页脚本只依赖 JnaoAcademy。 */
(function (root) {
  var ns = root.JnaoAcademy = root.JnaoAcademy || {}

  ns.$ = function (id) { return document.getElementById(id) }

  ns.userId = function () {
    var state = ns.state
    if (state && state.user_id) return String(state.user_id)
    try { return localStorage.getItem('jnao_child_user_id') || '' } catch (e) { return '' }
  }

  ns.toast = function (title) {
    try {
      if (root.parent && root.parent !== root) {
        root.parent.postMessage({ type: 'dayu-toast', title: title }, '*')
        return
      }
    } catch (e) { /* ignore */ }
    alert(title)
  }

  ns.goEpisode = function (id) {
    var path = '/pages/hub/academy?ep=' + encodeURIComponent(id)
    try {
      if (root.parent && root.parent !== root) {
        root.parent.postMessage({ type: 'dayu-nav', path: path }, '*')
        return
      }
    } catch (e) { /* ignore */ }
    location.href = 'drama.html'
  }

  ns.api = function (path, body) {
    var uid = ns.userId()
    var url = path
    var headers = { 'Content-Type': 'application/json' }
    try {
      var did = localStorage.getItem('jnao_device_id')
      if (did) headers['X-Device-Id'] = did
      var token = localStorage.getItem('jnao_access_token') || localStorage.getItem('jnao_session_token')
      if (token) headers.Authorization = 'Bearer ' + token
      if (uid) headers['X-Child-User-Id'] = uid
    } catch (e) { /* ignore */ }
    if (uid && url.indexOf('user_id=') < 0) {
      url += (url.indexOf('?') >= 0 ? '&' : '?') + 'user_id=' + encodeURIComponent(uid)
    }
    return fetch(url, {
      method: body ? 'POST' : 'GET',
      headers: headers,
      credentials: 'include',
      body: body ? JSON.stringify(body) : undefined,
    }).then(function (res) {
      return res.json().catch(function () { return {} }).then(function (data) {
        if (!res.ok) {
          var err = new Error((data && data.detail) || '请求失败')
          err.status = res.status
          throw err
        }
        return data
      })
    })
  }

  ns.playTurns = function (turns) {
    return ns.renderTurns(turns, false)
  }

  ns.renderTurns = function (turns, instant) {
    var list = turns || []
    if (!instant) {
      var bots = list.filter(function (turn) { return turn && turn.who !== 'me' && turn.who !== 'user' })
      var chain = Promise.resolve()
      bots.forEach(function (turn, i) {
        chain = chain.then(function () {
          return new Promise(function (resolve) {
            var wait = i === 0 ? 600 : 3000
            if (typeof showTyping === 'function' && typeof addMsg === 'function') {
              showTyping(turn.who, function () { addMsg(turn.who, turn.text, turn); resolve() }, wait)
            } else {
              resolve()
            }
          })
        })
      })
      return chain
    }
    list.forEach(function (turn) {
      if (!turn || (!turn.text && !turn.sticker)) return
      if (turn.who === 'me' || turn.who === 'user') {
        if (typeof addMe === 'function') addMe(turn.text || turn.sticker, turn)
        return
      }
      if (typeof addMsg === 'function') addMsg(turn.who, turn.text, turn)
    })
    if (typeof scrollChat === 'function') scrollChat()
    return Promise.resolve()
  }
})(window)
