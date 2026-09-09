# -*- coding: utf-8 -*-
from companions import fill_talk, get_companion
from luna_service import _begin_consult_session, _honorific, parse_ai_reply


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


if __name__ == "__main__":
    test_honorific_uses_account_name_not_okyakusama()
    test_consult_is_short_and_named()
    test_fill_talk_empty_who()
    print("ALL personalization tests passed")
