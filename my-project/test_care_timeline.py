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
    assert "ストレス" in " ".join(res["life_effects"])
    assert state["life_modules"]["health"]["structured"]["mental_status"] == "普通"
    assert state["rpg"]["journey"]["completion_log"]
    rows = build_care_timeline(state)
    assert any(r.get("kind") == "study" for r in rows)
    print("OK life link study")


def test_life_quests_for_fsq():
    user = {
        "life_modules": {
            "health": {"structured": {}},
            "money": {"structured": {"spend_log": []}},
        }
    }
    quests = life_quests_for_fsq(user)
    assert quests
    assert quests[0].get("type") == "life"
    print("OK life quests", len(quests))


def test_timeline_shows_mood_spend_and_schedule():
    """All three categories the home timeline promises must appear."""
    today = date.today().isoformat()
    user = {
        "life_modules": {
            "health": {
                "structured": {"mental_status": "疲れ", "mental_checked_on": today}
            },
            "money": {
                "structured": {
                    "spend_log": [
                        {"date": today, "amount": 800, "note": "ランチ"},
                        {"date": today, "amount": 1200, "note": "本"},
                    ]
                }
            },
        }
    }
    items = [{"title": "バイト", "time": "09:00", "done": False}]
    rows = build_care_timeline(user, day=today, schedule_items=items)
    kinds = {r["kind"] for r in rows}
    assert {"health", "money", "schedule"} <= kinds, kinds
    labels = " ".join(r["label"] for r in rows)
    assert "800円" in labels and "1,200円" in labels, labels
    assert "バイト" in labels
    # Chronological, so the timeline reads like a journal.
    assert [r["at"] for r in rows] == sorted(r["at"] for r in rows)
    print("OK timeline mood+spend+schedule")


def test_spend_quest_clears_once_spending_is_logged():
    """The quest read a key nothing writes, so it never went away."""
    from care_memory import build_care_quests

    today = date.today().isoformat()
    user = {"life_modules": {"health": {"structured": {}}, "money": {"structured": {}}}}
    assert any(q["id"] == "spend" for q in build_care_quests(user))

    user["life_modules"]["money"]["structured"]["spend_log"] = [
        {"date": today, "amount": 800, "note": "ランチ"}
    ]
    assert not any(q["id"] == "spend" for q in build_care_quests(user))
    print("OK spend quest clears")


def test_weekly_review_totals_real_spending():
    user = {
        "life_modules": {
            "health": {"structured": {}},
            "money": {
                "structured": {
                    "spend_log": [
                        {"date": "2026-08-31", "amount": 800},
                        {"date": "2026-09-01", "amount": 1200},
                        {"date": "2026-08-20", "amount": 9999},
                    ]
                }
            },
        }
    }
    rev = build_weekly_review(user, today=date(2026, 9, 2))
    assert rev["spend_total"] == 2000, rev
    assert any("2,000円" in h for h in rev["highlights"]), rev
    print("OK weekly review spend total")


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
    test_timeline_shows_mood_spend_and_schedule()
    test_spend_quest_clears_once_spending_is_logged()
    test_weekly_review_totals_real_spending()
    print("ALL care_timeline tests OK")
