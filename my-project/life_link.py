"""FSQ ↔ Life linking — study wins touch health timeline + LUNA reacts."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from care_memory import build_care_quests
from care_timeline import append_care_event


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def on_lesson_complete(
    state: Dict[str, Any],
    lesson: Dict[str, Any],
    *,
    exp_gained: int,
) -> Dict[str, Any]:
    """After FSQ lesson clear: log timeline, gentle health note, LUNA congrats."""
    title = (lesson.get("title_ja") or lesson.get("id") or "学習").strip()
    raw_exp = int(lesson.get("exp") or exp_gained or 10)
    effects: List[str] = []

    j = ((state.get("rpg") or {}).setdefault("journey", {}))
    j.setdefault("completion_log", []).append(
        {
            "lesson_id": lesson.get("id"),
            "title_ja": title,
            "at": _utcnow_iso(),
            "detail": f"+{raw_exp} EXP",
        }
    )
    j["completion_log"] = j["completion_log"][-40:]

    append_care_event(
        state,
        "study",
        f"学習クリア：{title}",
        detail=f"+{raw_exp} EXP",
    )
    effects.append(f"EXP +{exp_gained or raw_exp}")

    modules = state.setdefault("life_modules", {})
    health = modules.setdefault("health", {})
    structured = health.setdefault("structured", {})
    notes = health.setdefault("notes", [])
    today = date.today().isoformat()

    prior = str(structured.get("mental_status") or "")
    if prior in ("疲れ", "不安", "落ち込み"):
        structured["last_study_relief_on"] = today
        effects.append("集中できたね（ストレス軽減メモ）")
    notes.append(
        {
            "at": _utcnow_iso(),
            "text": f"FSQ学習クリア：{title}（+{raw_exp} EXP）",
            "source": "fsq_study",
        }
    )
    health["notes"] = notes[-30:]
    health["updated_at"] = _utcnow_iso()

    who = state.get("user_display_name") or "冒険者"
    cname = state.get("companion_name") or "LUNA"
    if prior in ("疲れ", "不安", "落ち込み"):
        luna_message = (
            f"{who}さん、お疲れさま！「{title}」クリアしたね。"
            f"しんどい中でも集中できたの、すごいよ。{cname}がメモしておいた。"
        )
    else:
        luna_message = (
            f"{who}さん、「{title}」のクエストクリアおめでとう！"
            f"+{raw_exp} EXP だよ。今日の冒険、ちゃんと記録したね✨"
        )

    return {
        "luna_message": luna_message,
        "life_effects": effects,
        "timeline_kind": "study",
    }


def life_quests_for_fsq(user: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Care quests formatted for FSQ home (life data → daily quests)."""
    out: List[Dict[str, Any]] = []
    for q in build_care_quests(user):
        qid = q.get("id") or "care"
        icon = {"mood": "pink", "sleep": "blue", "spend": "yellow", "follow_health": "green"}.get(qid, "green")
        out.append(
            {
                "id": f"life_{qid}",
                "type": "life",
                "title_ja": q.get("label") or "ケアクエスト",
                "chip": q.get("chip") or "",
                "exp": 8,
                "icon_class": icon,
                "consult": qid in ("mood", "sleep", "spend", "follow_health"),
            }
        )
    return out[:3]
