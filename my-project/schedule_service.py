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


def _norm_time(value: Optional[str]) -> Optional[str]:
    text = (value or "").strip()[:5]
    if not text:
        return None
    try:
        datetime.strptime(text, "%H:%M")
    except ValueError as e:
        raise ValueError("invalid time (HH:MM)") from e
    return text


def _check_range(start: Optional[str], end: Optional[str]) -> None:
    # Allow overnight ranges like 22:00 -> 08:00.
    # We only validate HH:MM format in _norm_time.
    return


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


def _mark_schedule_dirty(user: Dict[str, Any]) -> None:
    user["_schedule_dirty"] = True


def _occupied_recurrence_dates(events: List[Dict[str, Any]]) -> Set[Tuple[str, str]]:
    """(recurrence_id, date) already covered by a stored exception/event."""
    out: Set[Tuple[str, str]] = set()
    for e in events:
        rid = e.get("recurrence_id")
        ds = e.get("date")
        if rid and ds:
            out.add((rid, ds))
    return out


def _purge_legacy_recurring_seeds(user: Dict[str, Any]) -> None:
    """Remove auto-seeded first-day copies of recurring templates.

    Older versions stored the template start date as a real event. That made the
    first occurrence behave differently (e.g. stuck as done/strikethrough) while
    later generated days looked normal. Keep only explicit exceptions.
    """
    templates = {t.get("id"): t for t in _recurring_store(user) if t.get("id")}
    if not templates:
        return
    store = _events_store(user)
    kept: List[Dict[str, Any]] = []
    changed = False
    for e in store:
        rid = e.get("recurrence_id")
        tpl = templates.get(rid) if rid else None
        if (
            tpl
            and not e.get("exception")
            and e.get("date") == tpl.get("start_date")
            and (e.get("title") or "").strip() == (tpl.get("title") or "").strip()
        ):
            changed = True
            continue
        kept.append(e)
    if changed:
        user["life_modules"]["schedule"]["structured"]["events"] = kept
        user["life_modules"]["schedule"]["updated_at"] = _utcnow_iso()
        _mark_schedule_dirty(user)


def _title_norm(title: Optional[str]) -> str:
    return (title or "").strip().lower()


def _series_key(tpl: Dict[str, Any]) -> Tuple[str, Optional[str], Optional[str]]:
    return (_title_norm(tpl.get("title")), tpl.get("time"), tpl.get("end_time"))


def _collapse_duplicate_recurring_series(user: Dict[str, Any]) -> None:
    """Normalize messy recurring templates created by older calendar bugs.

    Rules:
    - Keep at most one weekly series per (title, weekday).
    - If a title already has any weekly series, deactivate monthly clones
      of the same title (typical date-jump artifact like day-26 毎月).
    - Keep at most one monthly series per (title, day_of_month) when no weekly exists.
    - Drop non-exception stored events that sit on the wrong weekday of a weekly series.
    """
    templates = _recurring_store(user)
    by_title: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for tpl in templates:
        if not tpl.get("active", True):
            continue
        key = _title_norm(tpl.get("title"))
        if not key:
            continue
        by_title[key].append(tpl)

    changed = False
    for title_key, series in by_title.items():
        weeklies = [t for t in series if (t.get("recurrence") or "weekly") == "weekly"]
        monthlies = [t for t in series if t.get("recurrence") == "monthly"]

        # One weekly per weekday.
        weeklies_by_wd: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for t in weeklies:
            try:
                wd = int(t.get("weekday") if t.get("weekday") is not None else _parse_date(t["start_date"]).weekday())
            except (TypeError, ValueError, KeyError):
                wd = 0
            t["weekday"] = wd
            weeklies_by_wd[wd].append(t)
        for group in weeklies_by_wd.values():
            group.sort(key=lambda t: t.get("start_date") or "")
            for t in group[1:]:
                t["active"] = False
                changed = True

        active_weeklies = [t for t in weeklies if t.get("active", True)]
        if active_weeklies:
            # Weekly class title wins over monthly clones of the same title.
            for t in monthlies:
                if t.get("active", True):
                    t["active"] = False
                    changed = True
        else:
            monthlies_by_dom: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
            for t in monthlies:
                try:
                    dom = int(t.get("day_of_month") or _parse_date(t["start_date"]).day)
                except (TypeError, ValueError, KeyError):
                    continue
                t["day_of_month"] = dom
                monthlies_by_dom[dom].append(t)
            for group in monthlies_by_dom.values():
                group.sort(key=lambda t: t.get("start_date") or "")
                for t in group[1:]:
                    t["active"] = False
                    changed = True

    # Same weekday + same time slot = one series only (e.g. 「Đi học」and
    # AI/JP clone 「学校の授業」 both Mon 21:20). Keep the oldest.
    slot_groups: Dict[Tuple[int, Optional[str], Optional[str]], List[Dict[str, Any]]] = defaultdict(list)
    for t in templates:
        if not t.get("active", True):
            continue
        if (t.get("recurrence") or "weekly") != "weekly":
            continue
        try:
            wd = int(t.get("weekday") if t.get("weekday") is not None else _parse_date(t["start_date"]).weekday())
        except (TypeError, ValueError, KeyError):
            continue
        slot_groups[(wd, t.get("time"), t.get("end_time"))].append(t)
    for group in slot_groups.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda t: (t.get("created_at") or "", t.get("start_date") or "", t.get("id") or ""))
        for t in group[1:]:
            t["active"] = False
            changed = True

    if changed:
        user["life_modules"]["schedule"]["updated_at"] = _utcnow_iso()
        _mark_schedule_dirty(user)

    active_templates = [t for t in templates if t.get("id") and t.get("active", True)]
    templates_by_id = {t.get("id"): t for t in active_templates}
    weekly_by_title_wd: Dict[Tuple[str, int], Dict[str, Any]] = {}
    for t in active_templates:
        if (t.get("recurrence") or "weekly") != "weekly":
            continue
        wd = int(t.get("weekday") if t.get("weekday") is not None else _parse_date(t["start_date"]).weekday())
        weekly_by_title_wd[(_title_norm(t.get("title")), wd)] = t

    store = _events_store(user)
    kept_events: List[Dict[str, Any]] = []
    ev_changed = False
    for e in store:
        rid = e.get("recurrence_id")
        tpl = templates_by_id.get(rid) if rid else None
        # Drop orphans linked to deactivated templates (unless explicit exception kept? no — deactivate means gone)
        if rid and not tpl:
            # Keep explicit one-day exceptions only if template still active; otherwise drop.
            ev_changed = True
            continue
        if not tpl and e.get("date"):
            try:
                ev_day = _parse_date(e["date"]).weekday()
            except ValueError:
                ev_day = None
            if ev_day is not None:
                tpl = weekly_by_title_wd.get((_title_norm(e.get("title")), ev_day))
        if (
            tpl
            and (tpl.get("recurrence") or "weekly") == "weekly"
            and not e.get("exception")
            and e.get("date")
        ):
            try:
                ev_day = _parse_date(e["date"]).weekday()
            except ValueError:
                ev_day = None
            weekday = int(
                tpl.get("weekday")
                if tpl.get("weekday") is not None
                else _parse_date(tpl["start_date"]).weekday()
            )
            if ev_day is not None and ev_day != weekday:
                ev_changed = True
                continue
        kept_events.append(e)
    if ev_changed:
        user["life_modules"]["schedule"]["structured"]["events"] = kept_events
        user["life_modules"]["schedule"]["updated_at"] = _utcnow_iso()
        _mark_schedule_dirty(user)


def _cancel_template_date(user: Dict[str, Any], tpl_id: str, event_date: str) -> None:
    tpl = next((t for t in _recurring_store(user) if t.get("id") == tpl_id), None)
    if not tpl:
        return
    cancelled = tpl.setdefault("cancelled_dates", [])
    ds = event_date[:10]
    if ds not in cancelled:
        cancelled.append(ds)


def _default_horizon_end(start: date) -> str:
    return (start + timedelta(days=365)).isoformat()


def _ensure_template_horizon(tpl: Dict[str, Any], user: Optional[Dict[str, Any]] = None) -> str:
    """Ensure each recurring template has a 1-year generation horizon."""
    raw = tpl.get("horizon_end")
    if raw:
        try:
            return _parse_date(raw).isoformat()
        except ValueError:
            pass
    try:
        start = _parse_date(tpl.get("start_date") or date.today().isoformat())
    except ValueError:
        start = date.today()
    horizon = _default_horizon_end(start)
    tpl["horizon_end"] = horizon
    if user is not None:
        _mark_schedule_dirty(user)
    return horizon


def expand_recurring_templates(
    user: Dict[str, Any],
    *,
    today: Optional[date] = None,
    ahead_days: int = 45,
    lookback_days: int = 40,
) -> List[Dict[str, Any]]:
    """Materialize recurring instances within each template's 1-year horizon.

    Templates are permanent. Concrete dates are only generated up to
    ``horizon_end`` (default: start + 1 year), and only around the browsed
    month so the API stays small. When that year window is nearly over,
    the UI asks the user to extend another year.
    """
    focus = today or date.today()
    window_end = focus + timedelta(days=max(ahead_days, 31))
    stored = _events_store(user)
    existing = _existing_keys(stored)
    occupied = _occupied_recurrence_dates(stored)
    generated: List[Dict[str, Any]] = []

    for tpl in _recurring_store(user):
        if not tpl.get("active", True):
            continue
        title = (tpl.get("title") or "").strip()
        if not title:
            continue
        recurrence = tpl.get("recurrence") or "weekly"
        start = _parse_date(tpl.get("start_date") or focus.isoformat())
        time_val = tpl.get("time")
        tpl_id = tpl.get("id") or uuid.uuid4().hex[:12]
        cancelled = set(tpl.get("cancelled_dates") or [])
        horizon_end = _parse_date(_ensure_template_horizon(tpl, user))
        end = min(window_end, horizon_end)
        if end < start:
            continue

        horizon_start = focus - timedelta(days=lookback_days)
        cursor = max(start, horizon_start)
        if cursor > end:
            continue
        # ~2 months of weekly ticks per template is enough for the month grid.
        guard = 0
        guard_max = 70
        while cursor <= end and guard < guard_max:
            guard += 1
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
                    next_cursor = date(year, month, min(dom, 28))
                    if next_cursor <= cursor:
                        break
                    cursor = next_cursor
                    continue
            else:
                weekday = int(tpl.get("weekday") if tpl.get("weekday") is not None else start.weekday())
                while cursor.weekday() != weekday:
                    cursor += timedelta(days=1)
                if cursor <= end:
                    match = True

            if match:
                ds = cursor.isoformat()
                if recurrence != "monthly":
                    weekday = int(tpl.get("weekday") if tpl.get("weekday") is not None else start.weekday())
                    if cursor.weekday() != weekday:
                        cursor += timedelta(days=1)
                        continue
                key = (ds, title)
                if (
                    ds not in cancelled
                    and key not in existing
                    and (tpl_id, ds) not in occupied
                ):
                    generated.append(
                        {
                            "id": _virtual_id(tpl_id, ds),
                            "title": title,
                            "date": ds,
                            "time": time_val,
                            "end_time": tpl.get("end_time"),
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


def recurring_extend_prompt(user: Dict[str, Any], *, focus: Optional[date] = None) -> Dict[str, Any]:
    """Return UI payload when any series is near / past its 1-year generation window."""
    focus = focus or date.today()
    soon = focus + timedelta(days=45)
    needing: List[Dict[str, Any]] = []
    for tpl in _recurring_store(user):
        if not tpl.get("active", True):
            continue
        title = (tpl.get("title") or "").strip()
        if not title:
            continue
        horizon = _parse_date(_ensure_template_horizon(tpl, user))
        # Prompt when browsing near/past the end, or real today is near the end.
        real_today = date.today()
        if horizon <= soon or horizon <= real_today + timedelta(days=45) or focus > horizon:
            needing.append(
                {
                    "id": tpl.get("id"),
                    "title": title,
                    "horizon_end": horizon.isoformat(),
                    "recurrence": tpl.get("recurrence") or "weekly",
                }
            )
    if not needing:
        return {"needed": False, "templates": [], "message_ja": ""}
    names = "、".join(t["title"] for t in needing[:3])
    if len(needing) > 3:
        names += " など"
    return {
        "needed": True,
        "templates": needing,
        "message_ja": (
            "繰り返し予定（"
            + names
            + "）の1年分がまもなく終わります。あと1年分を続けて追加しますか？"
        ),
    }


def extend_recurring_horizons(
    user: Dict[str, Any],
    *,
    template_ids: Optional[List[str]] = None,
    days: int = 365,
) -> Dict[str, Any]:
    """Extend generation horizon by another year for selected (or all due) templates."""
    focus = date.today()
    soon = focus + timedelta(days=45)
    extended: List[Dict[str, Any]] = []
    id_set = set(template_ids or [])
    for tpl in _recurring_store(user):
        if not tpl.get("active", True):
            continue
        tid = tpl.get("id")
        if id_set and tid not in id_set:
            continue
        horizon = _parse_date(_ensure_template_horizon(tpl, user))
        if id_set or horizon <= soon or focus > horizon:
            base = max(horizon, focus)
            tpl["horizon_end"] = (base + timedelta(days=max(days, 30))).isoformat()
            extended.append(
                {
                    "id": tid,
                    "title": tpl.get("title"),
                    "horizon_end": tpl["horizon_end"],
                }
            )
    if extended:
        user["life_modules"]["schedule"]["updated_at"] = _utcnow_iso()
        _mark_schedule_dirty(user)
    return {"ok": True, "extended": extended, "count": len(extended)}


def _all_events(user: Dict[str, Any], *, on_date: Optional[str] = None) -> List[Dict[str, Any]]:
    _purge_legacy_recurring_seeds(user)
    _collapse_duplicate_recurring_series(user)
    stored = list(_events_store(user))
    # Deduplicate accidental duplicates, but don't block the user from
    # having multiple events on the same day (even with the same title).
    deduped: List[Dict[str, Any]] = []
    seen_keys: Set[Tuple[str, str, Optional[str], Optional[str], Optional[str]]] = set()
    for e in sorted(stored, key=lambda x: (0 if x.get("exception") else 1, x.get("updated_at") or x.get("created_at") or "")):
        key = (
            e.get("date") or "",
            (e.get("title") or "").strip(),
            e.get("time"),
            e.get("end_time"),
            e.get("recurrence_id"),
        )
        if key[0] and key[1] and key in seen_keys:
            continue
        if key[0] and key[1]:
            seen_keys.add(key)
        deduped.append(e)
    if len(deduped) != len(stored):
        user["life_modules"]["schedule"]["structured"]["events"] = deduped
        user["life_modules"]["schedule"]["updated_at"] = _utcnow_iso()
        _mark_schedule_dirty(user)
        stored = deduped
    focus = date.today()
    if on_date:
        try:
            focus = _parse_date(on_date)
        except ValueError:
            pass
    generated = expand_recurring_templates(user, today=focus)
    # Keep payload small: only return stored + generated near the focus month.
    window_start = (focus - timedelta(days=40)).isoformat()
    window_end = (focus + timedelta(days=45)).isoformat()
    near_stored = [
        e
        for e in stored
        if e.get("date") and window_start <= e.get("date", "") <= window_end
    ]
    merged = near_stored + generated
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
        "extend_prompt": recurring_extend_prompt(user, focus=today),
    }


def add_recurring_template(
    user: Dict[str, Any],
    *,
    title: str,
    start_date: str,
    event_time: Optional[str] = None,
    event_end_time: Optional[str] = None,
    note: Optional[str] = None,
    recurrence: str = "weekly",
) -> Dict[str, Any]:
    if recurrence not in ("weekly", "monthly"):
        raise ValueError("recurrence must be weekly or monthly")
    start_t = _norm_time(event_time)
    end_t = _norm_time(event_end_time)
    _check_range(start_t, end_t)
    start = _parse_date(start_date)
    title_text = title[:200]
    note_text = (note or "").strip()[:500] or None

    # Reuse carefully:
    # - weekly: one series per (title, weekday)
    # - monthly: blocked/reused if a weekly with same title already exists
    for existing in _recurring_store(user):
        if not existing.get("active", True):
            continue
        if _title_norm(existing.get("title")) != _title_norm(title_text):
            continue
        existing_rec = existing.get("recurrence") or "weekly"
        if recurrence == "monthly" and existing_rec == "weekly":
            # Date-jump used to create 毎月 clones of 毎週 classes — refuse.
            return existing
        if existing_rec != recurrence:
            continue
        if existing_rec == "weekly":
            wd = int(existing.get("weekday") if existing.get("weekday") is not None else _parse_date(existing["start_date"]).weekday())
            if wd == start.weekday() and existing.get("time") == start_t and existing.get("end_time") == end_t:
                return existing
            continue
        if existing_rec == "monthly":
            if int(existing.get("day_of_month") or -1) == start.day and existing.get("time") == start_t and existing.get("end_time") == end_t:
                return existing

    tpl = {
        "id": uuid.uuid4().hex[:12],
        "title": title_text,
        "start_date": start_date[:10],
        "time": start_t,
        "end_time": end_t,
        "note": note_text,
        "recurrence": recurrence,
        "weekday": start.weekday(),
        "day_of_month": start.day,
        "active": True,
        "cancelled_dates": [],
        "horizon_end": _default_horizon_end(start),
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
    event_end_time: Optional[str] = None,
    note: Optional[str] = None,
    recurrence: Optional[str] = None,
) -> Dict[str, Any]:
    _purge_legacy_recurring_seeds(user)
    _collapse_duplicate_recurring_series(user)
    text = (title or "").strip()
    if not text:
        raise ValueError("title is required")
    try:
        _parse_date(event_date)
    except ValueError as e:
        raise ValueError("invalid date (YYYY-MM-DD)") from e
    start_t = _norm_time(event_time)
    end_t = _norm_time(event_end_time)
    _check_range(start_t, end_t)
    note_text = (note or "").strip()[:500] or None
    ds = event_date[:10]

    # If user picks 毎月 but a 毎週 series already exists for this title,
    # save as a one-off day instead of spawning a confusing monthly clone.
    if recurrence == "monthly":
        has_weekly = any(
            t.get("active", True)
            and (t.get("recurrence") or "weekly") == "weekly"
            and _title_norm(t.get("title")) == _title_norm(text)
            for t in _recurring_store(user)
        )
        if has_weekly:
            recurrence = None

    if recurrence in ("weekly", "monthly"):
        tpl = add_recurring_template(
            user,
            title=text,
            start_date=ds,
            event_time=start_t,
            event_end_time=end_t,
            note=note_text,
            recurrence=recurrence,
        )
        # Template reuse may hand back a weekly while the user asked for monthly.
        # In that case store a plain one-off for this date only.
        if recurrence == "monthly" and (tpl.get("recurrence") or "weekly") == "weekly":
            recurrence = None
        else:
            return {
                "id": _virtual_id(tpl["id"], ds),
                "title": text[:200],
                "date": ds,
                "time": start_t,
                "end_time": end_t,
                "note": note_text,
                "done": False,
                "recurrence_id": tpl["id"],
                "recurrence": recurrence,
                "is_generated": True,
                "created_at": tpl.get("created_at"),
            }

    ev = {
        "id": uuid.uuid4().hex[:12],
        "title": text[:200],
        "date": ds,
        "time": start_t,
        "end_time": end_t,
        "note": note_text,
        "done": False,
        "created_at": _utcnow_iso(),
    }
    store = _events_store(user)
    store.append(ev)
    if len(store) > 200:
        del store[:-200]
    user["life_modules"]["schedule"]["updated_at"] = _utcnow_iso()
    return ev


def _resolve_event_template_id(user: Dict[str, Any], event_id: str) -> Optional[str]:
    parsed = _parse_virtual_id(event_id)
    if parsed:
        return parsed[0]
    for e in _events_store(user):
        if e.get("id") == event_id and e.get("recurrence_id"):
            return e.get("recurrence_id")
    return None


def _update_recurring_template(
    user: Dict[str, Any],
    tpl_id: str,
    *,
    title: Optional[str] = None,
    event_date: Optional[str] = None,
    event_time: Optional[str] = None,
    event_end_time: Optional[str] = None,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    tpl = next((t for t in _recurring_store(user) if t.get("id") == tpl_id), None)
    if not tpl or not tpl.get("active", True):
        raise ValueError("event not found")

    if title is not None:
        text = title.strip()
        if not text:
            raise ValueError("title is required")
        tpl["title"] = text[:200]
    if event_time is not None:
        tpl["time"] = _norm_time(event_time)
    if event_end_time is not None:
        tpl["end_time"] = _norm_time(event_end_time)
    _check_range(tpl.get("time"), tpl.get("end_time"))
    if note is not None:
        tpl["note"] = (note or "").strip()[:500] or None
    if event_date is not None:
        try:
            start = _parse_date(event_date)
        except ValueError as err:
            raise ValueError("invalid date (YYYY-MM-DD)") from err
        tpl["start_date"] = event_date[:10]
        tpl["weekday"] = start.weekday()
        tpl["day_of_month"] = start.day
        # Series moved — clear one-off cancellations/exceptions tied to old dates.
        tpl["cancelled_dates"] = []

    # Drop prior one-day exceptions so the updated series regenerates cleanly.
    store = _events_store(user)
    user["life_modules"]["schedule"]["structured"]["events"] = [
        e for e in store if e.get("recurrence_id") != tpl_id
    ]
    user["life_modules"]["schedule"]["updated_at"] = _utcnow_iso()
    ds = tpl.get("start_date") or date.today().isoformat()
    return {
        "id": _virtual_id(tpl_id, ds),
        "title": tpl["title"],
        "date": ds,
        "time": tpl.get("time"),
        "end_time": tpl.get("end_time"),
        "note": tpl.get("note"),
        "done": False,
        "recurrence_id": tpl_id,
        "recurrence": tpl.get("recurrence"),
        "is_generated": True,
        "scope": "all",
        "created_at": tpl.get("created_at"),
    }


def _find_exception(user: Dict[str, Any], tpl_id: str, event_date: str) -> Optional[Dict[str, Any]]:
    ds = event_date[:10]
    for e in _events_store(user):
        if e.get("recurrence_id") == tpl_id and e.get("date") == ds:
            return e
    return None


def _materialize_exception(
    user: Dict[str, Any],
    tpl: Dict[str, Any],
    event_date: str,
    *,
    done: Optional[bool] = None,
) -> Dict[str, Any]:
    """Create or reuse a one-day exception for a recurring template."""
    tpl_id = tpl["id"]
    existing = _find_exception(user, tpl_id, event_date)
    if existing:
        if done is not None:
            existing["done"] = bool(done)
            existing["completed_at"] = _utcnow_iso() if done else None
        existing["exception"] = True
        existing["recurrence"] = tpl.get("recurrence")
        existing["updated_at"] = _utcnow_iso()
        return existing
    ev = {
        "id": uuid.uuid4().hex[:12],
        "title": tpl["title"],
        "date": event_date[:10],
        "time": tpl.get("time"),
        "end_time": tpl.get("end_time"),
        "note": tpl.get("note"),
        "done": bool(done) if done is not None else False,
        "completed_at": _utcnow_iso() if done else None,
        "created_at": _utcnow_iso(),
        "recurrence_id": tpl_id,
        "recurrence": tpl.get("recurrence"),
        "exception": True,
    }
    store = _events_store(user)
    store.append(ev)
    if len(store) > 200:
        del store[:-200]
    return ev


def update_event(
    user: Dict[str, Any],
    event_id: str,
    *,
    title: Optional[str] = None,
    event_date: Optional[str] = None,
    event_time: Optional[str] = None,
    event_end_time: Optional[str] = None,
    note: Optional[str] = None,
    done: Optional[bool] = None,
    scope: str = "this",
) -> Dict[str, Any]:
    """Update an event.

    scope='this' → only this occurrence (exception).
    scope='all'  → update the whole recurring series template.
    """
    _purge_legacy_recurring_seeds(user)
    scope = (scope or "this").lower()
    if scope not in ("this", "all"):
        raise ValueError("scope must be this or all")

    tpl_id = _resolve_event_template_id(user, event_id)
    if scope == "all":
        if not tpl_id:
            raise ValueError("not a recurring event")
        return _update_recurring_template(
            user,
            tpl_id,
            title=title,
            event_date=event_date,
            event_time=event_time,
            event_end_time=event_end_time,
            note=note,
        )

    parsed = _parse_virtual_id(event_id)
    if parsed:
        tpl_id_v, event_date_v = parsed
        tpl = next((t for t in _recurring_store(user) if t.get("id") == tpl_id_v), None)
        if not tpl:
            raise ValueError("event not found")
        ev = _materialize_exception(user, tpl, event_date_v)
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
            old_date = e.get("date")
            e["date"] = event_date[:10]
            if e.get("recurrence_id") and old_date and old_date != e["date"]:
                # Prevent the series from regenerating the old day.
                _cancel_template_date(user, e["recurrence_id"], old_date)
        if event_time is not None:
            e["time"] = _norm_time(event_time)
        if event_end_time is not None:
            e["end_time"] = _norm_time(event_end_time)
        _check_range(e.get("time"), e.get("end_time"))
        if note is not None:
            e["note"] = (note or "").strip()[:500] or None
        if done is not None:
            e["done"] = bool(done)
            e["completed_at"] = _utcnow_iso() if done else None
        if e.get("recurrence_id"):
            e["exception"] = True
        e["updated_at"] = _utcnow_iso()
        user["life_modules"]["schedule"]["updated_at"] = _utcnow_iso()
        return e
    raise ValueError("event not found")


def complete_event(user: Dict[str, Any], event_id: str, done: bool = True) -> Dict[str, Any]:
    _purge_legacy_recurring_seeds(user)
    parsed = _parse_virtual_id(event_id)
    if parsed:
        tpl_id, event_date = parsed
        tpl = next((t for t in _recurring_store(user) if t.get("id") == tpl_id), None)
        if not tpl:
            raise ValueError("event not found")
        ev = _materialize_exception(user, tpl, event_date, done=done)
        user["life_modules"]["schedule"]["updated_at"] = _utcnow_iso()
        return ev

    for e in _events_store(user):
        if e.get("id") == event_id:
            e["done"] = bool(done)
            e["completed_at"] = _utcnow_iso() if done else None
            if e.get("recurrence_id"):
                e["exception"] = True
            user["life_modules"]["schedule"]["updated_at"] = _utcnow_iso()
            return e
    raise ValueError("event not found")


def delete_event(user: Dict[str, Any], event_id: str, *, scope: str = "this") -> None:
    _purge_legacy_recurring_seeds(user)
    scope = (scope or "this").lower()
    if scope not in ("this", "all"):
        raise ValueError("scope must be this or all")

    tpl_id = _resolve_event_template_id(user, event_id)
    if scope == "all":
        if not tpl_id:
            # Fall back to deleting the single stored event.
            store = _events_store(user)
            user["life_modules"]["schedule"]["structured"]["events"] = [
                e for e in store if e.get("id") != event_id
            ]
            user["life_modules"]["schedule"]["updated_at"] = _utcnow_iso()
            return
        templates = _recurring_store(user)
        for t in templates:
            if t.get("id") == tpl_id:
                t["active"] = False
        store = _events_store(user)
        user["life_modules"]["schedule"]["structured"]["events"] = [
            e for e in store if e.get("recurrence_id") != tpl_id
        ]
        user["life_modules"]["schedule"]["updated_at"] = _utcnow_iso()
        return

    parsed = _parse_virtual_id(event_id)
    if parsed:
        tpl_id_v, event_date = parsed
        # Cancel only this occurrence — keep the rest of the series.
        _cancel_template_date(user, tpl_id_v, event_date)
        store = _events_store(user)
        user["life_modules"]["schedule"]["structured"]["events"] = [
            e
            for e in store
            if not (e.get("recurrence_id") == tpl_id_v and e.get("date") == event_date)
        ]
        user["life_modules"]["schedule"]["updated_at"] = _utcnow_iso()
        return

    store = _events_store(user)
    target = next((e for e in store if e.get("id") == event_id), None)
    user["life_modules"]["schedule"]["structured"]["events"] = [e for e in store if e.get("id") != event_id]
    if target and target.get("recurrence_id") and target.get("date"):
        # Removing a stored recurring exception cancels that date only.
        _cancel_template_date(user, target["recurrence_id"], target["date"])
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
        ends = [g.get("end_time") for g in group if g.get("end_time")]
        time_hint = Counter(times).most_common(1)[0][0] if times else sample.get("time")
        end_hint = Counter(ends).most_common(1)[0][0] if ends else sample.get("end_time")
        dates = [_parse_date(g["date"]) for g in group if g.get("date")]
        if not dates:
            continue
        last = max(dates)
        weekday_counts = Counter(d.weekday() for d in dates)
        weekday, top_count = weekday_counts.most_common(1)[0]
        candidate = last + timedelta(days=1)
        while candidate.weekday() != weekday or candidate <= today:
            candidate += timedelta(days=1)
        if (candidate.isoformat(), title) in existing:
            continue
        # Only mark 毎週 when the same weekday repeated (not 5 different weekdays once each).
        recurrence = "weekly" if top_count >= 2 else None
        reason = "過去の「" + title + "」"
        if top_count >= 2:
            reason += "（同じ曜日" + str(top_count) + "回）から提案"
        elif len(group) >= 2:
            reason += "（" + str(len(group)) + "回）から提案"
        else:
            reason += "をもとに提案"
        suggestions.append(
            {
                "title": title,
                "date": candidate.isoformat(),
                "time": time_hint,
                "end_time": end_hint,
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
            {"title": e.get("title"), "date": e.get("date"), "time": e.get("time"), "end_time": e.get("end_time"), "done": e.get("done")}
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
        "\"time\":\"HH:MM start or null\",\"end_time\":\"HH:MM end or null\","
        "\"reason_ja\":\"Japanese explanation\",\"recurrence\":\"weekly|monthly|null\"}]}. "
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
                "end_time": (item.get("end_time") or "")[:5] or None,
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
    """Apply AI/pattern suggestions without creating date-jump clones.

    If a title already has a weekly series, only accept suggestions on that
    weekday and never spawn a monthly/one-off clone on other weekdays.
    """
    created: List[Dict[str, Any]] = []

    def weekly_weekdays_for_title(title: str) -> Set[int]:
        out: Set[int] = set()
        for t in _recurring_store(user):
            if not t.get("active", True):
                continue
            if (t.get("recurrence") or "weekly") != "weekly":
                continue
            if _title_norm(t.get("title")) != _title_norm(title):
                continue
            wd = t.get("weekday")
            if wd is None:
                try:
                    wd = _parse_date(t["start_date"]).weekday()
                except (KeyError, ValueError):
                    continue
            out.add(int(wd))
        return out

    for s in suggestions:
        title = s.get("title") or ""
        rec = s.get("recurrence")
        weekdays = weekly_weekdays_for_title(title)
        try:
            sug_day = _parse_date(s["date"]).weekday()
        except (KeyError, ValueError):
            sug_day = None

        if weekdays:
            # Already have weekly class(es) for this title.
            if sug_day is None or sug_day not in weekdays:
                continue
            # Do not create another recurring series — one-off on the right weekday is ok,
            # but prefer reusing weekly (recurrence weekly with same weekday).
            if rec == "monthly":
                rec = None
                continue
            if rec == "weekly":
                # Safe: add_recurring_template will reuse same weekday series.
                pass
            else:
                # Skip plain duplicates on days the weekly series already covers.
                continue

        created.append(
            add_event(
                user,
                title=title,
                event_date=s["date"],
                event_time=s.get("time"),
                event_end_time=s.get("end_time"),
                recurrence=rec,
            )
        )
        # Refresh after create so later suggestions see new weekly templates.
    return created


def home_summary(user: Dict[str, Any]) -> Dict[str, Any]:
    # Today-only focus keeps this cheap (calendar uses its own month window).
    today_s = date.today().isoformat()
    sched = list_events(user, on_date=today_s)
    from health_eval import evaluate_health, mental_needed, mental_reminder_due

    health = user.get("life_modules", {}).get("health", {}).get("structured", {}) or {}
    ev = evaluate_health(health)
    score = int(ev.get("score") or 0)
    status = ev.get("status_ja") or "注意"
    today_items = sorted(
        (sched.get("today_open") or []) + (sched.get("today_done") or []),
        key=lambda e: (e.get("time") or "99:99", e.get("title") or ""),
    )
    today_open_n = len(sched.get("today_open") or [])
    needed = mental_needed(health)
    remind = mental_reminder_due(health)
    if remind and not user.get("pending_notification"):
        user["pending_notification"] = "LUNAが今日の気分を聞きたいよ"
    from goals_service import home_goals_summary
    from money_eval import evaluate_money, spend_pace_snapshot

    goals_sum = home_goals_summary(user)
    money_s = (user.get("life_modules") or {}).get("money", {}).get("structured", {}) or {}
    money_ev = evaluate_money(user, money_s)
    money_pace = spend_pace_snapshot(money_s)
    money_label = money_ev.get("status_ja") or "—"
    if money_pace.get("today_spent"):
        money_label = f"今日{int(money_pace['today_spent']):,}円"
    elif money_ev.get("score") is not None:
        money_label = f"{money_ev.get('status_ja') or '—'} {money_ev.get('score')}"
    return {
        "schedule": {
            "open_count": today_open_n,
            "today_open": today_open_n,
            "label": ("今日" + str(today_open_n) + "件") if today_open_n else "今日の予定なし",
            "today_items": today_items,
        },
        "health": {
            "score": score,
            "status_ja": status,
            "label": f"{status} {score}",
            "mental_needed": needed,
            "mental_reminder": remind,
        },
        "money": {
            "score": money_ev.get("score"),
            "status_ja": money_ev.get("status_ja"),
            "label": money_label,
            "today_spent": money_pace.get("today_spent") or 0,
        },
        "goals": goals_sum,
        "date_ja": f"{date.today().month}月{date.today().day}日",
        "pending_notification": user.get("pending_notification"),
    }
