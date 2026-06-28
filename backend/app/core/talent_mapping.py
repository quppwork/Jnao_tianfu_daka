"""天赋名称 ↔ 课程编码映射"""

TALENT_NAME_TO_CODE: dict[str, int] = {
    "学者": 1,
    "思者": 2,
    "行者": 3,
    "德者": 4,
    "赢者": 5,
    # 迷者 不再隐射为思者 — 迷者表示测评结果不明确，应提示重新测试
}

TALENT_CODE_TO_TAG: dict[int, str] = {1: "学", 2: "思", 3: "行", 4: "德", 5: "赢"}
TALENT_CODE_TO_COURSE: dict[int, int] = {1: 28, 2: 25, 3: 24, 4: 27, 5: 26}

EXPECTED_COUNTS_BY_TAG = {"学": 9, "思": 8, "行": 8, "德": 8, "赢": 8}


def resolve_talent_code(talent_name: str | None) -> int | None:
    if not talent_name:
        return None
    name = talent_name.strip()
    if name in TALENT_NAME_TO_CODE:
        return TALENT_NAME_TO_CODE[name]
    if name.endswith("者") and name not in TALENT_NAME_TO_CODE:
        for key, code in TALENT_NAME_TO_CODE.items():
            if key.startswith(name[0]):
                return code
    return None


def resolve_talent_tag(talent_code: int | None) -> str | None:
    if talent_code is None:
        return None
    return TALENT_CODE_TO_TAG.get(talent_code)
