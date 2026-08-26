"""Tests for goals module and money daily spend pace."""
from datetime import date

from goals_service import add_goal, delete_goal, goals_dashboard, home_goals_summary, update_goal
from money_eval import append_spend_entry, spend_pace_snapshot
from life_dashboard import add_money_spend, money_dashboard
from schedule_service import home_summary


def test_goals_crud_and_home_label():
    user = {"life_modules": {}}
    dash = add_goal(user, {"title": "イヤホン", "current": 3000, "target": 15000, "unit": "円"})
    assert dash["total"] == 1
    assert dash["items"][0]["pct"] == 20
    gid = dash["items"][0]["id"]
    dash = update_goal(user, gid, {"current": 15000})
    assert dash["items"][0]["pct"] == 100
    assert dash["done"] == 1
    add_goal(user, {"title": "運動", "current": 2, "target": 10, "unit": "回"})
    home = home_goals_summary(user)
    assert home["total"] == 2
    assert "進行中" in home["label"] or "達成" in home["label"]
    dash = delete_goal(user, gid)
    assert dash["total"] == 1
    print("OK goals crud", home["label"])


def test_spend_pace_warning():
    structured = {
        "monthly_expense": 30000,
        "spend_log": [],
    }
    append_spend_entry(structured, amount=5000, note="lunch")
    pace = spend_pace_snapshot(structured, today=date.today())
    assert pace["today_spent"] == 5000
    assert pace["daily_budget"] > 0
    assert pace["pace_warning_ja"]
    print("OK spend pace", pace["pace_level"], pace["today_spent"])


def test_add_money_spend_dashboard():
    user = {"life_modules": {"money": {"notes": [], "structured": {"monthly_expense": 30000}, "updated_at": None}}}
    dash = add_money_spend(user, amount=1200, note="cafe")
    assert dash["today_spent"] >= 1200
    assert "pace_warning_ja" in dash
    print("OK money spend dashboard", dash["today_spent"])


def test_home_summary_uses_goals_items():
    user = {
        "life_modules": {
            "health": {"notes": [], "structured": {}, "updated_at": None},
            "schedule": {"notes": [], "structured": {"events": []}, "updated_at": None},
        }
    }
    add_goal(user, {"title": "PC", "current": 0, "target": 100000})
    s = home_summary(user)
    assert s["goals"]["total"] == 1
    assert s["goals"]["label"]
    print("OK home summary goals", s["goals"])


if __name__ == "__main__":
    test_goals_crud_and_home_label()
    test_spend_pace_warning()
    test_add_money_spend_dashboard()
    test_home_summary_uses_goals_items()
    print("ALL OK")
