"""Dashboard payloads for health / money subviews (charts + summary metrics)."""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List

from life_modules import ensure_life_modules, summarize_module

_MONTH_LABELS = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"]


def _parse_int(value: Any, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value)
    nums = re.findall(r"\d+", text.replace(",", ""))
    return int(nums[0]) if nums else default


def _default_sleep_history(score: int) -> List[Dict[str, Any]]:
    base = max(60, min(98, score))
    return [
        {"month": _MONTH_LABELS[i], "score": max(55, min(98, base - 6 + i * 2))}
        for i in range(6)
    ]


def _default_steps_history(steps: int) -> List[Dict[str, Any]]:
    base = max(3000, steps)
    return [
        {"month": _MONTH_LABELS[i], "steps": max(2000, int(base * (0.72 + i * 0.05)))}
        for i in range(6)
    ]


def health_dashboard(user: Dict[str, Any]) -> Dict[str, Any]:
    summary = summarize_module(user, "health")
    structured = dict(summary.get("structured") or {})
    baseline = summary.get("baseline") or {}

    score = _parse_int(structured.get("score"), 85)
    steps = _parse_int(structured.get("steps"), 10500)
    heart_rate = _parse_int(structured.get("heart_rate"), 72)
    water = _parse_int(structured.get("water_glasses"), 6)
    water_goal = max(1, _parse_int(structured.get("water_goal"), 8))

    sleep_history = structured.get("sleep_history") or _default_sleep_history(score)
    steps_history = structured.get("steps_history") or _default_steps_history(steps)

    if baseline.get("health_sleep") and score == 85:
        score = min(95, score + 2)
    if baseline.get("health_lifestyle"):
        steps = max(steps, 9000)

    status = "良好" if score >= 75 else "注意"
    message = structured.get("message_ja") or "今日もバッチリだね！この調子で頑張ろう！"

    return {
        "score": score,
        "status_ja": status,
        "steps": steps,
        "heart_rate": heart_rate,
        "water_glasses": water,
        "water_goal": water_goal,
        "message_ja": message,
        "sleep_history": sleep_history,
        "steps_history": steps_history,
        "baseline": baseline,
    }


def _default_balance_history(balance: int) -> List[Dict[str, Any]]:
    cur = max(10000, balance)
    return [
        {"month": _MONTH_LABELS[i], "balance": max(5000, int(cur * (0.82 + i * 0.04)))}
        for i in range(5)
    ]


def _default_categories(expense: int) -> List[Dict[str, Any]]:
    total = max(expense, 1)
    parts = [("食費", 0.32), ("住居", 0.28), ("交通", 0.12), ("娯楽", 0.18), ("貯蓄", 0.10)]
    return [{"name": name, "amount": int(total * ratio)} for name, ratio in parts]


def money_dashboard(user: Dict[str, Any]) -> Dict[str, Any]:
    summary = summarize_module(user, "money")
    structured = dict(summary.get("structured") or {})
    baseline = summary.get("baseline") or {}

    income = _parse_int(structured.get("income"), _parse_int(baseline.get("money_income"), 120000))
    expense = _parse_int(structured.get("expense"), _parse_int(baseline.get("money_expense"), 90000))
    income_goal = max(income, _parse_int(structured.get("income_goal"), int(income * 1.08)))
    expense_budget = max(expense, _parse_int(structured.get("expense_budget"), int(expense * 1.15)))
    savings_total = _parse_int(structured.get("savings_total"), 2500000)
    savings_target = max(savings_total, _parse_int(structured.get("savings_target"), 3000000))

    balance_history = structured.get("balance_history") or _default_balance_history(
        _parse_int(structured.get("current_balance"), 45678)
    )
    categories = structured.get("expense_categories") or _default_categories(expense)
    accounts = structured.get("accounts") or [
        {"name": "定期預金A", "amount": int(savings_total * 0.4), "pct": 70},
        {"name": "投資信託B", "amount": int(savings_total * 0.32), "pct": 55},
        {"name": "つみたてC", "amount": int(savings_total * 0.28), "pct": 48},
    ]

    message = structured.get("message_ja") or "今月の予算は大丈夫かな？一緒に家計簿をチェックしよう！"
    notes = (summary.get("notes") or [])[-6:]

    return {
        "income": income,
        "expense": expense,
        "income_goal": income_goal,
        "expense_budget": expense_budget,
        "income_pct": min(100, int(income / max(1, income_goal) * 100)),
        "expense_pct": min(100, int(expense / max(1, expense_budget) * 100)),
        "savings_total": savings_total,
        "savings_target": savings_target,
        "savings_pct": min(100, int(savings_total / max(1, savings_target) * 100)),
        "current_balance": _parse_int(structured.get("current_balance"), balance_history[-1]["balance"]),
        "balance_history": balance_history,
        "expense_categories": categories,
        "accounts": accounts,
        "message_ja": message,
        "notes": notes,
        "baseline": baseline,
    }
