"""训练域服务包 — 对外 API 与历史 training_service 对齐。"""

from . import checkin as _checkin
from . import checkin_cards as _checkin_cards
from . import common as _common
from . import service as _service
from . import window as _window

for _mod in (_common, _window, _checkin_cards, _checkin, _service):
    for _name, _val in vars(_mod).items():
        if _name.startswith("__"):
            continue
        globals()[_name] = _val

del _mod, _name, _val
