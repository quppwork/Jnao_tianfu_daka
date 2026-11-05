"""拍题模糊 / 多题澄清门。"""

from app.agents.qa.clarify_ocr import assess_ocr_gate


def test_multi_question_asks_which():
    ocr = (
        "第1题 计算 1+1=？\n"
        "第2题 若 z/(z-1)=1+i，求 z。\n"
        "第3题 解方程 x^2=4。"
    )
    gate = assess_ocr_gate(ocr, user_message="")
    assert gate is not None
    assert gate.status == "multi"
    assert gate.question_count >= 2
    assert "第几题" in gate.reply or "哪一题" in gate.reply


def test_blurry_asks_reshoot():
    ocr = "第2题 若 ??/(??-1)=1+i 求 ?? 看不清 □□□"
    gate = assess_ocr_gate(ocr, user_message="")
    assert gate is not None
    assert gate.status == "blurry"
    assert "模糊" in gate.reply or "再拍" in gate.reply


def test_user_picked_question_skips_gate():
    ocr = "第1题 …\n第2题 …\n第3题 …"
    assert assess_ocr_gate(ocr, user_message="讲第2题") is None


def test_clear_single_passes():
    ocr = "已知直角三角形两直角边为 3 和 4，求斜边长。"
    assert assess_ocr_gate(ocr, user_message="") is None


def test_empty_ocr_asks_reshoot():
    gate = assess_ocr_gate("", user_message="")
    assert gate is not None
    assert gate.status == "blurry"
    assert "再拍" in gate.reply or "打字" in gate.reply
