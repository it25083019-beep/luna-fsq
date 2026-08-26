"""Reproduce calendar bugs by simulating real user flows."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta

from schedule_service import (
    add_event,
    apply_suggestions,
    complete_event,
    delete_event,
    list_events,
    suggest_similar,
    update_event,
    _events_store,
    _recurring_store,
)


def fresh_user():
    return {
        "life_modules": {
            "schedule": {"structured": {}, "updated_at": None},
            "health": {"structured": {}},
            "money": {"structured": {}},
        },
        "rpg": {},
        "life_profile": {},
    }


def titles_on(user, ds: str):
    return [
        (e.get("title"), e.get("time"), e.get("end_time"), e.get("recurrence"), e.get("done"), e.get("is_generated"))
        for e in list_events(user, on_date=ds)["events"]
        if e.get("date") == ds
    ]


def dates_for_title(user, title: str, focus: str):
    return sorted(
        {
            e["date"]
            for e in list_events(user, on_date=focus)["events"]
            if e.get("title") == title
        }
    )


def active_templates(user):
    return [
        {
            "recurrence": t.get("recurrence"),
            "weekday": t.get("weekday"),
            "day_of_month": t.get("day_of_month"),
            "title": t.get("title"),
            "time": t.get("time"),
            "end_time": t.get("end_time"),
            "active": t.get("active", True),
            "start_date": t.get("start_date"),
        }
        for t in _recurring_store(user)
        if t.get("active", True)
    ]


def test_month_panel_focus_expansion():
    """Browsing far months must still show recurring dots for that month."""
    user = fresh_user()
    add_event(user, title="Di hoc", event_date="2026-08-24", event_time="09:20", event_end_time="16:40", recurrence="weekly")
    add_event(user, title="Di hoc", event_date="2026-08-25", event_time="09:20", event_end_time="16:40", recurrence="weekly")
    data = list_events(user, on_date="2027-03-15")
    dates = {e["date"] for e in data["events"] if e.get("title") == "Di hoc"}
    assert "2027-03-01" in dates, dates
    assert "2027-03-02" in dates, dates
    assert "2027-03-29" in dates, dates
    assert "2027-03-30" in dates, dates
    # Sliding window: focusing 2030 still works without generating forever from 2026
    data2 = list_events(user, on_date="2030-06-01")
    dates2 = {e["date"] for e in data2["events"] if e.get("title") == "Di hoc"}
    assert any(d.startswith("2030-06") for d in dates2), dates2
    # Payload stays bounded (no multi-year dump in one response)
    assert len(data["events"]) < 500, len(data["events"])
    print("OK month expansion sliding window (bounded payload)")




def test_screenshot_desync_data_shape():
    """Aug26 monthly + Mon/Tue weekly must not leave active monthly for same title."""
    user = fresh_user()
    add_event(user, title="Đi học", event_date="2026-09-07", event_time="09:20", event_end_time="16:40", recurrence="weekly")
    add_event(user, title="Đi học", event_date="2026-09-08", event_time="09:20", event_end_time="16:40", recurrence="weekly")
    # User (or date-jump) saves monthly on Aug 26
    add_event(user, title="Đi học", event_date="2026-08-26", event_time="09:20", event_end_time="16:40", recurrence="monthly")
    tpls = active_templates(user)
    assert all(t["recurrence"] == "weekly" for t in tpls), tpls
    assert len(tpls) == 2, tpls
    # Aug 26 can exist as one-off only
    aug = titles_on(user, "2026-08-26")
    assert len(aug) == 1 and aug[0][3] is None, aug
    sep = dates_for_title(user, "Đi học", "2026-09-01")
    assert "2026-09-07" in sep and "2026-09-08" in sep
    assert "2026-09-24" not in sep  # Thursday must not get weekly class
    print("OK screenshot monthly/weekly cleanup")


def test_save_each_day_then_auto_suggest():
    """User saves one-off days, then applies auto suggestions — must not explode clones."""
    user = fresh_user()
    # Save several one-off Mondays manually
    for ds in ("2026-09-07", "2026-09-14", "2026-09-21"):
        add_event(user, title="Di hoc", event_date=ds, event_time="09:20", event_end_time="16:40", recurrence=None)

    # Pattern suggestions often mark recurrence=weekly
    sug = suggest_similar(user, limit=6)
    print("suggestions", sug)
    # Force apply including weekly recurrence like the UI auto button
    fake = [
        {
            "title": "Di hoc",
            "date": "2026-09-28",
            "time": "09:20",
            "end_time": "16:40",
            "recurrence": "weekly",
        },
        {
            "title": "Di hoc",
            "date": "2026-09-24",  # Thursday — bad auto
            "time": "09:20",
            "end_time": "16:40",
            "recurrence": "monthly",
        },
        {
            "title": "Di hoc",
            "date": "2026-10-05",
            "time": "09:20",
            "end_time": "16:40",
            "recurrence": "weekly",
        },
    ]
    apply_suggestions(user, fake)
    tpls = active_templates(user)
    print("after auto templates", tpls)
    # Only Monday weekly should exist (weekday=0), not monthly, not Thursday weekly
    weeklies = [t for t in tpls if t["recurrence"] == "weekly"]
    assert len(weeklies) == 1 and weeklies[0]["weekday"] == 0, tpls
    assert not any(t["recurrence"] == "monthly" for t in tpls), tpls
    dates = dates_for_title(user, "Di hoc", "2026-09-01")
    assert "2026-09-24" not in dates, dates
    assert "2026-09-28" in dates
    print("OK save-each-day + auto suggest")


def test_multiple_same_day_and_edit_scopes():
    user = fresh_user()
    add_event(user, title="Study", event_date="2026-09-24", event_time="09:00", event_end_time="10:00")
    add_event(user, title="Study", event_date="2026-09-24", event_time="11:00", event_end_time="12:00")
    assert len(titles_on(user, "2026-09-24")) == 2

    add_event(user, title="Gym", event_date="2026-09-07", event_time="18:00", event_end_time="19:00", recurrence="weekly")
    data = list_events(user, on_date="2026-09-07")
    mon = [e for e in data["events"] if e["date"] == "2026-09-14" and e["title"] == "Gym"][0]
    update_event(user, mon["id"], title="Gym night", scope="this")
    assert titles_on(user, "2026-09-14")[0][0] == "Gym night"
    assert any(t[0] == "Gym" for t in titles_on(user, "2026-09-21"))

    update_event(user, [e for e in list_events(user)["events"] if e["date"] == "2026-09-21" and e["title"] == "Gym"][0]["id"], title="Gym all", scope="all")
    assert all(
        e["title"] == "Gym all"
        for e in list_events(user, on_date="2026-09-01")["events"]
        if e.get("recurrence") == "weekly" and e["date"] >= "2026-09-21"
    )
    # exception day stays exception title unless cleared by scope=all — scope=all clears exceptions
    assert not any(e["date"] == "2026-09-14" and e["title"] == "Gym night" for e in list_events(user)["events"])
    print("OK multi same-day + edit scopes")


def test_legacy_corrupt_store_cleanup():
    """Simulate production junk: weekly Mon + monthly day26 same title different end_time."""
    user = fresh_user()
    user["life_modules"]["schedule"]["structured"] = {
        "events": [
            {
                "id": "x1",
                "title": "Đi học",
                "date": "2026-08-26",
                "time": "09:20",
                "end_time": "16:40",
                "done": False,
                "recurrence_id": "m1",
                "recurrence": "monthly",
            }
        ],
        "recurring_templates": [
            {
                "id": "w1",
                "title": "Đi học",
                "start_date": "2026-09-07",
                "time": "09:20",
                "end_time": "18:20",
                "recurrence": "weekly",
                "weekday": 0,
                "day_of_month": 7,
                "active": True,
            },
            {
                "id": "w2",
                "title": "Đi học",
                "start_date": "2026-09-08",
                "time": "09:20",
                "end_time": "18:20",
                "recurrence": "weekly",
                "weekday": 1,
                "day_of_month": 8,
                "active": True,
            },
            {
                "id": "m1",
                "title": "Đi học",
                "start_date": "2026-08-26",
                "time": "09:20",
                "end_time": "16:40",
                "recurrence": "monthly",
                "weekday": 2,
                "day_of_month": 26,
                "active": True,
            },
        ],
    }
    data = list_events(user, on_date="2026-09-01")
    tpls = active_templates(user)
    assert not any(t["recurrence"] == "monthly" for t in tpls), tpls
    assert len([t for t in tpls if t["recurrence"] == "weekly"]) == 2
    # orphan monthly stored event dropped
    assert "2026-08-26" not in {e["date"] for e in data["events"] if e.get("recurrence") == "monthly"}
    print("OK legacy corrupt cleanup")


def test_spam_save_same_day_recurring():
    user = fresh_user()
    for _ in range(5):
        add_event(user, title="Laws", event_date="2026-08-24", event_time="22:00", event_end_time="08:00", recurrence="weekly")
    assert len(active_templates(user)) == 1
    assert len([e for e in _events_store(user)]) == 0
    dates = dates_for_title(user, "Laws", "2026-08-24")
    assert "2026-08-24" in dates and "2026-08-31" in dates
    print("OK spam save recurring overnight")


def test_auto_mixed_weekdays_no_false_weekly():
    user = fresh_user()
    for ds in ("2026-08-24", "2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28"):
        add_event(user, title="Di hoc", event_date=ds, event_time="09:20", event_end_time="16:40")
    sug = suggest_similar(user, limit=5)
    assert sug and sug[0].get("recurrence") is None, sug
    apply_suggestions(user, sug)
    assert not active_templates(user), active_templates(user)
    print("OK mixed weekdays auto does not invent weekly")


def test_auto_true_weekly_pattern():
    user = fresh_user()
    for ds in ("2026-08-10", "2026-08-17", "2026-08-24"):  # Mondays
        add_event(user, title="Di hoc", event_date=ds, event_time="09:20", event_end_time="16:40")
    sug = suggest_similar(user, limit=5)
    assert sug and sug[0].get("recurrence") == "weekly", sug
    apply_suggestions(user, sug)
    # Bad Thursday monthly clone in same batch
    apply_suggestions(
        user,
        [{"title": "Di hoc", "date": "2026-09-24", "time": "09:20", "end_time": "16:40", "recurrence": "monthly"}],
    )
    assert "2026-09-24" not in dates_for_title(user, "Di hoc", "2026-09-01")
    print("OK true weekly pattern + reject Thursday monthly auto")


if __name__ == "__main__":
    test_month_panel_focus_expansion()
    test_screenshot_desync_data_shape()
    test_save_each_day_then_auto_suggest()
    test_multiple_same_day_and_edit_scopes()
    test_legacy_corrupt_store_cleanup()
    test_spam_save_same_day_recurring()
    test_auto_mixed_weekdays_no_false_weekly()
    test_auto_true_weekly_pattern()
    print("\nALL SCHEDULE FLOW TESTS PASSED")

