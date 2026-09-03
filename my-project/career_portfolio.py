# -*- coding: utf-8 -*-
"""Job-facing portfolio built from graded lesson answers and boss exams."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from journey_engine import _career_meta, _utcnow, ensure_journey, get_curriculum, list_ranks


def record_study_evidence(
    state: Dict[str, Any],
    *,
    kind: str,
    item_id: str,
    title_ja: str,
    answer: str,
    score: float,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    j = ensure_journey(state)
    text = (answer or "").strip()
    if not text:
        return
    row: Dict[str, Any] = {
        "kind": kind,
        "id": item_id,
        "title_ja": title_ja,
        "snippet": text[:280],
        "score": round(float(score), 2),
        "at": _utcnow(),
    }
    if extra:
        row.update(extra)
    ev = list(j.get("portfolio_evidence") or [])
    ev = [x for x in ev if not (x.get("kind") == kind and x.get("id") == item_id)]
    ev.append(row)
    j["portfolio_evidence"] = ev[-48:]


def _self_pr_bullets(j: Dict[str, Any], career_title: str, evidence: List[Dict[str, Any]]) -> List[str]:
    skills = j.get("skills") or []
    skill_names = [s.get("label_ja") or s.get("id") for s in skills[:6] if s]
    exams = [x for x in (j.get("boss_attempts") or {}).values() if x.get("passed")]
    bullets: List[str] = []
    if evidence:
        latest = evidence[-1]
        bullets.append(
            f"{career_title or '進路'}の学習で「{latest.get('title_ja') or '課題'}」に取り組み、"
            f"自分の言葉で解答を残した（習熟 {int((latest.get('score') or 0) * 100)}%）。"
        )
    if skill_names:
        bullets.append("身につけたスキル：" + "、".join(str(n) for n in skill_names if n) + "。")
    if exams:
        bullets.append(
            f"単元・総合テストを{len(exams)}回クリアし、期末／認定相当の確認に耐える記録がある。"
        )
    if len(evidence) >= 4:
        bullets.append(
            "提出物は短い感想ではなく、課題の用語と手順を含む実践ログとして蓄積されている。"
        )
    if not bullets:
        bullets.append("レッスンを提出すると、就活用の自己PRの種がここに増えていきます。")
    return bullets[:5]


def build_career_portfolio(state: Dict[str, Any]) -> Dict[str, Any]:
    j = ensure_journey(state)
    career_id = j.get("career_id") or ""
    career = _career_meta(career_id) if career_id else None
    career_title = (career or {}).get("title_ja") or ""
    ranks = {r["id"]: r for r in list_ranks()}
    rank_id = j.get("rank_id") or "novice"
    evidence = list(j.get("portfolio_evidence") or [])
    evidence_sorted = sorted(evidence, key=lambda x: x.get("at") or "", reverse=True)

    exams: List[Dict[str, Any]] = []
    cur = get_curriculum(career_id) if career_id else {}
    les_by_id = {x["id"]: x for x in (cur.get("lessons") or [])}
    for bid, row in (j.get("boss_attempts") or {}).items():
        les = les_by_id.get(bid) or {}
        exams.append(
            {
                "id": bid,
                "title_ja": les.get("title_ja") or bid,
                "boss_type": les.get("boss_type") or row.get("boss_type") or "",
                "score": row.get("score"),
                "passed": bool(row.get("passed")),
                "updated_at": row.get("updated_at"),
            }
        )
    exams.sort(key=lambda x: x.get("updated_at") or "", reverse=True)

    completed = list(j.get("completed_lessons") or [])
    cleared = list(j.get("boss_clears") or [])
    final_cleared = any(
        (les_by_id.get(bid) or {}).get("boss_type") == "career_final" for bid in cleared
    )
    job_ready = bool(final_cleared) or (len(evidence) >= 8 and sum(1 for e in exams if e.get("passed")) >= 2)

    name = state.get("user_display_name") or "学習者"
    skill_n = len(j.get("skills") or [])
    if not career_id:
        story = "クラスと職業を選ぶと、提出した課題から就活用の記録が育ちます。"
    elif not evidence:
        story = (
            f"{name}は『{career_title or '進路'}』の旅を始めたばかり。"
            "課題に自分の言葉で答え、提出すると経験値と履歴書の種が同時に残ります。"
        )
    else:
        story = (
            f"{name}は『{career_title}』でレッスン{len(completed)}本・試験クリア{len(cleared)}回。"
            f"スキル{skill_n}件と提出エビデンス{len(evidence)}件が、将来の自己PRの根拠になる。"
            + (" 認定試験相当を突破済み。応募書類に使える段階です。" if final_cleared else "")
        )

    return {
        "ok": True,
        "generated_at": _utcnow(),
        "career_id": career_id,
        "career_title_ja": career_title,
        "rank_id": rank_id,
        "rank_ja": (ranks.get(rank_id) or {}).get("label_ja"),
        "completed_count": len(completed),
        "boss_clears": len(cleared),
        "skills": j.get("skills") or [],
        "evidence": evidence_sorted[:16],
        "exams": exams[:12],
        "self_pr": _self_pr_bullets(j, career_title, evidence_sorted),
        "job_ready": job_ready,
        "story_ja": story,
    }
