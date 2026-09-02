"""Regression tests for reply parsing.

These cover the real malformed shapes gemini-2.5-flash produced when the token
budget cut the reply off mid-sentence, which leaked raw markup into the chat.
"""
import luna_service as ls

LEAK_MARKERS = ("<dialogue>", "</dialogue>", "<game_state_json>", "[cheer]", "[think]")


def _assert_clean(dialogue: str) -> None:
    for marker in LEAK_MARKERS:
        assert marker not in dialogue, f"{marker!r} leaked into: {dialogue!r}"


def test_well_formed_reply():
    raw = (
        "<dialogue>\n[cheer]よくできました。\n</dialogue>\n"
        '<game_state_json>\n{"emotion": "cheer", "current_do_now": "休憩"}\n</game_state_json>'
    )
    dialogue, state = ls.parse_ai_reply(raw)
    assert dialogue == "よくできました。"
    assert state["emotion"] == "cheer"
    assert state["current_do_now"] == "休憩"
    _assert_clean(dialogue)


def test_unclosed_dialogue_tag_does_not_leak():
    raw = "<dialogue>\n[think]800円の支出、記録したよ。今日は何を買ったのかな"
    dialogue, state = ls.parse_ai_reply(raw)
    assert dialogue.startswith("800円の支出")
    assert state["emotion"] == "think"
    _assert_clean(dialogue)


def test_emotion_tag_before_wrapper():
    raw = "[cheer]お疲れ様でした。\n\n<dialogue>\n今日の頑張り、メモしたよ。"
    dialogue, state = ls.parse_ai_reply(raw)
    assert "お疲れ様でした。" not in dialogue  # text before the wrapper is dropped
    assert dialogue.startswith("今日の頑張り")
    _assert_clean(dialogue)


def test_no_wrapper_at_all():
    raw = "[wave]ケン様、こんにちは！"
    dialogue, state = ls.parse_ai_reply(raw)
    assert dialogue == "ケン様、こんにちは！"
    assert state["emotion"] == "wave"
    _assert_clean(dialogue)


def test_state_json_without_closing_tag_is_recovered():
    raw = (
        "<dialogue>\n記録したよ。\n</dialogue>\n"
        '<game_state_json>\n{"life_updates": {"spend": {"amount": 800}}}'
    )
    dialogue, state = ls.parse_ai_reply(raw)
    assert dialogue == "記録したよ。"
    assert state["life_updates"]["spend"]["amount"] == 800
    _assert_clean(dialogue)


def test_truncated_state_json_recovers_longest_valid_prefix():
    raw = (
        "<dialogue>\nメモしたよ。\n</dialogue>\n"
        '<game_state_json>\n{"emotion": "happy"}, "life_updates": {"spend"'
    )
    dialogue, state = ls.parse_ai_reply(raw)
    assert dialogue == "メモしたよ。"
    assert state.get("emotion") == "happy"
    _assert_clean(dialogue)


def test_state_json_inside_dialogue_is_stripped():
    raw = (
        "<dialogue>\nこんにちは。\n"
        '<game_state_json>\n{"emotion": "joy"}\n</game_state_json>\n</dialogue>'
    )
    dialogue, state = ls.parse_ai_reply(raw)
    assert dialogue == "こんにちは。"
    assert state["emotion"] == "joy"
    _assert_clean(dialogue)


def test_empty_reply_is_safe():
    dialogue, state = ls.parse_ai_reply("")
    assert dialogue == ""
    assert state == {}
