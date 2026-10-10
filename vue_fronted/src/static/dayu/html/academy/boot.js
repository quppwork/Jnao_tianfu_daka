/* 把父页注入的 sector 分给频道、剧情、课程。各页缺的 DOM 自己跳过。 */
(function (root) {
  var ns = root.JnaoAcademy
  if (!ns) return

  function apply(payload) {
    if (!payload) return
    // 同集：iframe 内已解锁时，勿被父页陈旧 sector 盖回 locked
    try {
      var prev = ns.state && ns.state.episode
      var next = payload.episode
      if (prev && next && prev.id === next.id && prev.unlocked && !next.unlocked) {
        next.unlocked = true
        next.percent = Math.max(Number(next.percent) || 0, Number(prev.percent) || 0, 100)
      }
    } catch (eKeep) { /* ignore */ }
    ns.state = payload
    if (ns.bindChannel) ns.bindChannel()
    if (ns.paintChannel) ns.paintChannel(payload)
    if (ns.paintStory) ns.paintStory(payload)
    if (ns.paintCourses) ns.paintCourses(payload)
    if (!payload.fake && payload.episode) {
      try {
        var uid = ''
        try { uid = localStorage.getItem('jnao_child_user_id') || '' } catch (e0) { /* ignore */ }
        if (!uid && payload.user_id) uid = String(payload.user_id)
        localStorage.removeItem('jnao_academy_sector')
        localStorage.setItem(
          uid ? ('jnao_academy_sector_' + uid) : 'jnao_academy_sector',
          JSON.stringify(payload)
        )
      } catch (e) { /* ignore */ }
    }
  }

  root.addEventListener('message', function (ev) {
    var data = ev.data
    if (!data || typeof data !== 'object') return
    if (data.type === 'dayu-academy-collapse') {
      if (typeof ns.collapseChannel === 'function') ns.collapseChannel()
      return
    }
    if (data.type !== 'dayu-academy' || !data.academy) return
    apply(data.academy)
  })
  if (ns.bindChannel) ns.bindChannel()
  try {
    var cached = root.__ACADEMY_CACHED_SECTOR
    if (!cached) {
      var uidR = ''
      try { uidR = localStorage.getItem('jnao_child_user_id') || '' } catch (e1) { /* ignore */ }
      if (uidR) {
        cached = JSON.parse(localStorage.getItem('jnao_academy_sector_' + uidR) || 'null')
      }
      if (!cached || !cached.episode) {
        cached = JSON.parse(localStorage.getItem('jnao_academy_sector') || 'null')
        if (cached && uidR && String(cached.user_id || '') !== String(uidR)) {
          cached = null
        }
      }
      // uid 未就绪时扫一份 sector 缓存，避免首屏默认锁定
      if ((!cached || !cached.episode) && !uidR) {
        try {
          for (var i = 0; i < localStorage.length; i++) {
            var k = localStorage.key(i)
            if (!k || k.indexOf('jnao_academy_sector_') !== 0) continue
            var cand = JSON.parse(localStorage.getItem(k) || 'null')
            if (cand && cand.episode && !cand.fake) {
              cached = cand
              break
            }
          }
        } catch (eScan) { /* ignore */ }
      }
    }
    if (cached && cached.episode) apply(cached)
  } catch (e) { /* 没有上次目录就等父页 */ }
  var delay = 700
  try {
    if (localStorage.getItem('jnao_child_user_id')) delay = 3500
  } catch (e) { /* ignore */ }
  setTimeout(function () {
    if (ns.state || !ns.fakeSector) return
    apply(ns.fakeSector())
  }, delay)
})(window)
