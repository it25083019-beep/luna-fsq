"""Tests for additive chat → life data capture."""
from datetime import date

from chat_life_capture import apply_life_updates, capture_life_from_chat, extract_life_hints_from_text


def test_extract_mood_and_spend():
    h = extract_life_hints_from_text("今日めっちゃ疲れた。ランチ800円使った")
    assert h.get("mental_status") == "疲れ"
    assert h.get("spend", {}).get("amount") == 800
    print("OK mood+spend", h)


def test_extract_schedule_tomorrow():
    h = extract_life_hints_from_text("明日14:00にバイトの予定を入れて", today=date(2026, 8, 26))
    assert h.get("schedule_add")
    assert h["schedule_add"]["date"] == "2026-08-27"
    assert h["schedule_add"]["time"] == "14:00"
    print("OK schedule", h["schedule_add"])


def test_apply_additive_no_wipe():
    user = {
        "life_modules": {
            "health": {"notes": [], "structured": {"age": 20}, "updated_at": None},
            "money": {
                "notes": [],
                "structured": {
                    "monthly_expense": 30000,
                    "spend_log": [{"date": "2026-08-25", "amount": 500, "note": "old"}],
                },
                "updated_at": None,
            },
            "schedule": {
                "notes": [],
                "structured": {
                    "events": [
                        {
                            "id": "keep1",
                            "title": "既存予定",
                            "date": "2026-08-30",
                            "time": "10:00",
                            "done": False,
                        }
                    ]
                },
                "updated_at": None,
            },
            "goals": {"notes": [], "structured": {"items": []}, "updated_at": None},
        }
    }
    capture_life_from_chat(user, "今日カフェ1200円使った。元気だよ")
    money = user["life_modules"]["money"]["structured"]
    assert any(x.get("amount") == 500 for x in money.get("spend_log") or [])
    assert any(x.get("amount") == 1200 for x in money.get("spend_log") or [])
    events = user["life_modules"]["schedule"]["structured"]["events"]
    assert any(e.get("id") == "keep1" for e in events)
    health = user["life_modules"]["health"]["structured"]
    assert health.get("mental_status") == "元気"
    assert health.get("age") == 20
    print("OK additive apply", len(money["spend_log"]), health.get("mental_status"))


def test_llm_life_updates_merge():
    user = {"life_modules": {}}
    applied = apply_life_updates(
        user,
        {
            "goal_add": {"title": "イヤホン", "target": 15000, "current": 0, "unit": "円"},
        },
    )
    assert applied
    items = user["life_modules"]["goals"]["structured"]["items"]
    assert items[0]["title"] == "イヤホン"
    # second capture same title should not duplicate
    apply_life_updates(user, {"goal_add": {"title": "イヤホン", "target": 15000}})
    assert len(user["life_modules"]["goals"]["structured"]["items"]) == 1
    print("OK goals additive", items[0]["pct"])


def test_extract_sleep_hours_and_concern():
    h = extract_life_hints_from_text("昨夜は6時間しか眠れなかった")
    assert h.get("sleep_hours") == 6
    assert h.get("sleep_concern") is True
    chip = extract_life_hints_from_text("睡眠を教える")
    assert chip.get("sleep_concern") is True
    assert "sleep_hours" not in chip
    print("OK sleep extract")


def test_apply_sleep_hours():
    user = {"life_modules": {}}
    applied = apply_life_updates(user, {"sleep_hours": 6.5, "sleep_concern": True})
    assert any("睡眠→6.5時間" in a for a in applied), applied
    health = user["life_modules"]["health"]["structured"]
    assert health.get("sleep_hours") == 6.5
    print("OK sleep apply")


if __name__ == "__main__":
    test_extract_mood_and_spend()
    test_extract_schedule_tomorrow()
    test_apply_additive_no_wipe()
    test_llm_life_updates_merge()
    test_extract_sleep_hours_and_concern()
    test_apply_sleep_hours()
    print("ALL OK")
