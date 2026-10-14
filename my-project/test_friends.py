# -*- coding: utf-8 -*-
"""QR friends and nearby hints never keep a real coordinate."""
from __future__ import annotations

from friends_service import (
    accept_friend,
    clear_presence,
    geohash,
    issue_code,
    nearby_people,
    public_card,
    redeem_code,
    request_friend,
    send_chat,
    set_presence,
    set_showcase,
)
from privacy_vault import sanitize_admin_export_brain


def _person(name: str) -> dict:
    return {
        "user_display_name": name,
        "current_level": 3,
        "companion_name": "ルナ",
        "rpg": {"journey": {"completed_lessons": ["a"], "portfolio_evidence": [{"id": "e1"}]}},
    }


def test_presence_drops_the_coordinate():
    user = _person("ユウ")
    set_presence(user, 35.6812, 139.7671)
    blob = str(user["social"]["presence"])
    assert "35.6812" not in blob
    assert "139.7671" not in blob
    assert user["social"]["presence"]["cell"] == geohash(35.6812, 139.7671)
    assert "lat" not in user["social"]["presence"]
    print("OK no coordinate")


def test_nearby_is_only_a_name():
    me = _person("ユウ")
    other = _person("アオ")
    far = _person("ハル")
    set_presence(me, 35.6812, 139.7671)
    set_presence(other, 35.6830, 139.7680)
    set_presence(far, 34.70, 135.50)
    store = {"me": me, "ao": other, "haru": far}

    people = nearby_people("me", me, load=store.get, ids=["me", "ao", "haru"])
    assert people == [{"id": "ao", "name": "アオ"}]
    assert "cell" not in people[0]
    clear_presence(other)
    assert nearby_people("me", me, load=store.get, ids=["me", "ao", "haru"]) == []
    print("OK nearby")


def test_qr_links_once_and_chat_stays_between_friends():
    me = _person("ユウ")
    other = _person("アオ")
    store = {"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa": me, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb": other}
    issued = issue_code(other)
    saved = []

    def save(pid, brain):
        store[pid] = brain
        saved.append(pid)

    friend = redeem_code(
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        me,
        issued["payload"],
        load=store.get,
        save=save,
        ids=list(store),
    )
    assert friend["name"] == "アオ"
    try:
        redeem_code(
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            me,
            issued["token"],
            load=store.get,
            save=save,
            ids=list(store),
        )
        raise AssertionError("code reused")
    except ValueError as exc:
        assert "使われ" in str(exc)
    stranger = _person("リン")
    try:
        send_chat(
            "cccccccccccccccccccccccccccccccc",
            stranger,
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "やあ",
            load=store.get,
            save=save,
        )
        raise AssertionError("stranger chatted")
    except ValueError:
        pass
    sent = send_chat(
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        me,
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "  こんにちは  ",
        load=store.get,
        save=save,
    )
    assert sent["text"] == "こんにちは"
    card = public_card(me, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", other)
    assert card["level"] == 3
    assert card["works"] == 1
    set_showcase(other, show_rpg=False, show_portfolio=False)
    hidden = public_card(me, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", other)
    assert "level" not in hidden
    assert "works" not in hidden
    export = sanitize_admin_export_brain({"social": me["social"], "user_display_name": "ユウ"})
    assert "social" not in export
    print("OK qr chat card")


def test_nearby_request_needs_a_shared_area():
    me = _person("ユウ")
    other = _person("アオ")
    store = {"me": me, "ao": other}
    set_presence(me, 35.6812, 139.7671)
    set_presence(other, 34.70, 135.50)
    try:
        request_friend("me", me, "ao", load=store.get, save=lambda *_a: None, ids=["me", "ao"])
        raise AssertionError("far request")
    except ValueError as exc:
        assert "近く" in str(exc)
    set_presence(other, 35.6820, 139.7675)
    request_friend("me", me, "ao", load=store.get, save=lambda pid, brain: store.__setitem__(pid, brain), ids=["me", "ao"])
    assert store["ao"]["social"]["inbox"][0]["name"] == "ユウ"
    accept_friend("ao", store["ao"], "me", load=store.get, save=lambda pid, brain: store.__setitem__(pid, brain))
    assert store["me"]["social"]["friends"][0]["id"] == "ao"
    print("OK request")


if __name__ == "__main__":
    test_presence_drops_the_coordinate()
    test_nearby_is_only_a_name()
    test_qr_links_once_and_chat_stays_between_friends()
    test_nearby_request_needs_a_shared_area()
    print("ALL friend tests passed")
