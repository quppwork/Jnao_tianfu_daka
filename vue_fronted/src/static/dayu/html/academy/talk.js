/* 讨论区 @、引用、表情。表情是系统 Unicode，不加载 QQ / 微信版权包。 */
(function (root) {
  var style = document.createElement('style')
  style.textContent = '.ib{width:36px;height:36px;border-radius:50%;border:1.5px solid #2A3040;background:#161D2B;color:#EDEBE4;font-size:16px;font-weight:900;flex:none;cursor:pointer}'
    + '.qbar{position:fixed;left:50%;transform:translateX(-50%);bottom:118px;width:calc(100% - 36px);max-width:444px;display:flex;gap:8px;align-items:center;background:#161D2B;border-left:3px solid #C9A869;border-radius:10px;padding:7px 10px;z-index:30;box-sizing:border-box}'
    + '.qbar[hidden],.talkpan[hidden]{display:none!important}'
    + '.qbar b{font-size:11px;color:#C9A869;flex:none}.qbar span{flex:1;font-size:12px;color:#B9C0CE;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'
    + '.qbar button{border:none;background:transparent;color:#B9C0CE;font-size:18px;cursor:pointer}'
    + '.talkpan{position:fixed;left:50%;transform:translateX(-50%);bottom:118px;width:calc(100% - 28px);max-width:452px;background:#121826;border:1px solid #2A3040;border-radius:14px;padding:8px;z-index:40;max-height:240px;overflow:auto;box-sizing:border-box}'
    + '.talkpan button{border:none;background:#1A2233;color:#E4E8F0;border-radius:10px;padding:8px 10px;margin:4px;font-size:13px;font-weight:800;cursor:pointer}'
    + '.talkpan button i{font-style:normal;color:#8b93a5;font-size:10px;margin-left:4px;font-weight:700}'
    + '.emtab{font-size:11px;color:#8b93a5;font-weight:800;padding:4px 6px}.ems{display:flex;flex-wrap:wrap}'
    + '.ems button{font-size:22px;background:transparent;padding:4px 6px}.ems.bigs button{font-size:34px}'
    + '.mq{border-left:3px solid rgba(201,168,105,.9);padding:0 0 4px 8px;margin-bottom:4px}'
    + '.mq b{display:block;font-size:10px;opacity:.8}.mq span{display:block;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:190px;opacity:.85}'
    + '.msticker{font-size:42px;line-height:1.15}.mb .at{color:#8EBEFF;font-weight:800}.msg.me .mb .at{color:#FFF3C4}'
    + 'html.lt .ib{background:#d4dbe9;border-color:#bfc5d5;color:#1b1912}'
    + 'html.lt .qbar,html.lt .talkpan{background:#e7ebf4;border-color:#c2cadc}'
    + 'html.lt .qbar span,html.lt .talkpan button{color:#1b1912}'
    + 'html.lt .talkpan button{background:#d4dbe9}'
  document.head.appendChild(style)
  var phone = document.createElement('style')
  phone.textContent = '.inbar{gap:8px;padding:8px 10px}'
    + '.inbar .ifield{flex:1;min-width:0;display:flex;align-items:center;background:#161D2B;border:1.5px solid #2A3040;border-radius:999px;padding-right:2px}'
    + '.inbar .ifield input,.inbar .ifield input:focus{flex:1;width:100%;min-width:0;border:none;background:transparent;box-shadow:none;padding:10px 4px 10px 14px;font-size:16px}'
    + '.ib.em{width:34px;height:34px;border:none;background:transparent;font-size:22px}'
    + '.inbar .send.talk-send{width:auto;min-width:64px;height:36px;border-radius:8px;padding:0 12px;font-size:15px}'
    + '.mb{-webkit-touch-callout:none;-webkit-user-select:none;user-select:none;touch-action:manipulation}'
    + '.mb.faceonly{background:transparent!important;padding:0!important}'
    + '.msticker{font-size:68px;line-height:1}'
    + '.rx{display:flex;gap:4px;margin-top:4px;flex-wrap:wrap}.rx i{font-style:normal;background:rgba(255,255,255,.08);border-radius:99px;padding:1px 7px;font-size:14px}'
    + '.holdmask{position:fixed;inset:0;z-index:80;background:rgba(0,0,0,.12)}'
    + '.holdpop{position:fixed;z-index:81;width:min(286px,calc(100vw - 20px))}'
    + '.reactbar{display:flex;justify-content:space-between;background:#2b2f3a;border-radius:999px;padding:6px 10px;margin-bottom:8px;box-shadow:0 8px 24px rgba(0,0,0,.28)}'
    + '.reactbar button{border:none;background:transparent;font-size:22px;padding:2px 3px;cursor:pointer;line-height:1}'
    + '.holdmenu{display:grid;grid-template-columns:repeat(3,1fr);background:#2c303a;color:#fff;border-radius:14px;overflow:hidden;box-shadow:0 10px 28px rgba(0,0,0,.32)}'
    + '.holdmenu button{border:none;background:transparent;color:#fff;padding:14px 4px 12px;font-size:12px;font-weight:700;display:flex;flex-direction:column;align-items:center;gap:6px;cursor:pointer}'
    + '.holdmenu button b{font-size:18px;font-weight:600;line-height:1}'
    + '.mb.picked{box-shadow:0 0 0 2px #C9A869}'
    + 'html.lt .inbar .ifield{background:#fff;border-color:#d5dbe8}'
    + 'html.lt .inbar .ifield input{color:#1b1912}'
    + '.talkshade{position:fixed;inset:0;z-index:36;background:transparent}'
    + '.talkshade[hidden]{display:none!important}'
    + '.talkpan{z-index:45}'
    + '.inbar{z-index:46}'
  document.head.appendChild(phone)
  var PACK = ['😂','🤣','😭','😅','🥹','🥺','😏','🙄','🤔','😤','🥰','😎','🙈','🫠','👍','👏','❤️','🔥','✨','💪','🤝','👀','🙏','👋','💯','😴','🤡','😮','🐶','📒']
  var pendingQuote = null
  var pendingSticker = null
  var pendingMention = ''

  function esc(value) {
    return String(value || '').replace(/[&<>"']/g, function (ch) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]
    })
  }

  function people() {
    if (typeof CHARS !== 'undefined') return CHARS
    return root.CHARS || {}
  }

  function cast() {
    var chars = people()
    return Object.keys(chars).map(function (key) {
      return { key: key, name: chars[key].n, tag: chars[key].tag }
    })
  }

  function nameOf(who) {
    if (!who || who === 'me' || who === 'user') return '我'
    var chars = people()
    return (chars[who] && chars[who].n) || who
  }

  function resolveMention(text) {
    var found = ''
    cast().forEach(function (item) {
      if (text.indexOf('@' + item.name) >= 0 || text.indexOf('@' + item.key) >= 0) found = item.key
    })
    return found || pendingMention
  }

  function paint(text) {
    return esc(text).replace(/@([^\s@]{1,8})/g, '<span class="at">@$1</span>')
  }

  function $(id) { return document.getElementById(id) }

  function hidePickers() {
    var at = $('atPanel')
    var em = $('emPanel')
    var shade = $('talkshade')
    if (at) at.hidden = true
    if (em) em.hidden = true
    if (shade) shade.hidden = true
  }

  function showShade() {
    var shade = $('talkshade')
    if (!shade) return
    shade.hidden = false
  }

  function closePanels() {
    hidePickers()
    closeMenu()
  }

  function closeMenu() {
    var mask = $('holdmask')
    var pop = $('holdpop')
    if (mask) mask.remove()
    if (pop) pop.remove()
    var picked = document.querySelector('.mb.picked')
    if (picked) picked.classList.remove('picked')
  }

  function copyText(text) {
    var done = function () {}
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).catch(function () { fallbackCopy(text) }).then(done)
      return
    }
    fallbackCopy(text)
  }

  function fallbackCopy(text) {
    var area = document.createElement('textarea')
    area.value = text
    area.setAttribute('readonly', '')
    area.style.position = 'fixed'
    area.style.left = '-999px'
    document.body.appendChild(area)
    area.select()
    try { document.execCommand('copy') } catch (err) { /* ignore */ }
    area.remove()
  }

  function addReaction(bubble, face) {
    var card = bubble.parentNode
    if (!card) return
    var row = card.querySelector('.rx')
    if (!row) {
      row = document.createElement('div')
      row.className = 'rx'
      card.appendChild(row)
    }
    var chip = document.createElement('i')
    chip.textContent = face
    row.appendChild(chip)
  }

  function openMenu(anchor, meta) {
    closeMenu()
    var at = $('atPanel')
    var em = $('emPanel')
    if (at) at.hidden = true
    if (em) em.hidden = true
    var mask = document.createElement('div')
    mask.id = 'holdmask'
    mask.className = 'holdmask'
    var pop = document.createElement('div')
    pop.id = 'holdpop'
    pop.className = 'holdpop'
    var faces = ['👍', '👌', '❤️', '🤣', '😤', '🤔']
    var actions = [
      { id: 'copy', icon: '❐', label: '复制' },
      { id: 'quote', icon: '↩', label: '引用' }
    ]
    if (!meta.mine && meta.who && meta.who !== 'me') {
      actions.push({ id: 'at', icon: '@', label: nameOf(meta.who) })
    }
    pop.innerHTML = '<div class="reactbar">' + faces.map(function (face) {
      return '<button type="button" data-react="' + face + '">' + face + '</button>'
    }).join('') + '</div><div class="holdmenu">' + actions.map(function (act) {
      return '<button type="button" data-act="' + act.id + '"><b>' + act.icon + '</b>' + esc(act.label) + '</button>'
    }).join('') + '</div>'
    document.body.appendChild(mask)
    document.body.appendChild(pop)
    anchor.classList.add('picked')
    var rect = anchor.getBoundingClientRect()
    var width = pop.offsetWidth
    var height = pop.offsetHeight
    var left = Math.max(10, Math.min(rect.left, window.innerWidth - width - 10))
    var top = rect.bottom + 8
    if (top + height > window.innerHeight - 72) top = Math.max(8, rect.top - height - 8)
    pop.style.left = left + 'px'
    pop.style.top = top + 'px'
    mask.addEventListener('click', closeMenu)
    pop.addEventListener('click', function (event) {
      var btn = event.target.closest('button')
      if (!btn) return
      var face = btn.getAttribute('data-react')
      if (face) {
        addReaction(anchor, face)
        closeMenu()
        return
      }
      var act = btn.getAttribute('data-act')
      if (act === 'quote') quote(meta.who, meta.plain)
      if (act === 'at') mention(meta.who)
      if (act === 'copy') copyText(meta.plain)
      closeMenu()
    })
  }

  function armHold(bubble, meta) {
    var timer = 0
    var startX = 0
    var startY = 0
    var moved = false
    bubble.addEventListener('pointerdown', function (event) {
      if (event.button && event.button !== 0) return
      startX = event.clientX
      startY = event.clientY
      moved = false
      timer = setTimeout(function () {
        if (moved) return
        if (navigator.vibrate) {
          try { navigator.vibrate(12) } catch (err) { /* ignore */ }
        }
        openMenu(bubble, meta)
      }, 420)
    })
    bubble.addEventListener('pointermove', function (event) {
      if (Math.abs(event.clientX - startX) > 8 || Math.abs(event.clientY - startY) > 8) {
        moved = true
        clearTimeout(timer)
      }
    })
    bubble.addEventListener('pointerup', function () { clearTimeout(timer) })
    bubble.addEventListener('pointercancel', function () { clearTimeout(timer) })
    bubble.addEventListener('contextmenu', function (event) { event.preventDefault() })
  }

  function paintQuoteBar() {
    var bar = $('qbar')
    if (!bar) return
    if (!pendingQuote) {
      bar.hidden = true
      bar.innerHTML = ''
      return
    }
    bar.hidden = false
    bar.innerHTML = '<b>回复 ' + esc(nameOf(pendingQuote.who)) + '</b><span>' + esc(pendingQuote.text) + '</span><button type="button" id="qbarX">×</button>'
    var close = $('qbarX')
    if (close) close.onclick = function () {
      pendingQuote = null
      paintQuoteBar()
    }
  }

  function insertAtCursor(token) {
    var inp = $('inp')
    if (!inp || inp.disabled) return
    var start = inp.selectionStart || inp.value.length
    var end = inp.selectionEnd || start
    inp.value = inp.value.slice(0, start) + token + inp.value.slice(end)
    var next = start + token.length
    inp.focus()
    if (inp.setSelectionRange) inp.setSelectionRange(next, next)
  }

  function mention(key) {
    var item = cast().filter(function (row) { return row.key === key })[0]
    if (!item) return
    pendingMention = key
    var inp = $('inp')
    if (!inp) return
    var value = inp.value || ''
    value = value.replace(/@[^\s@]*$/, '')
    inp.value = value
    if (value && !/\s$/.test(value)) insertAtCursor(' ')
    insertAtCursor('@' + item.name + ' ')
    closePanels()
  }

  function quote(who, text) {
    var plain = String(text || '').replace(/<[^>]+>/g, '').trim()
    if (!plain) return
    pendingQuote = { who: who || 'me', text: plain.slice(0, 80) }
    paintQuoteBar()
    var inp = $('inp')
    if (inp && !inp.disabled) inp.focus()
  }

  function mount(who, text, extra, mine) {
    extra = extra || {}
    var box = $('msgs')
    if (!box) return
    var person = people()[who] || {}
    var d = document.createElement('div')
    d.className = 'msg' + (mine ? ' me' : '')
    var quoted = extra.quote && extra.quote.text
      ? '<div class="mq"><b>' + esc(nameOf(extra.quote.who)) + '</b><span>' + esc(extra.quote.text) + '</span></div>'
      : ''
    var sticker = extra.sticker ? '<div class="msticker">' + esc(extra.sticker) + '</div>' : ''
    var body = text ? '<div class="mt">' + paint(text) + '</div>' : ''
    var avatar = mine ? '' : '<img class="ma" alt="" src="' + esc(person.av || '') + '">'
    var tag = !mine && person.tag ? '<i>' + esc(person.tag) + '</i>' : ''
    var onlyFace = !!(extra.sticker && !text)
    d.innerHTML = avatar + '<div class="mc"><div class="mn">' + esc(mine ? '我' : (person.n || who)) + tag + '</div><div class="mb' + (onlyFace ? ' faceonly' : '') + '">' + quoted + sticker + body + '</div></div>'
    var plain = text || extra.sticker || ''
    var bubble = d.querySelector('.mb')
    if (bubble) {
      bubble.setAttribute('role', 'button')
      bubble.setAttribute('aria-label', (mine ? '我' : (person.n || who)) + '的消息，长按可引用')
      armHold(bubble, { who: mine ? 'me' : who, plain: plain, mine: !!mine })
    }
    var face = d.querySelector('.ma')
    if (face) face.addEventListener('click', function (event) {
      event.stopPropagation()
      mention(who)
    })
    box.appendChild(d)
    if (typeof root.scrollChat === 'function') root.scrollChat()
  }

  function renderPanel(id, html) {
    var node = $(id)
    if (!node) return null
    node.innerHTML = html
    return node
  }

  function openAt() {
    var panel = renderPanel('atPanel', cast().map(function (item) {
      return '<button type="button" data-key="' + esc(item.key) + '">' + esc(item.name) + '<i>' + esc(item.tag) + '</i></button>'
    }).join(''))
    var emo = $('emPanel')
    if (emo) emo.hidden = true
    if (!panel) return
    panel.hidden = false
    showShade()
    panel.onclick = function (event) {
      var btn = event.target.closest('button')
      if (!btn) return
      mention(btn.getAttribute('data-key'))
    }
  }

  function openEmoji(list) {
    var faces = list && list.length ? list : PACK
    var small = faces.map(function (face) {
      return '<button type="button" data-face="' + face + '">' + face + '</button>'
    }).join('')
    var big = faces.slice(0, 16).map(function (face) {
      return '<button type="button" class="big" data-big="' + face + '">' + face + '</button>'
    }).join('')
    var panel = renderPanel('emPanel', '<div class="emtab">小表情</div><div class="ems">' + small + '</div><div class="emtab">大表情</div><div class="ems bigs">' + big + '</div>')
    var at = $('atPanel')
    if (at) at.hidden = true
    if (!panel) return
    panel.hidden = false
    showShade()
    panel.onclick = function (event) {
      var btn = event.target.closest('button')
      if (!btn) return
      if (btn.getAttribute('data-big')) {
        pendingSticker = btn.getAttribute('data-big')
        closePanels()
        if (typeof root.sendFree === 'function') root.sendFree()
        return
      }
      insertAtCursor(btn.getAttribute('data-face') || '')
      closePanels()
    }
  }

  function bind() {
    if ($('atBtn')) return
    var bar = document.querySelector('.inbar')
    var inp = $('inp')
    if (!bar || !inp) return
    var at = document.createElement('button')
    at.type = 'button'
    at.id = 'atBtn'
    at.className = 'ib'
    at.textContent = '@'
    at.setAttribute('aria-label', '提到某人')
    var em = document.createElement('button')
    em.type = 'button'
    em.id = 'emBtn'
    em.className = 'ib'
    em.textContent = '😊'
    em.setAttribute('aria-label', '表情')
    var field = document.createElement('div')
    field.className = 'ifield'
    bar.insertBefore(field, inp)
    field.appendChild(inp)
    em.classList.add('em')
    field.appendChild(em)
    bar.insertBefore(at, field)
    var send = bar.querySelector('.send')
    if (send) {
      send.classList.add('talk-send')
      send.textContent = '发送'
    }
    var qbar = document.createElement('div')
    qbar.id = 'qbar'
    qbar.className = 'qbar'
    qbar.hidden = true
    bar.parentNode.insertBefore(qbar, bar)
    var panels = document.createElement('div')
    panels.innerHTML = '<div id="atPanel" class="talkpan" hidden></div><div id="emPanel" class="talkpan" hidden></div>'
    bar.parentNode.insertBefore(panels, bar)
    var shade = document.createElement('div')
    shade.id = 'talkshade'
    shade.className = 'talkshade'
    shade.hidden = true
    shade.setAttribute('aria-label', '关闭')
    document.body.appendChild(shade)
    shade.addEventListener('click', function (event) {
      event.preventDefault()
      event.stopPropagation()
      hidePickers()
      var box = $('inp')
      if (box && !box.disabled) box.focus()
    })
    at.onclick = function () {
      if ($('atPanel') && !$('atPanel').hidden) closePanels()
      else openAt()
    }
    em.onclick = function () {
      if ($('emPanel') && !$('emPanel').hidden) {
        closePanels()
        return
      }
      var ns = root.JnaoAcademy
      var loaded = ns && ns.api ? ns.api('/api/academy/stickers') : Promise.reject()
      loaded.then(function (data) {
        openEmoji((data && data.small) || PACK)
      }).catch(function () {
        openEmoji(PACK)
      })
    }
    inp.addEventListener('input', function () {
      if (/@[^\s@]*$/.test(inp.value)) openAt()
    })
  }

  root.AcademyTalk = {
    mount: mount,
    mention: mention,
    quote: quote,
    bind: bind,
    collect: function (text) {
      return {
        text: text || '',
        mention: resolveMention(text || '') || undefined,
        quote: pendingQuote || undefined,
        sticker: pendingSticker || undefined
      }
    },
    clear: function () {
      pendingQuote = null
      pendingSticker = null
      pendingMention = ''
      paintQuoteBar()
      closePanels()
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bind)
  else bind()
})(window)
