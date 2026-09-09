# -*- coding: utf-8 -*-
from datetime import date, timedelta

from mail_ingest import extract_tasks_from_text, import_pasted_mail, parse_when
from schedule_service import list_events


def test_parse_tomorrow_meeting():
    today = date(2026, 9, 9)
    ds, clock = parse_when("明日14時からA棟203で打ち合わせをお願いします。", today=today)
    assert ds == "2026-09-10"
    assert clock == "14:00"


def test_extract_urgent_assignment():
    today = date(2026, 9, 9)
    tasks = extract_tasks_from_text(
        "至急ご確認ください。9月10日 16:00 教室Bで課題提出です。",
        subject="課題提出のお願い",
        today=today,
    )
    assert tasks
    assert tasks[0]["urgency"] == "high"
    assert tasks[0]["location"]
    assert "教室B" in (tasks[0]["location"] or "")
    assert tasks[0]["time"] == "16:00"
    print("OK mail extract", tasks[0])


def test_import_adds_schedule_event():
    user = {
        "notify_schedule": True,
        "life_modules": {"schedule": {"structured": {"events": []}}},
    }
    today = date.today()
    raw = f"明日14時から会議室Aでミーティングをお願いします。ご確認ください。"
    result = import_pasted_mail(user, raw, subject="打ち合わせ")
    assert result["count"] >= 1
    sched = list_events(user, on_date=(today + timedelta(days=1)).isoformat())
    titles = [e.get("title") for e in (sched.get("today_open") or []) + (sched.get("today_done") or [])]
    assert titles
    assert any("打ち合わせ" in (t or "") or "ミーティング" in (t or "") for t in titles)
    print("OK mail import", result["count"], titles)


def test_extract_uses_action_not_subject():
    tasks = extract_tasks_from_text(
        "9月10日16時、教室Bでレポートを提出してください。",
        subject="【重要】Fwd: ご確認ください 大学からのお知らせ",
        today=date(2026, 9, 9),
    )
    assert tasks
    assert tasks[0]["title"] == "課題提出"
    assert tasks[0]["note"] is None
    assert tasks[0]["time"] == "16:00"
    print("OK action title", tasks[0])


def test_skip_fyi_only():
    tasks = extract_tasks_from_text(
        "ご確認ください。明日の授業は通常通りです。よろしくお願いします。",
        subject="お知らせ",
        today=date(2026, 9, 9),
    )
    assert tasks == []
    print("OK skip FYI")


def test_skip_newsletter():
    tasks = extract_tasks_from_text(
        "今週のセールです。配信停止はこちら。unsubscribe",
        subject="【広告】Newsletter",
        today=date(2026, 9, 9),
    )
    assert tasks == []
    print("OK skip newsletter")


if __name__ == "__main__":
    test_parse_tomorrow_meeting()
    test_extract_urgent_assignment()
    test_import_adds_schedule_event()
    test_extract_uses_action_not_subject()
    test_skip_fyi_only()
    test_skip_newsletter()
    print("ALL mail ingest tests passed")
