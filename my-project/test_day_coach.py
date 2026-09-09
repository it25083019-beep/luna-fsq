# -*- coding: utf-8 -*-
"""Schedule load → FSQ pace + reminder payloads."""
from datetime import date, datetime, timedelta

from day_coach import JST, assess_day_load, build_today_reminders, event_minutes
from life_link import life_quests_for_fsq
from schedule_service import add_event, home_summary
from tts_service import resolve_voice_profile


def _user():
    return {
        "notify_schedule": True,
        "life_modules": {
            "health": {"structured": {"mental_status": "普通", "sleep_hours": 7}},
            "schedule": {"structured": {"events": []}},
            "money": {"structured": {"spend_log": []}},
        },
    }


def test_voice_profiles_differ():
    luna = resolve_voice_profile("luna")
    luno = resolve_voice_profile("luno")
    ren = resolve_voice_profile("ren")
    hachi = resolve_voice_profile("hachi")
    assert luna["gemini_name"] != luno["gemini_name"]
    assert luna["gemini_name"] != ren["gemini_name"]
    assert "教師" in luna["style_ja"]
    assert "可愛" in luno["style_ja"] or "女の子" in luno["style_ja"]
    assert "男性" in ren["style_ja"]
    assert "いぬ" in hachi["style_ja"] or "わん" in hachi["style_ja"]
    print("OK voice profiles", luna["gemini_name"], luno["gemini_name"], ren["gemini_name"])


def test_light_day_recommends_lesson():
    fit = assess_day_load(_user())
    assert fit["load"] == "light"
    assert fit["recommend"] == "lesson"
    assert fit["study_minutes"] >= 20
    print("OK light day", fit["label_ja"])


def test_busy_calendar_shortens_study():
    user = _user()
    today = date.today().isoformat()
    for i, title in enumerate(["授業A", "授業B", "授業C", "バイト"]):
        add_event(
            user,
            title=title,
            event_date=today,
            event_time=f"{9 + i:02d}:00",
            event_end_time=f"{11 + i:02d}:00",
        )
    fit = assess_day_load(user)
    assert fit["open_count"] >= 4
    assert fit["recommend"] in ("micro", "rest")
    assert fit["study_minutes"] <= 12
    print("OK busy day", fit["load"], fit["open_minutes"], fit["recommend"])


def test_tired_plus_busy_recommends_rest_quests():
    user = _user()
    user["life_modules"]["health"]["structured"] = {"mental_status": "疲れ", "sleep_hours": 4}
    today = date.today().isoformat()
    add_event(user, title="授業", event_date=today, event_time="09:00", event_end_time="16:00")
    add_event(user, title="バイト", event_date=today, event_time="17:00", event_end_time="21:00")
    add_event(user, title="課題", event_date=today, event_time="21:30", event_end_time="23:00")
    fit = assess_day_load(user)
    assert fit["recommend"] == "rest"
    quests = life_quests_for_fsq(user)
    types = [q.get("type") for q in quests]
    assert "rest" in types
    assert any("ストレッチ" in (q.get("title_ja") or "") for q in quests)
    print("OK rest quests", fit["load"], types)


def test_home_summary_exposes_day_fit():
    s = home_summary(_user())
    assert s.get("day_fit", {}).get("recommend")
    assert "reminders" in s
    print("OK home summary day_fit", s["day_fit"]["label_ja"])


def test_upcoming_event_becomes_reminder():
    user = _user()
    now = datetime.now(JST)
    start = (now + timedelta(minutes=40)).time().replace(second=0, microsecond=0)
    if start.hour == 23 and start.minute > 40:
        print("SKIP reminder timing near midnight")
        return
    end_h = min(23, start.hour + 1)
    add_event(
        user,
        title="数学",
        event_date=now.date().isoformat(),
        event_time=start.strftime("%H:%M"),
        event_end_time=f"{end_h:02d}:{start.minute:02d}",
    )
    payload = build_today_reminders(user, now=now)
    kinds = {r["kind"] for r in payload["reminders"]}
    assert "schedule" in kinds
    body = " ".join(r["body"] for r in payload["reminders"] if r["kind"] == "schedule")
    assert "数学" in body
    print("OK reminders", len(payload["reminders"]))


def test_event_minutes():
    assert event_minutes({"time": "09:00", "end_time": "10:30"}) == 90
    assert event_minutes({"time": "09:00"}) == 50
    print("OK event minutes")


if __name__ == "__main__":
    test_voice_profiles_differ()
    test_light_day_recommends_lesson()
    test_busy_calendar_shortens_study()
    test_tired_plus_busy_recommends_rest_quests()
    test_home_summary_exposes_day_fit()
    test_upcoming_event_becomes_reminder()
    test_event_minutes()
    print("ALL day-coach tests passed")
