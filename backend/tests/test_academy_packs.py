"""剧集包：一集一套资料可加载。"""

from app.agents.academy.packs import all_packs, get_pack, pack_lines
from app.agents.academy.perception import messages_fit_episode, sample_lines


def test_packs_load_switchable_three():
    packs = all_packs()
    assert set(packs) >= {"E13", "E14", "EH01"}
    assert get_pack("e14").oss_key.startswith("AIshipin/")
    assert "眼罩" in pack_lines("E14", "jiahui")[1] or "粒子" in pack_lines("E14", "jiahui")[0]


def test_sample_lines_prefer_pack_over_stake_defaults():
    text = sample_lines("limo", "E14")[0]
    assert "站桩" not in text
    assert "黄" in text or "摸" in text


def test_messages_fit_rejects_stake_on_e14():
    assert messages_fit_episode("E14", [{"text": "先站3分钟标准桩"}]) is False
    assert messages_fit_episode("E14", [{"text": "戴上眼罩摸到卡片"}]) is True
