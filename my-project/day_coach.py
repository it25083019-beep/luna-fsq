# -*- coding: utf-8 -*-
"""Today's calendar + health → study pace, rest quests, and reminder payloads."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional

JST = timezone(timedelta(hours=9))
LEAD_MINUTES = 10
LEAD_OFFSETS = (60, 30, 10)
DEFAULT_DIGEST_HOUR = 7
DEFAULT_BLOCK_MIN = 50
WEEKDAYS_JA = "月火水木金土日"
LEAD_LABEL_JA = {60: "1時間前", 30: "30分前", 10: "10分前"}


def _now_jst() -> datetime:
    return datetime.now(JST)


def _today_jst() -> date:
    return _now_jst().date()


def _parse_hhmm(value: Optional[str]) -> Optional[time]:
    raw = (value or "").strip()
    if not raw or ":" not in raw:
        return None
    parts = raw.split(":")
    try:
        h = int(parts[0])
        m = int(parts[1])
    except (TypeError, ValueError):
        return None
    if h < 0 or h > 23 or m < 0 or m > 59:
        return None
    return time(h, m)


def _hhmm_minutes(value: Optional[str]) -> Optional[int]:
    parsed = _parse_hhmm(value)
    if parsed is None:
        return None
    return parsed.hour * 60 + parsed.minute


def event_minutes(event: Dict[str, Any]) -> int:
    start = _hhmm_minutes(event.get("time"))
    end = _hhmm_minutes(event.get("end_time"))
    if start is not None and end is not None and end > start:
        return end - start
    return DEFAULT_BLOCK_MIN


def _sleep_hours(health: Dict[str, Any]) -> Optional[float]:
    raw = health.get("sleep_hours")
    try:
        if raw is None or raw == "":
            return None
        return float(raw)
    except (TypeError, ValueError):
        return None


def date_label_ja(iso: Optional[str], *, today: Optional[date] = None) -> str:
    raw = str(iso or "").strip()[:10]
    try:
        d = date.fromisoformat(raw)
    except ValueError:
        d = today or _today_jst()
    return f"{d.year}年{d.month}月{d.day}日（{WEEKDAYS_JA[d.weekday()]}）"


def clock_label(event: Dict[str, Any]) -> str:
    start = (event.get("time") or "").strip()
    end = (event.get("end_time") or "").strip()
    if start and end:
        return f"{start}〜{end}"
    if start:
        return start
    if end:
        return f"〜{end}"
    return "終日"


def format_event_detail(event: Dict[str, Any], *, today: Optional[date] = None) -> str:
    title = (event.get("title") or "予定").strip() or "予定"
    lines = [
        f"{date_label_ja(event.get('date'), today=today)} {clock_label(event)}",
        f"やること：{title}",
    ]
    loc = str(event.get("location") or "").strip()
    if loc:
        lines.append(f"場所：{loc}")
    note = str(event.get("note") or "").strip()
    if note:
        lines.append(note[:80])
    return "\n".join(lines)


def _companion_who(user: Dict[str, Any]) -> str:
    name = str(user.get("companion_name") or "ルナ").strip()
    return name or "ルナ"


def _digest_hour(user: Dict[str, Any]) -> int:
    try:
        hour = int(user.get("notify_digest_hour") if user.get("notify_digest_hour") is not None else DEFAULT_DIGEST_HOUR)
    except (TypeError, ValueError):
        hour = DEFAULT_DIGEST_HOUR
    return max(0, min(23, hour))


def _lead_offsets(user: Dict[str, Any]) -> List[int]:
    raw = user.get("notify_leads")
    if isinstance(raw, list) and raw:
        out: List[int] = []
        for item in raw:
            try:
                n = int(item)
            except (TypeError, ValueError):
                continue
            if n in LEAD_OFFSETS and n not in out:
                out.append(n)
        if out:
            return out
    return list(LEAD_OFFSETS)


def rest_actions(load: str) -> List[Dict[str, Any]]:
    rows = [
        {
            "id": "rest_stretch",
            "type": "rest",
            "title_ja": "5分ストレッチ",
            "chip": "5分ストレッチしたよ",
            "exp": 6,
            "icon_class": "green",
        },
        {
            "id": "rest_water",
            "type": "rest",
            "title_ja": "水を一杯飲む",
            "chip": "水を飲んだよ",
            "exp": 4,
            "icon_class": "blue",
        },
        {
            "id": "rest_eyes",
            "type": "rest",
            "title_ja": "画面から目を休める",
            "chip": "目を休めたよ",
            "exp": 4,
            "icon_class": "pink",
        },
        {
            "id": "rest_walk",
            "type": "rest",
            "title_ja": "短い散歩・体を動かす",
            "chip": "ちょっと体を動かしたよ",
            "exp": 8,
            "icon_class": "yellow",
        },
    ]
    if load == "recover":
        return rows
    if load in ("heavy", "busy"):
        return rows[:2]
    return []


def assess_day_load(user: Dict[str, Any]) -> Dict[str, Any]:
    """How packed today is, and what FSQ should recommend."""
    today = _today_jst()
    today_s = today.isoformat()
    from schedule_service import list_events

    sched = list_events(user, on_date=today_s)
    open_items = list(sched.get("today_open") or [])
    done_items = list(sched.get("today_done") or [])
    open_n = len(open_items)
    open_min = sum(event_minutes(e) for e in open_items)
    done_min = sum(event_minutes(e) for e in done_items)

    health = (user.get("life_modules") or {}).get("health", {}).get("structured", {}) or {}
    mental = str(health.get("mental_status") or "").strip()
    sleep = _sleep_hours(health)

    load = "light"
    if open_n >= 5 or open_min >= 360:
        load = "heavy"
    elif open_n >= 3 or open_min >= 180:
        load = "busy"

    worn = mental in ("疲れ", "落ち込み", "不安")
    short_sleep = sleep is not None and sleep < 5.5
    if mental == "落ち込み" or (short_sleep and worn) or (mental == "疲れ" and load in ("busy", "heavy")):
        load = "recover"
    elif short_sleep and load == "light":
        load = "busy"

    if load == "recover":
        recommend = "rest"
        study_minutes = 0
        label_ja = "回復デー"
        coach_ja = (
            "今日は予定が多いか、心と体がお疲れ気味だよ。"
            "学習は無理しなくていい。ストレッチ・水分・短い休憩で回復しよう。"
        )
    elif load == "heavy":
        recommend = "micro"
        study_minutes = 8
        label_ja = "満員デー"
        coach_ja = (
            f"今日の予定は残り{open_n}件（約{open_min}分）。"
            "長いレッスンより、8分くらいの短いクエストか、体を休める行動がおすすめ。"
        )
    elif load == "busy":
        recommend = "micro"
        study_minutes = 12
        label_ja = "忙しい日"
        coach_ja = (
            f"今日は少し忙しいよ（残り{open_n}件）。"
            "12分くらいの短い学習か、合間のストレッチがちょうどいい。"
        )
    else:
        recommend = "lesson"
        study_minutes = 25
        label_ja = "学習向き"
        if open_n:
            coach_ja = (
                f"今日の予定は残り{open_n}件。余裕があるから、次のレッスンを進めやすい日だよ。"
            )
        else:
            coach_ja = "今日は予定が空いているよ。次のレッスンか、好きな休憩、どっちでも大丈夫。"

    return {
        "date": today_s,
        "load": load,
        "recommend": recommend,
        "study_minutes": study_minutes,
        "label_ja": label_ja,
        "coach_ja": coach_ja,
        "open_count": open_n,
        "open_minutes": open_min,
        "done_count": len(done_items),
        "done_minutes": done_min,
        "mental_status": mental or None,
        "sleep_hours": sleep,
        "rest_actions": rest_actions(load),
    }


def build_today_reminders(
    user: Dict[str, Any],
    *,
    fit: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Daily digest + 60/30/10-minute reminders with specific what/when/where copy."""
    now = now or _now_jst()
    today = now.date()
    today_s = today.isoformat()
    fit = fit or assess_day_load(user)
    from schedule_service import list_events

    sched = list_events(user, on_date=today_s)
    open_items = list(sched.get("today_open") or [])
    who = _companion_who(user)
    leads = _lead_offsets(user)
    reminders: List[Dict[str, Any]] = []

    digest_at = datetime.combine(today, time(_digest_hour(user), 0), tzinfo=JST)
    if digest_at < now:
        digest_at = now
    if open_items:
        numbered = []
        for i, ev in enumerate(open_items, 1):
            numbered.append(f"{i}. {format_event_detail(ev, today=today)}")
        digest_body = f"今日の予定は{len(open_items)}件だよ。\n\n" + "\n\n".join(numbered)
    else:
        digest_body = "今日は予定が空いているよ。新しい用事がメールから入ったら、また知らせるね。"
    reminders.append(
        {
            "id": f"digest-{today_s}",
            "kind": "digest",
            "fire_at": digest_at.isoformat(),
            "title": f"{who}｜今日の予定",
            "body": digest_body,
            "url": "/app?digest=1",
            "require_interaction": True,
            "events": [
                {
                    "id": ev.get("id"),
                    "title": ev.get("title"),
                    "date": ev.get("date") or today_s,
                    "time": ev.get("time"),
                    "end_time": ev.get("end_time"),
                    "location": ev.get("location"),
                    "detail": format_event_detail(ev, today=today),
                }
                for ev in open_items
            ],
        }
    )

    for ev in open_items:
        detail = format_event_detail(ev, today=today)
        eid = ev.get("id")
        urgency = str(ev.get("urgency") or "normal").lower()
        start_t = _parse_hhmm(ev.get("time"))
        if start_t is None:
            if urgency == "high":
                reminders.append(
                    {
                        "id": f"urgent-{eid or ev.get('title')}",
                        "kind": "urgent",
                        "fire_at": now.isoformat(),
                        "title": f"{who}｜急ぎの用事",
                        "body": detail + "\n\n急ぎみたい。今の体調と気持ち、教えてくれる？",
                        "event_id": eid,
                        "url": f"/app?checkin=1&eid={eid or ''}&lead=0",
                        "require_interaction": True,
                        "ask_mood": True,
                        "lead_minutes": 0,
                    }
                )
            continue
        start_at = datetime.combine(today, start_t, tzinfo=JST)
        if urgency == "high" and start_at - now <= timedelta(hours=2):
            reminders.append(
                {
                    "id": f"urgent-{eid or ev.get('title')}",
                    "kind": "urgent",
                    "fire_at": now.isoformat(),
                    "title": f"{who}｜急ぎの用事",
                    "body": detail + "\n\n急ぎの予定だよ。体調と気持ち、教えてくれる？",
                    "event_id": eid,
                    "url": f"/app?checkin=1&eid={eid or ''}&lead=0",
                    "require_interaction": True,
                    "ask_mood": True,
                    "lead_minutes": 0,
                }
            )
        for lead in leads:
            fire_at = start_at - timedelta(minutes=lead)
            if fire_at < now - timedelta(minutes=1):
                continue
            label = LEAD_LABEL_JA.get(lead, f"{lead}分前")
            reminders.append(
                {
                    "id": f"evt-{eid or ev.get('title')}-{lead}",
                    "kind": "schedule",
                    "fire_at": fire_at.isoformat(),
                    "title": f"{who}｜{label}のリマインド",
                    "body": (
                        f"{detail}\n\n"
                        f"あと{label.replace('前', '')}だよ。"
                        "今の体調と気持ち、教えてくれる？"
                    ),
                    "event_id": eid,
                    "url": f"/app?checkin=1&eid={eid or ''}&lead={lead}",
                    "require_interaction": True,
                    "ask_mood": True,
                    "lead_minutes": lead,
                }
            )

    if fit.get("recommend") in ("rest", "micro") and fit.get("coach_ja"):
        reminders.insert(
            1,
            {
                "id": f"pace-{today_s}",
                "kind": "coach",
                "fire_at": now.isoformat(),
                "title": f"{who}｜今日のペース",
                "body": fit["coach_ja"],
                "url": "/app",
            },
        )

    enabled = bool(user.get("notify_schedule"))
    return {
        "enabled": enabled,
        "date": today_s,
        "lead_minutes": LEAD_MINUTES,
        "lead_offsets": leads,
        "digest_hour": _digest_hour(user),
        "day_fit": fit,
        "reminders": reminders,
        "hint_ja": (
            "毎日、今日の予定を大きな通知でまとめます。"
            "各予定の1時間前・30分前・10分前にも、何を・いつ・どこでするかを知らせて、体調を聞きます。"
            "ホーム画面に追加すると使いやすいです。"
            "タブを完全に閉じると届かないことがあります。"
        ),
    }


def record_schedule_checkin(
    user: Dict[str, Any],
    *,
    event_id: str,
    mood: str,
    lead_minutes: int = 10,
) -> Dict[str, Any]:
    """Remember how the user felt before a specific event."""
    from care_memory import touch_care_memory
    from care_timeline import append_care_event
    from life_dashboard import save_mental_checkin
    from schedule_service import attach_event_checkin, get_event

    ev = get_event(user, event_id)
    title = ((ev or {}).get("title") or "予定").strip() or "予定"
    when = clock_label(ev or {}) if ev else ""
    dash = save_mental_checkin(user, mood)
    stored = attach_event_checkin(
        user,
        event_id,
        mood=mood,
        lead_minutes=lead_minutes,
    )
    lead_ja = LEAD_LABEL_JA.get(int(lead_minutes or 0), f"{lead_minutes}分前") if lead_minutes else "直前"
    snippet = f"「{title}」の{lead_ja}、気分は{mood}"
    if when:
        snippet = f"{when} {snippet}"
    touch_care_memory(user, "health", snippet, applied=[f"気分→{mood}"])
    append_care_event(user, "schedule", f"「{title}」前に気分「{mood}」", detail=snippet)
    return {
        "ok": True,
        "dashboard": dash,
        "event": stored or ev,
        "mood": mood,
        "lead_minutes": lead_minutes,
    }
