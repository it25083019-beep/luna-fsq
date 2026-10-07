# -*- coding: utf-8 -*-
"""One spoken answer decides the next care beat: close, rescue, or ask again."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
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


def care_tone(text: str) -> Optional[str]:
    """heavy opens the 60s rescue, tired books a later ask, ok closes."""
    raw = (text or "").strip()
    if not raw or len(raw) > 80:
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
    fire, when = _followup_when(user, now=now)
    note = _snippet(text)
    user["care_followup"] = {
        "id": f"care-back-{fire.strftime('%Y%m%d%H%M')}",
        "fire_at": fire.isoformat(),
        "note": note,
    }
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
