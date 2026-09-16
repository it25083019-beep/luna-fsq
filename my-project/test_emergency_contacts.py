# -*- coding: utf-8 -*-
from emergency_contacts import (
    add_emergency_contact,
    crisis_contact_payload,
    delete_emergency_contact,
    mark_emergency_called,
    ranked_emergency_contacts,
)
from crisis_switch_service import build_crisis_protocol


def test_family_ranks_above_friend():
    user = {}
    add_emergency_contact(user, name="友達A", tel="09011112222", relation="friend")
    add_emergency_contact(user, name="お母さん", tel="09033334444", relation="family")
    ranked = ranked_emergency_contacts(user)
    assert ranked[0]["name"] == "お母さん"
    mark_emergency_called(user, ranked[1]["id"])
    mark_emergency_called(user, ranked[1]["id"])
    ranked2 = ranked_emergency_contacts(user)
    assert ranked2[0]["relation"] == "family"
    print("OK family ranks first")


def test_call_count_breaks_friend_tie():
    user = {}
    a = add_emergency_contact(user, name="親友A", tel="08011112222", relation="friend")
    b = add_emergency_contact(user, name="親友B", tel="08033334444", relation="friend")
    mark_emergency_called(user, b["id"])
    ranked = ranked_emergency_contacts(user)
    assert ranked[0]["id"] == b["id"]
    assert a["id"] != ranked[0]["id"]
    print("OK frequency")


def test_crisis_protocol_has_contacts_not_hotline():
    user = {"companion_id": "luno", "user_display_name": "試験"}
    add_emergency_contact(user, name="お母さん", tel="09012345678", relation="family")
    proto = build_crisis_protocol(user)
    assert proto.get("hotline_ja") in (None, "")
    assert proto["contacts"]
    assert proto["contacts"][0]["name"] == "お母さん"
    assert proto["contacts"][0]["call_href"].startswith("tel:")
    assert "0570" not in str(proto)
    assert "いのちの電話" not in str(proto)
    payload = crisis_contact_payload(user)
    assert "お母さん" in payload["hint_ja"]
    print("OK crisis contacts", proto["hint_ja"])


def test_delete_contact():
    user = {}
    row = add_emergency_contact(user, name="父", tel="09099998888", relation="family")
    assert delete_emergency_contact(user, row["id"]) is True
    assert ranked_emergency_contacts(user) == []
    print("OK delete")


if __name__ == "__main__":
    test_family_ranks_above_friend()
    test_call_count_breaks_friend_tie()
    test_crisis_protocol_has_contacts_not_hotline()
    test_delete_contact()
    print("ALL emergency contact tests passed")
