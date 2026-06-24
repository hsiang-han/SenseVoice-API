# SenseVoice-API

[English](README.md) | [中文](README_zh.md)

基于 [SenseVoice-Small](https://github.com/FunAudioLLM/SenseVoice)（阿里 FunAudioLLM）的 OpenAI 兼容语音转文本 API。

超低延迟（10秒音频 ~70ms）。情感识别。音频事件检测。语种识别。字级时间戳。一键部署。

## 特性

- OpenAI 兼容 `/v1/audio/transcriptions` 接口
- WebSocket 流式识别 `/v1/audio/transcriptions/stream`
- **情感检测**（开心、伤心、愤怒、中性）
- **音频事件检测**（语音、音乐、掌声、笑声、背景音乐等）
- **语种自动识别**（中文、英文、日文、韩文、粤语）
- 字级时间戳（通过 `verbose_json`）
- 非自回归架构：GPU 上 10 秒音频仅需 ~70ms
- CUDA 12.8 支持 RTX 5060 Ti / Blackwell GPU
- 模型在镜像中预下载（无首次启动等待）

## 快速开始

```bash
docker run -d --gpus all \
  -p 10095:10095 \
  -v /mnt/user/appdata/sensevoice-api/models:/root/.cache/huggingface \
  --name sensevoice-api \
  ghcr.io/hsiang-han/sensevoice-api:latest
```

## 使用示例

```bash
# 基本转写（OpenAI 兼容）
curl -X POST http://localhost:10095/v1/audio/transcriptions \
  -F "file=@audio.wav"

# 返回: {"text": "识别结果"}

# 详细响应（含情感 + 事件 + 时间戳）
curl -X POST http://localhost:10095/v1/audio/transcriptions \
  -F "file=@audio.wav" \
  -F "response_format=verbose_json"
```

### 响应示例

**标准格式 (json):**
```json
{"text": "今天天气真好，我们出去玩吧。"}
```

**详细格式 (verbose_json):**
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

### WebSocket 流式识别

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

### OpenAI SDK 使用

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:10095/v1", api_key="none")
result = client.audio.transcriptions.create(
    model="sensevoice-small",
    file=open("audio.wav", "rb"),
)
print(result.text)
```

## API 接口

| 接口 | 方法 | 描述 |
|------|------|------|
| `/v1/audio/transcriptions` | POST | 语音转文本（OpenAI 兼容） |
| `/v1/audio/transcriptions/stream` | WebSocket | 流式语音识别 |
| `/v1/models` | GET | 模型列表 |
| `/health` | GET | 健康检查（显示已启用功能） |
| `/docs` | GET | Swagger 接口文档 |

## SenseVoice 独有功能

| 功能 | 说明 | 获取方式 |
|------|------|----------|
| 情感检测 | happy, sad, angry, neutral | `verbose_json` → `emotion` 字段 |
| 音频事件检测 | Speech, Music, Applause, Laughter, BGM, Cry, Cough, Sneeze, Breath | `verbose_json` → `event` 字段 |
| 语种识别 | zh, en, ja, ko, yue（自动检测） | `verbose_json` → `language` 字段 |
| 字级时间戳 | 每个词的强制对齐时间戳 | `verbose_json` → `words` 数组 |
| 多语种混合 | 支持语种之间的代码切换 | 自动 |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEVICE` | `cuda:0` | 计算设备 (cuda:0, cuda:1, cpu) |
| `MODEL_ID` | `FunAudioLLM/SenseVoiceSmall` | ModelScope 模型 ID |
| `BATCH_SIZE` | `1` | 推理批大小 |
| `PORT` | `10095` | 服务端口 |

## Unraid 安装

添加模板仓库：`https://github.com/hsiang-han/unraid_templates`

或手动安装：
- Repository: `ghcr.io/hsiang-han/sensevoice-api:latest`
- Extra Parameters: `--gpus all`
- 模型缓存路径: `/mnt/user/appdata/sensevoice-api/models` → `/root/.cache/huggingface`

## 硬件要求

- NVIDIA GPU，2GB+ 显存
- NVIDIA 驱动 550+（Ampere/Ada）或 570+（Blackwell）
- Docker + NVIDIA Container Toolkit

## 构建

```bash
docker compose -f docker/gpu/docker-compose.yml up --build
```

## 致谢

- [SenseVoice](https://github.com/FunAudioLLM/SenseVoice) — 阿里 FunAudioLLM / 通义实验室
- [FunASR](https://github.com/modelscope/FunASR) 工具包

## 许可证

MIT
