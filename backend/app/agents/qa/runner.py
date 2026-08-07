"""QA Agent 编排（P2/Q8）— chat / stream；禁止 import Guide runner。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.agents.qa.clarify import clarification_reply, needs_stem_clarification
from app.agents.qa.clarify_guide import wont_guide_reply
from app.agents.qa.memory import QaMemory
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
from app.services.assessment_service import resolve_effective_talent
from app.services.ai_output_guard import (
    is_prompt_injection_attempt,
    refusal_message,
    sanitize_ai_reply,
)
from app.services.doubao_client import chat_completion, vision_chat_completion
from app.services.qa_coach import build_coach_metadata, fetch_recent_coach_context_for_prompt
from app.services.qa_image_store import image_data_url
from app.services.qa_rag_client import rag_chat
from app.services.qa_rag_router import should_use_rag
from app.services.text_sanitize import sanitize_subject, sanitize_text, session_title_from_message


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
        reply = mismatch_reply(mismatch)
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
        reply, meta_patch = wont
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

    ocr_preview = None
    image_url = None
    if image_id:
        data_url = image_data_url(image_id, child_user_id)
        if not data_url:
            raise ValueError("图片不存在或已过期")
        image_url = f"/api/qa/images/{image_id}?user_id={child_user_id}"
        ocr_preview = await vision_chat_completion(
            system_prompt="你是 OCR 助手。请简要识别图片中的学科题目文字与关键条件，不要解题。",
            user_message="请识别图中题目，列出已知条件和问题。",
            image_data_url=data_url,
            max_tokens=400,
        )

    rag_used = False
    rag_sources: list[str] = []
    rag_context = None
    if should_use_rag(message, subject=subject or session.subject, has_image=has_image, use_rag=use_rag):
        rag = await rag_chat(
            message,
            user_id=f"child_{child_user_id}",
            subject=subject or session.subject,
        )
        if rag and rag.get("answer"):
            rag_used = True
            rag_sources = list(rag.get("sources") or [])
            rag_context = rag["answer"]

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
    )
    learner_context = build_learner_context_block(
        grade=profile.get("grade"),
        age=profile.get("age"),
        talent_primary=talent,
        report_json=report_json,
        coach_context=coach_context,
        ocr_preview=ocr_preview,
    )
    user_message = build_qa_user_message(message, learner_context)

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

    if has_image and image_id:
        data_url = image_data_url(image_id, child_user_id)
        reply = await vision_chat_completion(
            system_prompt=system,
            user_message=user_message,
            image_data_url=data_url or "",
            history=history,
            max_tokens=900,
        )
    else:
        reply = await chat_completion(
            system_prompt=system,
            user_message=user_message,
            history=history,
            max_tokens=900,
        )

    if not reply:
        reply = "抱歉，AI 暂时无法响应，请稍后再试。"
    reply = sanitize_ai_reply(reply)

    assistant_meta = svc.assistant_meta_for_storage(
        coach_meta,
        rag_used=rag_used,
        rag_sources=rag_sources,
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
    from app.services.doubao_client import chat_completion_stream, vision_chat_completion_stream

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
        yield ("token", reply)
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
        reply, meta_patch = wont
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
        yield ("token", reply)
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

    ocr_preview = None
    image_url = None
    if image_id:
        data_url = image_data_url(image_id, child_user_id)
        if not data_url:
            yield ("error", "图片不存在或已过期")
            return
        image_url = f"/api/qa/images/{image_id}?user_id={child_user_id}"
        ocr_preview = await vision_chat_completion(
            system_prompt="你是 OCR 助手。请简要识别图片中的学科题目文字与关键条件，不要解题。",
            user_message="请识别图中题目，列出已知条件和问题。",
            image_data_url=data_url,
            max_tokens=400,
        )

    rag_used = False
    rag_sources: list[str] = []
    rag_context = None
    if should_use_rag(message, subject=subject or session.subject, has_image=has_image, use_rag=use_rag):
        rag = await rag_chat(
            message,
            user_id=f"child_{child_user_id}",
            subject=subject or session.subject,
        )
        if rag and rag.get("answer"):
            rag_used = True
            rag_sources = list(rag.get("sources") or [])
            rag_context = rag["answer"]

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
    )
    learner_context = build_learner_context_block(
        grade=profile.get("grade"),
        age=profile.get("age"),
        talent_primary=talent,
        report_json=report_json,
        coach_context=coach_context,
        ocr_preview=ocr_preview,
    )
    user_message = build_qa_user_message(message, learner_context)

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
    if has_image and image_id:
        data_url = image_data_url(image_id, child_user_id) or ""
        token_iter = vision_chat_completion_stream(
            system_prompt=system,
            user_message=user_message,
            image_data_url=data_url,
            history=history,
            max_tokens=900,
        )
    else:
        token_iter = chat_completion_stream(
            system_prompt=system,
            user_message=user_message,
            history=history,
            max_tokens=900,
        )

    async for token in token_iter:
        if token.startswith("[ERROR]"):
            yield ("error", token)
            return
        parts.append(token)
        yield ("token", token)

    reply = "".join(parts) or "抱歉，AI 暂时无法响应，请稍后再试。"
    reply = sanitize_ai_reply(reply)
    assistant_meta = svc.assistant_meta_for_storage(
        coach_meta,
        rag_used=rag_used,
        rag_sources=rag_sources,
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
