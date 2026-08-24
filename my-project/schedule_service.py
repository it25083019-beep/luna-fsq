"""User schedule / ToDo events with pattern-based similar suggestions."""
from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from life_modules import ensure_life_modules


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_date(s: str) -> date:
    return date.fromisoformat(s[:10])


def _events_store(user: Dict[str, Any]) -> List[Dict[str, Any]]:
    ensure_life_modules(user)
    row = user["life_modules"]["schedule"]
    structured = row.setdefault("structured", {})
    events = structured.setdefault("events", [])
    if not isinstance(events, list):
        structured["events"] = []
    return structured["events"]


def list_events(user: Dict[str, Any], *, on_date: Optional[str] = None) -> Dict[str, Any]:
    events = sorted(_events_store(user), key=lambda e: (e.get("date", ""), e.get("time") or ""))
    today = date.today()
    if on_date:
        try:
            today = _parse_date(on_date)
        except ValueError:
            pass
    today_s = today.isoformat()
    past_done: List[Dict[str, Any]] = []
    today_open: List[Dict[str, Any]] = []
    today_done: List[Dict[str, Any]] = []
    future: List[Dict[str, Any]] = []
    for e in events:
        d = e.get("date") or today_s
        if e.get("done") and d < today_s:
            past_done.append(e)
        elif d == today_s:
            (today_done if e.get("done") else today_open).append(e)
        elif d > today_s:
            future.append(e)
    past_done = past_done[-20:]
    future = future[:30]
    open_count = len([x for x in events if not x.get("done") and (x.get("date") or today_s) >= today_s])
    return {
        "today": today_s,
        "past_done": past_done,
        "today_open": today_open,
        "today_done": today_done,
        "future": future,
        "open_count": open_count,
        "events": events,
    }


def add_event(
    user: Dict[str, Any],
    *,
    title: str,
    event_date: str,
    event_time: Optional[str] = None,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    text = (title or "").strip()
    if not text:
        raise ValueError("title is required")
    try:
        _parse_date(event_date)
    except ValueError as e:
        raise ValueError("invalid date (YYYY-MM-DD)") from e
    ev = {
        "id": uuid.uuid4().hex[:12],
        "title": text[:200],
        "date": event_date[:10],
        "time": (event_time or "").strip()[:5] or None,
        "note": (note or "").strip()[:500] or None,
        "done": False,
        "created_at": _utcnow_iso(),
    }
    store = _events_store(user)
    store.append(ev)
    if len(store) > 200:
        del store[:-200]
    user["life_modules"]["schedule"]["updated_at"] = _utcnow_iso()
    return ev


def complete_event(user: Dict[str, Any], event_id: str, done: bool = True) -> Dict[str, Any]:
    for e in _events_store(user):
        if e.get("id") == event_id:
            e["done"] = bool(done)
            e["completed_at"] = _utcnow_iso() if done else None
            user["life_modules"]["schedule"]["updated_at"] = _utcnow_iso()
            return e
    raise ValueError("event not found")


def delete_event(user: Dict[str, Any], event_id: str) -> None:
    store = _events_store(user)
    user["life_modules"]["schedule"]["structured"]["events"] = [e for e in store if e.get("id") != event_id]
    user["life_modules"]["schedule"]["updated_at"] = _utcnow_iso()


def _title_key(title: str) -> str:
    t = title.strip()
    for sep in (" - ", "：", ":", "－"):
        if sep in t:
            t = t.split(sep, 1)[-1].strip()
    return t[:40].lower()


def suggest_similar(user: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    """Suggest future events based on repeated titles / weekday patterns."""
    events = _events_store(user)
    today = date.today()
    existing = {(e.get("date"), e.get("title")) for e in events if not e.get("done")}
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in events:
        if not e.get("title"):
            continue
        groups[_title_key(e["title"])].append(e)

    suggestions: List[Dict[str, Any]] = []
    for key, group in groups.items():
        if len(group) < 1:
            continue
        sample = group[-1]
        title = sample["title"]
        times = [g.get("time") for g in group if g.get("time")]
        time_hint = Counter(times).most_common(1)[0][0] if times else sample.get("time")
        dates = [_parse_date(g["date"]) for g in group if g.get("date")]
        if not dates:
            continue
        last = max(dates)
        weekday_counts = Counter(d.weekday() for d in dates)
        weekday = weekday_counts.most_common(1)[0][0]
        # next same weekday after last date, at least tomorrow
        candidate = last + timedelta(days=1)
        while candidate.weekday() != weekday or candidate <= today:
            candidate += timedelta(days=1)
        if (candidate.isoformat(), title) in existing:
            continue
        reason = "過去の「" + title + "」"
        if len(group) >= 2:
            reason += "（" + str(len(group)) + "回）から提案"
        else:
            reason += "をもとに提案"
        suggestions.append(
            {
                "title": title,
                "date": candidate.isoformat(),
                "time": time_hint,
                "reason_ja": reason,
                "pattern": "repeat_title",
            }
        )
    suggestions.sort(key=lambda s: s["date"])
    return suggestions[:limit]


def home_summary(user: Dict[str, Any]) -> Dict[str, Any]:
    sched = list_events(user)
    health = user.get("life_modules", {}).get("health", {}).get("structured", {}) or {}
    score = int(health.get("score") or 85)
    goals_done = int(health.get("goals_done") or 0)
    goals_total = max(int(health.get("goals_total") or 5), 1)
    rpg = user.get("rpg") or {}
    active_quests = len(rpg.get("active_quests") or [])
    return {
        "schedule": {
            "open_count": sched["open_count"],
            "today_open": len(sched["today_open"]),
            "label": str(sched["open_count"]) + "件のToDo" if sched["open_count"] else "予定なし",
        },
        "health": {"score": score, "label": "良好 " + str(score)},
        "goals": {
            "done": goals_done or active_quests,
            "total": goals_total,
            "label": str(goals_done or active_quests) + "/" + str(goals_total) + " 達成",
        },
        "date_ja": f"{date.today().month}月{date.today().day}日",
    }
