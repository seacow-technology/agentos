"""Voice pipeline helpers for format negotiation, ASR, and TTS."""

from __future__ import annotations

import io
import math
import os
import wave
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class AudioFormat:
    codec: str
    sample_rate_hz: int
    channels: int
    frame_ms: int

    def to_dict(self) -> dict:
        return {
            "codec": self.codec,
            "sample_rate_hz": self.sample_rate_hz,
            "channels": self.channels,
            "frame_ms": self.frame_ms,
        }


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        value = default
    return value


def get_audio_formats() -> tuple[AudioFormat, AudioFormat]:
    codec_in = os.getenv("OCTOPUSOS_CALLS_AUDIO_CODEC_IN", "pcm_f32").strip() or "pcm_f32"
    codec_out = os.getenv("OCTOPUSOS_CALLS_AUDIO_CODEC_OUT", "pcm_f32").strip() or "pcm_f32"

    default_rate = _int_env("OCTOPUSOS_CALLS_AUDIO_SAMPLE_RATE", 24000)
    sample_rate_in = _int_env("OCTOPUSOS_CALLS_AUDIO_SAMPLE_RATE_IN", default_rate)
    sample_rate_out = _int_env("OCTOPUSOS_CALLS_AUDIO_SAMPLE_RATE_OUT", default_rate)

    frame_ms_in = _int_env("OCTOPUSOS_CALLS_AUDIO_FRAME_MS_IN", 20)
    frame_ms_out = _int_env("OCTOPUSOS_CALLS_AUDIO_FRAME_MS_OUT", 20)

    return (
        AudioFormat(codec=codec_in, sample_rate_hz=sample_rate_in, channels=1, frame_ms=frame_ms_in),
        AudioFormat(codec=codec_out, sample_rate_hz=sample_rate_out, channels=1, frame_ms=frame_ms_out),
    )


def _samples_to_wav_bytes(samples: List[float], sample_rate_hz: int) -> bytes:
    pcm = bytearray()
    for sample in samples:
        value = max(min(sample, 1.0), -1.0)
        pcm_int = int(value * 32767.0)
        pcm += int.to_bytes(pcm_int, length=2, byteorder="little", signed=True)

    with io.BytesIO() as buffer:
        with wave.open(buffer, "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(sample_rate_hz)
            writer.writeframes(bytes(pcm))
        return buffer.getvalue()


def _wav_bytes_to_samples(wav_bytes: bytes) -> List[float]:
    with io.BytesIO(wav_bytes) as buffer:
        with wave.open(buffer, "rb") as reader:
            raw = reader.readframes(reader.getnframes())
            samples: List[float] = []
            for i in range(0, len(raw), 2):
                chunk = raw[i:i + 2]
                if len(chunk) < 2:
                    break
                value = int.from_bytes(chunk, byteorder="little", signed=True)
                samples.append(value / 32768.0)
            return samples


def transcribe_samples(samples: List[float], fmt: AudioFormat, provider_hint: str | None = None) -> str:
    provider = (provider_hint or os.getenv("OCTOPUSOS_CALLS_ASR_PROVIDER", "mock")).strip().lower()
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if api_key:
            try:
                from openai import OpenAI  # type: ignore

                client = OpenAI(api_key=api_key)
                wav_bytes = _samples_to_wav_bytes(samples, fmt.sample_rate_hz)
                model = os.getenv("OCTOPUSOS_CALLS_ASR_MODEL", "gpt-4o-transcribe")
                transcript = client.audio.transcriptions.create(
                    model=model,
                    file=("call.wav", wav_bytes, "audio/wav"),
                )
                text = getattr(transcript, "text", "") or ""
                try:
                    from octopusos.core.llm.usage_events import LLMUsageEvent, record_llm_usage_event_best_effort
                    record_llm_usage_event_best_effort(
                        LLMUsageEvent(
                            provider="openai",
                            model=model,
                            operation="voice.asr.transcribe",
                            confidence="LOW",
                            metadata={
                                "bytes": len(wav_bytes),
                                "sample_rate_hz": fmt.sample_rate_hz,
                                "codec": fmt.codec,
                            },
                        )
                    )
                except Exception:
                    pass
                return text.strip()
            except Exception:
                pass

    if not samples:
        return ""
    return "收到你的语音。"


def synthesize_samples(text: str, fmt: AudioFormat, provider_hint: str | None = None) -> List[float]:
    provider = (provider_hint or os.getenv("OCTOPUSOS_CALLS_TTS_PROVIDER", "mock")).strip().lower()
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if api_key:
            try:
                from openai import OpenAI  # type: ignore

                client = OpenAI(api_key=api_key)
                model = os.getenv("OCTOPUSOS_CALLS_TTS_MODEL", "gpt-4o-mini-tts")
                voice = os.getenv("OCTOPUSOS_CALLS_TTS_VOICE", "alloy")
                response = client.audio.speech.create(
                    model=model,
                    voice=voice,
                    input=text,
                    format="wav",
                )
                wav_bytes = response.read()
                try:
                    from octopusos.core.llm.usage_events import LLMUsageEvent, record_llm_usage_event_best_effort
                    record_llm_usage_event_best_effort(
                        LLMUsageEvent(
                            provider="openai",
                            model=model,
                            operation="voice.tts.synthesize",
                            confidence="LOW",
                            metadata={
                                "chars": len(text),
                                "voice": voice,
                                "bytes": len(wav_bytes),
                                "sample_rate_hz": fmt.sample_rate_hz,
                                "codec": fmt.codec,
                            },
                        )
                    )
                except Exception:
                    pass
                return _wav_bytes_to_samples(wav_bytes)
            except Exception:
                pass

    duration_sec = min(max(len(text) / 25.0, 0.15), 1.0)
    total = int(fmt.sample_rate_hz * duration_sec)
    hz = 440.0
    return [0.12 * math.sin(2 * math.pi * hz * (i / fmt.sample_rate_hz)) for i in range(total)]
