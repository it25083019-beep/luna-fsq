"""Crisis lines must never wait on the model or take the mood-ping path."""
from luna_service import (
    _crisis_reply,
    _is_crisis_message,
    _is_bare_mood_ping,
    parse_ai_reply,
)


def test_crisis_phrases_are_detected():
    for text in ["死にたい", "もう消えたい", "kill myself", "muốn chết"]:
        assert _is_crisis_message(text) is True, text
        assert _is_bare_mood_ping(text) is False, text


def test_ordinary_distress_is_not_crisis():
    for text in ["つらい", "疲れた", "しんどい", "おはよう"]:
        assert _is_crisis_message(text) is False, text


def test_crisis_reply_opens_rescue_without_public_hotline():
    user = {"user_display_name": "ユウ", "gender": "female", "companion_name": "ルナ"}
    dialogue, state = parse_ai_reply(_crisis_reply(user))
    assert "0570" not in dialogue
    assert "いのちの電話" not in dialogue
    assert state.get("crisis") is True
    assert state.get("open_rescue") is True
    assert "<dialogue>" not in dialogue


if __name__ == "__main__":
    test_crisis_phrases_are_detected()
    test_ordinary_distress_is_not_crisis()
    test_crisis_reply_opens_rescue_without_public_hotline()
    print("ALL crisis tests OK")
