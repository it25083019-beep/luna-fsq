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
    from care_memory import maybe_daily_care_notification

    maybe_daily_care_notification(user)

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
    from care_memory import maybe_daily_care_notification

    maybe_daily_care_notification(user)
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
    from money_eval import evaluate_money, profile_snapshot, spend_pace_snapshot

    ensure_life_modules(user)
    summary = summarize_module(user, "money")
    structured = dict(summary.get("structured") or {})
    baseline = summary.get("baseline") or {}
    evaluation = evaluate_money(user, structured)
    pace = spend_pace_snapshot(structured)
    return {
        **evaluation,
        **pace,
        "profile": profile_snapshot(structured),
        "baseline": baseline,
        "notes": (summary.get("notes") or [])[-6:],
    }


def save_money_profile(
    user: Dict[str, Any],
    profile: Dict[str, Any],
    note: Optional[str] = None,
) -> Dict[str, Any]:
    from money_eval import apply_money_evaluation, sanitize_money_profile

    clean = sanitize_money_profile(profile)
    ensure_life_modules(user)
    row = user["life_modules"]["money"]
    structured = dict(row.get("structured") or {})
    structured.update(clean)
    apply_money_evaluation(user, structured)
    update_module_structured(
        user,
        "money",
        structured,
        note or "お金プロフィールを更新",
    )
    return money_dashboard(user)


def add_money_spend(
    user: Dict[str, Any],
    *,
    amount: int,
    note: Optional[str] = None,
    on_date: Optional[str] = None,
) -> Dict[str, Any]:
    from money_eval import append_spend_entry, apply_money_evaluation

    ensure_life_modules(user)
    row = user["life_modules"]["money"]
    structured = dict(row.get("structured") or {})
    append_spend_entry(structured, amount=amount, note=note or "", on_date=on_date)
    apply_money_evaluation(user, structured)
    update_module_structured(
        user,
        "money",
        structured,
        note or f"今日の支出 +{int(amount):,}円",
    )
    return money_dashboard(user)
