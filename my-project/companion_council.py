# -*- coding: utf-8 -*-
"""Companion Council — strategist / strict / empathic voices on the same facts."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

STYLES = {
    "strategist": {
        "id": "strategist",
        "companion_id": "luna",
        "label_ja": "戦略",
        "who_ja": "ルナ",
        "hint_ja": "次の一手を短く切る",
    },
    "strict": {
        "id": "strict",
        "companion_id": "ren",
        "label_ja": "厳しめ",
        "who_ja": "レン",
        "hint_ja": "逃げずに要点だけ",
    },
    "empathic": {
        "id": "empathic",
        "companion_id": "luno",
        "label_ja": "寄り添い",
        "who_ja": "ルノ",
        "hint_ja": "気持ちを先に受け止める",
    },
}

VALID_STYLES = set(STYLES) | {"auto"}


def normalize_advisor_style(raw: Any) -> str:
    v = str(raw or "auto").strip().lower()
    return v if v in VALID_STYLES else "auto"


def resolve_advisor_style(user: Dict[str, Any], facts: Optional[Dict[str, Any]] = None) -> str:
    mode = str(user.get("luna_mode") or "auto").strip().lower()
    if mode == "gentle":
        return "empathic"
    if mode == "command":
        return "strict"
    chosen = normalize_advisor_style(user.get("advisor_style"))
    if chosen != "auto":
        return chosen
    facts = facts or {}
    mental = facts.get("mental")
    load = facts.get("load")
    if mental in ("落ち込み", "不安") or load == "recover":
        return "empathic"
    if load == "heavy" or facts.get("pace_level") == "warn" or int(facts.get("open_goals") or 0) and int(facts.get("goal_avg") or 0) < 30:
        return "strict"
    return "strategist"


def _lines(facts: Dict[str, Any], twin: Optional[Dict[str, Any]], radar: Optional[Dict[str, Any]]) -> Dict[str, str]:
    alerts = (radar or {}).get("alerts") or []
    top = alerts[0] if alerts else None
    gap = (twin or {}).get("week") or {}
    shock = gap.get("shock_ja") or ""
    study = int(facts.get("study_week") or 0)
    if top and top.get("kind") == "burnout":
        return {
            "strategist": "今日の勝ちは回復。短い休みを先に入れて、学習は明日に回そう。",
            "strict": "無理して崩れる方が高い。今は休め。それが仕事だ。",
            "empathic": "しんどい日だね。がんばらなくていい。隣にいるよ。",
        }
    if top and top.get("kind") == "spend":
        return {
            "strategist": "支出は責めるより記録。1件メモすれば来週の余白が見える。",
            "strict": "使ったなら書け。見ないふりが一番高い買い物だ。",
            "empathic": "使っちゃった日もあるよ。メモだけしたら、もう十分えらい。",
        }
    if top and top.get("kind") == "study_slip":
        return {
            "strategist": "8分のレッスン1つで、このまま側とルナ案の差が開き始める。",
            "strict": "今週ゼロは言い訳にしない。短くていい、着手しろ。",
            "empathic": "遅れても大丈夫。一緒に、ほんの少しだけ触ってみよ？",
        }
    if top and top.get("kind") == "goal_slip":
        return {
            "strategist": "目標は大きく動かさなくていい。今日は1メモリ。",
            "strict": "見てない目標は消える。数字を1つ更新しろ。",
            "empathic": "遠く感じる日もあるね。小さな印を、今日ひとつ。",
        }
    if study:
        return {
            "strategist": shock or "今週の学習は残ってる。このまま積み上げよう。",
            "strict": "いい調子だ。気を抜くな。次の1本までが本番。",
            "empathic": "ちゃんと進んでるよ。今日も自分を褒めていい。",
        }
    return {
        "strategist": shock or "今日の一手を決めよう。予定・休む・学ぶ、どれか1つ。",
        "strict": "迷う時間がもったいない。今やることを一つ言え。",
        "empathic": "急がなくていいよ。いまの気持ちから、一緒に選ぼう。",
    }


def build_council(
    user: Dict[str, Any],
    *,
    facts: Optional[Dict[str, Any]] = None,
    twin: Optional[Dict[str, Any]] = None,
    radar: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from future_twin_service import collect_twin_facts

    facts = facts or collect_twin_facts(user)
    active = resolve_advisor_style(user, facts)
    copy = _lines(facts, twin, radar)
    voices: List[Dict[str, Any]] = []
    for sid, meta in STYLES.items():
        voices.append(
            {
                **meta,
                "line_ja": copy[sid],
                "active": sid == active,
            }
        )
    return {
        "ok": True,
        "title_ja": "コンパニオン評議会",
        "advisor_style": normalize_advisor_style(user.get("advisor_style")),
        "resolved_style": active,
        "voices": voices,
    }


def council_prompt_block(user: Dict[str, Any]) -> str:
    from future_twin_service import collect_twin_facts

    facts = collect_twin_facts(user)
    style = resolve_advisor_style(user, facts)
    meta = STYLES[style]
    extra = {
        "strategist": "Be a planner: one concrete next move, no lecture.",
        "strict": "Be a senior: warm but blunt. Do not soften the ask. Still kind, never cruel.",
        "empathic": "Feel first, then one tiny step. Never scold.",
    }[style]
    return (
        f"ADVISOR COUNCIL STYLE: {style} (voice of {meta['who_ja']}). {extra}\n"
        "You still keep YOUR companion name. Do not rename yourself."
    )
