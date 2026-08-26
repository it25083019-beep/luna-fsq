"""Tests for health profile evaluation and daily mental check-in."""
from __future__ import annotations

from datetime import date, datetime

from health_eval import (
    evaluate_health,
    mental_needed,
    mental_reminder_due,
    record_mental_status,
    sanitize_health_profile,
)
from life_dashboard import health_dashboard, mental_status_payload, save_health_profile, save_mental_checkin
from life_modules import ensure_life_modules


def fresh_user():
    user = {
        "life_modules": {},
        "life_profile": {},
        "rpg": {},
        "pending_notification": None,
    }
    ensure_life_modules(user)
    return user


def test_evaluate_empty_is_safe():
    ev = evaluate_health({})
    assert 0 <= ev["score"] <= 100
    assert ev["status_ja"] in ("良好", "注意", "要ケア")
    assert ev["breakdown"]
    print("OK empty evaluate")


def test_age_aware_bmi_and_coaching():
    teen = evaluate_health(
        {
            "age": 16,
            "weight_kg": 70,
            "height_cm": 165,
            "target_weight_kg": 60,
            "sleep_hours": 6,
            "hobbies": "Osake",
            "mental_status": "普通",
            "mental_checked_on": date.today().isoformat(),
        }
    )
    assert teen["exercise_suggestions"], teen
    assert teen["goal_suggestions"], teen
    assert any("成長" in g or "減量" in g for g in teen["goal_suggestions"]), teen["goal_suggestions"]
    senior = evaluate_health(
        {
            "age": 70,
            "weight_kg": 65,
            "height_cm": 165,
            "sleep_hours": 8,
            "mental_status": "元気",
            "mental_checked_on": date.today().isoformat(),
        }
    )
    assert any("シニア" in x or "散歩" in x for x in senior["exercise_suggestions"]), senior["exercise_suggestions"]
    print("OK age-aware coaching")


def test_evaluate_healthy_profile_high_score():
    s = {
        "age": 20,
        "weight_kg": 55,
        "height_cm": 165,
        "target_weight_kg": 54,
        "target_height_cm": 165,
        "sleep_hours": 8,
        "wake_time": "07:00",
        "bedtime": "23:00",
        "school_hours": 6,
        "study_hours": 2,
        "relax_hours": 2,
        "exercise_plan": "週3ジョギング",
        "mental_status": "元気",
        "mental_checked_on": date.today().isoformat(),
    }
    ev = evaluate_health(s)
    assert ev["score"] >= 80, ev
    assert ev["status_ja"] == "良好"
    assert ev["bmi"] is not None
    assert ev["goal_suggestions"] is not None
    print("OK healthy high score", ev["score"])


def test_evaluate_poor_sleep_lowers():
    good = evaluate_health(
        {
            "sleep_hours": 8,
            "mental_status": "普通",
            "mental_checked_on": date.today().isoformat(),
        }
    )
    bad = evaluate_health(
        {
            "sleep_hours": 4,
            "mental_status": "普通",
            "mental_checked_on": date.today().isoformat(),
        }
    )
    assert bad["score"] < good["score"], (good["score"], bad["score"])
    print("OK poor sleep lowers score")


def test_mental_cadence():
    s = {}
    assert mental_needed(s, today=date(2026, 8, 26)) is True
    record_mental_status(s, "普通", today=date(2026, 8, 26))
    assert s["mental_checked_on"] == "2026-08-26"
    assert mental_needed(s, today=date(2026, 8, 26)) is False
    assert mental_needed(s, today=date(2026, 8, 27)) is True
    assert mental_reminder_due(s, now=datetime(2026, 8, 26, 10, 0, 0)) is False
    assert mental_reminder_due(
        {"mental_checked_on": "2026-08-25"},
        now=datetime(2026, 8, 26, 17, 0, 0),
    ) is True
    print("OK mental cadence")


def test_sanitize_and_save_profile():
    user = fresh_user()
    dash = save_health_profile(
        user,
        {
            "weight_kg": "60",
            "height_cm": 170,
            "sleep_hours": 7.5,
            "wake_time": "6:30",
            "bedtime": "23:00",
            "hobbies": "音楽",
            "school_hours": 6,
            "study_hours": 1.5,
            "relax_hours": 1,
            "exercise_plan": "",
        },
    )
    assert dash["profile"]["wake_time"] == "06:30"
    assert dash["score"] == evaluate_health(user["life_modules"]["health"]["structured"])["score"]
    assert "breakdown" in dash
    print("OK save profile", dash["score"], dash["status_ja"])


def test_mental_checkin_api_helpers():
    user = fresh_user()
    st = mental_status_payload(user)
    assert st["needed"] is True
    dash = save_mental_checkin(user, "元気")
    assert dash["mental_needed"] is False
    assert dash["mental_status"] == "元気"
    st2 = mental_status_payload(user)
    assert st2["needed"] is False
    print("OK mental checkin helpers")


def test_dashboard_no_legacy_wearables():
    user = fresh_user()
    save_health_profile(user, {"weight_kg": 58, "height_cm": 160, "sleep_hours": 8})
    dash = health_dashboard(user)
    assert "steps" not in dash
    assert "water_glasses" not in dash
    assert "profile" in dash
    print("OK dashboard shape")


def test_sanitize_rejects_bad_time_silently():
    clean = sanitize_health_profile({"wake_time": "25:99", "bedtime": "22:00"})
    assert clean.get("wake_time") is None
    assert clean.get("bedtime") == "22:00"
    print("OK sanitize time")


if __name__ == "__main__":
    test_evaluate_empty_is_safe()
    test_evaluate_healthy_profile_high_score()
    test_age_aware_bmi_and_coaching()
    test_evaluate_poor_sleep_lowers()
    test_mental_cadence()
    test_sanitize_and_save_profile()
    test_mental_checkin_api_helpers()
    test_dashboard_no_legacy_wearables()
    test_sanitize_rejects_bad_time_silently()
    print("\nALL HEALTH TESTS PASSED")
