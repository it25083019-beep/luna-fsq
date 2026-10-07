# -*- coding: utf-8 -*-
"""Open line follows the clock, then remembers the last talk."""
from __future__ import annotations

from datetime import datetime, timedelta

from care_turn import plan_care_reply, recall_greeting
from day_coach import JST, companion_agenda_line
from luna_service import companion_hello_line
from schedule_service import add_event
from suggestions import _chips_with_agenda


def _user():
    return {
        "companion_id": "luno",
        "companion_name": "ルノ",
        "user_display_name": "ユウ",
        "life_modules": {
            "health": {"structured": {}},
            "schedule": {"structured": {"events": []}},
            "money": {"structured": {}},
        },
    }


def test_during_school_asks_what_happened():
    user = _user()
    now = datetime(2026, 10, 7, 11, 51, tzinfo=JST)
    add_event(user, title="学校", event_date="2026-10-07", event_time="09:20", event_end_time="16:30")
    line = companion_agenda_line(user, now=now, who="ユウさん")
    assert "何かあった" in line
    assert "クエスト" not in line
    assert "レベル" not in line
    print("OK during school")


def test_after_shift_asks_if_tired():
    user = _user()
    now = datetime(2026, 10, 7, 21, 10, tzinfo=JST)
    add_event(user, title="バイト", event_date="2026-10-07", event_time="17:00", event_end_time="21:00")
    line = companion_agenda_line(user, now=now, who="ユウさん")
    assert "疲れ" in line
    print("OK after shift", line)


def test_next_open_remembers_last_words():
    user = _user()
    user["care_recall"] = {"note": "疲れた", "at": "2026-10-06T03:00:00+00:00", "tone": "tired"}
    line = companion_hello_line(user)
    assert "疲れた" in line
    assert "クエスト" not in line
    remembered = recall_greeting(user, who="ユウさん", now=datetime(2026, 10, 7, 8, 0, tzinfo=JST))
    assert remembered.startswith("ユウさん、")
    assert "この前" in remembered
    print("OK remember", line)


def test_heavy_stops_and_opens_rescue():
    user = _user()
    line, state = plan_care_reply(user, "つらい", now=datetime(2026, 10, 7, 12, 0, tzinfo=JST))
    assert state["open_rescue"] is True
    assert state["care_action"] == "rescue"
    assert "60秒" in line
    print("OK heavy handoff")


def test_chips_answer_the_clock_question():
    user = _user()
    now = datetime.now(JST)
    start = (now - timedelta(minutes=30)).strftime("%H:%M")
    end = (now + timedelta(hours=2)).strftime("%H:%M")
    add_event(user, title="学校", event_date=now.date().isoformat(), event_time=start, event_end_time=end)
    assert _chips_with_agenda(user) == ["大丈夫", "疲れた", "何かあった"]
    print("OK chips")


if __name__ == "__main__":
    test_during_school_asks_what_happened()
    test_after_shift_asks_if_tired()
    test_next_open_remembers_last_words()
    test_heavy_stops_and_opens_rescue()
    test_chips_answer_the_clock_question()
    print("ALL open-care tests passed")
