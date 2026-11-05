"""拍题门面编排：压缩 → OCR → 领域路由 → 题库优先 → RAG/LLM →（理科）符号校验。

流式协议由 API 层消费；此处只 yield (kind, payload)。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.agents.solve.compress import compress_image_bytes
from app.agents.solve.domain import classify_domain, profile_for_domain


async def run_solve_photo_stream(
    image_bytes: bytes,
    *,
    user_id: int | None = None,
    subject_hint: str | None = None,
    filename: str = "photo.jpg",
) -> AsyncIterator[tuple[str, Any]]:
    del filename  # 预留
    from app.harness.context import ToolContext
    from app.harness.runtime import call_tool
    from app.runtime import run_turn_stream as run_profile_turn_stream
    from app.services.doubao_client import is_configured

    yield ("status", "正在压缩图片…")
    try:
        _jpeg, data_url = compress_image_bytes(image_bytes, max_side=1600, quality=85)
    except Exception as e:
        yield ("error", f"图片处理失败：{e}")
        return

    yield ("status", "正在识别题目文字…")
    ocr = await call_tool(
        "ocr_extract",
        {"image_data_url": data_url, "subject_hint": subject_hint or ""},
        profile="solve_science",
    )
    if not ocr.ok:
        yield ("error", ocr.error or "OCR 失败")
        return
    ocr_text = str((ocr.data or {}).get("text") or "").strip()
    ocr_mock = bool((ocr.data or {}).get("mock"))
    if not ocr_text:
        yield ("error", "未能识别到题目文字")
        return

    domain = classify_domain(ocr_text, subject_hint=subject_hint)
    profile = profile_for_domain(domain)
    yield ("status", f"已识别为「{domain}」→ {profile}")
    yield (
        "meta",
        {
            "type": "route",
            "domain": domain,
            "profile": profile,
            "ocr_preview": ocr_text[:400],
            "ocr_provider": (ocr.data or {}).get("provider"),
            "ocr_mock": ocr_mock,
        },
    )

    # PRD §4.3：个性化学科引导 / 同类练习前校验学业规划（OCR 结果仍回传可保存）
    plan_gate: dict[str, Any] | None = None
    if user_id:
        try:
            from app.db.session import get_session_factory
            from app.services.academic_plan_service import check_academic_plan_ready

            s = get_session_factory()()
            try:
                plan_gate = check_academic_plan_ready(s, int(user_id))
            finally:
                s.close()
        except Exception:
            plan_gate = None
        if plan_gate and not plan_gate.get("ok"):
            hint = str(plan_gate.get("student_hint") or "请先完善学业规划。")
            yield ("status", "需要先完善学业规划")
            yield ("token", hint)
            yield (
                "done",
                {
                    "ok": False,
                    "profile": profile,
                    "domain": domain,
                    "answer": hint,
                    "steps": [],
                    "knowledge_points": [],
                    "source": "need_academic_plan",
                    "ocr_text": ocr_text,
                    "plan_gate": plan_gate,
                    "mock": False,
                },
            )
            return

    yield ("status", "正在检索题库…")
    bank = await call_tool(
        "search_question_bank",
        {"query": ocr_text, "subject": subject_hint or domain},
        profile=profile,
    )
    bank_data = bank.data or {}
    if bank.ok and bank_data.get("hit"):
        # PRD：默认不直接抛完整标准答案；先给线索引导
        steps = list(bank_data.get("steps") or [])
        kps = list(bank_data.get("knowledge_points") or [])
        guide = (
            "题库里有相似题，我们先自己想，不先看完整答案。\n"
            f"题干确认：{ocr_text[:280]}\n\n"
            "请先告诉我：题目给出了哪些条件？要求求什么？"
        )
        if kps:
            guide += "\n（相关知识点：" + "、".join(str(x) for x in kps[:5]) + "）"
        if steps:
            guide += "\n需要提示时再说「提示」，我再按步骤给线索。"
        yield ("token", guide)
        yield (
            "done",
            {
                "profile": profile,
                "domain": domain,
                "answer": guide,
                "steps": steps,
                "knowledge_points": kps,
                "source": "question_bank_guided",
                "bank_provider": bank_data.get("provider"),
                "ocr_text": ocr_text,
                "bank_answer_withheld": True,
                "mock": bool(bank_data.get("mock")),
                "plan_gate": plan_gate,
            },
        )
        return

    if not is_configured() and ocr_mock:
        demo = (
            f"【模拟引导 · {profile}】\n"
            f"题干：{ocr_text}\n\n"
            "先指出已知条件和要求什么；需要时再要提示。"
            "配置 DEEPSEEK_API_KEY 后走真实引导生成。"
        )
        yield ("token", demo)
        yield (
            "done",
            {
                "profile": profile,
                "domain": domain,
                "answer": demo,
                "steps": [],
                "knowledge_points": [],
                "source": "mock_demo",
                "ocr_text": ocr_text,
                "mock": True,
                "plan_gate": plan_gate,
            },
        )
        return

    yield ("status", "正在结合知识库做线索引导…")
    system_extra = (
        f"【OCR 题干】\n{ocr_text}\n\n"
        "按学科引导流程：先确认题干 → 分步提问线索 → 让孩子作答；"
        "默认不要一次给出完整原题标准答案；公式用 LaTeX。"
        "可 retrieve_kb；提示逐级增加。"
    )
    if profile == "solve_science":
        system_extra += "关键数值推导可调用 symbolic_verify 校验。"

    ctx = ToolContext(
        db=None,
        child_user_id=int(user_id or 0),
        profile=profile,
    )
    science = profile == "solve_science"
    answer = ""
    done_payload: dict[str, Any] | None = None
    verify_info: dict[str, Any] | None = None

    if science:
        # 理科：缓冲全文 → 符号校验（失败则重推一次）→ 通过后再吐 token
        answer, done_payload, err = await _collect_turn(
            profile, ocr_text, ctx=ctx, system_extra=system_extra, history=[], max_steps=5
        )
        if err:
            yield ("error", err)
            return
        verify_info = await _maybe_verify_science(answer)
        if verify_info and verify_info.get("verified") is False and not verify_info.get("skipped"):
            yield ("status", "符号校验未通过，正在重新推理…")
            feedback = (
                f"【符号校验失败】expression={verify_info.get('expression')!s} "
                f"claimed={verify_info.get('claimed_result')!s} "
                f"actual={verify_info.get('actual_result')!s}。"
                "请纠正推导后重新给出完整解答，勿重复错误结果。"
            )
            answer2, done2, err2 = await _collect_turn(
                profile,
                ocr_text,
                ctx=ctx,
                system_extra=system_extra + "\n" + feedback,
                history=[
                    {"role": "assistant", "content": answer},
                    {"role": "user", "content": feedback},
                ],
                max_steps=4,
            )
            if err2 or not answer2:
                yield ("error", "理科符号校验未通过，已拒绝输出。请核对题干后重试。")
                return
            answer, done_payload = answer2, done2 or done_payload
            verify_info = await _maybe_verify_science(answer)
            if verify_info and verify_info.get("verified") is False and not verify_info.get("skipped"):
                yield ("error", "理科符号校验仍未通过，已拒绝输出。请核对题干后重试。")
                return
        if answer:
            yield ("token", answer)
    else:
        parts: list[str] = []
        async for kind, payload in run_profile_turn_stream(
            profile,
            ocr_text,
            history=[],
            ctx=ctx,
            system_extra=system_extra,
            max_steps=5,
            allow_tools=True,
        ):
            if kind == "token":
                parts.append(str(payload or ""))
                yield ("token", payload)
            elif kind == "error":
                yield ("error", payload)
                return
            elif kind == "done" and isinstance(payload, dict):
                done_payload = payload
        answer = ((done_payload or {}).get("reply") or "".join(parts) or "").strip()

    yield (
        "done",
        {
            "profile": profile,
            "domain": domain,
            "answer": answer,
            "steps": [],
            "knowledge_points": [],
            "source": "llm_rag",
            "ocr_text": ocr_text,
            "tools_used": list((done_payload or {}).get("tools_used") or []),
            "rag_used": bool((done_payload or {}).get("rag_used")),
            "symbolic_verify": verify_info,
            "mock": False,
            "user_id": user_id,
        },
    )


async def _collect_turn(
    profile: str,
    user_message: str,
    *,
    ctx: Any,
    system_extra: str,
    history: list[dict[str, Any]],
    max_steps: int,
) -> tuple[str, dict[str, Any] | None, str | None]:
    from app.runtime import run_turn_stream as run_profile_turn_stream

    parts: list[str] = []
    done_payload: dict[str, Any] | None = None
    async for kind, payload in run_profile_turn_stream(
        profile,
        user_message,
        history=history,
        ctx=ctx,
        system_extra=system_extra,
        max_steps=max_steps,
        allow_tools=True,
    ):
        if kind == "token":
            parts.append(str(payload or ""))
        elif kind == "error":
            return "", None, str(payload)
        elif kind == "done" and isinstance(payload, dict):
            done_payload = payload
    answer = ((done_payload or {}).get("reply") or "".join(parts) or "").strip()
    return answer, done_payload, None


async def run_solve_photo(
    image_bytes: bytes,
    *,
    user_id: int | None = None,
    subject_hint: str | None = None,
    filename: str = "photo.jpg",
) -> dict[str, Any]:
    """非流式聚合。"""
    tokens: list[str] = []
    done: dict[str, Any] = {}
    async for kind, payload in run_solve_photo_stream(
        image_bytes,
        user_id=user_id,
        subject_hint=subject_hint,
        filename=filename,
    ):
        if kind == "token":
            tokens.append(str(payload or ""))
        elif kind == "done" and isinstance(payload, dict):
            done = payload
        elif kind == "error":
            return {"ok": False, "error": str(payload)}
    if not done:
        done = {"answer": "".join(tokens), "source": "unknown"}
    done.setdefault("ok", True)
    return done


async def _maybe_verify_science(answer: str) -> dict[str, Any] | None:
    import re

    from app.harness.runtime import call_tool

    m = re.search(r"([0-9a-zA-Z\+\-\*/\(\)\s]{1,40})\s*=\s*([0-9a-zA-Z\.\-/]+)", answer)
    if not m:
        return None
    expr, claimed = m.group(1).strip(), m.group(2).strip()
    result = await call_tool(
        "symbolic_verify",
        {"expression": expr, "claimed_result": claimed},
        profile="solve_science",
    )
    data = dict(result.data or {})
    data.setdefault("expression", expr)
    data.setdefault("claimed_result", claimed)
    return {"ok": result.ok, **data, "error": result.error}
