"""语音服务 API — TTS 语音合成 + ASR 语音识别（本地 Whisper）"""

import os
import io
import tempfile
from pathlib import Path
import httpx
from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import Response

from app.core.deps import get_authenticated_student
from app.core.rate_limit import check_rate_limit
from app.core.logger import get_logger

logger = get_logger("voice")

router = APIRouter(prefix="/api/voice", tags=["voice"])

SPEECH_TOKEN = os.getenv("SPEECH_ACCESS_TOKEN", "") or os.getenv("DOUBAO_API_KEY", "")
TTS_URL = "https://openspeech.bytedance.com/api/v1/tts"


# ── TTS ──

@router.post("/tts")
async def text_to_speech(
    data: dict,
    auth_user_id: int = Depends(get_authenticated_student),
):
    """TTS 暂不使用 — 前端未接入，保留路由供后续启用。"""
    from fastapi import HTTPException
    raise HTTPException(status_code=501, detail="TTS 功能暂未启用")


# ── ASR（本地 Whisper）──

_whisper_model = None

def _get_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    return _whisper_model


@router.post("/asr")
async def speech_to_text(
    audio: UploadFile = File(...),
    auth_user_id: int = Depends(get_authenticated_student),
):
    check_rate_limit(f"asr:{auth_user_id}", max_calls=30, window_sec=60)
    try:
        model = _get_model()
    except ImportError:
        return {"error": "faster-whisper 未安装，请运行: pip install faster-whisper"}
    except Exception as e:
        return {"error": f"Whisper 模型加载失败: {e}"}

    audio_bytes = await audio.read()
    suffix = Path(audio.filename or "audio.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name

    try:
        segments, _ = model.transcribe(tmp_path, language="zh", beam_size=5)
        text = " ".join(s.text for s in segments)
        logger.info(f"ASR result: {text[:80]}...")
        return {"text": text}
    except Exception as e:
        logger.error(f"ASR failed: {e}")
        return {"error": f"语音识别失败: {e}"}
    finally:
        os.unlink(tmp_path)
