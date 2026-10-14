# -*- coding: utf-8 -*-
"""Open line follows the clock, then remembers the last talk."""
from __future__ import annotations

from datetime import datetime, timedelta

from care_turn import (
    balance_advice,
    fulfill_duty,
    linked_open_line,
    plan_care_reply,
    plan_one_move,
    recall_greeting,
)
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
    assert "話して" not in hello_during
    after = datetime(2026, 10, 8, 16, 20, tzinfo=JST)
    user["check_back"]["asked"] = False
    hello_after = companion_hello_line(user, now=after)
    assert "今日は発表" in hello_after
    assert "何かあったら話して" in hello_after
    assert "どうだった" not in hello_after
    assert _chips_with_agenda(user, now=after)[0] == "うまくいった"
    later = datetime(2026, 10, 9, 9, 0, tzinfo=JST)
    user["check_back"]["asked"] = False
    user["check_back"]["answered"] = False
    hello_next = companion_hello_line(user, now=later)
    assert "この前、発表" in hello_next
    assert "何かあったら話して" in hello_next
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
    assert "予定に入れた。終わったら、ひとこと言って。" in done_sentence(planned)
    skipped = capture_life_from_chat(user, "課題がつらい")
    assert "予定を追加" not in skipped
    sync_life_graph(user)
    cards = memory_cards(user)
    assert cards
    assert any(card["label"] == "支出" for card in cards)
    print("OK graph", [(c["label"], c["value"], c["source"]) for c in cards])


def test_tell_line_follows_the_task():
    from chat_life_capture import capture_life_from_chat
    from life_graph import done_sentence

    cases = (
        ("明日、面接がある", "終わったら、何かあったら話して。", "うまくいった"),
        ("明日、試験がある", "終わったら、きつかったら言って。", "きつかった"),
        ("明日、受診がある", "終わったら、話したくなったら言って。", "話したい"),
        ("明日16:00に打ち合わせを予定に入れて", "終わったら、ひとこと言って。", "終わった"),
    )
    for text, phrase, chip in cases:
        person = _user()
        applied = capture_life_from_chat(person, text)
        assert phrase in done_sentence(applied), text
        saved = person["check_back"]
        saved["on"] = "2026-10-07"
        saved["asked"] = False
        saved["answered"] = False
        moment = datetime(2026, 10, 7, 18, 0, tzinfo=JST)
        line = companion_hello_line(person, now=moment)
        assert phrase.replace("終わったら、", "") in line, text
        assert "どうだった" not in line
        assert _chips_with_agenda(person, now=moment)[0] == chip
    shift = _user()
    baito = capture_life_from_chat(shift, "明日バイトを予定に入れて")
    said = done_sentence(baito)
    assert said == "予定に入れた。"
    assert "check_back" not in shift
    school = _user()
    now = datetime(2026, 10, 8, 10, 0, tzinfo=JST)
    add_event(
        school,
        title="授業",
        event_date="2026-10-08",
        event_time="09:00",
        event_end_time="12:00",
        note="チャットから追加",
    )
    school["check_back"] = {"title": "発表", "on": "2026-10-08", "asked": False, "answered": False}
    during_class = companion_hello_line(school, now=now)
    assert "何かあった" in during_class
    assert "話して" not in during_class
    print("OK tell line", said)


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


def test_weekday_plan_is_spoken():
    from chat_life_capture import capture_life_from_chat, compose_companion_dialogue
    from life_graph import done_sentence

    user = _user()
    applied = capture_life_from_chat(user, "金曜、課題出す")
    said = done_sentence(applied)
    assert said == "予定に入れた。終わったら、ひとこと言って。", said
    spoken = compose_companion_dialogue(user, "金曜、課題出す", applied)["dialogue"]
    assert spoken.startswith("予定に入れた。終わったら、ひとこと言って。")
    print("OK weekday plan", said)


def test_one_word_after_the_last_class():
    user = _user()
    add_event(
        user,
        title="授業",
        event_date="2026-10-08",
        event_time="09:00",
        event_end_time="10:30",
    )
    during = datetime(2026, 10, 8, 9, 30, tzinfo=JST)
    assert "何かあった" in companion_hello_line(user, now=during)
    assert "一言" not in companion_hello_line(user, now=during)
    after = datetime(2026, 10, 8, 12, 0, tzinfo=JST)
    asked = companion_hello_line(user, now=after)
    assert "今日、一言だけ残す？" in asked
    from care_turn import keep_day_word

    kept = keep_day_word(user, "プログラミングが難しかった", after)
    assert "明日の朝" in kept
    morning = datetime(2026, 10, 9, 8, 0, tzinfo=JST)
    add_event(
        user,
        title="授業",
        event_date="2026-10-09",
        event_time="09:00",
        event_end_time="10:30",
    )
    quoted = companion_hello_line(user, now=morning)
    assert "プログラミングが難しかった" in quoted
    assert "一言だけ残す" not in quoted
    in_class = companion_hello_line(user, now=datetime(2026, 10, 9, 9, 20, tzinfo=JST))
    assert "何かあった" in in_class
    assert "プログラミング" not in in_class
    print("OK one word", quoted)


def test_first_class_then_one_question_a_day():
    from luna_service import accept_first_class

    user = _user()
    line = accept_first_class(user, "9時", today=datetime(2026, 10, 8, tzinfo=JST).date())
    assert line == "予定に入れた。その時間に開いたら、何かあったか聞くね。"
    assert user["profile_complete"] is True
    during = companion_hello_line(user, now=datetime(2026, 10, 8, 9, 30, tzinfo=JST))
    assert "何かあった" in during
    user["cared_once"] = True
    user["cared_on"] = "2026-10-08"
    nxt = companion_hello_line(user, now=datetime(2026, 10, 9, 15, 0, tzinfo=JST))
    assert "睡眠" in nxt
    assert _chips_with_agenda(user, now=datetime(2026, 10, 9, 15, 0, tzinfo=JST))[0] == "6時間"
    print("OK first class", line, nxt)


def test_morning_notification_quotes_the_sentence():
    from care_turn import day_word_morning_reminder, keep_day_word
    from day_coach import build_today_reminders

    user = _user()
    add_event(
        user,
        title="授業",
        event_date="2026-10-09",
        event_time="09:00",
        event_end_time="10:30",
    )
    user["day_word"] = {
        "on": "2026-10-08",
        "note": "プログラミングが難しかった",
        "asked": True,
        "answered": True,
    }
    morning = datetime(2026, 10, 9, 7, 0, tzinfo=JST)
    row = day_word_morning_reminder(user, now=morning, who="ユウ")
    assert row["kind"] == "day_word"
    assert row["body"] == "この前「プログラミングが難しかった」って言ってたよね。"
    assert "2026-10-09T08:20" in row["fire_at"]
    assert day_word_morning_reminder(user, now=datetime(2026, 10, 9, 9, 20, tzinfo=JST), who="ユウ") is None
    assert day_word_morning_reminder(user, now=datetime(2026, 10, 9, 15, 0, tzinfo=JST), who="ユウ") is None
    payload = build_today_reminders(user, now=morning)
    assert any(item.get("kind") == "day_word" for item in payload["reminders"])
    speaker = _user()
    add_event(
        speaker,
        title="授業",
        event_date="2026-10-08",
        event_time="09:00",
        event_end_time="10:30",
    )
    during = datetime(2026, 10, 8, 9, 30, tzinfo=JST)
    assert keep_day_word(speaker, "大丈夫", during) == ""
    assert "明日の朝" in keep_day_word(speaker, "プログラミングが難しかった", during)
    print("OK morning note", row["fire_at"])


def test_heavy_stops_and_opens_rescue():
    user = _user()
    line, state = plan_care_reply(user, "つらい", now=datetime(2026, 10, 7, 12, 0, tzinfo=JST))
    assert state["open_rescue"] is True
    assert state["care_action"] == "rescue"
    assert "60秒" in line
    print("OK heavy handoff")


def test_a_tired_question_keeps_one_burden():
    user = _user()
    now = datetime(2026, 10, 7, 14, 24, tzinfo=JST)
    ping, _state = plan_care_reply(user, "疲れた", now=now)
    assert "少ししたら" in ping or "また聞く" in ping
    asked, asked_state = plan_care_reply(user, "疲れるとなにすればいい", now=now)
    assert "助言はしない" in asked
    assert asked_state["care_action"] == "one"
    assert "すれば" not in asked
    story, _story_state = plan_care_reply(
        user,
        "バイトと学校で疲れてるけど、就活もあるからもっと疲れる",
        now=now,
    )
    assert story.startswith("就活、残した") or "就活、残した" in story
    assert "明日の朝" in story
    assert "助言" not in story
    assert user["day_word"]["note"] == "就活が一番重い"
    school = _user()
    add_event(
        school,
        title="授業",
        event_date="2026-10-07",
        event_time="09:00",
        event_end_time="12:00",
    )
    during, _during_state = plan_care_reply(school, "就活で疲れた", now=datetime(2026, 10, 7, 10, 0, tzinfo=JST))
    assert "就活、残した" in during
    assert "これが終わってから" in during
    ask = "バイトと学校で疲れてるけど、就活もあるからもっと疲れるこれをなくす何をすればいい"
    move, move_state = plan_care_reply(user, ask, now=now)
    assert "就活が一番重い" in move
    assert "応募を1件だけ開いて" in move
    assert "残した" not in move
    assert move_state["care_action"] == "move"
    follow, _follow_state = plan_one_move(user, "何をすればいい？", now=now)
    assert "応募を1件だけ開いて" in follow
    assert "どんな感じ" not in follow
    print("OK one burden", story)


def test_a_short_tired_line_cites_saved_facts():
    user = _user()
    user["life_modules"]["health"]["structured"] = {"sleep_hours": 4}
    add_event(
        user,
        title="発表",
        event_date="2026-10-07",
        event_time="09:00",
        event_end_time="10:30",
    )
    now = datetime(2026, 10, 7, 11, 0, tzinfo=JST)
    line, state = plan_care_reply(user, "疲れた", now=now)
    assert "4時間" in line
    assert "09:00" in line
    assert "発表" in line
    assert "少ししたら" not in line
    assert state["care_action"] == "cite"
    bare, _bare_state = plan_care_reply(_user(), "疲れた", now=now)
    assert "少ししたら" in bare or "また聞く" in bare
    kept = _user()
    kept["day_word"] = {
        "on": "2026-10-07",
        "note": "就活が一番重い",
        "asked": True,
        "answered": True,
    }
    named, _named_state = plan_care_reply(kept, "疲れた", now=now)
    assert "就活" in named
    assert "少ししたら" not in named
    print("OK tired cites facts", line)


def test_care_questions_stay_on_duty():
    user = _user()
    now = datetime(2026, 10, 7, 14, 55, tzinfo=JST)
    long = (
        "バイトと学校で疲れてるけど、就活もあるからもっと疲れる。"
        "これをなくすには何をすればいいのか、本当に困っているんだ。"
        "明日も同じなら、どこから手をつければいいか教えて。"
    )
    assert len(long) > 80
    line, state = fulfill_duty(user, long, now=now)
    assert "応募を1件だけ開いて" in line
    assert "どんな感じ" not in line
    assert state["care_action"] == "move"
    for question in (
        "何をすればいい？",
        "どうしたらいい？",
        "なんか方法ある？",
        "アドバイスちょうだい",
        "これをなくしたい",
    ):
        got, got_state = fulfill_duty(user, question, now=now)
        assert "応募を1件だけ開いて" in got
        assert "どんな感じ" not in got
        assert got_state["care_action"] == "move"
    fresh = _user()
    asked, asked_state = fulfill_duty(fresh, "何をすればいい？", now=now)
    assert "助言はしない" in asked
    assert asked_state["care_action"] == "one"
    named, _named_state = fulfill_duty(fresh, "親とのこと", now=now)
    assert "親とのこと" in named
    assert "残した" in named
    again, _again_state = fulfill_duty(fresh, "どうしよう", now=now)
    assert "親とのこと" in again
    assert "一つだけ手をつけて" in again
    assert fulfill_duty(_user(), "この数学の問題、どうすればいい？", now=now) is None
    print("OK duty holds the question")


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
    test_tell_line_follows_the_task()
    test_chat_writes_spend_and_plan()
    test_balance_advice_names_the_gap()
    test_next_open_remembers_last_words()
    test_weekday_plan_is_spoken()
    test_one_word_after_the_last_class()
    test_first_class_then_one_question_a_day()
    test_morning_notification_quotes_the_sentence()
    test_heavy_stops_and_opens_rescue()
    test_a_tired_question_keeps_one_burden()
    test_a_short_tired_line_cites_saved_facts()
    test_care_questions_stay_on_duty()
    test_chips_answer_the_clock_question()
    print("ALL open-care tests passed")
