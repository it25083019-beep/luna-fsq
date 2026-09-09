# -*- coding: utf-8 -*-
"""Today's calendar + health → study pace, rest quests, and reminder payloads."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional

JST = timezone(timedelta(hours=9))
LEAD_MINUTES = 10
DEFAULT_BLOCK_MIN = 50


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
    """Web/native-shaped reminder list from today's open events."""
    now = now or _now_jst()
    today = now.date()
    today_s = today.isoformat()
    fit = fit or assess_day_load(user)
    from schedule_service import list_events

    sched = list_events(user, on_date=today_s)
    open_items = list(sched.get("today_open") or [])
    reminders: List[Dict[str, Any]] = []

    for ev in open_items:
        start_t = _parse_hhmm(ev.get("time"))
        if start_t is None:
            continue
        start_at = datetime.combine(today, start_t, tzinfo=JST)
        fire_at = start_at - timedelta(minutes=LEAD_MINUTES)
        if fire_at < now - timedelta(minutes=1):
            continue
        title = (ev.get("title") or "予定").strip() or "予定"
        time_label = start_t.strftime("%H:%M")
        end_t = _parse_hhmm(ev.get("end_time"))
        if end_t:
            time_label += "–" + end_t.strftime("%H:%M")
        reminders.append(
            {
                "id": f"evt-{(ev.get('id') or title)}",
                "kind": "schedule",
                "fire_at": fire_at.isoformat(),
                "title": "もうすぐ予定",
                "body": f"{time_label} {title}（{LEAD_MINUTES}分前）",
                "event_id": ev.get("id"),
                "url": "/app",
            }
        )

    if fit.get("recommend") in ("rest", "micro") and fit.get("coach_ja"):
        reminders.insert(
            0,
            {
                "id": f"pace-{today_s}",
                "kind": "coach",
                "fire_at": now.isoformat(),
                "title": "今日のペース",
                "body": fit["coach_ja"],
                "url": "/app",
            },
        )

    enabled = bool(user.get("notify_schedule"))
    return {
        "enabled": enabled,
        "date": today_s,
        "lead_minutes": LEAD_MINUTES,
        "day_fit": fit,
        "reminders": reminders,
        "hint_ja": (
            "予定の10分前にリマインダーを出します。"
            "ホーム画面に追加すると使いやすいです。"
            "タブを完全に閉じると届かないことがあります。"
            "ネイティブアプリでは同じ内容をプッシュ通知にできます。"
        ),
    }
