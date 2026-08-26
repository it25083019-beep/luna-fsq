"""LUNA text-to-speech via Gemini (warm Japanese female narrator)."""
from __future__ import annotations

import base64
import io
import os
import wave
from typing import Optional

from google import genai
from google.genai import types

TTS_MODEL = os.getenv("LUNA_TTS_MODEL", "gemini-2.5-flash-preview-tts")
TTS_VOICE = os.getenv("LUNA_TTS_VOICE", "Leda")
TTS_MAX_CHARS = int(os.getenv("LUNA_TTS_MAX_CHARS", "900"))

_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("Missing GOOGLE_API_KEY")
        _client = genai.Client(api_key=api_key)
    return _client


def _pcm_to_wav(pcm: bytes, channels: int = 1, rate: int = 24000, sample_width: int = 2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def _normalize_audio_bytes(raw: bytes, mime_type: str = "") -> bytes:
    if not raw:
        return b""
    if raw[:4] == b"RIFF" or "wav" in (mime_type or "").lower():
        return raw
    return _pcm_to_wav(raw)


def _decode_inline_data(data) -> bytes:
    if data is None:
        return b""
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    if isinstance(data, str):
        return base64.b64decode(data)
    return bytes(data)


def _extract_audio_part(response) -> tuple[bytes, str]:
    candidates = getattr(response, "candidates", None) or []
    for cand in candidates:
        content = getattr(cand, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            inline = getattr(part, "inline_data", None)
            if not inline:
                continue
            raw = _decode_inline_data(getattr(inline, "data", None))
            mime = getattr(inline, "mime_type", "") or ""
            if raw:
                return _normalize_audio_bytes(raw, mime), mime
    raise RuntimeError("TTS response contained no audio")


def synthesize_speech(text: str) -> bytes:
    """Return WAV bytes for Japanese narration of `text`."""
    spoken = (text or "").strip()
    if not spoken:
        return b""
    if len(spoken) > TTS_MAX_CHARS:
        spoken = spoken[: TTS_MAX_CHARS - 1] + "…"

    prompt = (
        "次の日本語を、明るく自然な女性ナレーターの声で、そのまま読み上げてください。"
        "余計な説明や英語は入れないでください。\n\n"
        f"{spoken}"
    )

    client = _get_client()
    response = client.models.generate_content(
        model=TTS_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=TTS_VOICE,
                    )
                )
            ),
        ),
    )
    audio, _ = _extract_audio_part(response)
    return audio
