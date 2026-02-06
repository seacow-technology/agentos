# AgentOS Voice STT Module

本地 Whisper 语音转文本 (STT) 和语音活动检测 (VAD) 模块。

## 概述

该模块提供了基于本地 Whisper 模型的语音转文本功能，以及基于 WebRTC VAD 的语音活动检测功能。

### 核心组件

1. **ISTTProvider** (`base.py`): STT 提供者抽象接口
2. **WhisperLocalSTT** (`whisper_local.py`): 基于 faster-whisper 的本地 Whisper 实现
3. **VADDetector** (`vad.py`): 基于 webrtcvad 的语音活动检测

## 安装依赖

依赖已添加到 `pyproject.toml` 中：

```toml
"faster-whisper>=1.0.0",  # Local Whisper STT for voice communication
"webrtcvad>=2.0.10",      # Voice Activity Detection (VAD)
"numpy>=1.24.0",          # Required for audio processing
```

安装依赖：

```bash
pip install -e .
# 或者单独安装
pip install faster-whisper>=1.0.0 webrtcvad>=2.0.10 numpy>=1.24.0
```

## 使用示例

### 基本使用

```python
import asyncio
import numpy as np
from agentos.core.communication.voice.stt import WhisperLocalSTT, VADDetector

async def main():
    # 创建 STT 实例
    stt = WhisperLocalSTT(
        model_name="base",    # tiny/base/small/medium/large
        device="cpu",         # cpu/cuda/auto
        language=None         # None 表示自动检测，或指定如 "zh"/"en"
    )

    # 转录音频 (假设 audio_bytes 是 16kHz int16 PCM 格式)
    text = await stt.transcribe_audio(audio_bytes, sample_rate=16000)
    print(f"Transcription: {text}")

    # 创建 VAD 实例
    vad = VADDetector(aggressiveness=2)  # 0-3, 越大越严格

    # 检测语音 (audio_chunk 必须是 10/20/30ms 的音频帧)
    is_speech = vad.is_speech(audio_chunk, sample_rate=16000)
    print(f"Is speech: {is_speech}")

asyncio.run(main())
```

### 使用 VoiceService（推荐）

```python
from agentos.core.communication.voice.service import VoiceService

# 创建服务实例（自动从环境变量读取配置）
service = VoiceService()

# 或者显式指定配置
service = VoiceService(
    stt_model="base",
    stt_device="cpu",
    stt_language="zh",
    vad_aggressiveness=2
)

# 转录音频
text = await service.transcribe_audio(audio_bytes)

# 检测语音
is_speech = service.is_speech(audio_chunk)
```

### 环境变量配置

VoiceService 支持以下环境变量：

```bash
export VOICE_STT_MODEL=base              # Whisper 模型名称 (默认: base)
export VOICE_STT_DEVICE=cpu              # 推理设备 (默认: cpu)
export VOICE_STT_LANGUAGE=zh             # 目标语言 (默认: None, 自动检测)
export VOICE_VAD_AGGRESSIVENESS=2        # VAD 严格程度 0-3 (默认: 2)
```

## 架构设计

### 1. ISTTProvider 接口

定义了所有 STT 提供者必须实现的接口：

```python
class ISTTProvider(ABC):
    async def transcribe_audio(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """转录音频字节为文本"""
        pass

    async def transcribe_stream(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[str]:
        """流式转录音频"""
        pass
```

### 2. WhisperLocalSTT 实现

**核心特性：**

- **懒加载模型**：首次调用时才加载模型，避免启动延迟
- **线程池执行**：在线程池中运行 Whisper 推理，避免阻塞事件循环
- **多模型支持**：支持 tiny/base/small/medium/large 模型
- **设备选择**：支持 cpu/cuda/auto
- **语言检测**：自动检测语言或指定目标语言
- **内置 VAD**：使用 Whisper 内置的 VAD 过滤
- **错误处理**：完善的异常处理和日志记录

**音频格式要求：**

- 格式：PCM int16
- 采样率：16kHz（推荐）
- 声道：单声道

**实现细节：**

```python
# 音频字节 → numpy array (float32, [-1, 1])
audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
audio_float32 = audio_int16.astype(np.float32) / 32768.0

# 在线程池中运行推理
segments, info = await loop.run_in_executor(
    None,
    lambda: self._model.transcribe(audio_array, language=self.language)
)
```

### 3. VADDetector 实现

**核心特性：**

- **语音检测**：检测音频帧是否包含语音
- **静音检测**：检测连续静音（用于句子边界检测）
- **可配置严格程度**：0-3，数值越大越严格（越不容易检测到语音）

**音频格式要求：**

- 格式：PCM int16
- 采样率：8kHz/16kHz/32kHz
- 帧长度：10ms/20ms/30ms

**使用示例：**

```python
vad = VADDetector(aggressiveness=2)

# 检测单帧是否为语音
# 16kHz, 20ms = 320 samples = 640 bytes
frame_bytes = audio[0:640]
is_speech = vad.is_speech(frame_bytes, sample_rate=16000)

# 检测连续静音（句子结束检测）
buffer = [frame1, frame2, frame3, ...]  # 多个音频帧
silence_end = vad.detect_silence_end(
    buffer,
    sample_rate=16000,
    threshold_ms=500  # 连续 500ms 静音
)
```

## 测试

### 手动测试

运行手动测试脚本：

```bash
python -m tests.manual.test_whisper_local
```

该脚本会测试：
1. 模块导入
2. VADDetector 基本功能
3. WhisperLocalSTT 基本功能（使用合成静音音频）
4. VoiceService 集成

**注意**：首次运行时会下载 Whisper 模型（base 模型约 140MB），请确保网络连接正常。

### 预期输出

```
Testing module imports
✓ Successfully imported ISTTProvider
✓ Successfully imported WhisperLocalSTT
✓ Successfully imported VADDetector
✓ All imports PASSED

Testing VADDetector
✓ VADDetector instance created successfully
✓ is_speech() result: False
✓ Silence correctly detected as non-speech
✓ VADDetector test PASSED

Testing WhisperLocalSTT
✓ WhisperLocalSTT instance created successfully
Starting transcription (this will download model on first run)...
✓ Transcription completed: ''
✓ Empty result is expected for silence audio
✓ WhisperLocalSTT test PASSED

Testing VoiceService
✓ VoiceService instance created successfully
✓ transcribe_audio() completed: ''
✓ is_speech() completed: False
✓ VoiceService test PASSED

🎉 ALL TESTS PASSED
```

## 性能优化建议

### 1. 模型选择

| 模型 | 大小 | 速度 | 准确度 | 适用场景 |
|------|------|------|--------|----------|
| tiny | ~40MB | 最快 | 较低 | 原型开发、测试 |
| base | ~140MB | 快 | 良好 | 生产环境（推荐） |
| small | ~460MB | 中等 | 较好 | 高准确度需求 |
| medium | ~1.5GB | 慢 | 很好 | 离线转录 |
| large | ~3GB | 很慢 | 最好 | 离线批量处理 |

### 2. 设备选择

- **CPU**: 适用于低并发场景，无需 GPU 依赖
- **CUDA**: 适用于高并发场景，需要 NVIDIA GPU 和 CUDA
- **auto**: 自动检测，优先使用 GPU

### 3. VAD 严格程度

- **0**: 最宽松，几乎所有声音都被检测为语音（适用于嘈杂环境）
- **1**: 宽松
- **2**: 平衡（推荐）
- **3**: 最严格，只检测明确的语音（适用于安静环境）

## 故障排查

### 问题 1: ModuleNotFoundError: No module named 'faster_whisper'

**解决方案**：
```bash
pip install faster-whisper>=1.0.0
```

### 问题 2: ModuleNotFoundError: No module named 'webrtcvad'

**解决方案**：
```bash
pip install webrtcvad>=2.0.10
```

### 问题 3: 首次运行很慢

**原因**：首次运行需要下载 Whisper 模型。

**解决方案**：耐心等待，模型会被缓存到 `~/.cache/huggingface/`。

### 问题 4: ValueError: Audio chunk must be 10, 20, or 30 ms

**原因**：VAD 要求音频帧长度必须是 10/20/30ms。

**解决方案**：确保音频帧长度正确。例如：
- 16kHz, 20ms = 320 samples = 640 bytes

### 问题 5: CUDA out of memory

**原因**：GPU 内存不足。

**解决方案**：
1. 使用更小的模型（如 base 或 tiny）
2. 切换到 CPU: `device="cpu"`
3. 降低批处理大小

## 未来扩展

### 计划中的功能

1. **实时流式转录**：改进 `transcribe_stream()` 实现，支持真正的实时转录
2. **多语言混合检测**：自动检测和切换多种语言
3. **自定义词汇表**：支持专业术语和人名的优先识别
4. **说话人分离**：区分不同说话人
5. **标点符号恢复**：自动添加标点符号

### 替代 STT 提供者

可以实现其他 STT 提供者（只需继承 `ISTTProvider`）：

- **WhisperAPI**: 使用 OpenAI Whisper API
- **GoogleSTT**: 使用 Google Cloud Speech-to-Text
- **AzureSTT**: 使用 Azure Cognitive Services
- **DeepSpeech**: 使用 Mozilla DeepSpeech

## 参考资料

- [faster-whisper GitHub](https://github.com/guillaumekln/faster-whisper)
- [OpenAI Whisper](https://github.com/openai/whisper)
- [webrtcvad GitHub](https://github.com/wiseman/py-webrtcvad)
- [WebRTC VAD Documentation](https://webrtc.org/getting-started/overview)

## 许可证

MIT License - 与 AgentOS 主项目保持一致
