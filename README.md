# SenseVoice-API

[English](README.md) | [中文](README_zh.md)

OpenAI-compatible Speech-to-Text API powered by [SenseVoice-Small](https://github.com/FunAudioLLM/SenseVoice) (Alibaba FunAudioLLM).

Ultra-low latency (~70ms for 10s audio). Emotion detection. Audio event detection. Language identification. Word-level timestamps. One container.

## Features

- OpenAI-compatible `/v1/audio/transcriptions` endpoint
- WebSocket streaming `/v1/audio/transcriptions/stream`
- **Emotion detection** (happy, sad, angry, neutral)
- **Audio event detection** (Speech, Music, Applause, Laughter, BGM, etc.)
- **Auto language identification** (zh, en, ja, ko, yue)
- **Speaker diarization** — identify who is speaking (via `cam++` model, opt-in)
- Word-level timestamps (via `verbose_json`)
- Non-autoregressive: ~70ms for 10s audio on GPU
- CUDA 12.8 for RTX 5060 Ti / Blackwell GPUs
- First start downloads model (~900MB), subsequent starts are instant

## Quick Start

```bash
docker run -d --gpus all \
  -p 10095:10095 \
  -v /mnt/user/appdata/sensevoice-api/models:/root/.cache/huggingface \
  --name sensevoice-api \
  ghcr.io/hsiang-han/sensevoice-api:latest
```

## Usage Examples

```bash
# Basic transcription (OpenAI-compatible)
curl -X POST http://localhost:10095/v1/audio/transcriptions \
  -F "file=@audio.wav"

# Response: {"text": "识别结果"}

# Verbose response (emotion + event + timestamps)
curl -X POST http://localhost:10095/v1/audio/transcriptions \
  -F "file=@audio.wav" \
  -F "response_format=verbose_json"
```

### Response Examples

**Standard (json):**
```json
{"text": "今天天气真好，我们出去玩吧。"}
```

**Verbose (verbose_json):**
```json
{
  "task": "transcribe",
  "language": "zh",
  "duration": 4.8,
  "text": "今天天气真好，我们出去玩吧。",
  "emotion": "happy",
  "event": "Speech",
  "processing_time": 0.072,
  "words": [
    {"word": "今天", "start": 0.21, "end": 0.63},
    {"word": "天气", "start": 0.63, "end": 1.05},
    {"word": "真好", "start": 1.05, "end": 1.47}
  ]
}
```

**Verbose with speaker diarization (ENABLE_SPK=true):**
```json
{
  "task": "transcribe",
  "language": "zh",
  "duration": 12.4,
  "text": "今天开会讨论一下项目进展。好的没问题。",
  "emotion": "neutral",
  "event": "Speech",
  "processing_time": 0.183,
  "segments": [
    {"start": 0.24, "end": 4.10, "text": "今天开会讨论一下项目进展。", "speaker": "spk1", "emotion": "neutral"},
    {"start": 4.85, "end": 7.30, "text": "好的没问题。", "speaker": "spk2", "emotion": "happy"}
  ]
}
```

### WebSocket Streaming

```python
import websockets, asyncio

async def stream():
    async with websockets.connect("ws://localhost:10095/v1/audio/transcriptions/stream") as ws:
        with open("audio.wav", "rb") as f:
            await ws.send(f.read())
        result = await ws.recv()
        print(result)
        # {"text": "...", "language": "zh", "emotion": "neutral", "event": "Speech", "is_final": true}

asyncio.run(stream())
```

### OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:10095/v1", api_key="none")
result = client.audio.transcriptions.create(
    model="sensevoice-small",
    file=open("audio.wav", "rb"),
)
print(result.text)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/audio/transcriptions` | POST | Speech-to-text (OpenAI-compatible) |
| `/v1/audio/transcriptions/stream` | WebSocket | Streaming transcription |
| `/v1/models` | GET | List models |
| `/health` | GET | Health check (shows enabled features) |
| `/docs` | GET | Swagger documentation |

## SenseVoice Unique Capabilities

| Capability | Description | How to access |
|------------|-------------|---------------|
| Emotion detection | happy, sad, angry, neutral | `verbose_json` → `emotion` field |
| Audio event detection | Speech, Music, Applause, Laughter, BGM, Cry, Cough, Sneeze, Breath | `verbose_json` → `event` field |
| Language identification | zh, en, ja, ko, yue (auto-detected) | `verbose_json` → `language` field |
| Word-level timestamps | Forced-alignment timestamps per word | `verbose_json` → `words` array |
| Speaker diarization | Identify who is speaking (requires `ENABLE_SPK=true`) | `verbose_json` → `segments[].speaker` field |
| Mixed-language | Code-switching between supported languages | Automatic |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVICE` | `cuda:0` | Compute device (cuda:0, cuda:1, cpu) |
| `MODEL_ID` | `FunAudioLLM/SenseVoiceSmall` | HuggingFace model ID |
| `ENABLE_SPK` | `false` | Enable speaker diarization via `cam++` model (~7MB extra download) |
| `BATCH_SIZE` | `1` | Inference batch size |
| `PORT` | `10095` | Server port |
| `HF_ENDPOINT` | `https://huggingface.co` | HuggingFace mirror (China: `https://hf-mirror.com`) |

## Unraid

Add template repo: `https://github.com/hsiang-han/unraid_templates`

Or manually install with:
- Repository: `ghcr.io/hsiang-han/sensevoice-api:latest`
- Extra Parameters: `--gpus all`
- Model Cache path: `/mnt/user/appdata/sensevoice-api/models` → `/root/.cache/huggingface`

## Hardware Requirements

- NVIDIA GPU with 2GB+ VRAM
- NVIDIA driver 550+ (Ampere/Ada) or 570+ (Blackwell)
- Docker with NVIDIA Container Toolkit

## Build

```bash
docker compose -f docker/gpu/docker-compose.yml up --build
```

## Credits

- [SenseVoice](https://github.com/FunAudioLLM/SenseVoice) by Alibaba FunAudioLLM / Tongyi Lab
- [FunASR](https://github.com/modelscope/FunASR) toolkit

## License

MIT
