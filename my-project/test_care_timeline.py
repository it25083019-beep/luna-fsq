"""Tests for care timeline and FSQ life linking."""
from datetime import date

from care_timeline import append_care_event, build_care_timeline, build_weekly_review
from life_link import life_quests_for_fsq, on_lesson_complete


def test_append_and_build_timeline():
    user = {"care_timeline": []}
    append_care_event(user, "health", "気分「元気」を記録")
    rows = build_care_timeline(user, day=date.today().isoformat())
    assert any("元気" in r.get("label", "") for r in rows)
    print("OK timeline append")


def test_lesson_complete_life_link():
    state = {
        "user_display_name": "太郎",
        "companion_name": "LUNA",
        "life_modules": {"health": {"structured": {"mental_status": "疲れ"}, "notes": []}},
        "rpg": {"journey": {}},
    }
    res = on_lesson_complete(state, {"id": "se_l1", "title_ja": "HTML入門", "exp": 15}, exp_gained=12)
    assert "HTML入門" in res["luna_message"]
    assert state["rpg"]["journey"]["completion_log"]
    rows = build_care_timeline(state)
    assert any(r.get("kind") == "study" for r in rows)
    print("OK life link study")


def test_life_quests_for_fsq():
    user = {
        "life_modules": {
            "health": {"structured": {}},
            "money": {"structured": {"daily_spends": []}},
        }
    }
    quests = life_quests_for_fsq(user)
    assert quests
    assert quests[0].get("type") == "life"
    print("OK life quests", len(quests))


def test_weekly_review():
    user = {
        "care_timeline": [{"at": "2026-09-01T10:00:00+00:00", "kind": "health", "label": "気分"}],
        "life_modules": {"health": {"structured": {"mental_status": "普通"}}, "money": {"structured": {}}},
        "rpg": {"journey": {"completion_log": [{"at": "2026-09-01T12:00:00+00:00", "title_ja": "テスト"}]}},
    }
    rev = build_weekly_review(user, today=date(2026, 9, 2))
    assert rev and rev.get("highlights")
    print("OK weekly review")


if __name__ == "__main__":
    test_append_and_build_timeline()
    test_lesson_complete_life_link()
    test_life_quests_for_fsq()
    test_weekly_review()
    print("ALL care_timeline tests OK")
