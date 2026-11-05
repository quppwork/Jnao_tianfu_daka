"""QA Agent 编排（P2/Q8）— chat / stream；禁止 import Guide runner。"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.agents.qa.clarify import clarification_reply, needs_stem_clarification
from app.agents.qa.clarify_guide import wont_guide_reply
from app.agents.qa.clarify_ocr import assess_ocr_gate
from app.agents.qa.memory import QaMemory, load_session_passage, save_session_passage
from app.agents.qa.prompt_builder import (
    build_learner_context_block,
    build_qa_system_prompt,
    build_qa_user_message,
)
from app.agents.qa.router import check_subject_mismatch, mismatch_reply
from app.agents.qa.strategy import resolve_qa_strategy, strategy_to_prompt_block
from app.agents.qa.trace import TurnTimer
from app.agents.shared.stage import infer_school_stage
from app.db.models import ChildUser, QaMessage, QaSession, TalentAssessment
from app.harness.safety import sanitize_public_reply
from app.services.assessment_service import resolve_effective_talent
from app.services.ai_output_guard import (
    is_prompt_injection_attempt,
    refusal_message,
)
from app.services.qa_coach import build_coach_metadata, fetch_recent_coach_context_for_prompt
from app.services.qa_image_store import image_data_url
from app.services.qa_kb_router import QaKbPath, resolve_qa_kb_path
from app.services.text_sanitize import sanitize_subject, sanitize_text, session_title_from_message

_OCR_PROMPT = (
    "请完整识别图中题目与阅读材料的全部文字与公式；"
    "保持题号、小问(1)(2)(3)与段落换行；原文若有段落序号请原样保留，没有则不要编造 Paragraph/行号；"
    "数学公式用 LaTeX；不要解题、不要省略小问或段落。"
)

_LOCATION_CORRECTION_RE = re.compile(
    r"(段落|行数|行号|定位|原文).{0,16}(不对|错|有问题|不对应|不准|有点)|"
    r"(不对|错了|有问题|不准).{0,16}(段落|行数|行号|定位|原文)|"
    r"找错了|位置不对|原文不是|不是这一段|不是这行",
    re.I,
)

_CORRECTION_INSTRUCTION = (
    "【系统纠错指令】用户指出先前段落/行号/定位有误。"
    "请严格依据本会话题目原文（OCR）重新逐段核对并更正讲解与答案；"
    "可调用工具 qa_reload_passage（需要时可 reocr=true 重新识图）；"
    "原文已在上下文时不要让用户重拍，禁止用「以你书上为准」推脱；"
    "原文没有印刷行号时改用「第 N 段（按换行）」或直接引用句子。"
)


def looks_like_location_correction(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    return bool(_LOCATION_CORRECTION_RE.search(text))


async def _ocr_preview(image_data_url: str) -> str | None:
    """经 Harness MCP · ocr_extract（Qwen3.5-OCR）识别题干。"""
    from app.harness.runtime import call_tool

    result = await call_tool(
        "ocr_extract",
        {
            "image_data_url": image_data_url,
            "max_tokens": 3500,
            "prompt": _OCR_PROMPT,
        },
        profile="qa",
    )
    if not result.ok:
        return None
    text = str((result.data or {}).get("text") or "").strip()
    return text or None


async def _resolve_passage_for_turn(
    session: QaSession,
    *,
    child_user_id: int,
    image_id: str | None,
    message: str,
) -> tuple[str | None, str | None, str | None]:
    """返回 (ocr_text, image_url_for_bubble, resolved_image_id)。

    - 本轮有新图：OCR 并写入会话
    - 多轮纯文字：回灌会话里上次 OCR；若用户纠错定位则尽量重新识图
    """
    correction = looks_like_location_correction(message)
    if image_id:
        data_url = image_data_url(image_id, child_user_id)
        if not data_url:
            raise ValueError("图片不存在或已过期")
        ocr = await _ocr_preview(data_url)
        save_session_passage(session, image_id=image_id, ocr_text=ocr)
        url = f"/api/qa/images/{image_id}?user_id={child_user_id}"
        return ocr, url, image_id

    last_image_id, last_ocr = load_session_passage(session)
    if correction and last_image_id:
        data_url = image_data_url(last_image_id, child_user_id)
        if data_url:
            ocr = await _ocr_preview(data_url)
            if ocr:
                save_session_passage(session, image_id=last_image_id, ocr_text=ocr)
                return ocr, None, last_image_id
    return last_ocr, None, last_image_id


async def _fetch_qa_rag_bundle(
    message: str,
    *,
    child_user_id: int,
    subject: str | None,
    has_image: bool,
    use_rag: bool | None,
) -> dict[str, Any]:
    """按路径取知识库上下文：METHOD(百炼多轮) / LEGACY(旧 RAG) / 空。闸门仍在 QA。"""
    from app.harness.runtime import call_tool

    empty = {
        "rag_used": False,
        "rag_sources": [],
        "rag_context": None,
        "rag_kind": None,
        "rag_source": None,
    }
    path = resolve_qa_kb_path(
        message,
        subject=subject,
        has_image=has_image,
        use_rag=use_rag,
    )
    if path is QaKbPath.NONE:
        return empty

    if path is QaKbPath.METHOD:
        hit = await call_tool(
            "retrieve_qa_kb",
            {"query": message, "subject": subject or ""},
            profile="qa",
        )
        data = hit.data if hit.ok else {}
        if data.get("rag_used") and data.get("rag_context"):
            return {
                "rag_used": True,
                "rag_sources": list(data.get("rag_sources") or []),
                "rag_context": data["rag_context"],
                "rag_kind": "method",
                "rag_source": data.get("rag_source") or "bailian_method",
            }
        return empty

    if path is QaKbPath.LEGACY_TEACHING:
        rag = await call_tool(
            "retrieve_qa_legacy",
            {
                "query": message,
                "user_id": f"child_{child_user_id}",
                "subject": subject or "",
            },
            profile="qa",
        )
        data = rag.data if rag.ok else {}
        if data.get("rag_used") and data.get("rag_context"):
            return {
                "rag_used": True,
                "rag_sources": list(data.get("rag_sources") or []),
                "rag_context": data["rag_context"],
                "rag_kind": "legacy",
                "rag_source": data.get("rag_source") or "tianfu_rag",
            }
    return empty


def _confirmed_talent_bundle(db: Session, child_user_id: int) -> tuple[str | None, dict | None]:
    """只用用户已确认天赋；报告取确认对应的 assessment_id，不用最新测评。"""
    eff = resolve_effective_talent(db, child_user_id) or {}
    talent = eff.get("talent_primary")
    report_json = None
    aid = eff.get("assessment_id")
    if aid:
        row = db.get(TalentAssessment, int(aid))
        if row:
            report_json = row.report_json
    return talent, report_json


def _patch_session_meta(session: QaSession, patch: dict[str, Any]) -> None:
    meta = dict(session.meta_json or {})
    meta.update(patch)
    session.meta_json = meta
    flag_modified(session, "meta_json")


async def _run_product_gate(
    message: str,
    *,
    reply: str,
    code: str,
    extra: dict[str, Any] | None = None,
) -> str:
    """产品闸门经 GateLook 短接（不调模型）；返回闸门 reply。"""
    from app.runtime import run_turn as run_profile_turn

    gate = {"reply": reply, "code": code}
    if extra:
        gate.update(extra)
    turn = await run_profile_turn(
        "qa",
        message or "",
        max_steps=1,
        allow_tools=False,
        metadata={"product_gate": gate},
    )
    return (turn.get("reply") or reply).strip() or reply


async def _stream_product_gate(
    message: str,
    *,
    reply: str,
    code: str,
    extra: dict[str, Any] | None = None,
) -> AsyncIterator[tuple[str, Any]]:
    """流式产品闸门：经 iter_agent GateHook 吐 token，再由调用方补 done 业务字段。"""
    from app.runtime import run_turn_stream as run_profile_turn_stream

    gate = {"reply": reply, "code": code}
    if extra:
        gate.update(extra)
    async for kind, payload in run_profile_turn_stream(
        "qa",
        message or "",
        max_steps=1,
        allow_tools=False,
        metadata={"product_gate": gate},
    ):
        if kind == "token":
            yield ("token", payload)
        elif kind == "error":
            yield ("error", payload)
            return


async def run_chat(
    db: Session,
    child_user_id: int,
    message: str,
    *,
    session_id: int | None = None,
    subject: str | None = None,
    image_id: str | None = None,
    use_rag: bool | None = None,
) -> dict:
    from app.services import qa_service as svc

    timer = TurnTimer()
    message = sanitize_text(message)
    if not message and not image_id:
        raise ValueError("消息不能为空")
    subject = sanitize_subject(subject)

    if is_prompt_injection_attempt(message):
        if session_id:
            session = db.get(QaSession, session_id)
            if not session or session.child_user_id != child_user_id:
                raise ValueError("会话不存在")
        else:
            session = svc.create_session(db, child_user_id, subject)
        user = db.get(ChildUser, child_user_id)
        profile = svc.learner_profile(user)
        talent, _ = _confirmed_talent_bundle(db, child_user_id)
        school_stage = infer_school_stage(
            grade=profile.get("grade"),
            age=profile.get("age"),
            school_stage=profile.get("school_stage"),
        )
        QaMemory.append_message(db, session_id=session.id, role="user", content=message)
        reply = refusal_message()
        QaMemory.append_message(db, session_id=session.id, role="assistant", content=reply)
        db.commit()
        svc.invalidate_qa_caches(child_user_id)
        return svc.public_chat_payload(
            session_id=session.id,
            reply=reply,
            talent=talent,
            school_stage=school_stage,
        )

    user = db.get(ChildUser, child_user_id)
    profile = svc.learner_profile(user)
    talent, report_json = _confirmed_talent_bundle(db, child_user_id)

    school_stage = infer_school_stage(
        grade=profile.get("grade"),
        age=profile.get("age"),
        school_stage=profile.get("school_stage"),
    )

    if session_id:
        session = db.get(QaSession, session_id)
        if not session or session.child_user_id != child_user_id:
            raise ValueError("会话不存在")
    else:
        session = svc.create_session(db, child_user_id, subject)

    active_subject = subject or session.subject
    has_image = bool(image_id)
    mismatch = None if image_id else check_subject_mismatch(message, active_subject)
    if mismatch:
        QaMemory.append_message(db, session_id=session.id, role="user", content=message)
        if session.title == "新对话":
            session.title = session_title_from_message(message)
        reply = await _run_product_gate(
            message,
            reply=mismatch_reply(mismatch),
            code="subject_mismatch",
            extra={
                "suggested_subject": mismatch.detected,
                "selected_subject": mismatch.selected,
            },
        )
        QaMemory.append_message(
            db,
            session_id=session.id,
            role="assistant",
            content=reply,
            meta_json={
                "subject_mismatch": True,
                "suggested_subject": mismatch.detected,
                "selected_subject": mismatch.selected,
            },
        )
        db.commit()
        svc.invalidate_qa_caches(child_user_id)
        svc.emit_turn(
            timer=timer,
            child_user_id=child_user_id,
            session_id=session.id,
            subject=active_subject,
            message=message,
            reply=reply,
            school_stage=school_stage,
            subject_mismatch=True,
            suggested_subject=mismatch.detected,
        )
        return {
            "session_id": session.id,
            "reply": reply,
            "talent_primary": talent,
            "school_stage": school_stage,
            "subject_mismatch": True,
            "suggested_subject": mismatch.detected,
            "selected_subject": mismatch.selected,
        }

    wont = wont_guide_reply(
        message,
        subject=active_subject,
        session_meta=session.meta_json if isinstance(session.meta_json, dict) else None,
        has_image=has_image,
    )
    if wont:
        reply_raw, meta_patch = wont
        reply = await _run_product_gate(
            message,
            reply=reply_raw,
            code="wont_guide",
            extra={"wont_guide": True},
        )
        QaMemory.append_message(db, session_id=session.id, role="user", content=message)
        if session.title == "新对话":
            session.title = session_title_from_message(message)
        _patch_session_meta(session, {k: v for k, v in meta_patch.items() if k == "wont_guide_stage"})
        QaMemory.append_message(
            db,
            session_id=session.id,
            role="assistant",
            content=reply,
            meta_json=meta_patch,
        )
        db.commit()
        svc.invalidate_qa_caches(child_user_id)
        svc.emit_turn(
            timer=timer,
            child_user_id=child_user_id,
            session_id=session.id,
            subject=active_subject,
            message=message,
            reply=reply,
            school_stage=school_stage,
            clarified=True,
        )
        return svc.public_chat_payload(
            session_id=session.id,
            reply=reply,
            talent=talent,
            school_stage=school_stage,
            clarified=True,
            wont_guide=True,
        )

    prior_turns = sum(1 for m in session.messages if m.role in ("user", "assistant"))
    if needs_stem_clarification(
        message, has_image=has_image, has_prior_turns=prior_turns > 0
    ):
        QaMemory.append_message(db, session_id=session.id, role="user", content=message)
        if session.title == "新对话":
            session.title = session_title_from_message(message)
        reply = clarification_reply(subject=active_subject)
        QaMemory.append_message(
            db,
            session_id=session.id,
            role="assistant",
            content=reply,
            meta_json={"clarified": True},
        )
        db.commit()
        svc.invalidate_qa_caches(child_user_id)
        svc.emit_turn(
            timer=timer,
            child_user_id=child_user_id,
            session_id=session.id,
            subject=active_subject,
            message=message,
            reply=reply,
            school_stage=school_stage,
            clarified=True,
        )
        return svc.public_chat_payload(
            session_id=session.id,
            reply=reply,
            talent=talent,
            school_stage=school_stage,
            clarified=True,
        )

    history, memory_digest = QaMemory.prepare_history_and_digest(db, session)

    coach_meta = build_coach_metadata(
        talent_primary=talent,
        report_json=report_json,
        school_stage=school_stage,
        message=message,
    )
    topics = QaMemory.recent_topics(db, child_user_id)
    if topics:
        coach_meta["recent_topics"] = topics[:3]

    ocr_preview, image_url, resolved_image_id = await _resolve_passage_for_turn(
        session,
        child_user_id=child_user_id,
        image_id=image_id,
        message=message,
    )

    # 拍题模糊 / 多题：先澄清（状态：awaiting_question_pick），不直接开讲
    ocr_gate = assess_ocr_gate(ocr_preview, user_message=message) if has_image else None
    if ocr_gate is not None:
        user_row = QaMessage(
            session_id=session.id,
            role="user",
            content=message,
            image_url=image_url,
            meta_json={"image_id": image_id} if image_id else None,
        )
        db.add(user_row)
        if session.title == "新对话":
            session.title = session_title_from_message(message)
        reply = ocr_gate.reply
        db.add(
            QaMessage(
                session_id=session.id,
                role="assistant",
                content=reply,
                meta_json={
                    "clarified": True,
                    "ocr_gate": ocr_gate.status,
                    "question_count": ocr_gate.question_count,
                    "awaiting_question_pick": True,
                },
            )
        )
        db.commit()
        svc.invalidate_qa_caches(child_user_id)
        svc.emit_turn(
            timer=timer,
            child_user_id=child_user_id,
            session_id=session.id,
            subject=active_subject,
            message=message,
            reply=reply,
            school_stage=school_stage,
            clarified=True,
        )
        return svc.public_chat_payload(
            session_id=session.id,
            reply=reply,
            talent=talent,
            school_stage=school_stage,
            clarified=True,
        )

    rag_bundle = await _fetch_qa_rag_bundle(
        message,
        child_user_id=child_user_id,
        subject=subject or session.subject,
        has_image=has_image,
        use_rag=use_rag,
    )
    rag_used = bool(rag_bundle["rag_used"])
    rag_sources = list(rag_bundle["rag_sources"] or [])
    rag_context = rag_bundle["rag_context"]
    rag_kind = rag_bundle["rag_kind"]
    rag_source = rag_bundle["rag_source"]

    coach_context = fetch_recent_coach_context_for_prompt(
        db, child_user_id, session_id=session.id
    )
    strategy_block = strategy_to_prompt_block(
        resolve_qa_strategy(
            talent_primary=talent,
            school_stage=school_stage,
            has_image=has_image,
        )
    )

    system = build_qa_system_prompt(
        school_stage=school_stage,
        subject=subject or session.subject,
        rag_context=rag_context,
        memory_digest=memory_digest or None,
        strategy_block=strategy_block or None,
        rag_kind=rag_kind,
    )
    learner_context = build_learner_context_block(
        grade=profile.get("grade"),
        age=profile.get("age"),
        talent_primary=talent,
        report_json=report_json,
        coach_context=coach_context,
        ocr_preview=ocr_preview,
    )
    # 纯拍照：气泡可空；给模型一条非空指令（不写进用户气泡）
    model_text = message or (
        "请根据题目图片与识别预览讲解；勿编造未识别出的题干。" if has_image else ""
    )
    if looks_like_location_correction(message):
        model_text = f"{model_text}\n\n{_CORRECTION_INSTRUCTION}".strip()
    user_message = build_qa_user_message(model_text, learner_context)

    user_row = QaMessage(
        session_id=session.id,
        role="user",
        content=message,
        image_url=image_url,
        meta_json={"image_id": image_id} if image_id else None,
    )
    db.add(user_row)
    if session.title == "新对话":
        session.title = session_title_from_message(message)
    db.commit()

    # 拍图：先经 harness MCP ocr_extract（见 _ocr_preview），出话统一走 run_profile_turn
    from app.harness.context import ToolContext
    from app.runtime import run_turn as run_profile_turn

    turn = await run_profile_turn(
        "qa",
        user_message,
        history=history,
        ctx=ToolContext(
            db=db,
            child_user_id=child_user_id,
            profile="qa",
            extra={
                "qa_session_id": session.id,
                "last_image_id": resolved_image_id or "",
                "last_ocr_text": ocr_preview or "",
            },
        ),
        system_override=system,
        max_steps=6 if looks_like_location_correction(message) else 4,
        allow_tools=True,
    )
    reply = turn.get("reply")

    if not reply:
        reply = "抱歉，AI 暂时无法响应，请稍后再试。"
    reply = sanitize_public_reply(reply, profile="qa")

    assistant_meta = svc.assistant_meta_for_storage(
        coach_meta,
        rag_used=rag_used,
        rag_sources=rag_sources,
        rag_source=rag_source,
    )
    db.add(
        QaMessage(
            session_id=session.id,
            role="assistant",
            content=reply,
            meta_json=assistant_meta,
        )
    )
    db.commit()
    svc.invalidate_qa_caches(child_user_id)

    svc.emit_turn(
        timer=timer,
        child_user_id=child_user_id,
        session_id=session.id,
        subject=subject or session.subject,
        message=message,
        reply=reply,
        school_stage=school_stage,
        has_image=has_image,
        ocr_used=bool(ocr_preview),
        rag_used=rag_used,
    )
    return svc.public_chat_payload(
        session_id=session.id,
        reply=reply,
        talent=talent,
        school_stage=school_stage,
    )


async def run_chat_stream(
    db: Session,
    child_user_id: int,
    message: str,
    *,
    session_id: int | None = None,
    subject: str | None = None,
    image_id: str | None = None,
    use_rag: bool | None = None,
) -> AsyncIterator[tuple[str, Any]]:
    from app.services import qa_service as svc

    timer = TurnTimer()
    message = sanitize_text(message)
    if not message and not image_id:
        yield ("error", "消息不能为空")
        return

    subject = sanitize_subject(subject)

    if is_prompt_injection_attempt(message):
        if session_id:
            session = db.get(QaSession, session_id)
            if not session or session.child_user_id != child_user_id:
                yield ("error", "会话不存在")
                return
        else:
            session = svc.create_session(db, child_user_id, subject)
        user = db.get(ChildUser, child_user_id)
        profile = svc.learner_profile(user)
        talent, _ = _confirmed_talent_bundle(db, child_user_id)
        school_stage = infer_school_stage(
            grade=profile.get("grade"),
            age=profile.get("age"),
            school_stage=profile.get("school_stage"),
        )
        QaMemory.append_message(db, session_id=session.id, role="user", content=message)
        reply = refusal_message()
        QaMemory.append_message(db, session_id=session.id, role="assistant", content=reply)
        db.commit()
        svc.invalidate_qa_caches(child_user_id)
        yield ("token", reply)
        yield (
            "done",
            svc.public_chat_payload(
                session_id=session.id,
                reply=reply,
                talent=talent,
                school_stage=school_stage,
            ),
        )
        return

    user = db.get(ChildUser, child_user_id)
    profile = svc.learner_profile(user)
    talent, report_json = _confirmed_talent_bundle(db, child_user_id)

    school_stage = infer_school_stage(
        grade=profile.get("grade"),
        age=profile.get("age"),
        school_stage=profile.get("school_stage"),
    )

    if session_id:
        session = db.get(QaSession, session_id)
        if not session or session.child_user_id != child_user_id:
            yield ("error", "会话不存在")
            return
    else:
        session = svc.create_session(db, child_user_id, subject)

    active_subject = subject or session.subject
    has_image = bool(image_id)
    mismatch = None if image_id else check_subject_mismatch(message, active_subject)
    if mismatch:
        QaMemory.append_message(db, session_id=session.id, role="user", content=message)
        if session.title == "新对话":
            session.title = session_title_from_message(message)
        reply = mismatch_reply(mismatch)
        parts: list[str] = []
        async for kind, payload in _stream_product_gate(
            message,
            reply=reply,
            code="subject_mismatch",
            extra={
                "suggested_subject": mismatch.detected,
                "selected_subject": mismatch.selected,
            },
        ):
            if kind == "token":
                parts.append(str(payload))
                yield ("token", payload)
            elif kind == "error":
                yield ("error", payload)
                return
        reply = ("".join(parts) or reply).strip() or reply
        QaMemory.append_message(
            db,
            session_id=session.id,
            role="assistant",
            content=reply,
            meta_json={
                "subject_mismatch": True,
                "suggested_subject": mismatch.detected,
                "selected_subject": mismatch.selected,
            },
        )
        db.commit()
        svc.invalidate_qa_caches(child_user_id)
        svc.emit_turn(
            timer=timer,
            child_user_id=child_user_id,
            session_id=session.id,
            subject=active_subject,
            message=message,
            reply=reply,
            school_stage=school_stage,
            subject_mismatch=True,
            suggested_subject=mismatch.detected,
            stream=True,
        )
        yield (
            "done",
            {
                "session_id": session.id,
                "reply": reply,
                "talent_primary": talent,
                "school_stage": school_stage,
                "subject_mismatch": True,
                "suggested_subject": mismatch.detected,
                "selected_subject": mismatch.selected,
            },
        )
        return

    wont = wont_guide_reply(
        message,
        subject=active_subject,
        session_meta=session.meta_json if isinstance(session.meta_json, dict) else None,
        has_image=has_image,
    )
    if wont:
        reply_raw, meta_patch = wont
        parts = []
        async for kind, payload in _stream_product_gate(
            message,
            reply=reply_raw,
            code="wont_guide",
            extra={"wont_guide": True},
        ):
            if kind == "token":
                parts.append(str(payload))
                yield ("token", payload)
            elif kind == "error":
                yield ("error", payload)
                return
        reply = ("".join(parts) or reply_raw).strip() or reply_raw
        QaMemory.append_message(db, session_id=session.id, role="user", content=message)
        if session.title == "新对话":
            session.title = session_title_from_message(message)
        _patch_session_meta(session, {k: v for k, v in meta_patch.items() if k == "wont_guide_stage"})
        QaMemory.append_message(
            db,
            session_id=session.id,
            role="assistant",
            content=reply,
            meta_json=meta_patch,
        )
        db.commit()
        svc.invalidate_qa_caches(child_user_id)
        svc.emit_turn(
            timer=timer,
            child_user_id=child_user_id,
            session_id=session.id,
            subject=active_subject,
            message=message,
            reply=reply,
            school_stage=school_stage,
            clarified=True,
            stream=True,
        )
        yield (
            "done",
            svc.public_chat_payload(
                session_id=session.id,
                reply=reply,
                talent=talent,
                school_stage=school_stage,
                clarified=True,
                wont_guide=True,
            ),
        )
        return

    prior_turns = sum(1 for m in session.messages if m.role in ("user", "assistant"))
    if needs_stem_clarification(
        message, has_image=has_image, has_prior_turns=prior_turns > 0
    ):
        QaMemory.append_message(db, session_id=session.id, role="user", content=message)
        if session.title == "新对话":
            session.title = session_title_from_message(message)
        reply = clarification_reply(subject=active_subject)
        QaMemory.append_message(
            db,
            session_id=session.id,
            role="assistant",
            content=reply,
            meta_json={"clarified": True},
        )
        db.commit()
        svc.invalidate_qa_caches(child_user_id)
        svc.emit_turn(
            timer=timer,
            child_user_id=child_user_id,
            session_id=session.id,
            subject=active_subject,
            message=message,
            reply=reply,
            school_stage=school_stage,
            clarified=True,
            stream=True,
        )
        yield ("token", reply)
        yield (
            "done",
            svc.public_chat_payload(
                session_id=session.id,
                reply=reply,
                talent=talent,
                school_stage=school_stage,
                clarified=True,
            ),
        )
        return

    history, memory_digest = QaMemory.prepare_history_and_digest(db, session)
    coach_meta = build_coach_metadata(
        talent_primary=talent,
        report_json=report_json,
        school_stage=school_stage,
        message=message,
    )
    topics = QaMemory.recent_topics(db, child_user_id)
    if topics:
        coach_meta["recent_topics"] = topics[:3]

    try:
        ocr_preview, image_url, resolved_image_id = await _resolve_passage_for_turn(
            session,
            child_user_id=child_user_id,
            image_id=image_id,
            message=message,
        )
    except ValueError as e:
        yield ("error", str(e))
        return

    ocr_gate = assess_ocr_gate(ocr_preview, user_message=message) if has_image else None
    if ocr_gate is not None:
        user_row = QaMessage(
            session_id=session.id,
            role="user",
            content=message,
            image_url=image_url,
            meta_json={"image_id": image_id} if image_id else None,
        )
        db.add(user_row)
        if session.title == "新对话":
            session.title = session_title_from_message(message)
        reply = ocr_gate.reply
        db.add(
            QaMessage(
                session_id=session.id,
                role="assistant",
                content=reply,
                meta_json={
                    "clarified": True,
                    "ocr_gate": ocr_gate.status,
                    "question_count": ocr_gate.question_count,
                    "awaiting_question_pick": True,
                },
            )
        )
        db.commit()
        svc.invalidate_qa_caches(child_user_id)
        svc.emit_turn(
            timer=timer,
            child_user_id=child_user_id,
            session_id=session.id,
            subject=active_subject,
            message=message,
            reply=reply,
            school_stage=school_stage,
            clarified=True,
            stream=True,
        )
        yield ("token", reply)
        yield (
            "done",
            svc.public_chat_payload(
                session_id=session.id,
                reply=reply,
                talent=talent,
                school_stage=school_stage,
                clarified=True,
            ),
        )
        return

    rag_bundle = await _fetch_qa_rag_bundle(
        message,
        child_user_id=child_user_id,
        subject=subject or session.subject,
        has_image=has_image,
        use_rag=use_rag,
    )
    rag_used = bool(rag_bundle["rag_used"])
    rag_sources = list(rag_bundle["rag_sources"] or [])
    rag_context = rag_bundle["rag_context"]
    rag_kind = rag_bundle["rag_kind"]
    rag_source = rag_bundle["rag_source"]

    coach_context = fetch_recent_coach_context_for_prompt(db, child_user_id, session_id=session.id)
    strategy_block = strategy_to_prompt_block(
        resolve_qa_strategy(
            talent_primary=talent,
            school_stage=school_stage,
            has_image=has_image,
        )
    )
    system = build_qa_system_prompt(
        school_stage=school_stage,
        subject=subject or session.subject,
        rag_context=rag_context,
        memory_digest=memory_digest or None,
        strategy_block=strategy_block or None,
        rag_kind=rag_kind,
    )
    learner_context = build_learner_context_block(
        grade=profile.get("grade"),
        age=profile.get("age"),
        talent_primary=talent,
        report_json=report_json,
        coach_context=coach_context,
        ocr_preview=ocr_preview,
    )
    model_text = message or (
        "请根据题目图片与识别预览讲解；勿编造未识别出的题干。" if has_image else ""
    )
    if looks_like_location_correction(message):
        model_text = f"{model_text}\n\n{_CORRECTION_INSTRUCTION}".strip()
    user_message = build_qa_user_message(model_text, learner_context)

    user_row = QaMessage(
        session_id=session.id,
        role="user",
        content=message,
        image_url=image_url,
        meta_json={"image_id": image_id} if image_id else None,
    )
    db.add(user_row)
    if session.title == "新对话":
        session.title = session_title_from_message(message)
    db.commit()

    parts: list[str] = []
    from app.harness.context import ToolContext
    from app.runtime import run_turn_stream as run_profile_turn_stream

    done: dict | None = None
    async for kind, payload in run_profile_turn_stream(
        "qa",
        user_message,
        history=history,
        ctx=ToolContext(
            db=db,
            child_user_id=child_user_id,
            profile="qa",
            extra={
                "qa_session_id": session.id,
                "last_image_id": resolved_image_id or "",
                "last_ocr_text": ocr_preview or "",
            },
        ),
        system_override=system,
        max_steps=6 if looks_like_location_correction(message) else 4,
        allow_tools=True,
    ):
        if kind == "token":
            token = str(payload or "")
            parts.append(token)
            yield ("token", token)
        elif kind == "error":
            yield ("error", str(payload))
            return
        elif kind == "done" and isinstance(payload, dict):
            done = payload
    reply = ((done or {}).get("reply") or "".join(parts) or "").strip()
    if not reply:
        reply = "抱歉，AI 暂时无法响应，请稍后再试。"
    reply = sanitize_public_reply(reply, profile="qa")
    assistant_meta = svc.assistant_meta_for_storage(
        coach_meta,
        rag_used=rag_used,
        rag_sources=rag_sources,
        rag_source=rag_source,
    )
    db.add(
        QaMessage(
            session_id=session.id,
            role="assistant",
            content=reply,
            meta_json=assistant_meta,
        )
    )
    db.commit()
    svc.invalidate_qa_caches(child_user_id)

    svc.emit_turn(
        timer=timer,
        child_user_id=child_user_id,
        session_id=session.id,
        subject=subject or session.subject,
        message=message,
        reply=reply,
        school_stage=school_stage,
        has_image=has_image,
        ocr_used=bool(ocr_preview),
        rag_used=rag_used,
        stream=True,
    )
    yield (
        "done",
        svc.public_chat_payload(
            session_id=session.id,
            reply=reply,
            talent=talent,
            school_stage=school_stage,
        ),
    )
