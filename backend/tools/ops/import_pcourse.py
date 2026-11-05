# -*- coding: utf-8 -*-
"""Download missing pcourse assets from kimi and write adapted pcourse.html."""
from __future__ import annotations

import re
import urllib.request
from pathlib import Path

ROOT = Path(r"d:/daka/Jnao_tianfu_daka/vue_fronted/src/static/dayu")
HTML_DIR = ROOT / "html"
ASSETS = ROOT / "assets"
REMOTE = "https://jnao10.ok.kimi.link"
UA = {"User-Agent": "Mozilla/5.0"}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()


def ensure_asset(rel: str) -> None:
    dest = ASSETS / rel
    if dest.exists() and dest.stat().st_size > 100:
        print(f"skip {rel}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{REMOTE}/assets/{rel}"
    try:
        data = fetch(url)
        dest.write_bytes(data)
        print(f"ok {rel} ({len(data)})")
    except Exception as e:
        print(f"FAIL {rel}: {e}")


def main() -> None:
    for rel in (
        "mentor-chinese.png",
        "pcourse-tools.jpg",
    ):
        ensure_asset(rel)

    raw = (ROOT / "_remote_pcourse.html").read_text(encoding="utf-8")
    # strip kimi sdk
    raw = re.sub(
        r'<script src="https://www\.kimi\.com/sdk-seed\.js"[^>]*></script>',
        "",
        raw,
    )
    # absolute asset paths
    raw = re.sub(r'(?<!/static/dayu/)assets/', "/static/dayu/assets/", raw)

    # replace jn-back + append nav bridge like consult.html
    bridge = r'''
<script>
(function(){
  function post(type, extra){
    try{
      if(window.parent && window.parent !== window){
        window.parent.postMessage(Object.assign({type:type}, extra||{}), '*');
        return true;
      }
    }catch(e){}
    return false;
  }
  function nav(path){
    if(post('dayu-nav', {path: path})) return;
    location.href = path;
  }
  // back button → dayu-back or parent home
  document.querySelectorAll('.jn-back').forEach(function(b){
    b.onclick = function(){
      if(post('dayu-back')) return;
      if(window.history.length>1) window.history.back();
      else nav('/pages/parent/dayu');
    };
  });
  document.querySelectorAll('a.acctbtn[href="index.html"]').forEach(function(a){
    a.setAttribute('href','javascript:;');
    a.addEventListener('click', function(e){
      e.preventDefault();
      if(!post('dayu-student')) nav('/pages/dayu/home');
    });
  });
  document.addEventListener('click', function(e){
    var a = e.target.closest && e.target.closest('a');
    if(!a) return;
    var href = a.getAttribute('href') || '';
    if(!href || href.indexOf('javascript:')===0 || href.charAt(0)==='#') return;
    var file = href.split('?')[0].split('#')[0].split('/').pop();
    var map = {
      'parent.html': '/pages/parent/dayu',
      'pset.html': '/pages/parent/pset',
      'pdata.html': '/pages/parent/pdata',
      'consult.html': '/pages/parent/consult',
      'community.html': '/pages/parent/community',
      'pcourse.html': '/pages/parent/pcourse',
      'kids-manage.html': '/pages/parent/index',
      'index.html': '__student__'
    };
    if(map[file]){
      e.preventDefault();
      e.stopPropagation();
      if(map[file] === '__student__'){
        if(!post('dayu-student')) nav('/pages/dayu/home');
        return;
      }
      nav(map[file]);
    }
  }, true);
  // hide foot scrollbar chrome consistency
  try{ post('dayu-ready'); }catch(e){}
})();
</script>
</body></html>
'''
    # keep jn-back script but fix fallback; then append bridge before </body>
    raw = raw.replace(
        "location.href='parent.html';",
        "try{if(window.parent&&window.parent!==window){window.parent.postMessage({type:'dayu-back'},'*');return;}}catch(e){}location.href='parent.html';",
    )
    raw = re.sub(r"</body>\s*</html>\s*$", bridge, raw, count=1, flags=re.I)

    # align width with app
    raw = raw.replace(
        ".phone{max-width:430px;",
        ".phone{max-width:var(--app-max-width, 480px);",
    )
    raw = raw.replace(
        ".foot{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:100%;max-width:430px;",
        ".foot{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:100%;max-width:var(--app-max-width, 480px);",
    )
    # hide possible overflow scrollbars
    if "scrollbar-width" not in raw:
        raw = raw.replace(
            "body{background:#0D111F;",
            "body{scrollbar-width:none;-ms-overflow-style:none;background:#0D111F;",
        )
        raw = raw.replace(
            "</style>",
            "body::-webkit-scrollbar{display:none;width:0;height:0}\n</style>",
            1,
        )

    out = HTML_DIR / "pcourse.html"
    out.write_text(raw, encoding="utf-8", newline="\n")
    print(f"wrote {out} ({out.stat().st_size})")

    # cleanup remote temp
    tmp = ROOT / "_remote_pcourse.html"
    if tmp.exists():
        tmp.unlink()
        print("removed _remote_pcourse.html")


if __name__ == "__main__":
    main()
