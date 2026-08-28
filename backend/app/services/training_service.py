"""兼容入口：请优先 `from app.services.training import …`。

历史路径 `app.services.training_service` 仍可用（含私有 `_` 符号）。
"""

import app.services.training.checkin as _checkin
import app.services.training.checkin_cards as _checkin_cards
import app.services.training.common as _common
import app.services.training.elective as _elective
import app.services.training.media as _media
import app.services.training.plan_view as _plan_view
import app.services.training.service as _service
import app.services.training.window as _window

for _mod in (_common, _window, _media, _plan_view, _elective, _checkin_cards, _checkin, _service):
    for _name, _val in vars(_mod).items():
        if _name.startswith("__"):
            continue
        globals()[_name] = _val

del _mod, _name, _val
