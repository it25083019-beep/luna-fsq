# -*- coding: utf-8 -*-
"""Mood Aura + Dual Mode + Night Whisper + Life Pulse from today's real state."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

JST = timezone(timedelta(hours=9))

AURA = {
    "元気": {
        "id": "genki",
        "label_ja": "いまは元気",
        "emotion": "happy",
        "glow": "rgba(255,196,90,.42)",
        "mid": "rgba(255,140,170,.22)",
        "rate": 1.08,
        "pitch": 1.08,
        "speech": "明るく短く。一緒に進もう。",
    },
    "普通": {
        "id": "futsu",
        "label_ja": "穏やかな一日",
        "emotion": "neutral",
        "glow": "rgba(155,126,217,.32)",
        "mid": "rgba(180,200,255,.18)",
        "rate": 1.0,
        "pitch": 1.0,
        "speech": "落ち着いて、短い次の一歩。",
    },
    "疲れ": {
        "id": "tsukare",
        "label_ja": "少しお疲れ",
        "emotion": "think",
        "glow": "rgba(90,140,170,.38)",
        "mid": "rgba(40,70,90,.28)",
        "rate": 0.92,
        "pitch": 0.88,
        "speech": "急かさない。休む提案を先に。",
    },
    "落ち込み": {
        "id": "ochikomi",
        "label_ja": "心が重い日",
        "emotion": "sad",
        "glow": "rgba(80,90,160,.4)",
        "mid": "rgba(30,36,70,.35)",
        "rate": 0.88,
        "pitch": 0.82,
        "speech": "そばにいることだけ。責めない。",
    },
    "不安": {
        "id": "fuan",
        "label_ja": "ざわざわしてる",
        "emotion": "think",
        "glow": "rgba(180,140,80,.36)",
        "mid": "rgba(90,60,40,.28)",
        "rate": 0.9,
        "pitch": 0.9,
        "speech": "一つだけ決める。安心を先に。",
    },
}

MODES = {
    "gentle": {"id": "gentle", "label_ja": "ジェントル", "hint_ja": "抱きしめる声", "advisor": "empathic"},
    "command": {"id": "command", "label_ja": "コマンド", "hint_ja": "きびしく導く", "advisor": "strict"},
    "auto": {"id": "auto", "label_ja": "オート", "hint_ja": "今日の状態で選ぶ", "advisor": "auto"},
}


def _hour_jst(now: Optional[datetime] = None) -> int:
    now = now or datetime.now(JST)
    if now.tzinfo is None:
        now = now.replace(tzinfo=JST)
    return now.astimezone(JST).hour


def _mental(user: Dict[str, Any]) -> str:
    health = ((user.get("life_modules") or {}).get("health") or {}).get("structured") or {}
    raw = str(health.get("mental_status") or "").strip()
    return raw if raw in AURA else "普通"


def resolve_luna_mode(user: Dict[str, Any], mental: Optional[str] = None) -> str:
    chosen = str(user.get("luna_mode") or "auto").strip().lower()
    if chosen in ("gentle", "command"):
        return chosen
    mood = mental or _mental(user)
    if mood in ("落ち込み", "不安", "疲れ"):
        return "gentle"
    return "command" if mood == "元気" else "gentle"


def night_whisper_active(user: Dict[str, Any], *, now: Optional[datetime] = None) -> bool:
    if user.get("night_whisper") is False:
        return False
    if user.get("night_whisper") is True:
        return True
    hour = _hour_jst(now)
    return hour >= 22 or hour < 6


def build_mood_runtime(user: Dict[str, Any], *, now: Optional[datetime] = None) -> Dict[str, Any]:
    mental = _mental(user)
    aura = AURA[mental]
    whisper = night_whisper_active(user, now=now)
    mode = resolve_luna_mode(user, mental)
    rate = 0.82 if whisper else aura["rate"]
    pitch = 0.78 if whisper else aura["pitch"]
    if mode == "command" and not whisper:
        rate = min(1.12, rate + 0.04)
        pitch = max(0.75, pitch - 0.04)
    if mode == "gentle":
        rate = max(0.8, rate - 0.04)
    return {
        "ok": True,
        "mental": mental,
        "aura": {
            "id": aura["id"],
            "label_ja": aura["label_ja"],
            "emotion": "think" if whisper else aura["emotion"],
            "glow": aura["glow"],
            "mid": aura["mid"],
        },
        "mode": mode,
        "mode_pref": str(user.get("luna_mode") or "auto"),
        "mode_label_ja": MODES[mode]["label_ja"],
        "whisper": whisper,
        "whisper_pref": user.get("night_whisper"),
        "voice": {"rate": round(rate, 2), "pitch": round(pitch, 2)},
        "speech_ja": "夜は短く、そっと。安心だけ。" if whisper else aura["speech"],
        "crisis_ready": mental in ("落ち込み", "不安", "疲れ"),
    }


def pulse_from_scores(health: int, money: int, schedule_open: int, *, mental: str = "普通") -> Dict[str, Any]:
    sched = 88 if schedule_open <= 2 else (62 if schedule_open <= 4 else 38)
    mood_adj = {"元気": 8, "普通": 0, "疲れ": -10, "不安": -14, "落ち込み": -18}.get(mental, 0)
    score = int(max(8, min(98, round((health * 0.4 + money * 0.3 + sched * 0.3) + mood_adj))))
    if score >= 75:
        label, beat = "安定", "steady"
    elif score >= 50:
        label, beat = "ゆらぎ", "uneven"
    else:
        label, beat = "要ケア", "low"
    return {
        "score": score,
        "label_ja": label,
        "beat": beat,
        "parts": {"health": health, "money": money, "schedule": sched},
        "line_ja": f"今日のライフパルスは{score}（{label}）。",
    }


def build_life_pulse(user: Dict[str, Any]) -> Dict[str, Any]:
    from health_eval import evaluate_health
    from money_eval import evaluate_money
    from day_coach import assess_day_load

    health_s = ((user.get("life_modules") or {}).get("health") or {}).get("structured") or {}
    money_s = ((user.get("life_modules") or {}).get("money") or {}).get("structured") or {}
    he = evaluate_health(health_s)
    me = evaluate_money(user, money_s)
    fit = assess_day_load(user)
    mental = _mental(user)
    pulse = pulse_from_scores(
        int(he.get("score") or 50),
        int(me.get("score") or 50),
        int(fit.get("open_count") or 0),
        mental=mental,
    )
    pulse["ok"] = True
    pulse["mental"] = mental
    return pulse


def runtime_prompt_block(user: Dict[str, Any]) -> str:
    rt = build_mood_runtime(user)
    mode = rt["mode"]
    extra = (
        "GENTLE mode: warm, short, no scolding. One tiny step."
        if mode == "gentle"
        else "COMMAND mode: kind but firm. One clear order. No fluff."
    )
    whisper = " NIGHT WHISPER: 1 short sentence, hush, no lectures." if rt["whisper"] else ""
    return f"MOOD AURA: {rt['mental']} / {rt['aura']['label_ja']}. {rt['speech_ja']} {extra}{whisper}"
