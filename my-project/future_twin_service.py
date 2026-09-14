# -*- coding: utf-8 -*-
"""Future Self Twin / Shock Mode — two timelines from real life + FSQ data."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from exp_engine import level_from_exp


def _week_days(today: Optional[date] = None) -> List[str]:
    today = today or date.today()
    start = today - timedelta(days=today.weekday())
    return [(start + timedelta(days=i)).isoformat() for i in range(7)]


def _day_key(iso: str) -> str:
    return str(iso or "")[:10]


def _clamp(n: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, n))


def collect_twin_facts(user: Dict[str, Any], *, today: Optional[date] = None) -> Dict[str, Any]:
    today = today or date.today()
    week = set(_week_days(today))
    health = ((user.get("life_modules") or {}).get("health") or {}).get("structured") or {}
    money = ((user.get("life_modules") or {}).get("money") or {}).get("structured") or {}
    goals = ((user.get("life_modules") or {}).get("goals") or {}).get("structured") or {}
    j = ((user.get("rpg") or {}).get("journey") or {})

    completions = [
        x
        for x in (j.get("completion_log") or [])
        if isinstance(x, dict) and _day_key(str(x.get("at") or "")) in week
    ]
    from money_eval import spend_rows

    spend_week = 0
    spend_days = 0
    for row in spend_rows(money):
        if _day_key(str(row.get("date") or "")) not in week:
            continue
        spend_days += 1
        try:
            spend_week += int(row.get("amount") or 0)
        except (TypeError, ValueError):
            pass

    items = [x for x in (goals.get("items") or []) if isinstance(x, dict)]
    goal_pcts = [int(x.get("pct") or 0) for x in items] if items else []
    goal_avg = int(round(sum(goal_pcts) / len(goal_pcts))) if goal_pcts else 0
    open_goals = [x for x in items if not x.get("done")]

    from health_eval import evaluate_health
    from money_eval import evaluate_money, spend_pace_snapshot
    from day_coach import assess_day_load

    health_ev = evaluate_health(health)
    money_ev = evaluate_money(user, money)
    pace = spend_pace_snapshot(money, today=today)
    fit = assess_day_load(user)

    mental = str(health.get("mental_status") or "")
    stress_now = 35
    if mental == "落ち込み":
        stress_now = 78
    elif mental == "不安":
        stress_now = 70
    elif mental == "疲れ":
        stress_now = 62
    elif mental == "普通":
        stress_now = 42
    elif mental == "元気":
        stress_now = 28
    if fit.get("load") in ("heavy", "recover"):
        stress_now = min(92, stress_now + 8)

    skills = list(j.get("skills") or [])
    bosses = list(j.get("boss_clears") or [])
    lessons = list(j.get("completed_lessons") or [])
    exp = int(user.get("total_exp") or j.get("journey_exp") or 0)
    level = int(user.get("current_level") or level_from_exp(exp) or 1)
    career = bool(j.get("career_id"))
    career_opp = int(
        _clamp(
            12
            + len(skills) * 8
            + len(bosses) * 10
            + min(len(lessons), 12) * 3
            + (15 if career else 0),
            8,
            96,
        )
    )
    money_score = int(money_ev.get("score") or 50)
    if pace.get("pace_level") == "warn":
        money_score = max(12, money_score - 12)

    return {
        "today": today.isoformat(),
        "study_week": len(completions),
        "spend_week": spend_week,
        "spend_days": spend_days,
        "goal_avg": goal_avg,
        "open_goals": len(open_goals),
        "mental": mental or None,
        "health_score": int(health_ev.get("score") or 0),
        "money_score": money_score,
        "pace_level": pace.get("pace_level") or "ok",
        "load": fit.get("load") or "light",
        "recommend": fit.get("recommend") or "lesson",
        "exp": exp,
        "level": level,
        "skills": len(skills),
        "bosses": len(bosses),
        "lessons": len(lessons),
        "career": career,
        "stress": stress_now,
        "career_opp": career_opp,
    }


def _project(facts: Dict[str, Any], *, plan: bool, weeks: int) -> Dict[str, Any]:
    study = int(facts.get("study_week") or 0)
    load = facts.get("load") or "light"
    if plan:
        if load == "recover":
            study_w = 1
        elif load in ("heavy", "busy"):
            study_w = 3
        else:
            study_w = 5
        exp_w = study_w * 26 + 18
        stress_delta = -7 if facts.get("stress", 40) > 40 else -2
        money_delta = 4 if facts.get("pace_level") == "warn" else 2
        goal_delta = 10 if facts.get("open_goals") else 4
        skill_delta = 1 if weeks >= 4 else 0
        career_delta = 8
    else:
        study_w = study
        exp_w = study * 16 + (6 if study else 0)
        if facts.get("load") in ("heavy", "recover"):
            stress_delta = 6
        elif (facts.get("stress") or 0) >= 60:
            stress_delta = 4
        else:
            stress_delta = 1
        money_delta = -8 if facts.get("pace_level") == "warn" else -1
        goal_delta = 1 if study else -2
        skill_delta = 1 if study >= 3 and weeks >= 4 else 0
        career_delta = 1 if study else -3

    exp = int(facts.get("exp") or 0) + exp_w * weeks
    level = level_from_exp(exp)
    stress = int(_clamp((facts.get("stress") or 40) + stress_delta * weeks, 12, 94))
    money = int(_clamp((facts.get("money_score") or 50) + money_delta * (weeks / 4), 8, 96))
    goals = int(_clamp((facts.get("goal_avg") or 0) + goal_delta * (weeks / 4) * 4, 0, 100))
    skills = int(facts.get("skills") or 0) + skill_delta * max(1, weeks // 4)
    career = int(_clamp((facts.get("career_opp") or 20) + career_delta * (weeks / 4), 8, 98))
    return {
        "weeks": weeks,
        "level": level,
        "exp": exp,
        "skills": skills,
        "stress": stress,
        "money": money,
        "goals": goals,
        "career": career,
        "study_per_week": study_w,
    }


def _gap_line(now: Dict[str, Any], a: Dict[str, Any], b: Dict[str, Any], weeks: int) -> str:
    lv = int(b.get("level") or 0) - int(a.get("level") or 0)
    st = int(a.get("stress") or 0) - int(b.get("stress") or 0)
    cr = int(b.get("career") or 0) - int(a.get("career") or 0)
    if lv > 0:
        return f"このまま{weeks}週だとレベルは{a['level']}止まり。ルナ案ならLv.{b['level']}（+{lv}）。"
    if st >= 8:
        return f"{weeks}週後、ストレスは{a['stress']}対{b['stress']}。計画どおりなら心の余白が残る。"
    if cr >= 8:
        return f"進路チャンスは{weeks}週で{a['career']}→{b['career']}。差は「今の一歩」から開く。"
    if now.get("study_week") == 0:
        return "今週まだ学習記録がない。ルナ案は短いクエスト1つから差がつくよ。"
    return "数字はまだ近い。続けた週ほど、ふたつの未来が分かれていく。"


def build_future_twin(user: Dict[str, Any], *, today: Optional[date] = None) -> Dict[str, Any]:
    facts = collect_twin_facts(user, today=today)
    now = {
        "level": facts["level"],
        "skills": facts["skills"],
        "stress": facts["stress"],
        "money": facts["money_score"],
        "goals": facts["goal_avg"],
        "career": facts["career_opp"],
    }
    a4 = _project(facts, plan=False, weeks=4)
    b4 = _project(facts, plan=True, weeks=4)
    a12 = _project(facts, plan=False, weeks=12)
    b12 = _project(facts, plan=True, weeks=12)
    return {
        "ok": True,
        "tagline_ja": "他のアプリは行動を追う。LUNAは起きる前の結果を見せる。",
        "title_ja": "フューチャーセルフ",
        "label_a": "このまま",
        "label_b": "ルナ案",
        "now": now,
        "facts": {
            "study_week": facts["study_week"],
            "load": facts["load"],
            "mental": facts["mental"],
            "pace_level": facts["pace_level"],
        },
        "week": {"a": a4, "b": b4, "shock_ja": _gap_line(now, a4, b4, 4)},
        "month": {"a": a12, "b": b12, "shock_ja": _gap_line(now, a12, b12, 12)},
        "gaps": {
            "level": int(b4["level"]) - int(a4["level"]),
            "skills": int(b4["skills"]) - int(a4["skills"]),
            "stress": int(a4["stress"]) - int(b4["stress"]),
            "money": int(b4["money"]) - int(a4["money"]),
            "goals": int(b4["goals"]) - int(a4["goals"]),
            "career": int(b4["career"]) - int(a4["career"]),
        },
    }
