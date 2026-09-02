"""Care timeline — what LUNA noticed today (mood, spend, study, schedule)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

KIND_ICON = {
    "health": "💚",
    "money": "👛",
    "schedule": "📅",
    "study": "⚔️",
    "care": "🌸",
    "goal": "🎯",
}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _day_key(iso: str) -> str:
    return (iso or "")[:10]


def append_care_event(
    user: Dict[str, Any],
    kind: str,
    label: str,
    *,
    detail: Optional[str] = None,
    at: Optional[str] = None,
) -> Dict[str, Any]:
    """Append one timeline row (keeps last 80)."""
    row = {
        "at": at or _utcnow_iso(),
        "kind": kind or "care",
        "label": (label or "").strip()[:120],
        "detail": (detail or "").strip()[:160] or None,
        "icon": KIND_ICON.get(kind or "care", "🌸"),
    }
    log = list(user.get("care_timeline") or [])
    if log and log[-1].get("label") == row["label"] and _day_key(log[-1].get("at", "")) == _day_key(row["at"]):
        return row
    log.append(row)
    user["care_timeline"] = log[-80:]
    return row


def _module_events_today(user: Dict[str, Any], today: str) -> List[Dict[str, Any]]:
    """Derive display rows from life modules when not yet in care_timeline."""
    out: List[Dict[str, Any]] = []
    modules = user.get("life_modules") or {}
    health = (modules.get("health") or {}).get("structured") or {}
    money = (modules.get("money") or {}).get("structured") or {}

    checked = str(health.get("mental_checked_on") or "")[:10]
    if checked == today and health.get("mental_status"):
        out.append(
            {
                "at": f"{today}T12:00:00+00:00",
                "kind": "health",
                "label": f"気分「{health['mental_status']}」",
                "detail": None,
                "icon": KIND_ICON["health"],
                "source": "module",
            }
        )

    for s in money.get("daily_spends") or []:
        if not isinstance(s, dict):
            continue
        if str(s.get("date") or "")[:10] != today:
            continue
        amt = s.get("amount")
        note = (s.get("note") or s.get("category") or "支出").strip()
        out.append(
            {
                "at": f"{today}T14:00:00+00:00",
                "kind": "money",
                "label": f"{note} {int(amt):,}円" if amt else note,
                "detail": None,
                "icon": KIND_ICON["money"],
                "source": "module",
            }
        )

    j = ((user.get("rpg") or {}).get("journey") or {})
    for row in j.get("completion_log") or []:
        if not isinstance(row, dict):
            continue
        if _day_key(str(row.get("at") or "")) != today:
            continue
        title = row.get("title_ja") or row.get("lesson_id") or "学習"
        out.append(
            {
                "at": row.get("at") or f"{today}T16:00:00+00:00",
                "kind": "study",
                "label": f"学習クリア：{title}",
                "detail": row.get("detail"),
                "icon": KIND_ICON["study"],
                "source": "module",
            }
        )

    cm = user.get("care_memory") or {}
    for note in cm.get("notes") or []:
        if not isinstance(note, dict):
            continue
        if str(note.get("d") or "")[:10] != today:
            continue
        topic = note.get("t") or "care"
        kind = "health" if topic == "health" else "money" if topic == "money" else "care"
        snippet = (note.get("s") or "").strip()
        if not snippet:
            continue
        out.append(
            {
                "at": f"{today}T10:00:00+00:00",
                "kind": kind,
                "label": snippet[:80],
                "detail": "相談メモ",
                "icon": KIND_ICON.get(kind, "🌸"),
                "source": "care_memory",
            }
        )

    return out


def build_care_timeline(user: Dict[str, Any], *, day: Optional[str] = None) -> List[Dict[str, Any]]:
    """Today's care journal rows, newest last (UI can reverse)."""
    today = day or date.today().isoformat()
    stored = [
        dict(x)
        for x in (user.get("care_timeline") or [])
        if isinstance(x, dict) and _day_key(str(x.get("at") or "")) == today
    ]
    labels = {x.get("label") for x in stored}
    for row in _module_events_today(user, today):
        if row.get("label") not in labels:
            stored.append(row)
            labels.add(row.get("label"))
    stored.sort(key=lambda x: str(x.get("at") or ""))
    return stored[-20:]


def build_weekly_review(user: Dict[str, Any], *, today: Optional[date] = None) -> Optional[Dict[str, Any]]:
    """Sunday-style weekly recap from real module + timeline data."""
    today = today or date.today()
    week_start = today - timedelta(days=today.weekday())
    week_days = [(week_start + timedelta(days=i)).isoformat() for i in range(7)]

    events = [x for x in (user.get("care_timeline") or []) if isinstance(x, dict)]
    week_events = [e for e in events if _day_key(str(e.get("at") or "")) in week_days]

    health = (user.get("life_modules") or {}).get("health", {}).get("structured") or {}
    money = (user.get("life_modules") or {}).get("money", {}).get("structured") or {}
    j = ((user.get("rpg") or {}).get("journey") or {})
    completions = [
        x
        for x in (j.get("completion_log") or [])
        if isinstance(x, dict) and _day_key(str(x.get("at") or "")) in week_days
    ]

    spend_total = 0
    spend_days = set()
    for s in money.get("daily_spends") or []:
        if not isinstance(s, dict):
            continue
        d = str(s.get("date") or "")[:10]
        if d not in week_days:
            continue
        spend_days.add(d)
        try:
            spend_total += int(s.get("amount") or 0)
        except (TypeError, ValueError):
            pass

    mood = health.get("mental_status")
    study_n = len(completions)
    care_n = len(week_events) + len(completions)

    if not week_events and not completions and not spend_days and not mood:
        return None

    highlights: List[str] = []
    if study_n:
        highlights.append(f"学習クエスト {study_n} 回クリア")
    if spend_days:
        highlights.append(f"支出記録 {len(spend_days)} 日（合計 {spend_total:,}円）")
    if mood:
        highlights.append(f"直近の気分：{mood}")
    if not highlights:
        highlights.append("今週も LUNA と一緒に記録を続けよう")

    goal = "明日は気分をひとこと教えてね" if not mood else "来週も小さな一歩を続けよう"

    return {
        "week_label": f"{week_start.month}/{week_start.day}〜",
        "highlights": highlights[:4],
        "study_count": study_n,
        "care_count": care_n,
        "spend_total": spend_total,
        "goal_next_week": goal,
        "show_banner": today.weekday() == 6 or care_n >= 3,
    }
