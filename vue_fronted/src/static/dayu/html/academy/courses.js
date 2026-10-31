/* 课程页：已报名讲次、九大秘籍、报名入口。席位数字来自模拟数据，不再自己倒计时。 */
(function (root) {
  var ns = root.JnaoAcademy
  if (!ns) return
  var $ = ns.$

  ns.paintCourses = function (sector) {
    var box = sector && sector.courses
    if (!box || !$('mj')) return
    root.__ACADEMY_HOLD_AD = true
    var camp = box.camp || {}
    if ($('adLeft')) $('adLeft').textContent = camp.open ? String(camp.seats_left || 0) : '未开通'
    if ($('adEn')) $('adEn').textContent = camp.enrolled != null ? String(camp.enrolled) : '—'
    if ($('adBar') && camp.seats_total) {
      $('adBar').style.width = Math.round((camp.enrolled || 0) / camp.seats_total * 100) + '%'
    }
    var mine = box.mine || {}
    var bar = document.querySelector('.pbar i')
    if (bar) bar.style.width = (mine.percent || 0) + '%'
    var text = document.querySelector('.ptxt')
    if (text) text.textContent = '已学 ' + (mine.done || 0) + ' / ' + (mine.total || 0) + ' 讲 · ' + (mine.percent || 0) + '%'
    var chapters = document.querySelector('.chaps')
    if (chapters) {
      chapters.innerHTML = (mine.chapters || []).map(function (chapter) {
        var cls = chapter.status === 'done' ? 'done' : (chapter.status === 'now' ? 'now' : 'todo')
        var mark = chapter.status === 'done' ? '✓' : (chapter.status === 'now' ? '▶' : '·')
        var label = chapter.status === 'done' ? '已看' : (chapter.status === 'now' ? '当前' : '未看')
        return '<div class="chap ' + cls + '" data-ep="' + chapter.episode_id + '"><span class="dot">' + mark + '</span>'
          + chapter.title + '<span class="tm">' + label + '</span></div>'
      }).join('')
      chapters.querySelectorAll('[data-ep]').forEach(function (node) {
        node.addEventListener('click', function () { ns.goEpisode(node.getAttribute('data-ep')) })
      })
    }
    $('mj').innerHTML = (box.miji || []).map(function (item) {
      return '<a class="mj" data-ep="' + item.episode_id + '"><img src="' + item.cover + '" alt="' + item.name + '"><div class="mn">' + item.name + '</div></a>'
    }).join('')
    $('mj').querySelectorAll('[data-ep]').forEach(function (node) {
      node.addEventListener('click', function (ev) {
        ev.preventDefault()
        ns.goEpisode(node.getAttribute('data-ep'))
      })
    })
    document.querySelectorAll('.vip .btn, .adbtn').forEach(function (btn) {
      btn.onclick = function (ev) {
        ev.preventDefault()
        ns.toast(camp.note || '报名通道尚未开通')
      }
    })
  }
})(window)
