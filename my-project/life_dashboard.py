"""Dashboard payloads for health / money subviews (charts + summary metrics)."""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional

from health_eval import (
    MENTAL_CHOICES,
    apply_health_evaluation,
    evaluate_health,
    mental_needed,
    mental_reminder_due,
    profile_snapshot,
    record_mental_status,
    sanitize_health_profile,
)
from life_modules import ensure_life_modules, summarize_module, update_module_structured

_MONTH_LABELS = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"]


def _parse_int(value: Any, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value)
    nums = re.findall(r"\d+", text.replace(",", ""))
    return int(nums[0]) if nums else default


def health_dashboard(user: Dict[str, Any]) -> Dict[str, Any]:
    ensure_life_modules(user)
    summary = summarize_module(user, "health")
    structured = dict(summary.get("structured") or {})
    baseline = summary.get("baseline") or {}

    evaluation = evaluate_health(structured)
    needed = mental_needed(structured)
    remind = mental_reminder_due(structured)
    if remind:
        note = "LUNAが今日の気分を聞きたいよ"
        if user.get("pending_notification") != note:
            user["pending_notification"] = note

    return {
        "score": evaluation["score"],
        "status_ja": evaluation["status_ja"],
        "message_ja": evaluation["message_ja"],
        "breakdown": evaluation["breakdown"],
        "tips_ja": evaluation.get("tips_ja") or [],
        "bmi": evaluation.get("bmi"),
        "age": evaluation.get("age"),
        "bmi_range_ja": evaluation.get("bmi_range_ja"),
        "goal_suggestions": evaluation.get("goal_suggestions") or structured.get("goal_suggestions") or [],
        "exercise_suggestions": evaluation.get("exercise_suggestions")
        or structured.get("exercise_suggestions")
        or [],
        "profile": profile_snapshot(structured),
        "mental_needed": needed,
        "mental_reminder": remind,
        "mental_choices": list(MENTAL_CHOICES),
        "mental_status": structured.get("mental_status"),
        "mental_checked_on": structured.get("mental_checked_on"),
        "baseline": baseline,
        "pending_notification": user.get("pending_notification"),
    }


def save_health_profile(
    user: Dict[str, Any],
    profile: Dict[str, Any],
    note: Optional[str] = None,
) -> Dict[str, Any]:
    clean = sanitize_health_profile(profile)
    ensure_life_modules(user)
    row = user["life_modules"]["health"]
    structured = dict(row.get("structured") or {})
    structured.update(clean)
    apply_health_evaluation(structured)
    update_module_structured(
        user,
        "health",
        structured,
        note or "健康プロフィールを更新",
    )
    return health_dashboard(user)


def save_mental_checkin(user: Dict[str, Any], status: str) -> Dict[str, Any]:
    ensure_life_modules(user)
    row = user["life_modules"]["health"]
    structured = dict(row.get("structured") or {})
    record_mental_status(structured, status)
    update_module_structured(
        user,
        "health",
        structured,
        note=f"今日の気分: {status}",
    )
    if user.get("pending_notification") == "LUNAが今日の気分を聞きたいよ":
        user["pending_notification"] = None
    return health_dashboard(user)


def mental_status_payload(user: Dict[str, Any]) -> Dict[str, Any]:
    ensure_life_modules(user)
    structured = dict(
        (user.get("life_modules") or {}).get("health", {}).get("structured") or {}
    )
    today = date.today().isoformat()
    needed = mental_needed(structured)
    remind = mental_reminder_due(structured)
    if remind:
        user["pending_notification"] = "LUNAが今日の気分を聞きたいよ"
    return {
        "needed": needed,
        "reminder": remind,
        "last_date": structured.get("mental_checked_on"),
        "today": today,
        "status": structured.get("mental_status"),
        "choices": list(MENTAL_CHOICES),
        "pending_notification": user.get("pending_notification"),
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
