"""FSQ weekly narrative from real player progress (local-first, optional LLM polish)."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

CLASS_ICON = {"swordsman": "⚔", "mage": "🔮", "archer": "🏹"}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _week_start(today: Optional[date] = None) -> date:
    today = today or date.today()
    return today - timedelta(days=today.weekday())


def _week_days(week_start: date) -> List[str]:
    return [(week_start + timedelta(days=i)).isoformat() for i in range(7)]


def _day_key(iso: str) -> str:
    return (iso or "")[:10]


def _collect_week_facts(state: Dict[str, Any], *, today: Optional[date] = None) -> Dict[str, Any]:
    today = today or date.today()
    week_start = _week_start(today)
    week_days = _week_days(week_start)
    j = ((state.get("rpg") or {}).get("journey") or {})

    completions = [
        x
        for x in (j.get("completion_log") or [])
        if isinstance(x, dict) and _day_key(str(x.get("at") or "")) in week_days
    ]
    lesson_titles = [str(x.get("title_ja") or x.get("lesson_id") or "学習") for x in completions]
    week_exp = sum(int(x.get("detail", "").replace("+", "").replace(" EXP", "") or 0) for x in completions if "EXP" in str(x.get("detail") or ""))
    if not week_exp:
        week_exp = len(completions) * 10

    care_events = [
        e
        for e in (state.get("care_timeline") or [])
        if isinstance(e, dict) and _day_key(str(e.get("at") or "")) in week_days
    ]
    health = (state.get("life_modules") or {}).get("health", {}).get("structured") or {}
    mood = health.get("mental_status")

    boss_clears = list(j.get("boss_clears") or [])
    rank_ja = None
    try:
        from journey_engine import list_ranks

        ranks = {r["id"]: r.get("label_ja") for r in list_ranks()}
        rank_ja = ranks.get(j.get("rank_id") or "novice")
    except Exception:
        rank_ja = j.get("rank_id") or "見習い"

    highlights: List[str] = []
    if lesson_titles:
        highlights.append(f"学習 {len(lesson_titles)} クエスト")
    if week_exp:
        highlights.append(f"週間 +{week_exp} EXP")
    if mood:
        highlights.append(f"気分：{mood}")
    if boss_clears:
        highlights.append(f"ボス討伐 {len(boss_clears)} 体")

    stage_id = j.get("stage_id")
    chapter = "始まりの平原"
    if stage_id:
        chapter = str(stage_id).replace("_", " ").title()

    has_activity = bool(completions or care_events or mood)
    selected = bool(j.get("class_id") and j.get("career_id"))

    return {
        "week_key": week_start.isoformat(),
        "week_label": f"{week_start.month}/{week_start.day}週",
        "display_name": state.get("user_display_name") or "冒険者",
        "class_id": j.get("class_id") or "swordsman",
        "class_ja": j.get("class_id"),
        "career_title_ja": None,
        "rank_ja": rank_ja,
        "lesson_titles": lesson_titles[:5],
        "lesson_count": len(lesson_titles),
        "week_exp": week_exp,
        "mood": mood,
        "boss_clears": len(boss_clears),
        "care_count": len(care_events),
        "chapter": chapter,
        "highlights": highlights[:4],
        "has_activity": has_activity,
        "selected": selected,
        "next_lesson": None,
    }


def _enrich_facts_from_status(facts: Dict[str, Any], status: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not status:
        return facts
    facts = dict(facts)
    if status.get("class_ja"):
        facts["class_ja"] = status["class_ja"]
    if status.get("career_title_ja"):
        facts["career_title_ja"] = status["career_title_ja"]
    nxt = status.get("next_lesson")
    if nxt:
        facts["next_lesson"] = nxt.get("title_ja") or nxt.get("id")
    return facts


def _local_weekly_story(facts: Dict[str, Any]) -> str:
    """JRPG guild-master tone, max 3 sentences — always available."""
    who = facts.get("display_name") or "冒険者"
    rank = facts.get("rank_ja") or "見習い"
    cls = facts.get("class_ja") or "冒険者"
    icon = CLASS_ICON.get(str(facts.get("class_id") or ""), "⚔")
    lessons = facts.get("lesson_titles") or []
    n = int(facts.get("lesson_count") or 0)
    exp = int(facts.get("week_exp") or 0)
    next_q = facts.get("next_lesson")
    mood = facts.get("mood")

    if n == 0 and not facts.get("care_count"):
        if next_q:
            return (
                f"今週の冒険ログはまだ白紙だ。{icon}{cls}の{who}よ、"
                f"次は「{next_q}」から一歩踏み出そう。小さな勝利が伝説の序章になる。"
            )
        return (
            f"霧に包まれた週のはじまり。{icon}{rank}の{who}よ、"
            f"拠点でクエストを選び、未来の自分を少しずつ育てていこう。"
        )

    parts: List[str] = []
    if n == 1:
        parts.append(
            f"今週、{who}は「{lessons[0]}」を討ち取った。{icon}{rank}としての経験値が+{exp}光った。"
        )
    elif n >= 2:
        tail = lessons[-1] if lessons else "学習"
        parts.append(
            f"今週{who}は{n}つのクエストを制覇。「{lessons[0]}」から「{tail}」まで、"
            f"経験値+{exp}が冒険録に刻まれた。"
        )
    else:
        parts.append(f"今週も{who}の歩みが続いている。{icon}{rank}の力が少しずつ育っている。")

    if mood in ("疲れ", "不安", "落ち込み"):
        parts.append("体と心の回復も大切なクエストだ。無理せず、拠点で休もう。")
    elif facts.get("boss_clears"):
        parts.append("ボスの影を退けた勇気は、きっと本番の試練にも効く。")
    elif next_q:
        parts.append(f"次の扉には「{next_q}」が待っている。装備を整えて出撃だ。")
    else:
        parts.append("この調子で、ワールドマップの先へ進もう。")

    text = "".join(parts[:3])
    return text[:420]


def _try_llm_weekly_story(facts: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        from luna_service import generate_json_task
        from llm_client import llm_configured

        if not llm_configured():
            return None
    except Exception:
        return None

    payload = {
        "display_name": facts.get("display_name"),
        "class": facts.get("class_ja"),
        "rank": facts.get("rank_ja"),
        "career": facts.get("career_title_ja"),
        "lessons_this_week": facts.get("lesson_titles"),
        "exp": facts.get("week_exp"),
        "mood": facts.get("mood"),
        "next_quest": facts.get("next_lesson"),
    }
    system = (
        "You are the Guild Master narrator of Future Skill Quest (FSQ), a JRPG career-learning app. "
        "Write ONE short weekly story in Japanese (ja-JP) from REAL progress data only. "
        "Tone: encouraging, strategic, JRPG terms (冒険者, クエスト, レベルアップ). "
        "Max 3 sentences. Never invent lessons not in the data. "
        'Return JSON: {"story_ja":"...","tip_ja":"one short tip"}'
    )
    try:
        from luna_service import generate_json_task

        raw = generate_json_task(system, json.dumps(payload, ensure_ascii=False))
        if isinstance(raw, dict) and (raw.get("story_ja") or "").strip():
            return raw
    except Exception:
        pass
    return None


def _story_stale(cached: Dict[str, Any], state: Dict[str, Any], facts: Dict[str, Any]) -> bool:
    """Refresh if new completions since cache."""
    gen = str(cached.get("generated_at") or "")
    if not gen:
        return True
    j = ((state.get("rpg") or {}).get("journey") or {})
    for row in j.get("completion_log") or []:
        if not isinstance(row, dict):
            continue
        at = str(row.get("at") or "")
        if at > gen:
            return True
    return int(cached.get("lesson_count") or 0) != int(facts.get("lesson_count") or 0)


def build_fsq_weekly_story(
    state: Dict[str, Any],
    *,
    status: Optional[Dict[str, Any]] = None,
    today: Optional[date] = None,
    force_refresh: bool = False,
) -> Optional[Dict[str, Any]]:
    """Weekly FSQ narrative card for world narrator + adventure log."""
    facts = _collect_week_facts(state, today=today)
    facts = _enrich_facts_from_status(facts, status)

    if not facts.get("selected"):
        return None

    week_key = facts["week_key"]
    cached = dict(state.get("fsq_weekly_story") or {})

    if (
        not force_refresh
        and cached.get("week_key") == week_key
        and cached.get("story_ja")
        and not _story_stale(cached, state, facts)
    ):
        return {
            "week_key": cached.get("week_key"),
            "week_label": cached.get("week_label") or facts["week_label"],
            "story_ja": cached.get("story_ja"),
            "tip_ja": cached.get("tip_ja"),
            "highlights": cached.get("highlights") or facts.get("highlights"),
            "source": cached.get("source") or "cache",
        }

    story_ja = _local_weekly_story(facts)
    tip_ja = "学びは経験値。小さくても毎日の一歩が最強の装備になる。"
    source = "local"

    if facts.get("has_activity") or facts.get("lesson_count", 0) > 0:
        ai = _try_llm_weekly_story(facts)
        if ai and (ai.get("story_ja") or "").strip():
            story_ja = (ai.get("story_ja") or "").strip()[:420]
            tip_ja = (ai.get("tip_ja") or tip_ja).strip()[:120]
            source = "llm"

    if mood := facts.get("mood"):
        if mood in ("疲れ", "不安", "落ち込み") and "休" not in tip_ja:
            tip_ja = "回復も冒険の一部。睡眠と水分を忘れずに。"

    result = {
        "week_key": week_key,
        "week_label": facts["week_label"],
        "story_ja": story_ja,
        "tip_ja": tip_ja,
        "highlights": facts.get("highlights") or [],
        "lesson_count": facts.get("lesson_count") or 0,
        "source": source,
        "generated_at": _utcnow_iso(),
    }
    state["fsq_weekly_story"] = result
    return result


def mini_quest_story(state: Dict[str, Any], lesson: Dict[str, Any], *, exp: int) -> str:
    """One-line dynamic story after clearing a lesson (local)."""
    title = (lesson.get("title_ja") or lesson.get("id") or "クエスト").strip()
    who = state.get("user_display_name") or "冒険者"
    cls = ((state.get("rpg") or {}).get("journey") or {}).get("class_id") or "swordsman"
    icon = CLASS_ICON.get(cls, "⚔")
    return f"{icon} {who}、「{title}」を討伐！ 経験値+{exp} — 伝説の一ページが増えた。"
