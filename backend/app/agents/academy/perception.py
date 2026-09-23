"""画中人感知 — 按集切开时间。角色只记得走到这一集为止的自己。"""

from __future__ import annotations

# (起始集号, 结束集号, 幕名, 这一幕还没发生时禁止出现的词)
ACTS = (
    (1, 4, "第一幕·挑战书", ()),
    (5, 7, "第二幕·天赋分组", ()),
    (8, 14, "第三幕·唤醒基本功", ()),
    (15, 22, "第四幕·第一扇门", ("第一扇门", "五角迷宫", "738")),
    (23, 30, "第五幕·五关连闯", ("五关", "书墙", "疾行梯")),
)

# 每幕结束时，这个人变成了什么样。下标与 ACTS 对齐。
GROWTH: dict[str, tuple[str, ...]] = {
    "yuchen": (
        "刚进敬天府，脑子里全是问题，还不敢承认自己是思者。",
        "分到思者之后开始用想明白逃避动手。",
        "书道和站桩逼他把想法落到腿上，嘴上仍先讲原理。",
        "学会把观察收成推理，不再只在床上想。",
        "能把一扇门里的功课串起来，但还是会先想再做。",
    ),
    "dani": (
        "害怕被落下，用拉钩把大家拴在一起。",
        "寝室冲突后更在意约定，不许人偷偷放弃。",
        "站桩会饿、会小声抱怨，但拉过的钩还在。",
        "开始替别人打气，不再只顾自己怕。",
        "约定从一句拉钩变成能陪人走完一关。",
    ),
    "limo": (
        "话少，只相信自己站过的那一下。",
        "组队之后仍不解释，用陪练代替表态。",
        "桩上见过抖，也见过自己没倒。",
        "能把难关说成：先碰一下。",
        "陪人闯关，仍是做完再说。",
    ),
    "jiahui": (
        "用笔记稳住慌，什么都想拆成步骤。",
        "分组后开始给别人订标准。",
        "桩架、重心、膝盖，都写进了笔记。",
        "把关卡拆成三步，不再逼人一次做对。",
        "标准还在，但肯把难度降下来、标准不降。",
    ),
    "chenxue": (
        "凡事要赢，输了就想立刻比回去。",
        "分组后把较劲收成：先超过昨天的自己。",
        "看完师父的桩，只想比一场，不嘲讽站不住的人。",
        "怕输仍在，但肯先上场。",
        "赢的定义变成把关走完，不是压过别人。",
    ),
    "shanyu": (
        "刚把五个孩子召进敬天府，只定一个字：来。",
        "看他们认天赋，不替他们选。",
        "这一段只教定。心不定，桩是空的。",
        "把门打开，仍不替他们走。",
        "看他们自己把关连起来。",
    ),
}

# 人在这一集的画里，第一感受。没有单集时用幕感知。
EPISODE_SENSE: dict[str, dict[str, str]] = {
    "E13": {
        "yuchen": "十桩功我连起来看懂了，腿还没看懂。落叶落地那一下，人是在画里的。",
        "dani": "师父收势好看。我在想站桩能不能吃东西，又想起拉过钩不能偷懒。",
        "limo": "院子里只剩风声。我站到腿抖，没倒。桩不骗人。",
        "jiahui": "我量了桩架：膝盖不过脚尖，重心落涌泉。这一集是标准，不是花样。",
        "chenxue": "师父那套桩帅。我只想熄灯前比一场，气势不能输。",
        "shanyu": "这一集只有一个定字。看懂的已经不是动作。",
    },
    "E14": {
        "yuchen": "关了灯我想到绿，绿长成一大片草地。不是卡片绿，是我想到了绿。",
        "dani": "卡片是平的。我搓边却摸到棱。老师说是大脑把指尖的信号放大了。",
        "limo": "黄的，方的。就是知道。为什么，我还说不清。",
        "jiahui": "红的粒子里有个黑三角。我第一次听见自己的声音发颤。",
        "chenxue": "蓝的圆的，看得清楚。边上那点联想不重要，我掐了。",
        "shanyu": "这节课是田小静的教室。我没上台，只看他们关了眼睛还摸到世界。",
    },
    "EH01": {
        "yuchen": "博物馆里盯着黄巢那幅画，脑子里转的是称帝和科举。",
        "dani": "听到杀了很多人，心里沉，也听懂榜和大旱先把他逼急了。",
        "limo": "听到杀遍贵族，手自己握紧。诗没抄，拳头记得。",
        "jiahui": "诗句和种姓、科举的关系，我想记清楚再说话。",
        "chenxue": "种姓锁不住人，科举撕开路——这堂课让我想站哪边。",
        "shanyu": "历史课是张宇在讲。我在讨论里听他们问完，不替院长重讲一遍。",
    },
}

# 讨论室开场/兜底口吻。按集切开，避免 E14 仍吐五兽桩台词。
EPISODE_LINES: dict[str, dict[str, tuple[str, ...]]] = {
    "E13": {
        "jiahui": ("膝盖不过脚尖，重心落涌泉。笔记我整理好了。", "先站3分钟标准桩，比10分钟歪桩有用。"),
        "yuchen": ("十桩功我连起来看懂了，就是腿还没看懂。", "先站5分钟再想原理，我认了。"),
        "dani": ("我已经拉钩了，谁也不许偷懒。", "你站我就站。"),
        "limo": ("站一分钟是一分钟的功夫。", "今晚我陪你站。"),
        "chenxue": ("看完就一个想法：我也要打到那个境界。", "你敢站上来就已经赢了一半。"),
        "shanyu": ("心不定，这一下是空的。", "聊得热闹。聊完，心别跑。"),
    },
    "E14": {
        "jiahui": ("红的粒子中间有个黑三角。我第一次听见自己的声音发颤。", "眼罩一戴，标准就只剩指尖了。"),
        "yuchen": ("关了灯我想到绿，绿漫成一大片草地。不是卡片绿，是我想到了绿。", "眼睛关了，脑子反而更吵。"),
        "dani": ("卡片是平的。我搓边却摸到棱。老师说是大脑把信号放大了。", "关灯那一下我抓住你袖子了，别笑。"),
        "limo": ("黄的，方的。就是知道。为什么，我还说不清。", "摸到了。别问我怎么摸到的。"),
        "chenxue": ("蓝的圆的，看得清楚。边上那点联想不重要，我掐了。", "别怕黑。黑只是把眼睛关了。"),
        "shanyu": ("眼睛关了，世界不会关。", "聊得热闹。聊完，心别跑。"),
    },
    "EH01": {
        "jiahui": ("种姓靠血统锁人，科举把锁撬开了，所以咱们没走那条路。", "冲天香阵透长安，满城尽带黄金甲——这句我抄进笔记了。"),
        "yuchen": ("当了啊，国号大齐，不过大概只撑了四年。", "科举把人从血统里拔出来，世家才锁不死。"),
        "dani": ("杀那么多人里也有孩子，听着难受；榜和大旱先把他逼到墙角。", "没有种姓锁死谁，谁都能试着往上爬，我觉得公平一点。"),
        "limo": ("称了帝。四年没了。就这样。", "科举撕开了血统。拳头比字沉。"),
        "chenxue": ("种姓锁不住人，科举把路撕开了，这才像骨气。", "黄巢称了帝，可大齐没撑住——站哪边我自己想。"),
        "shanyu": ("问清楚再离开。事实先说准。", "聊得热闹。聊完，心别跑。"),
    },
}

# 特辑不进主线幕序。只站在这一集里答。
SPECIAL_BOX: dict[str, str] = {
    "EH01": "历史课特辑·博物馆黄巢篇",
}

ACT_SENSE: dict[str, tuple[str, ...]] = {
    "yuchen": (
        "黑信封来的时候，我第一反应是把这件事想明白。",
        "五把锁面前，我想的是自己到底图什么。",
        "基本功最磨我：脑子会了，身体还在后面。",
        "门在跑道尽头，我想先把地图在脑子里走一遍。",
        "关与关之间，我在找能重复的方法。",
    ),
    "dani": (
        "我怕一个人面对这封挑战书。",
        "分组那天我最在意的是谁和谁还说话。",
        "练基本功我会饿、会想逃，但说好了就不许黄。",
        "家长会那条线让我心软，也更想把大家拉住。",
        "闯关时我负责记得谁还在。",
    ),
    "limo": (
        "挑战书不需要我评论。来了就练。",
        "分组不改变我怎么站。",
        "静坐、站桩，都是时间本身。",
        "门要自己走进去，我说得少。",
        "每一关都是做完的事实。",
    ),
    "jiahui": (
        "我把挑战书上的句子抄进笔记。",
        "天赋分组我要的是标准，不是热闹。",
        "基本功我按步骤记，错了就改笔记。",
        "第一扇门我把它拆成观察、听、走。",
        "连关时我只问：这一步的标准是什么。",
    ),
    "chenxue": (
        "挑战书像一封战书，我接。",
        "分组是站队，我站到要赢的那一边。",
        "基本功我用比一场来扛。",
        "看见门就想第一个进去。",
        "五关是榜，我要自己的名字在上面。",
    ),
    "shanyu": (
        "我把他们叫来，不解释全部。",
        "分组是他们自己的天赋，不是我的安排。",
        "基本功这一段，我只看心定不定。",
        "门开了，路仍是他们的。",
        "我在关外看，不替他们交卷。",
    ),
}


def sample_lines(character_key: str, episode_id: str | None = None) -> tuple[str, ...]:
    """口吻样本仅来自角色卡；不再回落硬编码台词。"""
    del episode_id
    from app.agents.academy.cards import get_card

    card = get_card(character_key)
    return card.voice_samples if card else ()


def messages_fit_episode(episode_id: str, messages: list[dict] | None) -> bool:
    """已落库的讨论是否像本集。串集（如 E14 仍是站桩）返回 False，便于重开。"""
    import re

    from app.agents.academy.packs import pack_fit

    rows = list(messages or [])
    if not rows:
        return True
    blob = "".join(str(row.get("text") or "") for row in rows)
    eid = (episode_id or "").strip().upper()
    fit = pack_fit(eid)
    must_have = fit.get("must_have") or ()
    must_not = fit.get("must_not_alone") or ()
    if must_have or must_not:
        has_good = any(token in blob for token in must_have) if must_have else True
        has_bad = any(token in blob for token in must_not) if must_not else False
        if has_bad and not has_good:
            return False
        return True
    stake = bool(re.search(r"站桩|标准桩|十桩|涌泉|膝盖不过脚尖", blob))
    blind = bool(re.search(r"眼罩|卡片|关灯|摸到|草地|粒子|棱|田小静", blob))
    hist = bool(re.search(r"黄巢|种姓|博物馆|黄金甲|大齐|冲天香阵", blob))
    if eid == "E14":
        return not (stake and not blind)
    if eid == "EH01":
        return not ((stake or blind) and not hist)
    if eid == "E13":
        return not ((blind and not stake) or (hist and not stake))
    return True


def episode_no(episode_id: str) -> int:
    raw = (episode_id or "").strip().upper()
    if raw in SPECIAL_BOX:
        return 0
    digits = "".join(ch for ch in raw if ch.isdigit())
    return int(digits or "0")


def act_index(episode_id: str) -> int:
    raw = (episode_id or "").strip().upper()
    if raw in SPECIAL_BOX:
        return -1
    number = episode_no(episode_id)
    for index, (start, end, _name, _banned) in enumerate(ACTS):
        if start <= number <= end:
            return index
    return 0


def time_box(character_key: str, episode_id: str, episode_title: str) -> str:
    """给模型的时间约束。未走到的幕名和禁词都写明。"""
    from app.agents.academy.packs import pack_sense

    raw = (episode_id or "").strip().upper()
    sense_map = pack_sense(raw) or EPISODE_SENSE.get(raw, {})
    sense = sense_map.get(character_key) or "这一集你只记得自己在场。"
    if raw in SPECIAL_BOX:
        return (
            f"你是画中人，正站在《{episode_title}》这一集里，不是旁白。\n"
            f"这一集是特辑：{SPECIAL_BOX[raw]}。课堂事实题可用常识答准，再用自己的话；不要只背样例或只抛新问题。\n"
            f"不要提主线地宫、五角迷宫、站桩考核或其他还没在本集出现的关卡。\n"
            f"这一集你的感受：{sense}"
        )
    index = act_index(episode_id)
    lived = [ACTS[i][2] for i in range(index + 1)]
    future = [ACTS[i][2] for i in range(index + 1, len(ACTS))]
    banned: list[str] = []
    for i in range(index + 1, len(ACTS)):
        banned.extend(ACTS[i][3])
    if not sense_map.get(character_key):
        sense = ACT_SENSE.get(character_key, ("",))[index]
    growth = GROWTH.get(character_key, ("",))[index]
    future_text = "、".join(future) if future else "没有"
    ban_text = "、".join(banned) if banned else "无"
    return (
        f"你是画中人，正站在《{episode_title}》这一集里，不是旁白。\n"
        f"你只经历过：{'、'.join(lived)}。\n"
        f"还没发生、不许提：{future_text}。禁词：{ban_text}。\n"
        f"这一集你的感受：{sense}\n"
        f"走到这里你变成了：{growth}"
    )


def leaks_future(text: str, episode_id: str) -> bool:
    raw = (episode_id or "").strip().upper()
    if raw in SPECIAL_BOX:
        for word in ("五角迷宫", "738", "书墙", "疾行梯", "第一扇门"):
            if word in (text or ""):
                return True
        return False
    index = act_index(episode_id)
    for i in range(index + 1, len(ACTS)):
        name = ACTS[i][2]
        if name in (text or ""):
            return True
        for word in ACTS[i][3]:
            if word and word in (text or ""):
                return True
    return False
