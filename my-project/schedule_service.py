"""User schedule / ToDo events with AI + pattern suggestions and recurring support."""
from __future__ import annotations

import json
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from life_modules import ensure_life_modules

try:
    from luna_service import generate_json_task
except ImportError:
    generate_json_task = None  # type: ignore


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


def _recurring_store(user: Dict[str, Any]) -> List[Dict[str, Any]]:
    ensure_life_modules(user)
    structured = user["life_modules"]["schedule"].setdefault("structured", {})
    templates = structured.setdefault("recurring_templates", [])
    if not isinstance(templates, list):
        structured["recurring_templates"] = []
    return structured["recurring_templates"]


def _virtual_id(template_id: str, event_date: str) -> str:
    return f"rec-{template_id}-{event_date}"


def _parse_virtual_id(event_id: str) -> Optional[Tuple[str, str]]:
    if not event_id.startswith("rec-"):
        return None
    parts = event_id.split("-", 2)
    if len(parts) != 3:
        return None
    return parts[1], parts[2]


def _existing_keys(events: List[Dict[str, Any]]) -> Set[Tuple[str, str]]:
    return {(e.get("date", ""), e.get("title", "")) for e in events}


def expand_recurring_templates(
    user: Dict[str, Any],
    *,
    today: Optional[date] = None,
    horizon_days: int = 90,
) -> List[Dict[str, Any]]:
    """Materialize upcoming instances from recurring templates."""
    today = today or date.today()
    end = today + timedelta(days=horizon_days)
    existing = _existing_keys(_events_store(user))
    generated: List[Dict[str, Any]] = []

    for tpl in _recurring_store(user):
        if not tpl.get("active", True):
            continue
        title = (tpl.get("title") or "").strip()
        if not title:
            continue
        recurrence = tpl.get("recurrence") or "weekly"
        start = _parse_date(tpl.get("start_date") or today.isoformat())
        time_val = tpl.get("time")
        tpl_id = tpl.get("id") or uuid.uuid4().hex[:12]

        cursor = max(start, today)
        while cursor <= end:
            match = False
            if recurrence == "monthly":
                dom = int(tpl.get("day_of_month") or start.day)
                try:
                    candidate = cursor.replace(day=min(dom, 28))
                except ValueError:
                    candidate = cursor.replace(day=28)
                if candidate < cursor:
                    month = candidate.month + 1
                    year = candidate.year + (month - 1) // 12
                    month = ((month - 1) % 12) + 1
                    candidate = date(year, month, min(dom, 28))
                if candidate >= cursor and candidate <= end:
                    cursor = candidate
                    match = True
                else:
                    month = cursor.month + 1
                    year = cursor.year + (month - 1) // 12
                    month = ((month - 1) % 12) + 1
                    cursor = date(year, month, min(dom, 28))
                    continue
            else:
                weekday = int(tpl.get("weekday") if tpl.get("weekday") is not None else start.weekday())
                while cursor.weekday() != weekday:
                    cursor += timedelta(days=1)
                if cursor <= end:
                    match = True

            if match:
                ds = cursor.isoformat()
                key = (ds, title)
                if key not in existing:
                    generated.append(
                        {
                            "id": _virtual_id(tpl_id, ds),
                            "title": title,
                            "date": ds,
                            "time": time_val,
                            "note": tpl.get("note"),
                            "done": False,
                            "recurrence_id": tpl_id,
                            "recurrence": recurrence,
                            "is_generated": True,
                            "created_at": tpl.get("created_at"),
                        }
                    )
                if recurrence == "monthly":
                    month = cursor.month + 1
                    year = cursor.year + (month - 1) // 12
                    month = ((month - 1) % 12) + 1
                    cursor = date(year, month, min(int(tpl.get("day_of_month") or start.day), 28))
                else:
                    cursor += timedelta(days=7)
            else:
                break

    return generated


def _all_events(user: Dict[str, Any], *, on_date: Optional[str] = None) -> List[Dict[str, Any]]:
    stored = list(_events_store(user))
    today = date.today()
    if on_date:
        try:
            today = _parse_date(on_date)
        except ValueError:
            pass
    generated = expand_recurring_templates(user, today=today)
    merged = stored + generated
    merged.sort(key=lambda e: (e.get("date", ""), e.get("time") or ""))
    return merged


def list_events(user: Dict[str, Any], *, on_date: Optional[str] = None) -> Dict[str, Any]:
    events = _all_events(user, on_date=on_date)
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
    dates_with_events = sorted({e.get("date") for e in events if e.get("date")})
    return {
        "today": today_s,
        "past_done": past_done,
        "today_open": today_open,
        "today_done": today_done,
        "future": future,
        "open_count": open_count,
        "events": events,
        "dates_with_events": dates_with_events,
        "recurring_templates": _recurring_store(user),
    }


def add_recurring_template(
    user: Dict[str, Any],
    *,
    title: str,
    start_date: str,
    event_time: Optional[str] = None,
    note: Optional[str] = None,
    recurrence: str = "weekly",
) -> Dict[str, Any]:
    if recurrence not in ("weekly", "monthly"):
        raise ValueError("recurrence must be weekly or monthly")
    start = _parse_date(start_date)
    tpl = {
        "id": uuid.uuid4().hex[:12],
        "title": title[:200],
        "start_date": start_date[:10],
        "time": (event_time or "").strip()[:5] or None,
        "note": (note or "").strip()[:500] or None,
        "recurrence": recurrence,
        "weekday": start.weekday(),
        "day_of_month": start.day,
        "active": True,
        "created_at": _utcnow_iso(),
    }
    _recurring_store(user).append(tpl)
    user["life_modules"]["schedule"]["updated_at"] = _utcnow_iso()
    return tpl


def add_event(
    user: Dict[str, Any],
    *,
    title: str,
    event_date: str,
    event_time: Optional[str] = None,
    note: Optional[str] = None,
    recurrence: Optional[str] = None,
) -> Dict[str, Any]:
    text = (title or "").strip()
    if not text:
        raise ValueError("title is required")
    try:
        _parse_date(event_date)
    except ValueError as e:
        raise ValueError("invalid date (YYYY-MM-DD)") from e

    tpl = None
    if recurrence in ("weekly", "monthly"):
        tpl = add_recurring_template(
            user,
            title=text,
            start_date=event_date,
            event_time=event_time,
            note=note,
            recurrence=recurrence,
        )

    ev = {
        "id": uuid.uuid4().hex[:12],
        "title": text[:200],
        "date": event_date[:10],
        "time": (event_time or "").strip()[:5] or None,
        "note": (note or "").strip()[:500] or None,
        "done": False,
        "created_at": _utcnow_iso(),
    }
    if tpl:
        ev["recurrence_id"] = tpl["id"]
        ev["recurrence"] = recurrence
    store = _events_store(user)
    store.append(ev)
    if len(store) > 200:
        del store[:-200]
    user["life_modules"]["schedule"]["updated_at"] = _utcnow_iso()
    return ev


def update_event(
    user: Dict[str, Any],
    event_id: str,
    *,
    title: Optional[str] = None,
    event_date: Optional[str] = None,
    event_time: Optional[str] = None,
    note: Optional[str] = None,
    done: Optional[bool] = None,
) -> Dict[str, Any]:
    """Update a stored event. Virtual recurring instances are materialized first."""
    parsed = _parse_virtual_id(event_id)
    if parsed:
        # Materialize as a real editable event (without creating recurrence again)
        tpl_id, event_date_v = parsed
        tpl = next((t for t in _recurring_store(user) if t.get("id") == tpl_id), None)
        if not tpl:
            raise ValueError("event not found")
        ev = {
            "id": uuid.uuid4().hex[:12],
            "title": tpl["title"],
            "date": event_date_v,
            "time": tpl.get("time"),
            "note": tpl.get("note"),
            "done": False,
            "created_at": _utcnow_iso(),
            "recurrence_id": tpl_id,
            "recurrence": tpl.get("recurrence"),
        }
        _events_store(user).append(ev)
        event_id = ev["id"]

    for e in _events_store(user):
        if e.get("id") != event_id:
            continue
        if title is not None:
            text = title.strip()
            if not text:
                raise ValueError("title is required")
            e["title"] = text[:200]
        if event_date is not None:
            try:
                _parse_date(event_date)
            except ValueError as err:
                raise ValueError("invalid date (YYYY-MM-DD)") from err
            e["date"] = event_date[:10]
        if event_time is not None:
            e["time"] = (event_time or "").strip()[:5] or None
        if note is not None:
            e["note"] = (note or "").strip()[:500] or None
        if done is not None:
            e["done"] = bool(done)
            e["completed_at"] = _utcnow_iso() if done else None
        e["updated_at"] = _utcnow_iso()
        user["life_modules"]["schedule"]["updated_at"] = _utcnow_iso()
        return e
    raise ValueError("event not found")


def complete_event(user: Dict[str, Any], event_id: str, done: bool = True) -> Dict[str, Any]:
    parsed = _parse_virtual_id(event_id)
    if parsed:
        tpl_id, event_date = parsed
        tpl = next((t for t in _recurring_store(user) if t.get("id") == tpl_id), None)
        if not tpl:
            raise ValueError("event not found")
        ev = add_event(
            user,
            title=tpl["title"],
            event_date=event_date,
            event_time=tpl.get("time"),
            note=tpl.get("note"),
        )
        ev["done"] = bool(done)
        ev["completed_at"] = _utcnow_iso() if done else None
        ev["recurrence_id"] = tpl_id
        ev["recurrence"] = tpl.get("recurrence")
        user["life_modules"]["schedule"]["updated_at"] = _utcnow_iso()
        return ev

    for e in _events_store(user):
        if e.get("id") == event_id:
            e["done"] = bool(done)
            e["completed_at"] = _utcnow_iso() if done else None
            user["life_modules"]["schedule"]["updated_at"] = _utcnow_iso()
            return e
    raise ValueError("event not found")


def delete_event(user: Dict[str, Any], event_id: str) -> None:
    parsed = _parse_virtual_id(event_id)
    if parsed:
        tpl_id, _ = parsed
        templates = _recurring_store(user)
        user["life_modules"]["schedule"]["structured"]["recurring_templates"] = [
            t for t in templates if t.get("id") != tpl_id
        ]
        user["life_modules"]["schedule"]["updated_at"] = _utcnow_iso()
        return
    store = _events_store(user)
    target = next((e for e in store if e.get("id") == event_id), None)
    user["life_modules"]["schedule"]["structured"]["events"] = [e for e in store if e.get("id") != event_id]
    if target and target.get("recurrence_id"):
        rid = target["recurrence_id"]
        templates = _recurring_store(user)
        user["life_modules"]["schedule"]["structured"]["recurring_templates"] = [
            t for t in templates if t.get("id") != rid
        ]
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
    existing = _existing_keys([e for e in _all_events(user) if not e.get("done")])
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in events:
        if not e.get("title"):
            continue
        groups[_title_key(e["title"])].append(e)

    suggestions: List[Dict[str, Any]] = []
    for _, group in groups.items():
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
        candidate = last + timedelta(days=1)
        while candidate.weekday() != weekday or candidate <= today:
            candidate += timedelta(days=1)
        if (candidate.isoformat(), title) in existing:
            continue
        recurrence = "weekly" if len(group) >= 2 else None
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
                "source": "pattern",
                "recurrence": recurrence,
            }
        )
    suggestions.sort(key=lambda s: s["date"])
    return suggestions[:limit]


def suggest_ai(user: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    """Use Gemini to propose schedule items from history + life context."""
    if not generate_json_task:
        return []
    events = _events_store(user) + expand_recurring_templates(user)
    recent = sorted(events, key=lambda e: e.get("date", ""))[-25:]
    profile = user.get("life_profile") or {}
    schedule_notes = (user.get("life_modules", {}).get("schedule", {}).get("notes") or [])[-5:]
    payload = {
        "recent_events": [
            {"title": e.get("title"), "date": e.get("date"), "time": e.get("time"), "done": e.get("done")}
            for e in recent
        ],
        "life_profile": {
            k: profile.get(k)
            for k in ("time_weekday", "time_weekend", "study_future", "goals", "health_sleep", "money_goal")
            if profile.get(k)
        },
        "schedule_notes": [n.get("text") for n in schedule_notes],
        "today": date.today().isoformat(),
    }
    system = (
        "You are LUNA, a Japanese student life assistant. "
        "Given the user's past schedule entries and profile, propose future schedule items. "
        "Return JSON: {\"suggestions\":[{\"title\":\"...\",\"date\":\"YYYY-MM-DD\","
        "\"time\":\"HH:MM or null\",\"reason_ja\":\"Japanese explanation\","
        "\"recurrence\":\"weekly|monthly|null\"}]}. "
        "Dates must be today or later. Max " + str(limit) + " items. Use Japanese titles."
    )
    raw = generate_json_task(system, json.dumps(payload, ensure_ascii=False))
    if not raw:
        return []
    items = raw.get("suggestions") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []
    existing = _existing_keys([e for e in _all_events(user) if not e.get("done")])
    today = date.today()
    out: List[Dict[str, Any]] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip()
        ds = (item.get("date") or "")[:10]
        if not title or not ds:
            continue
        try:
            if _parse_date(ds) < today:
                continue
        except ValueError:
            continue
        if (ds, title) in existing:
            continue
        rec = item.get("recurrence")
        if rec not in ("weekly", "monthly"):
            rec = None
        out.append(
            {
                "title": title[:200],
                "date": ds,
                "time": (item.get("time") or "")[:5] or None,
                "reason_ja": (item.get("reason_ja") or "AIが生活パターンから提案")[:200],
                "pattern": "ai",
                "source": "ai",
                "recurrence": rec,
            }
        )
    return out


def suggest_combined(user: Dict[str, Any], limit: int = 6) -> Dict[str, Any]:
    ai = suggest_ai(user, limit=limit)
    pattern = suggest_similar(user, limit=limit)
    merged: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str]] = set()
    for bucket in (ai, pattern):
        for s in bucket:
            key = (s.get("date", ""), s.get("title", ""))
            if key in seen:
                continue
            seen.add(key)
            merged.append(s)
    merged.sort(key=lambda s: s.get("date", ""))
    merged = merged[:limit]
    return {
        "suggestions": merged,
        "ai_count": len(ai),
        "pattern_count": len(pattern),
        "source": "ai+pattern" if ai and pattern else ("ai" if ai else "pattern"),
    }


def apply_suggestions(
    user: Dict[str, Any],
    suggestions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    created: List[Dict[str, Any]] = []
    for s in suggestions:
        created.append(
            add_event(
                user,
                title=s["title"],
                event_date=s["date"],
                event_time=s.get("time"),
                recurrence=s.get("recurrence"),
            )
        )
    return created


def home_summary(user: Dict[str, Any]) -> Dict[str, Any]:
    sched = list_events(user)
    health = user.get("life_modules", {}).get("health", {}).get("structured", {}) or {}
    score = int(health.get("score") or 85)
    goals_done = int(health.get("goals_done") or 0)
    goals_total = max(int(health.get("goals_total") or 5), 1)
    rpg = user.get("rpg") or {}
    active_quests = len(rpg.get("active_quests") or [])
    today_items = sorted(
        (sched.get("today_open") or []) + (sched.get("today_done") or []),
        key=lambda e: (e.get("time") or "99:99", e.get("title") or ""),
    )
    return {
        "schedule": {
            "open_count": sched["open_count"],
            "today_open": len(sched["today_open"]),
            "label": str(sched["open_count"]) + "件のToDo" if sched["open_count"] else "予定なし",
            "today_items": today_items,
        },
        "health": {"score": score, "label": "良好 " + str(score)},
        "goals": {
            "done": goals_done or active_quests,
            "total": goals_total,
            "label": str(goals_done or active_quests) + "/" + str(goals_total) + " 達成",
        },
        "date_ja": f"{date.today().month}月{date.today().day}日",
    }
