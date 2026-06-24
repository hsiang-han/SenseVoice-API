import io
import os
import re
import tempfile
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

MODEL_ID = os.getenv("MODEL_ID", "FunAudioLLM/SenseVoiceSmall")
DEVICE = os.getenv("DEVICE", "cuda:0")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1"))

_model = None
_model_lock = threading.Lock()

# SenseVoice outputs: <|lang|><|emotion|><|event|><|textnorm|>text
_TAG_PATTERN = re.compile(r"<\|([^|]*)\|>")

_EMOTION_TAGS = {"HAPPY", "SAD", "ANGRY", "NEUTRAL"}
_EVENT_TAGS = {"Speech", "Applause", "BGM", "Laughter", "Cry", "Cough", "Sneeze", "Breath", "Music"}
_LANG_TAGS = {"zh", "en", "ja", "ko", "yue", "nospeech"}


def _parse_rich_text(raw_text: str) -> dict:
    """Parse SenseVoice rich transcription tags from raw output.

    Returns dict with keys: text, language, emotion, event
    """
    tags = _TAG_PATTERN.findall(raw_text)
    clean_text = _TAG_PATTERN.sub("", raw_text).strip()

    language = None
    emotion = None
    event = None

    for tag in tags:
        tag_upper = tag.upper()
        tag_orig = tag
        if tag_orig in _LANG_TAGS:
            language = tag_orig
        elif tag_upper in _EMOTION_TAGS:
            emotion = tag_upper.lower()
        elif tag_orig in _EVENT_TAGS:
            event = tag_orig
        # textnorm tags (withitn/woitn) are internal, skip

    return {
        "text": clean_text,
        "language": language,
        "emotion": emotion,
        "event": event,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model
    from funasr import AutoModel

    _model = AutoModel(
        model=MODEL_ID,
        hub="hf",
        trust_remote_code=True,
        disable_update=True,
        device=DEVICE,
    )
    yield
    _model = None


app = FastAPI(title="SenseVoice-API", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {
        "status": "ok" if _model else "loading",
        "model": MODEL_ID,
        "device": DEVICE,
        "features": ["emotion", "event", "language_detection", "timestamps", "itn"],
    }


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "sensevoice-small",
                "object": "model",
                "owned_by": "FunAudioLLM",
                "capabilities": {
                    "languages": ["zh", "en", "ja", "ko", "yue"],
                    "emotion_detection": True,
                    "event_detection": True,
                    "timestamps": True,
                },
            }
        ],
    }


@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    model: Optional[str] = Form(default=None),
    language: Optional[str] = Form(default=None),
    response_format: Optional[str] = Form(default="json"),
    timestamp_granularities: Optional[str] = Form(default=None),
):
    """OpenAI-compatible audio transcription endpoint.

    SenseVoice extensions (returned in verbose_json):
    - emotion: detected emotion (happy, sad, angry, neutral)
    - event: detected audio event (Speech, Music, Applause, Laughter, etc.)
    - language: auto-detected language code
    """
    if not _model:
        raise HTTPException(status_code=503, detail="Model not loaded")

    audio_bytes = await file.read()
    suffix = _get_suffix(file.filename)

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        want_timestamps = (
            response_format == "verbose_json"
            or (timestamp_granularities and "word" in timestamp_granularities)
        )

        start_time = time.time()
        with _model_lock:
            result = _model.generate(
                input=tmp_path,
                cache={},
                language=_map_language(language),
                use_itn=True,
                batch_size_s=300,
                merge_vad=True,
                output_timestamp=want_timestamps,
            )
        elapsed = time.time() - start_time
    finally:
        os.unlink(tmp_path)

    raw_text = _extract_raw(result)
    parsed = _parse_rich_text(raw_text)

    if response_format == "verbose_json":
        response = {
            "task": "transcribe",
            "language": parsed["language"] or language or "auto",
            "duration": _get_duration(audio_bytes),
            "text": parsed["text"],
            "emotion": parsed["emotion"],
            "event": parsed["event"],
            "processing_time": round(elapsed, 3),
        }

        # Word-level timestamps if available
        segments = _extract_timestamps(result)
        if segments:
            response["words"] = segments

        return JSONResponse(content=response)

    # Standard OpenAI json format
    return JSONResponse(content={"text": parsed["text"]})


@app.websocket("/v1/audio/transcriptions/stream")
async def transcribe_stream(websocket: WebSocket):
    """WebSocket streaming transcription.

    Send raw audio bytes, receive JSON with text, emotion, event, language.
    """
    await websocket.accept()

    if not _model:
        await websocket.send_json({"error": "Model not loaded"})
        await websocket.close(code=1013)
        return

    try:
        while True:
            data = await websocket.receive_bytes()
            if not data:
                break

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name

            try:
                with _model_lock:
                    result = _model.generate(
                        input=tmp_path,
                        cache={},
                        language="auto",
                        use_itn=True,
                        batch_size_s=300,
                        merge_vad=True,
                    )
            finally:
                os.unlink(tmp_path)

            raw_text = _extract_raw(result)
            parsed = _parse_rich_text(raw_text)

            await websocket.send_json({
                "text": parsed["text"],
                "language": parsed["language"],
                "emotion": parsed["emotion"],
                "event": parsed["event"],
                "is_final": True,
            })

    except WebSocketDisconnect:
        pass


def _extract_raw(result) -> str:
    if not result:
        return ""
    if isinstance(result, list) and len(result) > 0:
        item = result[0]
        if isinstance(item, dict):
            return item.get("text", "")
        if hasattr(item, "text"):
            return item.text
    return str(result)


def _extract_timestamps(result) -> list:
    """Extract word-level timestamps from FunASR result."""
    if not result or not isinstance(result, list) or len(result) == 0:
        return []

    item = result[0]
    if not isinstance(item, dict):
        return []

    timestamps = item.get("timestamp", [])
    words = item.get("words", [])

    if not timestamps or not words:
        return []

    segments = []
    for i, ts in enumerate(timestamps):
        if isinstance(ts, (list, tuple)) and len(ts) >= 2:
            word = words[i] if i < len(words) else ""
            segments.append({
                "word": word,
                "start": round(ts[0] / 1000.0, 3),
                "end": round(ts[1] / 1000.0, 3),
            })

    return segments


def _map_language(lang: str | None) -> str:
    if not lang:
        return "auto"
    mapping = {
        "zh": "zh", "en": "en", "ja": "ja", "ko": "ko", "yue": "yue",
        "chinese": "zh", "english": "en", "japanese": "ja",
        "korean": "ko", "cantonese": "yue",
    }
    return mapping.get(lang.lower(), "auto")


def _get_suffix(filename: str | None) -> str:
    if filename:
        suffix = Path(filename).suffix
        if suffix:
            return suffix
    return ".wav"


def _get_duration(audio_bytes: bytes) -> float:
    try:
        data, sr = sf.read(io.BytesIO(audio_bytes))
        return round(len(data) / sr, 2)
    except Exception:
        return 0.0
