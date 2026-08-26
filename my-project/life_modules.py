"""Life support modules: health / money / schedule.

Initial PROFILE_QUESTIONS fill a baseline. Users can append more notes
into each module anytime after onboarding.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

MODULE_KEYS = ("health", "money", "schedule", "goals")

MODULE_META = {
    "health": {
        "title_ja": "健康",
        "hint_ja": "睡眠・食事・運動・体調。後から追記できます。",
        "profile_keys": (
            "health_sleep",
            "health_body",
            "health_lifestyle",
            "mental_mood",
            "mental_stress",
            "mental_support",
        ),
    },
    "money": {
        "title_ja": "お金",
        "hint_ja": "収入・支出・目標・欲しいもの。時給なども追記可。",
        "profile_keys": ("money_income", "money_expense", "money_goal"),
    },
    "schedule": {
        "title_ja": "スケジュール",
        "hint_ja": "授業・バイト・締切。後から予定を足せます。",
        "profile_keys": ("time_weekday", "time_weekend", "study_future", "goals"),
    },
    "goals": {
        "title_ja": "目標",
        "hint_ja": "欲しいもの・達成したいこと。いくつでも追加できます。",
        "profile_keys": (),
    },
}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_life_modules(user: Dict[str, Any]) -> Dict[str, Any]:
    modules = user.setdefault("life_modules", {})
    for key in MODULE_KEYS:
        row = modules.setdefault(key, {})
        row.setdefault("notes", [])
        row.setdefault("structured", {})
        row.setdefault("updated_at", None)
    return modules


def summarize_module(user: Dict[str, Any], module: str) -> Dict[str, Any]:
    if module not in MODULE_KEYS:
        raise ValueError("invalid module")
    ensure_life_modules(user)
    profile = user.get("life_profile") or {}
    meta = MODULE_META[module]
    baseline = {k: profile.get(k) for k in meta["profile_keys"] if profile.get(k)}
    row = user["life_modules"][module]
    return {
        "module": module,
        "title_ja": meta["title_ja"],
        "hint_ja": meta["hint_ja"],
        "baseline": baseline,
        "notes": list(row.get("notes") or []),
        "structured": dict(row.get("structured") or {}),
        "updated_at": row.get("updated_at"),
        "profile_complete": bool(user.get("profile_complete")),
    }


def list_modules(user: Dict[str, Any]) -> Dict[str, Any]:
    ensure_life_modules(user)
    return {
        "profile_complete": bool(user.get("profile_complete")),
        "modules": [summarize_module(user, k) for k in MODULE_KEYS],
    }


def append_module_note(
    user: Dict[str, Any],
    module: str,
    note: str,
    structured: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if module not in MODULE_KEYS:
        raise ValueError("invalid module")
    text = (note or "").strip()
    if not text:
        raise ValueError("note is required")
    ensure_life_modules(user)
    row = user["life_modules"][module]
    entry = {"text": text[:2000], "at": _utcnow_iso()}
    row.setdefault("notes", []).append(entry)
    # keep last 40 notes
    row["notes"] = row["notes"][-40:]
    if structured:
        row.setdefault("structured", {}).update(structured)
    row["updated_at"] = _utcnow_iso()
    return summarize_module(user, module)


def update_module_structured(
    user: Dict[str, Any],
    module: str,
    structured: Dict[str, Any],
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """Merge structured metrics; optionally append a note."""
    if module not in MODULE_KEYS:
        raise ValueError("invalid module")
    if not isinstance(structured, dict) or not structured:
        raise ValueError("structured is required")
    ensure_life_modules(user)
    row = user["life_modules"][module]
    row.setdefault("structured", {}).update(structured)
    text = (note or "").strip()
    if text:
        row.setdefault("notes", []).append({"text": text[:2000], "at": _utcnow_iso()})
        row["notes"] = row["notes"][-40:]
    else:
        row.setdefault("notes", []).append({"text": "手動で数値を更新", "at": _utcnow_iso()})
        row["notes"] = row["notes"][-40:]
    row["updated_at"] = _utcnow_iso()
    return summarize_module(user, module)


def modules_prompt_block(user: Dict[str, Any]) -> str:
    """Inject into companion system prompt."""
    ensure_life_modules(user)
    lines: List[str] = [
        "LIFE MODULES (baseline from first meeting + later notes). "
        "Initial questions are only a start; user may add details anytime.",
    ]
    for key in MODULE_KEYS:
        s = summarize_module(user, key)
        lines.append(f"### {s['title_ja']} ({key})")
        if s["baseline"]:
            lines.append("baseline: " + "; ".join(f"{k}={v}" for k, v in s["baseline"].items()))
        else:
            lines.append("baseline: (empty)")
        notes = s["notes"][-5:]
        if notes:
            lines.append("recent notes: " + " | ".join(n["text"] for n in notes))
        if s["structured"]:
            lines.append("structured: " + str(s["structured"]))
    lines.append(
        "When user asks to update health/money/schedule, acknowledge and store facts in memory; "
        "UI also has /life endpoints for explicit append."
    )
    return "\n".join(lines)
