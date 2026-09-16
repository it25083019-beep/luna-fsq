# -*- coding: utf-8 -*-
"""Voice-clone setup: Luna/Luno WAV samples, no live Gemini call."""
from tts_service import _CLONE_CACHE, clone_wav_bytes, resolve_voice_profile


def test_luna_luno_load_clone_wav():
    _CLONE_CACHE.clear()
    luna = clone_wav_bytes("luna")
    luno = clone_wav_bytes("luno")
    ren = clone_wav_bytes("ren")
    assert luna[:4] == b"RIFF"
    assert luno[:4] == b"RIFF"
    assert len(luna) > 100_000
    assert len(luno) > 50_000
    assert luna != luno
    assert not ren
    profile_luna = resolve_voice_profile("luna")
    profile_luno = resolve_voice_profile("luno")
    assert profile_luna["clone"] is True
    assert profile_luno["clone"] is True
    assert str(profile_luna["reference_audio"]).endswith("luna-ref.wav")
    assert str(profile_luno["reference_audio"]).endswith("luno-ref.wav")
    print("OK clone wav", len(luna), len(luno))


if __name__ == "__main__":
    test_luna_luno_load_clone_wav()
    print("ALL tts clone tests passed")
