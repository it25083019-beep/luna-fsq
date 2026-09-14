# -*- coding: utf-8 -*-
"""Future twin, risk radar, council, portfolio export."""
from __future__ import annotations

from datetime import date, datetime, timezone

from companion_council import build_council, normalize_advisor_style, resolve_advisor_style
from future_twin_service import build_future_twin
from portfolio_export_service import render_export_html
from risk_radar_service import complete_rescue_quest, refresh_risk_radar


def _user(**extra):
    today = date.today().isoformat()
    base = {
        "user_display_name": "試験",
        "total_exp": 400,
        "current_level": 3,
        "daily_exp": 0,
        "advisor_style": "auto",
        "life_modules": {
            "health": {"structured": {"mental_status": "疲れ", "sleep_hours": 5, "mental_checked_on": today}},
            "money": {
                "structured": {
                    "monthly_expense": 30000,
                    "spend_log": [{"date": today, "amount": 8000, "note": "lunch"}],
                }
            },
            "goals": {"structured": {"items": [{"id": "g1", "title": "貯金", "current": 2, "target": 20, "pct": 10, "done": False}]}},
            "schedule": {"structured": {"events": [
                {"id": "e1", "title": "授業", "date": today, "time": "09:00", "minutes": 120, "done": False},
                {"id": "e2", "title": "バイト", "date": today, "time": "13:00", "minutes": 180, "done": False},
                {"id": "e3", "title": "課題", "date": today, "time": "19:00", "minutes": 90, "done": False},
            ]}},
        },
        "rpg": {"journey": {"career_id": "demo", "skills": [{"id": "s1", "label_ja": "基礎"}], "completed_lessons": [], "boss_clears": [], "completion_log": [], "portfolio_evidence": []}},
    }
    base.update(extra)
    return base


def test_twin_splits_futures():
    twin = build_future_twin(_user())
    assert twin["ok"]
    assert twin["week"]["b"]["level"] >= twin["week"]["a"]["level"]
    assert twin["week"]["b"]["stress"] <= twin["week"]["a"]["stress"]
    assert "起きる前" in twin["tagline_ja"]
    print("OK twin splits A/B")


def test_radar_makes_24h_rescue():
    user = _user()
    radar = refresh_risk_radar(user, now=datetime.now(timezone.utc))
    assert radar["alerts"]
    q = radar["alerts"][0]["rescue"]
    assert q["status"] == "open"
    assert q["expires_at"]
    out = complete_rescue_quest(user, q["id"])
    assert out["ok"]
    assert out["exp_gained"] >= 0
    assert out["quest"]["status"] == "done"
    print("OK radar rescue 24h")


def test_council_auto_picks_from_state():
    user = _user()
    facts = {"mental": "落ち込み", "load": "recover", "pace_level": "ok", "open_goals": 1, "goal_avg": 10}
    assert resolve_advisor_style(user, facts) == "empathic"
    user["advisor_style"] = "strict"
    assert normalize_advisor_style(user["advisor_style"]) == "strict"
    council = build_council(user)
    assert len(council["voices"]) == 3
    print("OK council styles")


def test_export_html_has_cv():
    html = render_export_html(_user())
    assert "学習CV" in html
    assert "ボス攻略記" in html
    print("OK export html")


if __name__ == "__main__":
    test_twin_splits_futures()
    test_radar_makes_24h_rescue()
    test_council_auto_picks_from_state()
    test_export_html_has_cv()
    print("ALL future shock tests passed")
