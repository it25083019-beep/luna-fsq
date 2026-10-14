# -*- coding: utf-8 -*-
"""One spoken answer decides the next care beat: close, rescue, or ask again."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

_HEAVY = re.compile(
    r"つらい|辛い|苦しい|泣|無理|限界|助けて|怖い|不安|最悪|しんど|"
    r"大丈夫(じゃ|では)ない|平気じゃない|"
    r"không ổn|chịu hết|khóc|nặng quá",
    re.I,
)
_TIRED = re.compile(
    r"疲|眠い|だるい|つかれ|ねむい|"
    r"mệt|buồn ngủ|sleepy|tired",
    re.I,
)
_OK = re.compile(
    r"大丈夫|平気|問題ない|なんともない|ổn rồi|không sao|i'?m fine|im fine",
    re.I,
)

_CLOSE = {
    "luna": "{prefix}大丈夫なら、それでいい。また何かあったら、ここに来て。",
    "luno": "{prefix}大丈夫なんだ。よかった。また来てね。",
    "ren": "{prefix}大丈夫なら、今日はここまででいい。また来い。",
    "hachi": "{prefix}大丈夫なら、よし。また来て。わん。",
}
_HOLD = {
    "luna": "{prefix}いま一人で抱えなくていい。60秒、一緒にいよう。",
    "luno": "{prefix}ひとりにしない。60秒、手つないでよ。",
    "ren": "{prefix}一人で抱えるな。60秒、俺がいる。",
    "hachi": "{prefix}ひとりじゃなくていい。60秒、ここにいるよ。わん。",
}
_ASK_LATER = {
    "luna": "{prefix}疲れてるんだね。{when}、さっきのこと聞くね。",
    "luno": "{prefix}つかれたんだ。{when}、また聞くね。",
    "ren": "{prefix}疲れてるな。{when}、もう一度聞く。",
    "hachi": "{prefix}つかれたわん。{when}、また聞くね。",
}
_ASK_LATER["momo"] = _ASK_LATER["luna"]
_ASK_LATER["taro"] = _ASK_LATER["luna"]
_ASK_LATER["ponta"] = _ASK_LATER["hachi"]
_CLOSE["momo"] = _CLOSE["luna"]
_CLOSE["taro"] = _CLOSE["luna"]
_CLOSE["ponta"] = _CLOSE["hachi"]
_HOLD["momo"] = _HOLD["luna"]
_HOLD["taro"] = _HOLD["luna"]
_HOLD["ponta"] = _HOLD["hachi"]


_NEEDS_REPLY = re.compile(r"どう|なに|何|すれば|教えて|けど|から|バイト|就活|学校|課題")


def _tired_needs_a_real_reply(text: str) -> bool:
    """A question or a real sentence should not get the short tired template."""
    raw = (text or "").strip()
    if len(raw) > 16:
        return True
    return bool(_NEEDS_REPLY.search(raw))


_BURDENS = (
    ("就活", "就活"),
    ("バイト", "バイト"),
    ("授業", "授業"),
    ("学校", "授業"),
    ("課題", "課題"),
    ("発表", "発表"),
    ("面接", "面接"),
    ("試験", "試験"),
    ("テスト", "試験"),
)
_ASK_ONE = {
    "luna": "{prefix}助言はしない。今日いちばん重いのを、一つだけ言って。",
    "luno": "{prefix}助言はしないよ。今日いちばん重いの、一つだけ。",
    "ren": "{prefix}助言はしない。今日いちばん重いのを一つ言え。",
    "hachi": "{prefix}助言はしないわん。今日いちばん重いの、一つだけ。",
}
_KEEP_ONE = {
    "luna": "{prefix}{word}、残した。{when}、これで聞くね。",
    "luno": "{prefix}{word}、残したよ。{when}、これで聞くね。",
    "ren": "{prefix}{word}、残した。{when}、それで聞く。",
    "hachi": "{prefix}{word}、残したわん。{when}、これで聞くね。",
}
for _cid in ("momo", "taro"):
    _ASK_ONE[_cid] = _ASK_ONE["luna"]
    _KEEP_ONE[_cid] = _KEEP_ONE["luna"]
_ASK_ONE["ponta"] = _ASK_ONE["hachi"]
_KEEP_ONE["ponta"] = _KEEP_ONE["hachi"]
ONE_BURDEN_CHIPS = ["授業", "バイト", "就活"]
_WANTS_MOVE = re.compile(
    r"すれば|したら|どうしよう|どうにか|なにを|何を|方法|アドバイス|助言|"
    r"なくした|無くした|なくす|無く|楽にな|解決|教えて|どうした"
)
_STUDY = re.compile(r"数学|漢字|英語|コード|プログラム|公式|文法|翻訳")
_ONE_MOVE = {
    "就活": "応募を1件だけ開いて",
    "バイト": "水を一杯だけ飲んで",
    "授業": "ノートを1行だけ残して",
    "課題": "最初の一行だけ書いて",
    "発表": "最初の一言だけ声に出して",
    "面接": "答えを1つだけ声に出して",
    "試験": "1問だけ開いて",
}
_MOVE = {
    "luna": "{prefix}{word}が一番重い。{when}、{move}。",
    "luno": "{prefix}{word}が一番重いよ。{when}、{move}。",
    "ren": "{prefix}{word}が一番重い。{when}、{move}。",
    "hachi": "{prefix}{word}が一番重いわん。{when}、{move}。",
}
for _cid in ("momo", "taro"):
    _MOVE[_cid] = _MOVE["luna"]
_MOVE["ponta"] = _MOVE["hachi"]


def wants_a_move(text: str) -> bool:
    """They asked what to do. One move, not a list and not another 'I'll ask later'."""
    return bool(_WANTS_MOVE.search(text or ""))


def _study_question(text: str) -> bool:
    """A schoolwork question is not the care duty, unless it is also about their day."""
    if not _STUDY.search(text or ""):
        return False
    if heaviest_word(text) or _TIRED.search(text) or _HEAVY.search(text):
        return False
    return True


def heaviest_word(text: str) -> str:
    """The burden named last. LUNA keeps one, not a list of advice."""
    raw = text or ""
    found = ""
    at = -1
    for key, label in _BURDENS:
        pos = raw.rfind(key)
        if pos > at:
            at = pos
            found = label
    return found


def _one_when(user: Dict[str, Any], now: datetime) -> Tuple[str, Optional[datetime]]:
    from day_coach import agenda_for_companion, event_bounds, event_kind_label

    agenda = agenda_for_companion(user, now=now)
    current = agenda.get("current")
    if isinstance(current, dict):
        _start, end = event_bounds(current, today=now.date())
        if end and end > now:
            return "これが終わってから", end
    nxt = agenda.get("next")
    if isinstance(nxt, dict):
        start, end = event_bounds(nxt, today=now.date())
        if start and start > now:
            label = event_kind_label(nxt)
            return f"{label}のあと", end or start
    return "明日の朝", None


def _kept_word(user: Dict[str, Any], now: datetime) -> str:
    row = user.get("day_word")
    if not isinstance(row, dict) or not row.get("answered"):
        return ""
    if str(row.get("on") or "") != now.date().isoformat():
        return ""
    note = str(row.get("note") or "")
    for _key, label in _BURDENS:
        if note.startswith(label):
            return label
    suffix = "が一番重い"
    if note.endswith(suffix) and len(note) > len(suffix):
        return note[: -len(suffix)]
    return ""


def _store_one_burden(
    user: Dict[str, Any],
    word: str,
    *,
    now: datetime,
    voice: str,
    prefix: str,
    ask: bool = False,
) -> Tuple[str, Dict[str, Any]]:
    when, fire = _one_when(user, now)
    user.pop("care_one", None)
    note = f"{word}が一番重い"
    user["day_word"] = {
        "on": now.date().isoformat(),
        "note": note,
        "asked": True,
        "answered": True,
    }
    if fire is not None:
        user["care_followup"] = {
            "id": f"care-one-{fire.strftime('%Y%m%d%H%M')}",
            "fire_at": fire.isoformat(),
            "note": note,
        }
    else:
        user.pop("care_followup", None)
    if ask:
        move = _ONE_MOVE.get(word, "一つだけ手をつけて")
        line = _MOVE.get(voice, _MOVE["luna"]).format(prefix=prefix, word=word, when=when, move=move)
        return line, {"emotion": "sad", "care_action": "move"}
    line = _KEEP_ONE.get(voice, _KEEP_ONE["luna"]).format(prefix=prefix, word=word, when=when)
    return line, {"emotion": "sad", "care_action": "one"}


def take_named_burden(
    user: Dict[str, Any],
    text: str,
    *,
    now: Optional[datetime] = None,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """They were asked for the one heavy thing. A name is enough."""
    if user.get("care_one") != "wait":
        return None
    word = heaviest_word(text) or _own_word(text)
    if not word:
        if wants_a_move(text):
            voice = _voice(user)
            prefix = _prefix(user)
            line = _ASK_ONE.get(voice, _ASK_ONE["luna"]).format(prefix=prefix)
            return line, {"emotion": "sad", "care_action": "one"}
        return None
    from day_coach import _now_jst

    now = now or _now_jst()
    return _store_one_burden(
        user, word, now=now, voice=_voice(user), prefix=_prefix(user), ask=wants_a_move(text)
    )


def _own_word(text: str) -> str:
    """A burden they named that is not on the fixed list. Still one word."""
    raw = re.sub(r"\s+", "", (text or "").strip())
    raw = raw.strip("。！？?!、. ")
    if not raw or len(raw) < 2 or len(raw) > 12:
        return ""
    if raw in _NOT_A_WORD or wants_a_move(raw) or _HEAVY.search(raw) or _TIRED.search(raw):
        return ""
    if re.search(r"すれば|したら|どう|何|なに|？|\?", raw):
        return ""
    return raw


def fulfill_duty(
    user: Dict[str, Any],
    text: str,
    *,
    now: Optional[datetime] = None,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """LUNA's job for this sentence. None means the model may answer.

    A care sentence always gets one burden, one clock moment, and one move
    when they ask what to do. It must not reach the API.
    """
    raw = (text or "").strip()
    if not raw or len(raw) > 400 or _study_question(raw):
        return None
    from day_coach import _now_jst

    now = now or _now_jst()
    if user.get("care_one") == "wait":
        named = take_named_burden(user, raw, now=now)
        if named:
            return named
        voice = _voice(user)
        prefix = _prefix(user)
        line = _ASK_ONE.get(voice, _ASK_ONE["luna"]).format(prefix=prefix)
        return line, {"emotion": "sad", "care_action": "one"}
    cared = plan_care_reply(user, raw, now=now)
    if cared:
        return cared
    asking = wants_a_move(raw) or bool(re.search(r"[？?]", raw) and (heaviest_word(raw) or _kept_word(user, now)))
    if not asking:
        return None
    word = heaviest_word(raw) or _kept_word(user, now)
    if word:
        return _store_one_burden(
            user, word, now=now, voice=_voice(user), prefix=_prefix(user), ask=True
        )
    user["care_one"] = "wait"
    voice = _voice(user)
    prefix = _prefix(user)
    line = _ASK_ONE.get(voice, _ASK_ONE["luna"]).format(prefix=prefix)
    return line, {"emotion": "sad", "care_action": "one"}


def plan_one_move(
    user: Dict[str, Any],
    text: str,
    *,
    now: Optional[datetime] = None,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """A what-to-do question with no tired word still gets the one kept burden."""
    if care_tone(text) or not wants_a_move(text):
        return None
    from day_coach import _now_jst

    now = now or _now_jst()
    word = heaviest_word(text) or _kept_word(user, now)
    if not word:
        return None
    return _store_one_burden(
        user, word, now=now, voice=_voice(user), prefix=_prefix(user), ask=True
    )


def care_tone(text: str) -> Optional[str]:
    """heavy opens the 60s rescue, tired books a later ask, ok closes."""
    raw = (text or "").strip()
    # Long enough for a real story. A care sentence must not fall through to the API.
    if not raw or len(raw) > 400:
        return None
    if _HEAVY.search(raw):
        return "heavy"
    if _TIRED.search(raw):
        return "tired"
    if _OK.search(raw) and len(raw) <= 28:
        return "ok"
    return None


def _voice(user: Dict[str, Any]) -> str:
    cid = str((user or {}).get("companion_id") or "luna").strip().lower()
    if cid in _CLOSE:
        return cid
    return "luna"


def _prefix(user: Dict[str, Any]) -> str:
    from companion_presence import _who

    who = _who(user)
    return f"{who}、" if who else ""


def _snippet(text: str) -> str:
    raw = re.sub(r"\s+", " ", (text or "").strip())
    raw = raw.replace("「", "").replace("」", "").replace("<", "").replace(">", "")
    if len(raw) > 18:
        return raw[:18] + "…"
    return raw


def _followup_when(user: Dict[str, Any], *, now: datetime) -> Tuple[datetime, str]:
    from day_coach import agenda_for_companion, event_bounds

    agenda = agenda_for_companion(user, now=now)
    current = agenda.get("current")
    if isinstance(current, dict):
        _start, end = event_bounds(current, today=now.date())
        if end and end > now:
            return end, end.strftime("%H:%M") + "に"
    return now + timedelta(minutes=45), "少ししたら"


def _saved_sleep_hours(user: Dict[str, Any]) -> Optional[float]:
    health = ((user.get("life_modules") or {}).get("health") or {}).get("structured") or {}
    hours = _sleep_hours(health if isinstance(health, dict) else {})
    if hours is not None:
        return hours
    profile = user.get("life_profile") if isinstance(user.get("life_profile"), dict) else {}
    raw = str((profile or {}).get("health_sleep") or "")
    match = re.search(r"(\d+(?:\.\d+)?)", raw)
    if not match:
        return None
    try:
        parsed = float(match.group(1))
    except ValueError:
        return None
    if parsed <= 0 or parsed > 14:
        return None
    return parsed


def _fact_event(user: Dict[str, Any], now: datetime) -> Optional[Dict[str, Any]]:
    from day_coach import agenda_for_companion

    agenda = agenda_for_companion(user, now=now)
    pool: list = []
    for key in ("current", "just_ended", "next"):
        ev = agenda.get(key)
        if isinstance(ev, dict):
            pool.append(ev)
    for ev in agenda.get("open_items") or []:
        if isinstance(ev, dict):
            pool.append(ev)
    for ev in pool:
        if re.search(r"発表|面接|試験|課題|受診", str(ev.get("title") or "")):
            return ev
    for ev in pool:
        if str(ev.get("title") or "").strip():
            return ev
    return None


def _tired_facts(user: Dict[str, Any], *, now: datetime) -> str:
    """Cite saved sleep, today's event, or the kept burden. Nothing invented."""
    bits: list = []
    hours = _saved_sleep_hours(user)
    if hours is not None:
        bits.append(f"記録だと睡眠は{hours:g}時間。")
    ev = _fact_event(user, now)
    if ev is not None:
        from day_coach import event_bounds

        title = str(ev.get("title") or "予定").strip()[:12] or "予定"
        clock = str(ev.get("time") or "")[:5]
        start, _end = event_bounds(ev, today=now.date())
        past = bool(start and start <= now)
        tail = "だったよね" if past else "があるよね"
        when = f"{clock}から" if clock else ""
        bits.append(f"今日は{when}{title}{tail}。")
    elif _kept_word(user, now):
        bits.append(f"{_kept_word(user, now)}が一番重い、って残してある。")
    if len(bits) < 2:
        word = _kept_word(user, now)
        already = any(word and word in bit for bit in bits)
        if word and not already:
            bits.append(f"{word}が一番重い、って残してある。")
    return "".join(bits[:2])


def plan_care_reply(
    user: Dict[str, Any],
    text: str,
    *,
    now: Optional[datetime] = None,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Return dialogue plus game-state, and store a follow-up when they are tired."""
    tone = care_tone(text)
    if not tone:
        return None
    from day_coach import _now_jst

    now = now or _now_jst()
    voice = _voice(user)
    prefix = _prefix(user)
    if tone == "heavy":
        line = _HOLD[voice].format(prefix=prefix)
        return line, {"emotion": "sad", "crisis": True, "open_rescue": True, "care_action": "rescue"}
    if tone == "ok":
        line = _CLOSE[voice].format(prefix=prefix)
        user.pop("care_followup", None)
        return line, {"emotion": "happy", "care_action": "close"}
    if _tired_needs_a_real_reply(text):
        word = heaviest_word(text)
        if not word:
            user["care_one"] = "wait"
            line = _ASK_ONE.get(voice, _ASK_ONE["luna"]).format(prefix=prefix)
            return line, {"emotion": "sad", "care_action": "one"}
        return _store_one_burden(
            user, word, now=now, voice=voice, prefix=prefix, ask=wants_a_move(text)
        )
    fire, when = _followup_when(user, now=now)
    note = _snippet(text)
    user["care_followup"] = {
        "id": f"care-back-{fire.strftime('%Y%m%d%H%M')}",
        "fire_at": fire.isoformat(),
        "note": note,
    }
    facts = _tired_facts(user, now=now)
    if facts:
        line = f"{prefix}{facts}"
        if voice in ("hachi", "ponta") and "わん" not in line:
            line = line.rstrip("。") + "わん。"
        return line, {"emotion": "sad", "care_action": "cite"}
    line = _ASK_LATER[voice].format(prefix=prefix, when=when)
    return line, {"emotion": "sad", "care_action": "follow"}


def recall_greeting(user: Dict[str, Any], *, who: str = "", now: Optional[datetime] = None) -> Optional[str]:
    """Next open remembers the last thing they actually said."""
    rec = user.get("care_recall")
    if not isinstance(rec, dict):
        return None
    note = str(rec.get("note") or "").strip()
    if not note:
        return None
    from privacy_vault import looks_secret

    if looks_secret(note):
        return None
    from day_coach import JST, _now_jst

    now = now or _now_jst()
    prefix = f"{who}、" if who else ""
    same_day = False
    try:
        at = datetime.fromisoformat(str(rec.get("at") or ""))
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        same_day = at.astimezone(JST).date() == now.date()
    except ValueError:
        same_day = False
    if same_day:
        return f"{prefix}さっき「{note}」って言ってたよね。いまはどう？"
    return f"{prefix}この前「{note}」って言ってたよね。今日はどう？"


def _check_back_row(user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    row = user.get("check_back")
    if not isinstance(row, dict):
        return None
    if row.get("answered"):
        return None
    title = str(row.get("title") or "").strip()
    on = str(row.get("on") or "")[:10]
    if not title or not on:
        return None
    return row


def check_back_due(user: Dict[str, Any], *, now: Optional[datetime] = None) -> bool:
    """True once the occasion they mentioned should be over."""
    row = _check_back_row(user)
    if not row:
        return False
    from day_coach import _now_jst

    now = now or _now_jst()
    try:
        day = datetime.fromisoformat(row["on"]).date()
    except ValueError:
        return False
    if day > now.date():
        return False
    if (now.date() - day).days > 2:
        return False
    if day < now.date():
        return True
    from day_coach import event_bounds
    from schedule_service import list_events

    sched = list_events(user, on_date=day.isoformat())
    items = list(sched.get("today_open") or []) + list(sched.get("today_done") or [])
    titled = [ev for ev in items if str(ev.get("title") or "") == row["title"]]
    timed = [ev for ev in titled if ev.get("time")]
    target = timed[0] if timed else (titled[0] if titled else None)
    if target:
        _start, end = event_bounds(target, today=day)
        if end:
            return now >= end
        if _start and now < _start:
            return False
    return now.hour >= 17


def tell_kind(title: str) -> Optional[str]:
    """Which invitation fits this occasion. Clock questions are not in this list."""
    t = title or ""
    if re.search(r"発表|面接|卒論|卒研|プレゼン", t):
        return "share"
    if re.search(r"試験|テスト", t):
        return "hard"
    if re.search(r"受診|病院", t):
        return "private"
    if re.search(r"課題|提出|打ち合わせ|打合せ|会議", t):
        return "word"
    return None


_TELL_SAVE = {
    "share": "終わったら、何かあったら話して。",
    "hard": "終わったら、きつかったら言って。",
    "private": "終わったら、話したくなったら言って。",
    "word": "終わったら、ひとこと言って。",
}
_TELL_DONE = {
    "share": "何かあったら話して。",
    "hard": "きつかったら言って。",
    "private": "話したくなったら言って。",
    "word": "ひとこと言って。",
}
_TELL_CHIPS = {
    "share": ["うまくいった", "疲れた", "まだ終わってない"],
    "hard": ["きつかった", "大丈夫", "まだ終わってない"],
    "private": ["話したい", "大丈夫", "まだ終わってない"],
    "word": ["終わった", "疲れた", "まだ終わってない"],
}


def tell_save_line(title: str) -> str:
    """Said once, when the occasion is written on the calendar."""
    kind = tell_kind(title)
    return _TELL_SAVE.get(kind or "", "")


def tell_done_line(title: str) -> str:
    """Said once, after that occasion is over."""
    kind = tell_kind(title)
    return _TELL_DONE.get(kind or "", "ひとこと言って。")


def tell_chips(title: str) -> list[str]:
    kind = tell_kind(title)
    return list(_TELL_CHIPS.get(kind or "", _TELL_CHIPS["share"]))


def _check_back_spoken(row: Dict[str, Any], *, now: datetime, prefix: str) -> str:
    title = str(row.get("title") or "その件")
    invite = tell_done_line(title)
    try:
        day = datetime.fromisoformat(str(row.get("on") or "")).date()
    except ValueError:
        day = now.date()
    if day == now.date():
        return f"{prefix}この前、今日は{title}だって言ってたよね。{invite}"
    return f"{prefix}この前、{title}だって言ってたよね。{invite}"


def check_back_line(user: Dict[str, Any], *, who: str = "", now: Optional[datetime] = None) -> Optional[str]:
    """After a mentioned occasion, invite them to tell what happened. One ask until they answer."""
    if not check_back_due(user, now=now):
        return None
    row = _check_back_row(user)
    if not row or row.get("asked"):
        return None
    from day_coach import _now_jst

    now = now or _now_jst()
    row["asked"] = True
    user["check_back"] = row
    prefix = f"{who}、" if who else ""
    return _check_back_spoken(row, now=now, prefix=prefix)


def check_back_reminder(user: Dict[str, Any], *, now: datetime, who: str) -> Optional[Dict[str, Any]]:
    """One notification after the occasion, for when the app is closed."""
    if not check_back_due(user, now=now):
        return None
    row = _check_back_row(user)
    if not row:
        return None
    title = str(row.get("title") or "その件")
    body = _check_back_spoken(row, now=now, prefix="")
    return {
        "id": f"check-back-{row.get('on')}-{title}",
        "kind": "check_back",
        "fire_at": now.isoformat(),
        "title": f"{who}｜{title}",
        "body": body,
        "url": "/app",
        "require_interaction": False,
        "ask_mood": False,
        "lead_minutes": 0,
    }


_NIGHT = {
    "luna": "{prefix}夜にアプリを開いたね。眠れない？何かあった？",
    "luno": "{prefix}夜だね。眠れないの？何かあった？",
    "ren": "{prefix}夜に開いたな。眠れないのか。何かあったなら言え。",
    "hachi": "{prefix}夜だよ。わんっ、眠れない？何かあった？",
}
_SLEEP = {
    "luna": "{prefix}睡眠が短かったみたい。今夜は眠れそう？それとも何かあった？",
    "luno": "{prefix}睡眠、短かったね。今夜は眠れそう？何かあった？",
    "ren": "{prefix}睡眠が短い。今夜は眠れそうか。何かあったなら言え。",
    "hachi": "{prefix}睡眠が短いわん。今夜は眠れそう？何かあった？",
}
_BOTH = {
    "luna": "{prefix}お金とからだ、両方きついね。今日は一つだけ。何が一番つらい？",
    "luno": "{prefix}お金もからだも、きつそう。一つだけ教えて。何がつらい？",
    "ren": "{prefix}金と身体、両方きつい。一つだけ言え。何が一番つらいか。",
    "hachi": "{prefix}お金とからだ、両方きついわん。一つだけ。何がつらい？",
}
_PACKED = {
    "luna": "{prefix}予定が詰まって、からだも余裕がなさそう。何かあった？",
    "luno": "{prefix}予定がいっぱいで、からだもきつそう。何かあった？",
    "ren": "{prefix}予定が詰まって、身体も余裕がない。何かあったか。",
    "hachi": "{prefix}予定がいっぱい。からだもきつそうわん。何かあった？",
}
_MONEY = {
    "luna": "{prefix}お金が少しきついみたい。今日、使いすぎた？",
    "luno": "{prefix}お金、少しきつそう。今日、使いすぎた？",
    "ren": "{prefix}金がきつい。今日、使いすぎたか。",
    "hachi": "{prefix}お金がきついわん。今日、使いすぎた？",
}
for _cid in ("momo", "taro"):
    _NIGHT[_cid] = _NIGHT["luna"]
    _SLEEP[_cid] = _SLEEP["luna"]
    _BOTH[_cid] = _BOTH["luna"]
    _PACKED[_cid] = _PACKED["luna"]
    _MONEY[_cid] = _MONEY["luna"]
_NIGHT["ponta"] = _NIGHT["hachi"]
_SLEEP["ponta"] = _SLEEP["hachi"]
_BOTH["ponta"] = _BOTH["hachi"]
_PACKED["ponta"] = _PACKED["hachi"]
_MONEY["ponta"] = _MONEY["hachi"]


def _line(table: Dict[str, str], user: Dict[str, Any], prefix: str) -> str:
    voice = _voice(user)
    return table.get(voice, table["luna"]).format(prefix=prefix)


def _sleep_hours(health: Dict[str, Any]) -> Optional[float]:
    sleep = health.get("sleep_hours")
    try:
        hours = float(sleep) if sleep not in (None, "") else None
    except (TypeError, ValueError):
        return None
    if hours is None or hours <= 0 or hours > 14:
        return None
    return hours


def linked_open_line(user: Dict[str, Any], *, who: str = "", now: Optional[datetime] = None) -> Optional[str]:
    """One caring question from night, sleep, money, and how packed the day is."""
    from day_coach import _now_jst, assess_day_load

    now = now or _now_jst()
    prefix = f"{who}、" if who else ""
    hour = now.hour
    health = ((user.get("life_modules") or {}).get("health") or {}).get("structured") or {}
    money = ((user.get("life_modules") or {}).get("money") or {}).get("structured") or {}
    from life_graph import mood_trust, money_trust, sleep_trust

    sleep_n = _sleep_hours(health)
    mental = str(health.get("mental_status") or "").strip()
    if hour >= 22 or hour < 6:
        line = _line(_NIGHT, user, prefix)
        cite = sleep_trust(sleep_n) if sleep_n is not None and sleep_n < 6 else ""
        return f"{line}{cite}"

    if 6 <= hour < 11 and sleep_n is not None and sleep_n < 6:
        return f"{_line(_SLEEP, user, prefix)}{sleep_trust(sleep_n)}"

    from health_eval import evaluate_health
    from money_eval import evaluate_money

    he = evaluate_health(health)
    me = evaluate_money(user, money)
    fit = assess_day_load(user)
    health_score = int(he.get("score") or 70)
    money_score = int(me.get("score") or 55)
    has_money = bool(money.get("monthly_income") or money.get("monthly_expense"))
    packed = fit.get("load") in ("busy", "heavy", "recover")
    worn = mental in ("疲れ", "落ち込み", "不安") or (sleep_n is not None and sleep_n < 6)
    cite_money = money_trust(money) if has_money else ""
    cite_body = mood_trust(mental) or (sleep_trust(sleep_n) if sleep_n is not None and sleep_n < 6 else "")
    if has_money and money_score < 50 and (worn or health_score < 55):
        return f"{_line(_BOTH, user, prefix)}{cite_money}"
    if packed and worn:
        return f"{_line(_PACKED, user, prefix)}{cite_body}"
    if has_money and money_score < 45:
        return f"{_line(_MONEY, user, prefix)}{cite_money}"
    return None


def balance_advice(health: int, money: int, schedule: int) -> str:
    """One sentence for the balance chart. High schedule score means spare time."""
    if health >= 70 and money >= 70 and schedule >= 70:
        return "健康・お金・予定、いまは釣り合ってる。"
    if health < 50 and schedule < 50:
        return "予定が詰まって、からだも追いついてない。今日は一つ休もう。"
    if money < 50 and health < 55:
        return "お金とからだ、両方きつい。予定を一つ減らして、今日の支出だけ控えよう。"
    if money < 50 and health >= 60:
        return "からだは大丈夫。お金だけ、今日の使い方を一つ見よう。"
    if schedule < 50 and health >= 65:
        return "予定は多いけど、からだはまだ大丈夫。終わりの時間だけ守ろう。"
    return "少し偏ってる。いちばん低いところから、一つだけ整えよう。"


def care_followup_reminder(user: Dict[str, Any], *, now: datetime, who: str) -> Optional[Dict[str, Any]]:
    follow = user.get("care_followup")
    if not isinstance(follow, dict) or not follow.get("fire_at"):
        return None
    try:
        fire = datetime.fromisoformat(str(follow["fire_at"]))
    except ValueError:
        return None
    if fire.tzinfo is None:
        fire = fire.replace(tzinfo=now.tzinfo)
    if fire.date() != now.date():
        return None
    if fire < now - timedelta(hours=3):
        return None
    when = fire if fire > now else now
    note = str(follow.get("note") or "").strip()
    body = (
        f"さっき「{note}」って言ってたよね。いま、少し楽になった？"
        if note
        else "さっき疲れてるって言ってたよね。いま、少し楽になった？"
    )
    return {
        "id": str(follow.get("id") or f"care-back-{now.date().isoformat()}"),
        "kind": "care_back",
        "fire_at": when.isoformat(),
        "title": f"{who}｜さっきのこと",
        "body": body,
        "url": "/app",
        "require_interaction": True,
    }


DAY_WORD_ASK = "今日、一言だけ残す？"
DAY_WORD_KEPT = "今日の一言、残した。明日の朝、これで聞くね。"
_NOT_A_WORD = {
    "大丈夫",
    "疲れた",
    "何かあった",
    "眠れない",
    "話したい",
    "話したいことがある",
    "今日はここまで",
    "まだ残ってる",
    "少し楽になった",
    "まだ疲れてる",
}

DAILY_ASK = {
    "gender": "性別を、男性か女性で教えて。",
    "health_sleep": "平均の睡眠、何時間くらい？",
    "health_body": "からだで気になることはある？",
    "health_lifestyle": "食事と運動、いまどんな感じ？",
    "mental_mood": "最近の気分を、10点中で一つ。",
    "mental_stress": "いま一番気になっていることは？",
    "mental_support": "しんどいとき、どうすると楽？",
    "study_future": "いま学んでいること、一言で。",
    "money_income": "収入は、仕送りかバイトか、ある？",
    "money_expense": "毎月気になっている支出は？",
    "money_goal": "1か月で、お金の目標はある？",
    "time_weekday": "平日の流れを、一言で。",
    "time_weekend": "休日は、だいたい何してる？",
    "goals": "この1か月で一番大事なことを一つ。",
}


def _day_note(text: str) -> str:
    raw = re.sub(r"\s+", " ", (text or "").strip())
    raw = raw.replace("「", "").replace("」", "").replace("<", "").replace(">", "")
    if len(raw) > 24:
        return raw[:24] + "…"
    return raw


def _school_bounds(user: Dict[str, Any], now: datetime) -> list:
    from day_coach import event_bounds, event_kind
    from schedule_service import list_events

    sched = list_events(user, on_date=now.date().isoformat())
    items = list(sched.get("today_open") or []) + list(sched.get("today_done") or [])
    rows = []
    for ev in items:
        if event_kind(ev) != "school":
            continue
        start, end = event_bounds(ev, today=now.date())
        if start and end:
            rows.append((start, end))
    return rows


def before_first_class(user: Dict[str, Any], now: datetime) -> bool:
    """Morning window before today's first class. With no class, the early morning."""
    rows = _school_bounds(user, now)
    if not rows:
        return 6 <= now.hour < 11
    return now < min(start for start, _end in rows)


def _day_row(user: Dict[str, Any]) -> Dict[str, Any]:
    row = user.get("day_word")
    return row if isinstance(row, dict) else {}


def day_word_ask_due(user: Dict[str, Any], now: datetime) -> bool:
    """After the last class, once the clock question has had its 45 minutes."""
    from day_coach import clock_care_now

    if clock_care_now(user, now=now):
        return False
    row = _day_row(user)
    today = now.date().isoformat()
    if str(row.get("on") or "")[:10] == today and (row.get("note") or row.get("asked")):
        return False
    rows = _school_bounds(user, now)
    if not rows:
        return False
    last_end = max(end for _start, end in rows)
    return now >= last_end + timedelta(minutes=45)


def day_word_waiting(user: Dict[str, Any], now: datetime) -> bool:
    row = _day_row(user)
    today = now.date().isoformat()
    return str(row.get("on") or "")[:10] == today and bool(row.get("asked")) and not row.get("note")


def day_word_morning_due(user: Dict[str, Any], now: datetime) -> bool:
    row = _day_row(user)
    note = str(row.get("note") or "").strip()
    if not note or not row.get("answered"):
        return False
    if str(row.get("quoted_on") or "")[:10] == now.date().isoformat():
        return False
    try:
        saved = date.fromisoformat(str(row.get("on") or "")[:10])
    except ValueError:
        return False
    if saved != now.date() - timedelta(days=1):
        return False
    from privacy_vault import looks_secret

    if looks_secret(note):
        return False
    return before_first_class(user, now)


def day_word_morning_line(user: Dict[str, Any], *, who: str = "", now: Optional[datetime] = None) -> Optional[str]:
    """Next morning, before class, quote the one sentence they left."""
    from day_coach import _now_jst

    now = now or _now_jst()
    if not day_word_morning_due(user, now):
        return None
    row = _day_row(user)
    row["quoted_on"] = now.date().isoformat()
    user["day_word"] = row
    prefix = f"{who}、" if who else ""
    return f"{prefix}この前「{row.get('note')}」って言ってたよね。"


def _morning_fire(user: Dict[str, Any], now: datetime) -> datetime:
    """One moment before the first class. With no class, eight in the morning."""
    from datetime import time as clock

    rows = _school_bounds(user, now)
    if rows:
        first = min(start for start, _end in rows)
        fire = first - timedelta(minutes=40)
        earliest = datetime.combine(now.date(), clock(6, 30), tzinfo=now.tzinfo)
        if fire < earliest:
            fire = earliest
        return fire
    return datetime.combine(now.date(), clock(8, 0), tzinfo=now.tzinfo)


def day_word_morning_reminder(
    user: Dict[str, Any], *, now: datetime, who: str
) -> Optional[Dict[str, Any]]:
    """One phone notification the next morning, before class, quoting their sentence."""
    row = _day_row(user)
    note = str(row.get("note") or "").strip()
    if not note or not row.get("answered"):
        return None
    if str(row.get("quoted_on") or "")[:10] == now.date().isoformat():
        return None
    try:
        saved = date.fromisoformat(str(row.get("on") or "")[:10])
    except ValueError:
        return None
    if saved != now.date() - timedelta(days=1):
        return None
    from privacy_vault import looks_secret

    if looks_secret(note):
        return None
    fire = _morning_fire(user, now)
    if now > fire + timedelta(minutes=90):
        return None
    if not before_first_class(user, now) and now >= fire:
        return None
    when = fire if now < fire else now
    return {
        "id": f"day-word-{row.get('on')}",
        "kind": "day_word",
        "fire_at": when.isoformat(),
        "title": f"{who}｜今朝",
        "body": f"この前「{note}」って言ってたよね。",
        "url": "/app",
        "require_interaction": False,
        "ask_mood": False,
        "lead_minutes": 0,
    }


def day_word_ask_line(user: Dict[str, Any], *, who: str = "", now: Optional[datetime] = None) -> Optional[str]:
    from day_coach import _now_jst

    now = now or _now_jst()
    if not day_word_ask_due(user, now):
        return None
    user["day_word"] = {
        "on": now.date().isoformat(),
        "note": "",
        "asked": True,
        "answered": False,
    }
    prefix = f"{who}、" if who else ""
    return f"{prefix}{DAY_WORD_ASK}"


def keep_day_word(user: Dict[str, Any], text: str, now: Optional[datetime] = None) -> str:
    """A sentence said in free time becomes the one line quoted tomorrow morning."""
    from day_coach import _now_jst, clock_care_now
    from privacy_vault import looks_secret

    now = now or _now_jst()
    raw = (text or "").strip()
    if not raw or raw in _NOT_A_WORD or looks_secret(raw) or care_tone(raw) == "heavy":
        return ""
    if re.search(r"どう|なに|何|すれば|教えて", raw):
        return ""
    if clock_care_now(user, now=now) and care_tone(raw) in ("ok", "tired") and len(raw) <= 8:
        return ""
    back = user.get("check_back")
    if isinstance(back, dict) and back.get("asked") and not back.get("answered"):
        return ""
    today = now.date().isoformat()
    row = _day_row(user)
    if str(row.get("on") or "")[:10] == today and row.get("note"):
        return ""
    note = _day_note(raw)
    if not note:
        return ""
    user["day_word"] = {"on": today, "note": note, "asked": True, "answered": True}
    return DAY_WORD_KEPT


def daily_intake_line(user: Dict[str, Any], *, who: str = "", now: Optional[datetime] = None) -> Optional[str]:
    """One profile question a day, starting the day after the first care greeting."""
    from day_coach import _now_jst

    now = now or _now_jst()
    if not user.get("cared_once"):
        return None
    today = now.date().isoformat()
    if str(user.get("cared_on") or "")[:10] == today:
        return None
    left = user.get("daily_questions_left") or []
    if not left:
        return None
    if str(user.get("daily_ask_on") or "")[:10] == today:
        return None
    key = str(left[0])
    line = DAILY_ASK.get(key)
    if not line:
        return None
    user["daily_ask_on"] = today
    user["daily_ask_key"] = key
    prefix = f"{who}、" if who else ""
    return f"{prefix}{line}"
