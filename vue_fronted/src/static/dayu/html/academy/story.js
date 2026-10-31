/* 历史剧情页：只画幕和集，点击交给 client.goEpisode。 */
(function (root) {
  var ns = root.JnaoAcademy
  if (!ns) return
  var $ = ns.$
  var LABEL = { done: '✓ 已看完', ing: '▶ 在追', lockd: '🔒 未解锁' }

  ns.paintStory = function (sector) {
    var banner = $('banner')
    var acts = $('acts')
    if (!banner || !acts || !sector || !sector.acts) return
    banner.innerHTML = sector.acts.map(function (act) {
      var status = act.status === 'done' ? 'done' : (act.status === 'ing' ? 'ing' : 'lockd')
      return '<div class="bslide ' + status + '"><img src="' + act.poster + '" alt=""><div class="mask"></div>'
        + '<span class="stp ' + status + '">' + (LABEL[status] || '') + '</span>'
        + '<div class="bt"><span class="no">' + act.no + ' · ' + act.range + '</span><b>' + act.name + '</b><small>' + act.tag + '</small></div></div>'
    }).join('')
    if ($('bdots')) $('bdots').innerHTML = sector.acts.map(function () { return '<i></i>' }).join('')
    acts.innerHTML = sector.acts.map(function (act) {
      var status = act.locked ? 'lockd' : (act.status || 'lockd')
      var rows = (act.episodes || []).map(function (ep) {
        if (ep.unlocked) {
          return '<div class="ep watched" data-ep="' + ep.id + '"><span class="eno">' + ep.id + '</span><span class="et">'
            + ep.title + '<small>' + ep.topic + '</small></span><span class="rb">↻ 回看讨论</span><span class="est">✓ 已看</span></div>'
        }
        if (ep.playable) {
          return '<div class="ep watched" data-ep="' + ep.id + '"><span class="eno">' + ep.id + '</span><span class="et">'
            + ep.title + '<small>' + ep.topic + '</small></span><span class="est">' + (ep.media === 'demo' ? '模拟片' : '去看') + '</span></div>'
        }
        return '<div class="ep unw"><span class="eno">' + ep.id + '</span><span class="et">'
          + ep.title + '<small>' + ep.topic + '</small></span><span class="est">待上传</span></div>'
      }).join('')
      var pct = act.total ? Math.round(act.watched / act.total * 100) : 0
      return '<div class="act ' + status + '"><span class="st ' + status + '">' + (LABEL[status] || LABEL.lockd) + '</span>'
        + '<div class="arow"><img class="poster" src="' + act.poster + '" alt=""><div class="ainfo"><div class="no">'
        + act.no + ' · ' + act.range + '</div><h3>' + act.name + '</h3><p>' + act.core + '</p><div class="epsn">'
        + (act.locked ? '未开始' : ('已看 ' + act.watched + '/' + act.total + ' 集')) + '</div></div></div>'
        + '<div class="eps" style="display:block">' + (rows || '<div style="padding:14px 4px;font-size:10.5px;color:#5E6B84;text-align:center">这一幕还没开始</div>') + '</div>'
        + '<div class="bar" style="width:' + pct + '%"></div></div>'
    }).join('')
    acts.querySelectorAll('[data-ep]').forEach(function (node) {
      node.addEventListener('click', function (ev) {
        ev.stopPropagation()
        ns.goEpisode(node.getAttribute('data-ep'))
      })
    })
  }
})(window)
