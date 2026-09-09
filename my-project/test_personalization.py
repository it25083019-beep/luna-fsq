# -*- coding: utf-8 -*-
from companions import (
    companion_spoken_name,
    fill_talk,
    get_companion,
    list_companions,
    sync_companion_identity,
)
from luna_service import (
    _begin_consult_session,
    _honorific,
    _stamp_companion_identity,
    companion_hello_line,
    parse_ai_reply,
)
from chat_life_capture import compose_companion_dialogue


def test_honorific_uses_account_name_not_okyakusama():
    assert _honorific({}) == ""
    assert _honorific({"user_display_name": "お客様"}) == ""
    female = _honorific({"user_display_name": "ユウ", "gender": "female"})
    assert female == "ユウさん"
    male = _honorific(
        {"user_display_name": "タロウ", "life_profile": {"gender": "male"}}
    )
    assert male == "タロウくん"
    dog = _honorific({"user_display_name": "ユウ", "companion_id": "hachi"})
    assert dog == "ユウちゃん"
    assert "様様" not in female
    print("OK honorific", female, male, dog)


def test_consult_is_short_and_named():
    user = {
        "user_display_name": "ユウ",
        "gender": "female",
        "companion_id": "hachi",
        "companion_name": "ハチ",
    }
    dialogue, _ = parse_ai_reply(_begin_consult_session(user, "health"))
    assert "お客様様" not in dialogue
    assert "LUNA" not in dialogue
    assert "ユウ" in dialogue
    assert "わん" in dialogue
    assert "眠れてる・食べられてる" not in dialogue
    assert len(dialogue) < 80
    print("OK short consult", dialogue)


def test_fill_talk_empty_who():
    tpl = get_companion("luna")["talk"]["consult_health"]
    assert fill_talk(tpl, "") == "体調はどう？いまの感じをひとつ教えて。"
    assert fill_talk(tpl, "ユウさん").startswith("ユウさん、")
    print("OK fill talk")


def test_every_companion_hello_uses_own_name():
    for row in list_companions():
        user = {
            "companion_id": row["id"],
            "companion_name": "LUNA",
            "user_display_name": "ユウ",
            "gender": "female",
        }
        sync_companion_identity(user)
        spoken = companion_spoken_name(user)
        hello = companion_hello_line(user)
        assert spoken in hello, (row["id"], hello)
        if row["id"] != "luna":
            assert "LUNA" not in hello, (row["id"], hello)
            assert "ルナ" not in hello, (row["id"], hello)
            assert user["companion_name"] == spoken
        greet = compose_companion_dialogue(user, "こんにちは", [])
        body = greet["dialogue"]
        assert spoken in body, (row["id"], body)
        if row["id"] != "luna":
            assert "LUNA" not in body, (row["id"], body)
            assert "ルナだよ" not in body, (row["id"], body)
        stamped = _stamp_companion_identity(
            user, "Adminさん、こんにちは。LUNAだよ。今日も一緒にがんばろうね。"
        )
        if row["id"] != "luna":
            assert "LUNA" not in stamped, (row["id"], stamped)
            assert spoken in stamped, (row["id"], stamped)
        print("OK identity", row["id"], hello)
    luna_onboard = {"companion_id": "luna", "companion_name": None}
    sync_companion_identity(luna_onboard)
    assert not luna_onboard.get("companion_name")
    print("OK every companion identity")


if __name__ == "__main__":
    test_honorific_uses_account_name_not_okyakusama()
    test_consult_is_short_and_named()
    test_fill_talk_empty_who()
    test_every_companion_hello_uses_own_name()
    print("ALL personalization tests passed")
