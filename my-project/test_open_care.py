# -*- coding: utf-8 -*-
"""Open line follows the clock, then remembers the last talk."""
from __future__ import annotations

from datetime import datetime, timedelta

from care_turn import balance_advice, linked_open_line, plan_care_reply, recall_greeting
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


def test_night_open_asks_if_awake():
    user = _user()
    now = datetime(2026, 10, 7, 23, 40, tzinfo=JST)
    line = companion_hello_line(user, now=now)
    assert "眠れない" in line
    assert "何かあった" in line
    assert "ルノ" in line
    assert "クエスト" not in line
    assert _chips_with_agenda(user, now=now) == ["眠れない", "何かあった", "大丈夫"]
    print("OK night", line)


def test_money_and_health_share_one_question():
    user = _user()
    user["life_modules"]["health"]["structured"] = {"mental_status": "疲れ", "sleep_hours": 4}
    user["life_modules"]["money"]["structured"] = {"monthly_income": "80000", "monthly_expense": "120000"}
    now = datetime(2026, 10, 7, 15, 0, tzinfo=JST)
    line = linked_open_line(user, who="ユウさん", now=now)
    assert line
    assert "お金" in line and "からだ" in line
    assert "記録" in line
    print("OK linked money health", line)


def test_night_cites_sleep_only_when_recorded():
    user = _user()
    now = datetime(2026, 10, 7, 23, 10, tzinfo=JST)
    plain = linked_open_line(user, who="ユウさん", now=now)
    assert "眠れない" in plain
    assert "時間" not in plain
    user["life_modules"]["health"]["structured"] = {"sleep_hours": 4}
    cited = linked_open_line(user, who="ユウさん", now=now)
    assert "4時間" in cited
    assert "記録" in cited
    print("OK night cite", cited)


def test_mentioned_event_is_asked_afterward():
    from datetime import date

    from chat_life_capture import apply_life_updates, extract_life_hints_from_text

    user = _user()
    hints = extract_life_hints_from_text("明日、卒論の発表がある", today=date(2026, 10, 7))
    assert hints["schedule_add"]["title"] == "発表"
    assert hints["schedule_add"]["date"] == "2026-10-08"
    assert hints["schedule_add"]["note"] == "あとで聞く"
    vi = extract_life_hints_from_text("ngày mai mình bảo vệ đồ án", today=date(2026, 10, 7))
    assert vi["schedule_add"]["title"] == "発表"
    apply_life_updates(user, hints)
    assert user["check_back"]["title"] == "発表"
    during = datetime(2026, 10, 8, 15, 10, tzinfo=JST)
    add_event(
        user,
        title="発表",
        event_date="2026-10-08",
        event_time="15:00",
        event_end_time="16:00",
        note="あとで聞く",
    )
    hello_during = companion_hello_line(user, now=during)
    assert "どうだった" not in hello_during
    after = datetime(2026, 10, 8, 16, 20, tzinfo=JST)
    user["check_back"]["asked"] = False
    hello_after = companion_hello_line(user, now=after)
    assert "今日は発表" in hello_after
    assert "どうだった" in hello_after
    assert _chips_with_agenda(user, now=after)[0] == "うまくいった"
    later = datetime(2026, 10, 9, 9, 0, tzinfo=JST)
    user["check_back"]["asked"] = False
    user["check_back"]["answered"] = False
    hello_next = companion_hello_line(user, now=later)
    assert "この前、発表" in hello_next
    assert "どうだった" in hello_next
    assert "予定を追加" not in extract_life_hints_from_text("課題がつらい", today=date(2026, 10, 7))
    print("OK check back", hello_after)


def test_chat_writes_spend_and_plan():
    from chat_life_capture import capture_life_from_chat
    from life_graph import done_sentence, memory_cards, sync_life_graph

    user = _user()
    spent = capture_life_from_chat(user, "疲れた。ランチ800円使った")
    assert any(tag.startswith("支出+") for tag in spent)
    assert "800" in done_sentence(spent)
    planned = capture_life_from_chat(user, "明日16:00に課題提出を予定に入れて")
    assert "予定を追加" in planned
    assert "予定に入れた" in done_sentence(planned)
    skipped = capture_life_from_chat(user, "課題がつらい")
    assert "予定を追加" not in skipped
    sync_life_graph(user)
    cards = memory_cards(user)
    assert cards
    assert any(card["label"] == "支出" for card in cards)
    print("OK graph", [(c["label"], c["value"], c["source"]) for c in cards])


def test_balance_advice_names_the_gap():
    assert "釣り合って" in balance_advice(80, 80, 80)
    assert "休もう" in balance_advice(40, 70, 30)
    assert "使い方" in balance_advice(75, 40, 80)
    print("OK balance advice")


def test_next_open_remembers_last_words():
    user = _user()
    user["care_recall"] = {"note": "疲れた", "at": "2026-10-06T03:00:00+00:00", "tone": "tired"}
    line = companion_hello_line(user, now=datetime(2026, 10, 7, 15, 0, tzinfo=JST))
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
    test_night_open_asks_if_awake()
    test_money_and_health_share_one_question()
    test_night_cites_sleep_only_when_recorded()
    test_mentioned_event_is_asked_afterward()
    test_chat_writes_spend_and_plan()
    test_balance_advice_names_the_gap()
    test_next_open_remembers_last_words()
    test_heavy_stops_and_opens_rescue()
    test_chips_answer_the_clock_question()
    print("ALL open-care tests passed")
