"""语音服务 API — TTS 语音合成 + ASR 语音识别（本地 Whisper）"""

import os
import io
import tempfile
from pathlib import Path
import httpx
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import Response
from app.core.logger import get_logger

logger = get_logger("voice")

router = APIRouter(prefix="/api/voice", tags=["voice"])

SPEECH_TOKEN = os.getenv("SPEECH_ACCESS_TOKEN", "") or os.getenv("DOUBAO_API_KEY", "")
TTS_URL = "https://openspeech.bytedance.com/api/v1/tts"


# ── TTS ──

@router.post("/tts")
async def text_to_speech(data: dict):
    text = data.get("text", "")
    if not text:
        return Response(status_code=400)
    if not SPEECH_TOKEN:
        return {"error": "语音服务未配置"}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            TTS_URL,
            headers={"Authorization": f"Bearer;{SPEECH_TOKEN}", "Content-Type": "application/json"},
            json={
                "app": {"appid": SPEECH_TOKEN, "token": SPEECH_TOKEN, "cluster": "volcano_tts"},
                "user": {"uid": "jnao_user"},
                "audio": {"voice_type": "zh_male_qingrun", "encoding": "mp3", "speed_ratio": 1.0},
                "request": {"reqid": "jnao_tts_" + str(hash(text))[:8], "text": text, "text_type": "plain", "operation": "query"},
            },
        )
    if resp.status_code != 200:
        return {"error": f"TTS 请求失败: {resp.status_code}"}
    return Response(content=resp.content, media_type="audio/mpeg")


# ── ASR（本地 Whisper）──

_whisper_model = None

def _get_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    return _whisper_model


@router.post("/asr")
async def speech_to_text(audio: UploadFile = File(...)):
    try:
        model = _get_model()
    except ImportError:
        return {"error": "faster-whisper 未安装，请运行: pip install faster-whisper"}
    except Exception as e:
        return {"error": f"Whisper 模型加载失败: {e}"}

    # 保存上传的音频到临时文件（保留真实后缀，Whisper 可识别 webm/mp3/wav）
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
