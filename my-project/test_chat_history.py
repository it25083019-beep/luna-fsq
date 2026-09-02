"""History reader: stored assistant turns must come back as plain text."""
import luna_service as ls


def _fake_brain(history):
    return {"user_id": "u1", "chat_history": history}


def _patch(monkey_history):
    original = ls.load_user_brain
    ls.load_user_brain = lambda uid: _fake_brain(monkey_history)
    return original


def _restore(original):
    ls.load_user_brain = original


def test_packed_model_turns_are_unwrapped():
    history = [
        {"role": "user", "content": "こんにちは", "at": "2026-09-02T01:00:00+00:00"},
        {
            "role": "model",
            "content": (
                "<dialogue>\n[wave]こんにちは！\n</dialogue>\n"
                '<game_state_json>\n{"emotion": "wave"}\n</game_state_json>'
            ),
            "at": "2026-09-02T01:00:01+00:00",
        },
    ]
    orig = _patch(history)
    try:
        out = ls.get_chat_history("u1")
    finally:
        _restore(orig)

    assert out["total"] == 2
    assert [t["role"] for t in out["turns"]] == ["user", "luna"]
    assert out["turns"][1]["text"] == "こんにちは！"
    assert "<dialogue>" not in out["turns"][1]["text"]
    assert out["has_more"] is False
    assert out["next_before"] is None


def test_legacy_turns_without_timestamp_still_load():
    history = [{"role": "model", "content": "<dialogue>やあ</dialogue>"}]
    orig = _patch(history)
    try:
        out = ls.get_chat_history("u1")
    finally:
        _restore(orig)
    assert out["turns"][0]["text"] == "やあ"
    assert out["turns"][0]["at"] is None


def test_truncated_legacy_turn_is_cleaned():
    """Replies saved while the token budget was too small kept their raw tags."""
    history = [{"role": "model", "content": "<dialogue>\n[think]800円、記録したよ"}]
    orig = _patch(history)
    try:
        out = ls.get_chat_history("u1")
    finally:
        _restore(orig)
    text = out["turns"][0]["text"]
    assert text == "800円、記録したよ"
    assert "<dialogue>" not in text
    assert "[think]" not in text


def test_pagination_walks_backwards():
    history = [
        {"role": "user" if i % 2 == 0 else "model", "content": f"m{i}"} for i in range(10)
    ]
    orig = _patch(history)
    try:
        page1 = ls.get_chat_history("u1", limit=4)
        page2 = ls.get_chat_history("u1", limit=4, before=page1["next_before"])
    finally:
        _restore(orig)

    assert [t["text"] for t in page1["turns"]] == ["m6", "m7", "m8", "m9"]
    assert page1["has_more"] is True
    assert page1["next_before"] == 6
    assert [t["text"] for t in page2["turns"]] == ["m2", "m3", "m4", "m5"]
    assert page2["next_before"] == 2


def test_blank_turns_are_skipped():
    history = [
        {"role": "model", "content": "<dialogue></dialogue>"},
        {"role": "user", "content": "   "},
        {"role": "user", "content": "ok"},
        "not-a-dict",
    ]
    orig = _patch(history)
    try:
        out = ls.get_chat_history("u1")
    finally:
        _restore(orig)
    assert [t["text"] for t in out["turns"]] == ["ok"]
    assert out["total"] == 4


def test_append_turns_stamps_both_sides():
    store = {}
    ls.append_turns(store, "やった", "<dialogue>いいね</dialogue>")
    assert [t["role"] for t in store["chat_history"]] == ["user", "model"]
    assert all(t.get("at") for t in store["chat_history"])


def test_append_turns_skips_empty_user_text():
    store = {}
    ls.append_turns(store, "", "<dialogue>はじめまして</dialogue>")
    assert len(store["chat_history"]) == 1
    assert store["chat_history"][0]["role"] == "model"
