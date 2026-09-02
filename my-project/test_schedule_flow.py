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
            "id": t.get("id"),
            "recurrence": t.get("recurrence"),
            "weekday": t.get("weekday"),
            "day_of_month": t.get("day_of_month"),
            "title": t.get("title"),
            "time": t.get("time"),
            "end_time": t.get("end_time"),
            "active": t.get("active", True),
            "start_date": t.get("start_date"),
            "horizon_end": t.get("horizon_end"),
        }
        for t in _recurring_store(user)
        if t.get("active", True)
    ]


def test_month_panel_focus_expansion():
    """Within the month window, browsing that month shows recurring dots."""
    user = fresh_user()
    add_event(user, title="Di hoc", event_date="2026-08-24", event_time="09:20", event_end_time="16:40", recurrence="weekly")
    add_event(user, title="Di hoc", event_date="2026-08-25", event_time="09:20", event_end_time="16:40", recurrence="weekly")
    # Focus March 2027 (still inside 1-year horizon) — events appear for that month only.
    data = list_events(user, on_date="2027-03-15")
    dates = {e["date"] for e in data["events"] if e.get("title") == "Di hoc"}
    assert "2027-03-01" in dates, dates
    assert "2027-03-02" in dates, dates
    assert "2027-03-29" in dates, dates
    assert "2027-03-30" in dates, dates
    # Aug 2026 is outside the March focus window — not dumped into this response.
    assert "2026-08-24" not in dates, dates
    # Past the 1-year horizon: no materialization until user extends
    data2 = list_events(user, on_date="2030-06-01")
    dates2 = {e["date"] for e in data2["events"] if e.get("title") == "Di hoc"}
    assert not any(d.startswith("2030-06") for d in dates2), dates2
    assert data2["extend_prompt"]["needed"] is True, data2["extend_prompt"]
    # Payload stays bounded (no multi-year dump in one response)
    assert len(data["events"]) < 80, len(data["events"])
    print("OK month expansion within focus window + extend prompt beyond")




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


def test_collapse_same_weekday_time_slot_clones():
    """JP/AI title clones on the same Mon+time must collapse to one series."""
    user = fresh_user()
    add_event(
        user,
        title="Đi học",
        event_date="2026-08-24",
        event_time="21:20",
        recurrence="weekly",
    )
    add_event(
        user,
        title="学校の授業",
        event_date="2026-08-24",
        event_time="21:20",
        recurrence="weekly",
    )
    add_event(
        user,
        title="Works",
        event_date="2026-08-24",
        event_time="22:00",
        event_end_time="08:00",
        recurrence="weekly",
    )
    add_event(
        user,
        title="夜間アルバイト",
        event_date="2026-08-24",
        event_time="22:00",
        event_end_time="08:00",
        recurrence="weekly",
    )
    # Trigger cleanup via list
    items = titles_on(user, "2026-08-24")
    titles = [t[0] for t in items]
    assert len(active_templates(user)) == 2, active_templates(user)
    assert len(titles) == 2, titles
    assert "Đi học" in titles or "学校の授業" in titles
    assert "Works" in titles or "夜間アルバイト" in titles
    print("OK same weekday+time slot clones collapsed")


def test_one_year_horizon_and_extend_prompt():
    from schedule_service import extend_recurring_horizons

    user = fresh_user()
    add_event(
        user,
        title="Laws",
        event_date="2025-09-01",
        event_time="22:00",
        event_end_time="08:00",
        recurrence="weekly",
    )
    tpls = active_templates(user)
    assert len(tpls) == 1
    assert tpls[0].get("horizon_end") == "2026-09-01", tpls[0]

    # Near end of horizon: events exist before, not after.
    near = "2026-08-24"
    dates = dates_for_title(user, "Laws", near)
    assert "2026-08-24" in dates or "2026-08-31" in dates
    far = "2026-09-14"
    assert "2026-09-14" not in dates_for_title(user, "Laws", far)

    prompt = list_events(user, on_date="2026-08-20")["extend_prompt"]
    assert prompt["needed"] is True, prompt
    assert any(t["title"] == "Laws" for t in prompt["templates"])

    result = extend_recurring_horizons(user, template_ids=[tpls[0]["id"]], days=365)
    assert result["count"] == 1
    # Extension anchors on whichever is later, the old horizon or today, so a
    # horizon that has already elapsed does not extend into the past.
    from datetime import date as _date, timedelta as _timedelta

    anchor = max(_date(2026, 9, 1), _date.today())
    assert active_templates(user)[0]["horizon_end"] == (anchor + _timedelta(days=365)).isoformat()
    assert "2026-09-14" in dates_for_title(user, "Laws", "2026-09-14")
    prompt2 = list_events(user, on_date="2026-08-20")["extend_prompt"]
    assert prompt2["needed"] is False, prompt2
    print("OK 1-year horizon + extend prompt")


if __name__ == "__main__":
    test_month_panel_focus_expansion()
    test_screenshot_desync_data_shape()
    test_save_each_day_then_auto_suggest()
    test_multiple_same_day_and_edit_scopes()
    test_legacy_corrupt_store_cleanup()
    test_spam_save_same_day_recurring()
    test_auto_mixed_weekdays_no_false_weekly()
    test_auto_true_weekly_pattern()
    test_collapse_same_weekday_time_slot_clones()
    test_one_year_horizon_and_extend_prompt()
    print("\nALL SCHEDULE FLOW TESTS PASSED")

