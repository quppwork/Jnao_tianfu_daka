"""天赋学院 — 频道、历史剧情、课程共用。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_authenticated_user, get_db
from app.services.academy import AcademyError, chat, get_sector, open_room, report_progress, sticker_pack
from app.services.academy.bots import (
    bot_payload,
    get_bot,
    list_bots,
    update_persona,
    upload_script,
)

router = APIRouter(prefix="/api/academy", tags=["academy"])


class ProgressBody(BaseModel):
    percent: float | None = None
    position_sec: float | None = None
    duration_sec: float | None = None


class QuoteBody(BaseModel):
    who: str = ""
    text: str = ""


class ChatBody(BaseModel):
    text: str = ""
    mention: str | None = None
    quote: QuoteBody | None = None
    sticker: str | None = None


class BotConfigBody(BaseModel):
    persona_prompt: str | None = None
    constraints: str | None = None


class ScriptBody(BaseModel):
    script_body: str = ""
    plot_summary: str = ""


def _raise(err: AcademyError):
    from fastapi import HTTPException

    raise HTTPException(status_code=err.status, detail=err.message)


@router.get("/stickers")
def academy_stickers(user_id: int = Depends(get_authenticated_user)):
    return sticker_pack()


@router.get("/sector")
def academy_sector(
    episode_id: str | None = None,
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    return get_sector(db, user_id, episode_id)


@router.post("/episodes/{episode_id}/progress")
def academy_progress(
    episode_id: str,
    body: ProgressBody,
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    try:
        return report_progress(
            db,
            user_id,
            episode_id,
            percent=body.percent,
            position_sec=body.position_sec,
            duration_sec=body.duration_sec,
        )
    except AcademyError as err:
        _raise(err)


@router.post("/episodes/{episode_id}/open")
async def academy_open(
    episode_id: str,
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    try:
        return await open_room(db, user_id, episode_id)
    except AcademyError as err:
        _raise(err)


@router.get("/bots")
def academy_bots(
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    return {"bots": [bot_payload(row) for row in list_bots(db)]}


@router.get("/bots/{bot_id}")
def academy_bot(
    bot_id: str,
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    try:
        return bot_payload(get_bot(db, bot_id))
    except AcademyError as err:
        _raise(err)


@router.put("/bots/{bot_id}")
def academy_bot_config(
    bot_id: str,
    body: BotConfigBody,
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    try:
        changed = update_persona(
            db,
            bot_id,
            persona_prompt=body.persona_prompt,
            constraints=body.constraints,
        )
    except AcademyError as err:
        _raise(err)
    return bot_payload(changed.bot, changed.memories)


@router.post("/bots/{bot_id}/episodes/{episode_id}/script")
def academy_bot_script(
    bot_id: str,
    episode_id: str,
    body: ScriptBody,
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    try:
        changed = upload_script(
            db,
            bot_id,
            episode_id,
            script_body=body.script_body,
            plot_summary=body.plot_summary,
        )
    except AcademyError as err:
        _raise(err)
    payload = bot_payload(changed.bot, changed.memories)
    payload["episode_id"] = changed.script.episode_id if changed.script else episode_id
    return payload


@router.post("/episodes/{episode_id}/chat")
async def academy_chat(
    episode_id: str,
    body: ChatBody,
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    try:
        return await chat(
            db,
            user_id,
            episode_id,
            body.text,
            mention=body.mention,
            quote=body.quote.model_dump() if body.quote else None,
            sticker=body.sticker,
        )
    except AcademyError as err:
        _raise(err)
