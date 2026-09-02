"""A greeting must not swallow the rest of the message.

`re.search` matched anywhere, so 「おはよう、今日テストがある」 took the instant
greeting template and the news about the test was never answered.
"""
import luna_service as ls


def test_bare_greetings_take_the_instant_path():
    for text in ["おはよう", "こんにちは！", "こんばんは。", "おはよう、ルナ"]:
        assert ls._is_bare_mood_ping(text) is True, text


def test_bare_mood_notes_take_the_instant_path():
    for text in ["疲れた", "疲れた…", "つらい", "眠い", "ちょっと疲れた", "今日は疲れた", "tired"]:
        assert ls._is_bare_mood_ping(text) is True, text


def test_greeting_with_real_content_goes_to_the_model():
    for text in [
        "おはよう、今日テストがある",
        "こんにちは、進路の相談がしたいんだけど",
        "疲れたけど、少し勉強したよ",
        "眠いけど明日の面接の準備をしないといけない",
        "こんばんは、バイト代が入ったから貯金したい",
    ]:
        assert ls._is_bare_mood_ping(text) is False, text


def test_messages_without_mood_words_are_never_the_instant_path():
    for text in ["今日テストがある", "800円使った", "", "   "]:
        assert ls._is_bare_mood_ping(text) is False, text


def test_punctuation_only_remainder_still_counts_as_bare():
    assert ls._is_bare_mood_ping("おはよう!!!  ???") is True


def test_ascii_filler_does_not_make_it_content():
    assert ls._is_bare_mood_ping("tired lol") is True
