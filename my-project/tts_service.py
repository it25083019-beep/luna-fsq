"""Companion text-to-speech via Gemini (cloned Luna/Luno + styled others)."""
from __future__ import annotations

import base64
import io
import os
import wave
from pathlib import Path
from typing import Any, Dict, Optional

_STATIC_DIR = Path(__file__).resolve().parent / "static"

TTS_MODEL = os.getenv("LUNA_TTS_MODEL", "gemini-2.5-flash-preview-tts")
TTS_VOICE = os.getenv("LUNA_TTS_VOICE", "Gacrux")
TTS_MAX_CHARS = int(os.getenv("LUNA_TTS_MAX_CHARS", "900"))
_FALLBACK_STYLE = "30歳前後の女性教師。落ち着いて丁寧で温かく、少し指導的"
_CLONE_CACHE: Dict[str, bytes] = {}

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("Missing GOOGLE_API_KEY")
        from google import genai

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


def resolve_voice_profile(companion_id: Optional[str] = None) -> Dict[str, Any]:
    """Gemini voice name + speaking style for a companion (no API call)."""
    voice: Dict[str, Any] = {}
    try:
        from companions import get_companion

        row = get_companion(companion_id)
        raw = row.get("voice") if isinstance(row.get("voice"), dict) else {}
        voice = dict(raw)
    except Exception:
        voice = {}
    name = (voice.get("gemini_name") or TTS_VOICE or "Gacrux").strip()
    style = (voice.get("style_ja") or _FALLBACK_STYLE).strip()
    cid = (companion_id or "luna").strip().lower() or "luna"
    return {
        "companion_id": cid,
        "gemini_name": name,
        "style_ja": style,
        "browser_rate": voice.get("browser_rate"),
        "browser_pitch": voice.get("browser_pitch"),
        "sample_ja": voice.get("sample_ja") or "",
        "reference_audio": voice.get("clone_wav") or voice.get("reference_audio") or voice.get("sample_audio") or "",
        "sample_audio": voice.get("sample_audio") or voice.get("reference_audio") or "",
        "clone": bool(voice.get("clone_wav") or voice.get("reference_audio")),
    }


def _static_path(rel: str) -> Path:
    path_s = (rel or "").strip()
    if path_s.startswith("/static/"):
        return _STATIC_DIR / path_s[len("/static/") :]
    return Path(path_s)


def clone_wav_bytes(companion_id: Optional[str] = None) -> bytes:
    """24 kHz mono 16-bit WAV used to replicate Luna/Luno's recorded voice."""
    profile = resolve_voice_profile(companion_id)
    cid = profile["companion_id"]
    cached = _CLONE_CACHE.get(cid)
    if cached:
        return cached
    rel = str(profile.get("reference_audio") or "")
    candidates = []
    if rel:
        p = _static_path(rel)
        candidates.append(p)
        if p.suffix.lower() != ".wav":
            candidates.append(p.with_name(p.stem + "-ref.wav"))
            candidates.append(p.with_suffix(".wav"))
    candidates.append(_STATIC_DIR / "audio" / f"{cid}-ref.wav")
    data = b""
    for path in candidates:
        if path.is_file() and path.suffix.lower() == ".wav":
            data = path.read_bytes()
            if data[:4] == b"RIFF":
                break
            data = b""
    if data:
        _CLONE_CACHE[cid] = data
    return data


def synthesize_speech(text: str, companion_id: Optional[str] = None) -> bytes:
    """Return WAV bytes for Japanese narration of `text` in that companion's voice."""
    spoken = (text or "").strip()
    try:
        from privacy_vault import looks_secret

        if looks_secret(spoken):
            spoken = "そばにいるよ。"
    except Exception:
        pass
    if not spoken:
        return b""
    if len(spoken) > TTS_MAX_CHARS:
        spoken = spoken[: TTS_MAX_CHARS - 1] + "…"

    profile = resolve_voice_profile(companion_id)
    clone = clone_wav_bytes(profile["companion_id"])
    if clone:
        prompt = (
            "次の日本語だけを、参考音声と同一人物・同じ声質・同じ話し方で読み上げてください。"
            "説明や英語は入れないでください。\n\n"
            f"{spoken}"
        )
    else:
        prompt = (
            f"次の日本語を、{profile['style_ja']}の声で、そのまま読み上げてください。"
            "余計な説明や英語は入れないでください。\n\n"
            f"{spoken}"
        )

    from google.genai import types

    if clone:
        voice_config = types.VoiceConfig(
            replicated_voice_config=types.ReplicatedVoiceConfig(
                mime_type="audio/wav",
                voice_sample_audio=clone,
            )
        )
    else:
        voice_config = types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                voice_name=profile["gemini_name"],
            )
        )
    client = _get_client()
    response = client.models.generate_content(
        model=TTS_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(voice_config=voice_config),
        ),
    )
    audio, _ = _extract_audio_part(response)
    return audio
