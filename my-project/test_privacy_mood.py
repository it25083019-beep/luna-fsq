# -*- coding: utf-8 -*-
from __future__ import annotations

from privacy_vault import (
    history_for_llm,
    keep_secret_dialogue,
    looks_secret,
    public_client_state,
    redact_text,
    reminders_for_llm,
    sanitize_admin_export_brain,
    seal_text,
    unseal_text,
)
from mood_runtime import build_mood_runtime, pulse_from_scores
from crisis_switch_service import build_crisis_protocol
from memory_drama_service import drama_line, remember_milestone


def test_secret_never_leaves():
    assert looks_secret("これは秘密だよ、誰にも言わないで")
    assert redact_text("内緒の話") == "〔秘めごと〕"
    hist = history_for_llm(
        [
            {"role": "user", "content": "普通の予定", "secret": False},
            {"role": "user", "content": "実は秘密なんだけど", "secret": True},
        ],
        limit=10,
    )
    joined = " ".join(x["content"] for x in hist)
    assert "実は秘密" not in joined
    view = public_client_state(
        {
            "chat_history": [{"content": "秘密"}],
            "mail_link": {"refresh_token": "tok"},
            "companion_id": "luno",
            "current_level": 3,
        }
    )
    assert "chat_history" not in view
    assert "mail_link" not in view
    dumped = sanitize_admin_export_brain(
        {"chat_history": [{"role": "user", "content": "password is hunter2"}], "mail_link": {"access_token": "x"}}
    )
    assert "mail_link" not in dumped
    assert dumped["chat_history"][0]["content"] == "〔秘めごと〕"
    sealed = seal_text("内緒の話")
    assert sealed.startswith("luna1:")
    assert "内緒" not in sealed
    assert unseal_text(sealed) == "内緒の話"
    assert "秘密" not in keep_secret_dialogue({"user_display_name": "試験"})
    safe_rem = reminders_for_llm(
        [{"when": "09:00", "title": "授業"}, {"when": "10:00", "title": "これは秘密の予定"}]
    )
    assert len(safe_rem) == 1
    assert safe_rem[0]["title"] == "授業"
    from chat_life_capture import capture_life_from_chat

    assert capture_life_from_chat({"life_modules": {}}, "これは秘密だよ、誰にも言わないで", None) == []
    print("OK privacy vault")


def test_mood_and_pulse():
    user = {
        "life_modules": {"health": {"structured": {"mental_status": "落ち込み"}}},
        "luna_mode": "auto",
    }
    rt = build_mood_runtime(user)
    assert rt["aura"]["id"] == "ochikomi"
    assert rt["mode"] == "gentle"
    assert rt["crisis_ready"]
    p = pulse_from_scores(40, 40, 6, mental="落ち込み")
    assert p["beat"] == "low"
    print("OK mood aura")


def test_crisis_and_drama():
    user = {"user_display_name": "試験"}
    proto = build_crisis_protocol(user)
    assert proto["seconds"] == 60
    assert len(proto["steps"]) == 3
    remember_milestone(user, "rise", "「落ち込み」の日から、また立てた")
    remember_milestone(user, "rise", "これは秘密だよ")
    line = drama_line(user)
    assert "立てた" in line
    assert "秘密" not in line
    print("OK crisis + drama")


def test_secret_chat_never_calls_model():
    import luna_service as ls

    store = {"user_id": "u1", "chat_history": [], "user_display_name": "試験"}
    orig_load, orig_save = ls.load_user_brain, ls.save_user_brain
    ls.load_user_brain = lambda uid: store
    ls.save_user_brain = lambda uid, data: None
    try:
        packed = ls.handle_chat_message("u1", "これは秘密だよ、誰にも言わないで")
    finally:
        ls.load_user_brain = orig_load
        ls.save_user_brain = orig_save
    dialogue, state = ls.parse_ai_reply(packed)
    assert "出さない" in dialogue
    assert state.get("secret_held") is True
    assert store["chat_history"][0].get("secret") is True
    print("OK secret stays local")


if __name__ == "__main__":
    test_secret_never_leaves()
    test_mood_and_pulse()
    test_crisis_and_drama()
    test_secret_chat_never_calls_model()
    print("ALL privacy/mood tests passed")
