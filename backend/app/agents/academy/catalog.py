"""天赋学院板块目录 — 历史剧情六幕、频道剧集、天赋课程。视频只存 OSS key。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Episode:
    id: str
    title: str
    topic: str
    task: str = "完成今晚训练并打卡"
    oss_key: str = ""
    duration_label: str = ""
    poster: str = "/static/dayu/assets/miji/mj-tfsd.jpg"
    cast: tuple[str, ...] = ("shanyu", "yuchen", "dani", "limo", "jiahui", "chenxue")
    chips: tuple[str, ...] = (
        "这集你印象最深的是什么？",
        "今晚训练谁跟我一组？",
        "我怕自己坚持不住怎么办？",
    )


@dataclass(frozen=True)
class Act:
    no: str
    name: str
    range: str
    poster: str
    core: str
    tag: str
    episode_ids: tuple[str, ...]
    locked: bool = False


def _ep(eid: str, title: str, topic: str, task: str | None = None) -> Episode:
    return Episode(
        id=eid,
        title=title,
        topic=topic,
        task=task or "看完这一集，到今日修炼打卡",
        chips=(
            f"《{title}》里你记住了哪一句？",
            "今晚训练谁跟我一组？",
            "我怕自己坚持不住怎么办？",
        ),
    )


# E13 是频道原型集。正片 key 留空，上传后只改这里，不把视频放进仓库。
EPISODES: dict[str, Episode] = {
    e.id: e
    for e in (
        _ep("E01", "挑战书", "AI危机 · 世界观"),
        _ep("E02", "黑信封", "信念启蒙"),
        _ep("E03", "开学第一课", "导师登场"),
        _ep("E04", "五者特战队", "天赋认知 · 组队"),
        _ep("E05", "天赋分组仪式", "五把锁 · 天赋测试"),
        _ep("E06", "女生寝室战争", "双女主冲突"),
        _ep("E07", "不能说的秘密", "存在的意义"),
        _ep("E08", "闹市静坐", "专注力"),
        _ep("E09", "被欺负的饭桶", "观察力"),
        _ep("E10", "石头开花", "记忆力"),
        _ep("E11", "眼中有太极", "书道Ⅰ"),
        _ep("E12", "心中有太极", "篆书开五窍"),
        Episode(
            id="E13",
            title="五兽桩",
            topic="站桩 · 专注力修炼",
            task="站桩5分钟",
            duration_label="正片 12:30",
            poster="/static/dayu/assets/miji/mj-tfsd.jpg",
            chips=(
                "这一集里师父哪一下你记得最清？",
                "今晚站桩谁跟我一组？",
                "我觉得我站不住怎么办？",
                "师父，十桩功最难的是哪一桩？",
            ),
        ),
        Episode(
            id="E14",
            title="蒙上眼睛之后",
            topic="多元感知 · 圆形教室",
            task="蒙眼认一张卡",
            duration_label="正片约 5:50",
            poster="/static/dayu/assets/miji/mj-tfsd.jpg",
            oss_key="AIshipin/E14_blindfold_720p.mp4",
            chips=(
                "戴上眼罩你怕不怕黑？",
                "你摸到卡片是什么感觉？",
                "五个世界里你最想问谁？",
                "眼睛关了世界真的没关吗？",
            ),
        ),
        Episode(
            id="EH01",
            title="历史课·黄巢篇",
            topic="博物馆 · 满城尽带黄金甲",
            task="记住今天这节历史课",
            duration_label="正片约 5:20",
            poster="/static/dayu/assets/hall/think1.png",
            oss_key="AIshipin/EH01_huangchao_720p.mp4",
            chips=(
                "中国为什么没有种姓？",
                "黄巢最后当上皇帝了吗？",
                "他杀那么多人，你怎么看？",
                "那首诗你记住哪一句？",
            ),
        ),
        _ep("E15", "跑道尽头", "观察推理 · 入口"),
        _ep("E16", "738", "听觉 · 录音破解"),
        _ep("E17", "第一扇门", "第一关 · 五角迷宫"),
        _ep("E18", "不需要眼睛", "蒙眼感知"),
        _ep("E19", "家长会", "家庭线"),
        _ep("E20", "一千只眼睛", "钥匙训练"),
        _ep("E21", "问题汇报（上）", "收束"),
        _ep("E22", "问题汇报（下）", "收束"),
        _ep("E23", "10万分之一（上）", "第二关 · 书墙"),
        _ep("E24", "10万分之一（下）", "超脑阅读"),
        _ep("E25", "记忆碎片拼图", "影像追忆"),
        _ep("E26", "10万组合里的一粒（上）", "速记阵"),
        _ep("E27", "10万组合里的一粒（下）", "扫描速记"),
        _ep("E28", "静水深流", "专注力考验"),
        _ep("E29", "最后交卷的人（上）", "疾行梯"),
        _ep("E30", "最后交卷的人（下）", "极速学习"),
    )
}

ACTS: tuple[Act, ...] = (
    Act("第一幕", "挑战书 · AI危机降临", "E01-E04", "/static/dayu/assets/hall/think1.png",
        "黑信封送到敬天府，五个孩子第一次知道自己的大脑里有一扇门。",
        "含 4 集 · 世界观 / 导师登场 / 组队", ("E01", "E02", "E03", "E04")),
    Act("第二幕", "天赋分组仪式", "E05-E07", "/static/dayu/assets/hall/virtue1.png",
        "五把锁现世，天赋测试分班。",
        "含 3 集 · 天赋认知 / 双女主", ("E05", "E06", "E07")),
    Act("第三幕", "唤醒基本功", "E08-E14", "/static/dayu/assets/hall/study2.png",
        "闹市静坐、石头开花、书道三部曲。",
        "含 7 集 · 专注 / 观察 / 记忆 / 书道", ("E08", "E09", "E10", "E11", "E12", "E13", "E14")),
    Act("第四幕", "第一扇门", "E15-E22", "/static/dayu/assets/hall/win1.png",
        "找到入口，蒙眼闯五角迷宫。",
        "含 8 集 · 观察推理 / 家庭线", ("E15", "E16", "E17", "E18", "E19", "E20", "E21", "E22")),
    Act("第五幕", "五关连闯", "E23-E30", "/static/dayu/assets/hall/act1.png",
        "九大秘籍逐一点亮。",
        "含 8 集 · 阅读 / 记忆 / 速记", ("E23", "E24", "E25", "E26", "E27", "E28", "E29", "E30")),
    Act("第六幕", "末日推演 · 机器人危机", "未解锁", "/static/dayu/assets/miji/sys-ai.jpg",
        "走出地下训练场，真正的对手才刚开机。",
        "看完第五幕自动解锁", (), True),
)

CURRENT_EPISODE_ID = "E13"

# 频道标题可切换的测试集。每集讨论与感知独立。
SWITCHABLE_IDS: tuple[str, ...] = ("E13", "E14", "EH01")

# 大书道章节对应剧集，进度跟观看解锁走，不再写死 38%。
CALLIGRAPHY = (
    ("第 1 讲 · 眼中有太极（书道Ⅰ）", "E11"),
    ("第 2 讲 · 心中有太极（篆书）", "E12"),
    ("第 3 讲 · 五兽桩 · 站桩定力", "E13"),
    ("第 4 讲 · 蒙上眼睛之后", "E14"),
)

MIJI = (
    ("六感神剑", "mj-tfsd", "多元感知 · 六感全开", "E14"),
    ("左右同搏", "mj-yxdy", "左右脑协同", "E08"),
    ("无相神功", "mj-yxzj", "想象力", "E10"),
    ("吸照大法", "mj-cnyd", "超脑阅读", "E24"),
    ("心门九剑", "mj-scyj", "直觉决策", "E16"),
    ("昙花宝典", "mj-gxzy", "影像追忆", "E25"),
    ("太极神功", "mj-jsys", "思维太极", "E12"),
    ("呼吸打坐", "mj-jlhf", "专注力", "E08"),
    ("九阳绝学", "mj-bddt", "极速学习", "E30"),
)

OFFERS = (
    {"title": "爱上学习训练营", "cover": "/static/dayu/assets/adv/love-together.png",
     "blurb": "21 天从要我学到我要学。", "note": "报名通道尚未开通"},
    {"title": "白名单赛事直通车", "cover": "/static/dayu/assets/miji/sys-contest.jpg",
     "blurb": "选题、集训、参赛一站式带赛。", "note": "报名通道尚未开通"},
    {"title": "AI 短剧创作营", "cover": "/static/dayu/assets/miji/sys-drama.jpg",
     "blurb": "用 AI 工具完成一部竖屏短剧。", "note": "报名通道尚未开通"},
)


def get_episode(episode_id: str | None) -> Episode | None:
    if not episode_id:
        return None
    return EPISODES.get(episode_id.strip().upper())
