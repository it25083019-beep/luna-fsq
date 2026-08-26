"""Tests for age-aware money buckets."""
from __future__ import annotations

from life_modules import ensure_life_modules
from money_eval import age_band, bucket_template, evaluate_money, sanitize_money_profile
from life_dashboard import money_dashboard, save_money_profile


def fresh_user(age=None):
    user = {"life_modules": {}, "life_profile": {}, "rpg": {}}
    ensure_life_modules(user)
    if age is not None:
        user["life_modules"]["health"]["structured"]["age"] = age
    return user


def test_teen_hides_invest():
    keys = {f["key"] for f in bucket_template("teen", 30000)}
    assert "invest" not in keys
    assert "emergency" in keys and "purchase" in keys
    print("OK teen buckets")


def test_adult_has_invest():
    keys = {f["key"] for f in bucket_template("adult", 120000)}
    assert keys == {"purchase", "emergency", "reserve", "invest"}
    print("OK adult buckets")


def test_evaluate_reads_health_age():
    user = fresh_user(age=16)
    ev = evaluate_money(
        user,
        {
            "monthly_income": 20000,
            "monthly_expense": 12000,
            "purchase_name": "イヤホン",
            "purchase_current": 5000,
            "purchase_target": 15000,
            "emergency_current": 3000,
            "emergency_target": 10000,
        },
    )
    assert ev["age"] == 16
    assert ev["age_band"] == "teen"
    assert all(f["key"] != "invest" for f in ev["funds"])
    assert ev["score"] >= 0
    assert ev["tips_ja"]
    print("OK teen evaluate", ev["score"], ev["status_ja"])


def test_invest_before_emergency_lowers():
    user = fresh_user(age=28)
    weak = evaluate_money(
        user,
        {
            "monthly_income": 200000,
            "monthly_expense": 150000,
            "emergency_current": 10000,
            "emergency_target": 600000,
            "invest_current": 200000,
            "invest_target": 200000,
        },
    )
    strong = evaluate_money(
        user,
        {
            "monthly_income": 200000,
            "monthly_expense": 150000,
            "emergency_current": 500000,
            "emergency_target": 600000,
            "invest_current": 200000,
            "invest_target": 200000,
        },
    )
    assert weak["score"] < strong["score"], (weak["score"], strong["score"])
    print("OK emergency-before-invest scoring")


def test_save_money_profile():
    user = fresh_user(age=22)
    dash = save_money_profile(
        user,
        {
            "monthly_income": "150000",
            "monthly_expense": 100000,
            "purchase_name": "PC",
            "purchase_current": 20000,
            "purchase_target": 100000,
            "emergency_current": 50000,
            "reserve_current": 10000,
        },
    )
    assert dash["monthly_income"] == 150000
    assert dash["profile"]["purchase_name"] == "PC"
    assert any(f["key"] == "invest" for f in dash["funds"])
    assert "steps" not in dash
    print("OK save money profile", dash["score"])


def test_sanitize():
    clean = sanitize_money_profile({"monthly_income": "12,000", "purchase_name": "  bag  "})
    assert clean["monthly_income"] == 12000
    assert clean["purchase_name"] == "bag"
    print("OK sanitize money")


def test_age_bands():
    assert age_band(15) == "teen"
    assert age_band(20) == "young"
    assert age_band(30) == "adult"
    assert age_band(50) == "senior"
    print("OK age bands")


def test_dashboard_empty_safe():
    user = fresh_user()
    dash = money_dashboard(user)
    assert "funds" in dash and "score" in dash
    print("OK empty money dashboard")


if __name__ == "__main__":
    test_teen_hides_invest()
    test_adult_has_invest()
    test_evaluate_reads_health_age()
    test_invest_before_emergency_lowers()
    test_save_money_profile()
    test_sanitize()
    test_age_bands()
    test_dashboard_empty_safe()
    print("\nALL MONEY TESTS PASSED")
