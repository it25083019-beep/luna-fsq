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
LEAD_SOON_JA = {60: "1時間後", 30: "30分後", 10: "10分後"}


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


def compact_date_ja(iso: Optional[str], *, today: Optional[date] = None) -> str:
    raw = str(iso or "").strip()[:10]
    try:
        d = date.fromisoformat(raw)
    except ValueError:
        d = today or _today_jst()
    return f"{d.month}/{d.day}"


def format_notify_brief(event: Dict[str, Any], *, today: Optional[date] = None) -> str:
    """Short notification line: date time · action · place."""
    title = (event.get("title") or "予定").strip() or "予定"
    bits = [f"{compact_date_ja(event.get('date'), today=today)} {clock_label(event)}", title]
    loc = str(event.get("location") or "").strip()
    if loc:
        bits.append(loc)
    return "・".join(bits)


def event_bounds(
    event: Dict[str, Any],
    *,
    today: Optional[date] = None,
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Start/end datetimes in JST. Missing end uses the event length (min 30m)."""
    day = today or _today_jst()
    start_t = _parse_hhmm(event.get("time"))
    if start_t is None:
        return None, None
    start = datetime.combine(day, start_t, tzinfo=JST)
    end_t = _parse_hhmm(event.get("end_time"))
    if end_t is not None:
        end = datetime.combine(day, end_t, tzinfo=JST)
        if end <= start:
            end = start + timedelta(minutes=max(event_minutes(event), 30))
    else:
        end = start + timedelta(minutes=max(event_minutes(event), 30))
    return start, end


def event_kind(event: Optional[Dict[str, Any]]) -> str:
    blob = " ".join(
        str((event or {}).get(k) or "") for k in ("title", "location", "note")
    )
    low = blob.lower()
    rules = (
        ("school", ("学校", "授業", "講義", "クラス", "学園", "登校", "school", "lecture", "class")),
        ("work", ("バイト", "シフト", "仕事", "勤務", "アルバイト", "workplace", "part-time", "job")),
        ("study", ("勉強", "課題", "自習", "宿題", "受験", "テスト", "試験", "ドリル")),
    )
    for kind, keys in rules:
        if any(k.lower() in low if k.isascii() else k in blob for k in keys):
            return kind
    return "event"


def event_kind_label(event: Optional[Dict[str, Any]]) -> str:
    kind = event_kind(event)
    if kind == "school":
        return "授業"
    if kind == "work":
        return "バイト"
    if kind == "study":
        title = str((event or {}).get("title") or "").strip()
        return title[:12] if title else "勉強"
    title = str((event or {}).get("title") or "").strip() or "予定"
    return title[:12]


def _companion_voice(user: Optional[Dict[str, Any]]) -> str:
    cid = str((user or {}).get("companion_id") or "luna").strip().lower()
    if cid in ("luno", "ren", "hachi", "momo", "taro", "ponta"):
        return cid
    return "luna"


def _pick_current_event(
    items: List[Dict[str, Any]],
    *,
    now: datetime,
    today: date,
) -> Optional[Dict[str, Any]]:
    happening: List[tuple[datetime, Dict[str, Any]]] = []
    for ev in items:
        start, end = event_bounds(ev, today=today)
        if start and end and start <= now < end:
            happening.append((start, ev))
    if not happening:
        return None
    happening.sort(key=lambda row: row[0], reverse=True)
    return happening[0][1]


def _pick_upcoming_event(
    items: List[Dict[str, Any]],
    *,
    now: datetime,
    today: date,
) -> Optional[Dict[str, Any]]:
    later: List[tuple[datetime, Dict[str, Any]]] = []
    for ev in items:
        start, _end = event_bounds(ev, today=today)
        if start and start > now:
            later.append((start, ev))
    if not later:
        return None
    later.sort(key=lambda row: row[0])
    return later[0][1]


def _pick_just_ended_event(
    items: List[Dict[str, Any]],
    *,
    now: datetime,
    today: date,
    within_min: int = 45,
) -> Optional[Dict[str, Any]]:
    ended: List[tuple[datetime, Dict[str, Any]]] = []
    for ev in items:
        _start, end = event_bounds(ev, today=today)
        if end and end <= now < end + timedelta(minutes=within_min):
            ended.append((end, ev))
    if not ended:
        return None
    ended.sort(key=lambda row: row[0], reverse=True)
    return ended[0][1]


def _care_line(user: Dict[str, Any], situation: str, kind: str, **fmt: str) -> str:
    voice = _companion_voice(user)
    table = _CARE_LINES.get(voice) or _CARE_LINES["luna"]
    bucket = table.get(situation) or _CARE_LINES["luna"][situation]
    tpl = bucket.get(kind) or bucket.get("event") or ""
    return tpl.format(**fmt).strip()


_CARE_LINES: Dict[str, Dict[str, Dict[str, str]]] = {
    "luna": {
        "during": {
            "school": "{prefix}いまは授業の時間ですね。アプリを開いてくれたのは、何かあったから？大丈夫？",
            "work": "{prefix}いまはバイトの時間ですね。少し休んでるの？それとも何かあった？",
            "study": "{prefix}いま勉強の時間ですね。詰まってる？ひとこと教えて。",
            "event": "{prefix}いま「{label}」の時間ですね。大丈夫？何かあったら聞いてます。",
        },
        "soon": {
            "school": "{prefix}もうすぐ授業だよ。準備できた？今日の調子はどう？",
            "work": "{prefix}もうすぐバイトだよ。体の調子、大丈夫？",
            "study": "{prefix}もうすぐ{label}だよ。準備できた？",
            "event": "{prefix}もうすぐ「{label}」だよ。準備できた？今日の調子はどう？",
        },
        "later": {
            "school": "{prefix}今日は{clock}から授業だよ。いまは空き時間だね。何か話したい？",
            "work": "{prefix}今日は{clock}からバイトだよ。いまは空き時間だね。何かあった？",
            "study": "{prefix}今日は{clock}から{label}だよ。{place}いまのうちに、ひとこと聞かせて。",
            "event": "{prefix}今日は{clock}から「{label}」だよ。{place}いまは空き時間だね。何か話したい？",
        },
        "ended": {
            "school": "{prefix}授業おつかれさま。いまの気分、ひとこと教えて？",
            "work": "{prefix}バイトおつかれさま。いま、大丈夫？",
            "study": "{prefix}{label}おつかれ。いまの感じ、教えて。",
            "event": "{prefix}「{label}」おつかれさま。いまの気分はどう？",
        },
        "overdue": {
            "school": "{prefix}授業の予定、時間は過ぎてるよ。終わった？まだ続いてる？",
            "work": "{prefix}バイトの予定、時間は過ぎてるよ。終わった？まだ続いてる？",
            "study": "{prefix}「{label}」の時間は過ぎてるよ。終わった？",
            "event": "{prefix}「{label}」の時間は過ぎてるよ。終わった？まだ続いてる？",
        },
    },
    "luno": {
        "during": {
            "school": "{prefix}いま授業の時間だよね。アプリ開いたの、何かあった？大丈夫？",
            "work": "{prefix}いまバイトの時間だよね。ちょっと休んでる？それとも何かあった？",
            "study": "{prefix}いま勉強の時間だよね。つまってる？ルノ、聞くよ。",
            "event": "{prefix}いま「{label}」の時間だよ。大丈夫？何かあった？",
        },
        "soon": {
            "school": "{prefix}もうすぐ授業だよ。準備できた？きょうの調子はどう？",
            "work": "{prefix}もうすぐバイトだよ。からだ、だいじょうぶ？",
            "study": "{prefix}もうすぐ{label}だよ。準備できた？",
            "event": "{prefix}もうすぐ「{label}」だよ。準備できた？調子はどう？",
        },
        "later": {
            "school": "{prefix}きょうは{clock}から授業だよ。いまは空き時間だね。何か話したい？",
            "work": "{prefix}きょうは{clock}からバイトだよ。いまは空き時間だね。何かあった？",
            "study": "{prefix}きょうは{clock}から{label}だよ。{place}いま、ひとこと聞かせて。",
            "event": "{prefix}きょうは{clock}から「{label}」だよ。{place}いまは空き時間だね。何か話したい？",
        },
        "ended": {
            "school": "{prefix}授業おつかれ。いまの気分、ひとこと教えて？",
            "work": "{prefix}バイトおつかれ。いま、大丈夫？",
            "study": "{prefix}{label}おつかれ。いまの感じ、教えて〜。",
            "event": "{prefix}「{label}」おつかれ。いまの気分はどう？",
        },
        "overdue": {
            "school": "{prefix}授業の予定、時間すぎてるよ。終わった？まだ続いてる？",
            "work": "{prefix}バイトの予定、時間すぎてるよ。終わった？まだ続いてる？",
            "study": "{prefix}「{label}」、時間すぎてるよ。終わった？",
            "event": "{prefix}「{label}」、時間すぎてるよ。終わった？まだ続いてる？",
        },
    },
    "ren": {
        "during": {
            "school": "{prefix}いま授業中だろ。アプリ開いたのは、何かあったのか。話せる範囲でいい。",
            "work": "{prefix}いまシフト中だろ。少し休んでるのか。無理してないか。",
            "study": "{prefix}いま勉強の時間だ。詰まってるなら、俺が聞く。",
            "event": "{prefix}いま「{label}」の時間だ。大丈夫か。何かあったら言え。",
        },
        "soon": {
            "school": "{prefix}もうすぐ授業だ。準備できたか。調子はどうだ。",
            "work": "{prefix}もうすぐバイトだ。体のほうは大丈夫か。",
            "study": "{prefix}もうすぐ{label}だ。準備はいいか。",
            "event": "{prefix}もうすぐ「{label}」だ。準備できたか。",
        },
        "later": {
            "school": "{prefix}今日は{clock}から授業だ。いまは空きだな。何かあれば言え。",
            "work": "{prefix}今日は{clock}からバイトだ。いまは空きだな。無理するなよ。",
            "study": "{prefix}今日は{clock}から{label}だ。{place}いまのうちにひとことくれ。",
            "event": "{prefix}今日は{clock}から「{label}」だ。{place}いまは空きだな。何かあれば言え。",
        },
        "ended": {
            "school": "{prefix}授業おつかれ。いまの気分、ひとことくれ。",
            "work": "{prefix}バイトおつかれ。無理してないか。",
            "study": "{prefix}{label}おつかれ。いまの感じを教えてくれ。",
            "event": "{prefix}「{label}」おつかれ。いまの調子はどうだ。",
        },
        "overdue": {
            "school": "{prefix}授業の時間は過ぎてる。終わったのか。まだ続いてるのか。",
            "work": "{prefix}バイトの時間は過ぎてる。終わったのか。",
            "study": "{prefix}「{label}」の時間は過ぎてる。終わったか。",
            "event": "{prefix}「{label}」の時間は過ぎてる。終わったのか。まだ続いてるのか。",
        },
    },
    "hachi": {
        "during": {
            "school": "{prefix}いま学校の時間だよ。わんっ、大丈夫？なにかあった？",
            "work": "{prefix}いまバイトの時間だよ。わんっ、ちょっと休憩？大丈夫？",
            "study": "{prefix}いま勉強の時間だよ。つまってる？ハチ、聞くよ。",
            "event": "{prefix}いま「{label}」の時間だよ。わんっ、大丈夫？",
        },
        "soon": {
            "school": "{prefix}もうすぐ学校だよ。準備できた？わんっ。",
            "work": "{prefix}もうすぐバイトだよ。からだ、だいじょうぶ？",
            "study": "{prefix}もうすぐ{label}だよ。準備できた？",
            "event": "{prefix}もうすぐ「{label}」だよ。準備できた？わんっ。",
        },
        "later": {
            "school": "{prefix}きょうは{clock}から学校だよ。いまは空きだね。なにか話そ？",
            "work": "{prefix}きょうは{clock}からバイトだよ。いまは空きだね。わんっ。",
            "study": "{prefix}きょうは{clock}から{label}だよ。{place}ひとこと聞かせて。",
            "event": "{prefix}きょうは{clock}から「{label}」だよ。{place}いまは空きだね。",
        },
        "ended": {
            "school": "{prefix}学校おつかれ。わんっ、いまの気分どう？",
            "work": "{prefix}バイトおつかれ。だいじょうぶ？",
            "study": "{prefix}{label}おつかれ。いまの感じ、教えて。",
            "event": "{prefix}「{label}」おつかれ。わんっ、気分どう？",
        },
        "overdue": {
            "school": "{prefix}学校の時間、すぎてるよ。終わった？まだ続いてる？",
            "work": "{prefix}バイトの時間、すぎてるよ。終わった？",
            "study": "{prefix}「{label}」、時間すぎてるよ。終わった？",
            "event": "{prefix}「{label}」、時間すぎてるよ。終わった？わんっ。",
        },
    },
}
_CARE_LINES["momo"] = _CARE_LINES["luna"]
_CARE_LINES["taro"] = _CARE_LINES["luna"]
_CARE_LINES["ponta"] = _CARE_LINES["hachi"]


def agenda_for_companion(
    user: Dict[str, Any],
    *,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Today's real calendar, compact enough for chat (not the whole inbox)."""
    now = now or _now_jst()
    today = now.date()
    from schedule_service import list_events

    sched = list_events(user, on_date=today.isoformat())
    open_items = sorted(
        list(sched.get("today_open") or []),
        key=lambda e: (e.get("time") or "99:99", e.get("title") or ""),
    )
    done_items = list(sched.get("today_done") or [])
    untimed: Optional[Dict[str, Any]] = next(
        (ev for ev in open_items if _parse_hhmm(ev.get("time")) is None),
        None,
    )
    current_ev = _pick_current_event(open_items, now=now, today=today)
    next_ev = _pick_upcoming_event(open_items, now=now, today=today)
    just_ended = _pick_just_ended_event(open_items, now=now, today=today)
    if next_ev is None and current_ev is None:
        next_ev = untimed or (open_items[0] if open_items else None)
    hour = now.hour
    if hour >= 20:
        phase = "evening"
    elif hour < 11:
        phase = "morning"
    else:
        phase = "day"
    return {
        "date": today.isoformat(),
        "phase": phase,
        "now": now.strftime("%H:%M"),
        "open_count": len(open_items),
        "done_count": len(done_items),
        "current": current_ev,
        "just_ended": just_ended,
        "next": next_ev,
        "open_items": open_items[:6],
        "done_items": done_items[:6],
    }


def _place_bit(event: Optional[Dict[str, Any]]) -> str:
    loc = str((event or {}).get("location") or "").strip()
    return f"場所は{loc}。" if loc else ""


def companion_agenda_line(
    user: Dict[str, Any],
    *,
    now: Optional[datetime] = None,
    who: str = "",
) -> Optional[str]:
    """Care about the clock: if they open during a saved event, ask what happened."""
    now = now or _now_jst()
    ag = agenda_for_companion(user, now=now)
    prefix = f"{who}、" if who else ""
    current = ag.get("current")
    just_ended = ag.get("just_ended")
    nxt = ag.get("next")
    open_n = int(ag.get("open_count") or 0)
    done_n = int(ag.get("done_count") or 0)
    today = now.date()

    if current:
        kind = event_kind(current)
        return _care_line(
            user, "during", kind, prefix=prefix, label=event_kind_label(current), clock="", place=""
        )

    if just_ended:
        kind = event_kind(just_ended)
        end = event_bounds(just_ended, today=today)[1]
        if end and now - end <= timedelta(minutes=45):
            return _care_line(
                user, "ended", kind, prefix=prefix, label=event_kind_label(just_ended), clock="", place=""
            )

    overdue = None
    for ev in ag.get("open_items") or []:
        _start, end = event_bounds(ev, today=today)
        if end and now >= end + timedelta(minutes=45):
            overdue = ev
            break
    if overdue:
        kind = event_kind(overdue)
        return _care_line(
            user, "overdue", kind, prefix=prefix, label=event_kind_label(overdue), clock="", place=""
        )

    if nxt:
        start, _end = event_bounds(nxt, today=today)
        kind = event_kind(nxt)
        label = event_kind_label(nxt)
        place = _place_bit(nxt)
        if start:
            mins = int((start - now).total_seconds() // 60)
            clock = start.strftime("%H:%M")
            if 0 < mins <= 30:
                return _care_line(user, "soon", kind, prefix=prefix, label=label, clock=clock, place=place)
            if mins > 30:
                return _care_line(user, "later", kind, prefix=prefix, label=label, clock=clock, place=place)

    if ag.get("phase") == "evening":
        if open_n == 0 and done_n:
            return f"{prefix}今日の用事は{done_n}件、ぜんぶおわったよ。よくがんばった。"
        if open_n:
            return f"{prefix}今日まだ{open_n}件残ってるよ。無理しないで、ひとこと聞かせて。"
        return None
    if not open_n:
        return None
    return f"{prefix}今日の予定は{open_n}件だよ。いまの調子、どう？"


def companion_evening_line(
    user: Dict[str, Any],
    *,
    now: Optional[datetime] = None,
    who: str = "",
) -> str:
    """End-of-day recap from the real calendar."""
    now = now or _now_jst()
    care = companion_agenda_line(user, now=now, who=who)
    if care:
        return care
    prefix = f"{who}、" if who else ""
    ag = agenda_for_companion(user, now=now)
    open_n = int(ag.get("open_count") or 0)
    done_n = int(ag.get("done_count") or 0)
    if open_n == 0 and done_n:
        return f"{prefix}今日の用事は{done_n}件、ぜんぶおわったよ。よくがんばった。"
    if open_n == 0:
        return f"{prefix}今日は予定が空いてたよ。ゆっくり休もう。"
    return f"{prefix}今日まだ{open_n}件残ってるよ。無理しないで、ひとこと聞かせて。"


def companion_agenda_prompt(user: Dict[str, Any], *, now: Optional[datetime] = None) -> str:
    """System-prompt block so the companion talks about real events, not invented ones."""
    now = now or _now_jst()
    ag = agenda_for_companion(user, now=now)
    lines = [
        "TODAY'S REAL CALENDAR (source of truth — do not invent events or dump mail):",
        f"now={ag['now']} JST phase={ag['phase']} open={ag['open_count']} done={ag['done_count']}",
    ]
    current = ag.get("current") or {}
    nxt = ag.get("next") or {}
    if not ag["open_count"] and not ag["done_count"]:
        lines.append("No events today. Greet normally. Do not invent a timetable.")
        return "\n".join(lines)
    if current:
        lines.append(f"- [NOW IN PROGRESS] {format_notify_brief(current)}")
        lines.append(
            "The user opened the app DURING this event. Do NOT say 「次は」. "
            "Compare the clock: they should be in that activity. Ask gently if "
            "something happened / if they are okay, in one short caring sentence."
        )
    if nxt and (not current or nxt.get("id") != current.get("id")):
        lines.append(f"- [UPCOMING] {format_notify_brief(nxt)}")
    for ev in ag.get("open_items") or []:
        eid = ev.get("id")
        if eid and eid in {current.get("id"), nxt.get("id")}:
            continue
        lines.append(f"- [open] {format_notify_brief(ev)}")
    for ev in ag.get("done_items") or []:
        lines.append(f"- [done] {format_notify_brief(ev)}")
    if not current:
        lines.append(
            "On greet, care about the clock vs the saved timetable. "
            "If the next event is later, say they have free time and invite a word. "
            "Never dump the whole inbox or a raw 「9/16 09:20〜16:30・学校だよ」 line. "
            "If they say 夜チェックイン or 振り返り, recap done vs left, then one next step."
        )
    return "\n".join(lines)


def _leads_for_event(
    event: Dict[str, Any],
    *,
    now: datetime,
    today: date,
    allowed: List[int],
) -> tuple[List[int], bool]:
    """Pick reminder offsets from remaining time and urgency. Returns (leads, ping_now)."""
    urgency = str(event.get("urgency") or "normal").lower()
    start_t = _parse_hhmm(event.get("time"))
    allowed_set = set(allowed)

    def pick(wanted: List[int]) -> List[int]:
        return [m for m in wanted if m in allowed_set]

    if start_t is None:
        return [], urgency == "high"
    start_at = datetime.combine(today, start_t, tzinfo=JST)
    mins_left = (start_at - now).total_seconds() / 60
    if mins_left < -1:
        return [], False
    if urgency == "high":
        return pick([30, 10]), mins_left <= 120
    if urgency == "low":
        return pick([30, 10]), False
    if mins_left <= 70:
        return pick([30, 10]), mins_left <= 20
    return pick([60, 30, 10]), False


def mail_catch_reminders(
    events: Optional[List[Dict[str, Any]]],
    user: Dict[str, Any],
    *,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """One-shot notices when mail becomes a calendar item. Low urgency stays quiet."""
    now = now or _now_jst()
    who = _companion_who(user)
    rows: List[Dict[str, Any]] = []
    for ev in events or []:
        urgency = str(ev.get("urgency") or "normal").lower()
        brief = format_notify_brief(ev, today=now.date())
        eid = ev.get("id")
        if urgency == "high":
            rows.append(
                {
                    "id": f"mail-catch-{eid or ev.get('title')}",
                    "kind": "urgent",
                    "fire_at": now.isoformat(),
                    "title": f"{who}｜急ぎの用事",
                    "body": f"今すぐ・{brief}",
                    "event_id": eid,
                    "url": f"/app?checkin=1&eid={eid or ''}&lead=0",
                    "require_interaction": True,
                    "ask_mood": True,
                    "lead_minutes": 0,
                }
            )
        elif urgency == "normal":
            rows.append(
                {
                    "id": f"mail-catch-{eid or ev.get('title')}",
                    "kind": "mail_catch",
                    "fire_at": now.isoformat(),
                    "title": f"{who}｜予定を入れたよ",
                    "body": brief,
                    "event_id": eid,
                    "url": "/app?digest=1",
                    "require_interaction": False,
                    "ask_mood": False,
                    "lead_minutes": 0,
                }
            )
    return rows


def attach_mail_reminders(result: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    fit = assess_day_load(user)
    payload = build_today_reminders(user, fit=fit)
    catch = mail_catch_reminders(result.get("added") or [], user)
    if catch:
        payload = dict(payload)
        payload["reminders"] = catch + list(payload.get("reminders") or [])
    result["reminders"] = payload
    return result


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
    """Daily digest + urgency-based lead reminders with short what/when/where copy."""
    now = now or _now_jst()
    today = now.date()
    today_s = today.isoformat()
    fit = fit or assess_day_load(user)
    from schedule_service import list_events

    sched = list_events(user, on_date=today_s)
    open_items = list(sched.get("today_open") or [])
    who = _companion_who(user)
    allowed_leads = _lead_offsets(user)
    reminders: List[Dict[str, Any]] = []

    digest_at = datetime.combine(today, time(_digest_hour(user), 0), tzinfo=JST)
    if digest_at < now:
        digest_at = now
    if open_items:
        lines = [f"今日{len(open_items)}件"]
        for ev in open_items:
            clock = clock_label(ev)
            title = (ev.get("title") or "予定").strip() or "予定"
            loc = str(ev.get("location") or "").strip()
            bit = f"{clock} {title}"
            if loc:
                bit += f"・{loc}"
            lines.append(bit)
        digest_body = "\n".join(lines)
    else:
        digest_body = "今日は予定なし。用事が入ったら知らせるね。"
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
        brief = format_notify_brief(ev, today=today)
        eid = ev.get("id")
        event_leads, ping_now = _leads_for_event(ev, now=now, today=today, allowed=allowed_leads)
        if ping_now:
            reminders.append(
                {
                    "id": f"urgent-{eid or ev.get('title')}",
                    "kind": "urgent",
                    "fire_at": now.isoformat(),
                    "title": f"{who}｜急ぎの用事",
                    "body": f"今すぐ・{brief}\n体調はどう？",
                    "event_id": eid,
                    "url": f"/app?checkin=1&eid={eid or ''}&lead=0",
                    "require_interaction": True,
                    "ask_mood": True,
                    "lead_minutes": 0,
                }
            )
        start_t = _parse_hhmm(ev.get("time"))
        if start_t is None:
            continue
        start_at = datetime.combine(today, start_t, tzinfo=JST)
        for lead in event_leads:
            fire_at = start_at - timedelta(minutes=lead)
            if fire_at < now - timedelta(minutes=1):
                continue
            soon = LEAD_SOON_JA.get(lead, f"{lead}分後")
            ask_mood = lead <= 10
            body = f"{soon}・{brief}"
            if ask_mood:
                body += "\n体調はどう？"
            reminders.append(
                {
                    "id": f"evt-{eid or ev.get('title')}-{lead}",
                    "kind": "schedule",
                    "fire_at": fire_at.isoformat(),
                    "title": f"{who}｜{soon}",
                    "body": body,
                    "event_id": eid,
                    "url": f"/app?checkin=1&eid={eid or ''}&lead={lead}",
                    "require_interaction": ask_mood,
                    "ask_mood": ask_mood,
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
        "lead_offsets": allowed_leads,
        "digest_hour": _digest_hour(user),
        "day_fit": fit,
        "reminders": reminders,
        "hint_ja": (
            "メールは用事だけ予定に入れます。"
            "急ぎはすぐ大きな通知、普通は1時間前・30分前・10分前、先の予定はその日のまとめと直前だけ。"
            "10分前に体調を聞きます。タブを完全に閉じると届かないことがあります。"
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
