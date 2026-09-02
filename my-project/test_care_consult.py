"""Consult 3-part replies, greeting recall, and once-a-day care pings."""
from datetime import date, timedelta

from care_memory import greeting_care_line, maybe_daily_care_notification
from luna_service import _companion_consult_followup, parse_ai_reply


def test_consult_reply_always_has_three_parts():
    user = {
        "user_display_name": "ユウ",
        "companion_name": "ルナ",
        "gender": "female",
        "consult_mode": "health",
        "consult_turns": 0,
        "life_modules": {},
    }
    dialogue, _ = parse_ai_reply(_companion_consult_followup(user, "睡眠を教える"))
    assert dialogue.startswith("【記録】"), dialogue
    assert "睡眠" in dialogue
    assert "明日" in dialogue or "教えて" in dialogue
    print("OK consult 3-part", dialogue[:80])


def test_sleep_hours_are_recorded_in_consult():
    user = {
        "user_display_name": "ユウ",
        "companion_name": "ルナ",
        "consult_mode": "health",
        "consult_turns": 0,
        "life_modules": {},
    }
    dialogue, state = parse_ai_reply(
        _companion_consult_followup(user, "昨夜は6時間しか眠れなかった")
    )
    assert "【記録】" in dialogue
    assert "6時間" in dialogue
    health = user["life_modules"]["health"]["structured"]
    assert health.get("sleep_hours") == 6
    assert user.get("care_memory", {}).get("last_health_concern") == "睡眠"
    print("OK sleep recorded")


def test_greeting_recalls_sleep_concern():
    user = {"care_memory": {"last_health_concern": "睡眠"}}
    line = greeting_care_line(user)
    assert line == "前回、睡眠が心配だったよね。今日はどう？"


def test_money_consult_chips_include_spend_record():
    # get_suggested_replies loads a brain; we check the chip table directly.
    from suggestions import _CONSULT_CHIPS

    assert "支出を記録" in _CONSULT_CHIPS["money"]
    assert "睡眠を教える" in _CONSULT_CHIPS["health"]


def test_daily_notification_fires_once():
    user = {
        "life_modules": {
            "health": {"structured": {}},
            "money": {
                "structured": {
                    "spend_log": [
                        {
                            "date": (date.today() - timedelta(days=4)).isoformat(),
                            "amount": 800,
                        }
                    ]
                }
            },
        }
    }
    first = maybe_daily_care_notification(user)
    assert first
    assert user.get("care_notified_on") == date.today().isoformat()
    user["pending_notification"] = None
    second = maybe_daily_care_notification(user)
    assert second is None or second == first
    # The date stamp must block a second distinct ping today.
    assert user.get("care_notified_on") == date.today().isoformat()
    assert user.get("pending_notification") in (None, first)


def test_three_day_spend_gap_is_the_trigger():
    today = date.today()
    user = {
        "life_modules": {
            "health": {
                "structured": {
                    "mental_status": "普通",
                    "mental_checked_on": today.isoformat(),
                }
            },
            "money": {
                "structured": {
                    "spend_log": [
                        {"date": (today - timedelta(days=4)).isoformat(), "amount": 500}
                    ]
                }
            },
        }
    }
    note = maybe_daily_care_notification(user)
    assert note and "支出" in note, note


if __name__ == "__main__":
    test_consult_reply_always_has_three_parts()
    test_sleep_hours_are_recorded_in_consult()
    test_greeting_recalls_sleep_concern()
    test_money_consult_chips_include_spend_record()
    test_daily_notification_fires_once()
    test_three_day_spend_gap_is_the_trigger()
    print("ALL care consult tests OK")
