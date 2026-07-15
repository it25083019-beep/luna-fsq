"""Career suggestion engine: map any personality/hobby/subject into clusters."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "career_taxonomy.json"
_TAXONOMY: Optional[Dict[str, Any]] = None


def load_taxonomy() -> Dict[str, Any]:
    global _TAXONOMY
    if _TAXONOMY is None:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            _TAXONOMY = json.load(f)
    return _TAXONOMY


def _norm(text: str) -> str:
    return (text or "").strip().lower()


def score_axes_from_text(text: str) -> Dict[str, float]:
    tax = load_taxonomy()
    t = _norm(text)
    scores = {a["id"]: 0.0 for a in tax["personality_axes"]}
    if not t:
        return scores
    for axis in tax["personality_axes"]:
        for kw in axis.get("keywords", []):
            if _norm(kw) and _norm(kw) in t:
                scores[axis["id"]] += 1.0
    return scores


def score_axes_from_subjects(
    subject_ids: List[str], grades: Optional[Dict[str, float]] = None
) -> Dict[str, float]:
    tax = load_taxonomy()
    scores = {a["id"]: 0.0 for a in tax["personality_axes"]}
    sub_map = {s["id"]: s for s in tax["subjects"]}
    grades = grades or {}
    for sid in subject_ids or []:
        s = sub_map.get(sid)
        if not s:
            for cand in tax["subjects"]:
                if any(_norm(k) in _norm(sid) for k in cand.get("keywords", [])):
                    s = cand
                    break
        if not s:
            continue
        weight = 1.0
        g = grades.get(s["id"]) or grades.get(sid)
        if g is not None:
            try:
                weight = max(0.5, min(2.0, float(g) / 3.0))
            except (TypeError, ValueError):
                weight = 1.0
        for ax in s.get("axes", []):
            scores[ax] = scores.get(ax, 0.0) + weight
    return scores


def merge_scores(*maps: Dict[str, float]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for m in maps:
        for k, v in m.items():
            out[k] = out.get(k, 0.0) + float(v)
    return out


def score_clusters(
    axis_scores: Dict[str, float], subject_ids: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    tax = load_taxonomy()
    subject_ids = subject_ids or []
    results = []
    for c in tax["career_clusters"]:
        score = 0.0
        for ax in c.get("axes", []):
            score += axis_scores.get(ax, 0.0) * 1.5
        for sid in c.get("subjects", []):
            if sid in subject_ids:
                score += 1.2
        if c.get("is_fallback"):
            score += 0.2
        results.append(
            {
                "cluster_id": c["id"],
                "label_ja": c["label_ja"],
                "score": round(score, 3),
                "example_jobs": c.get("example_jobs", []),
                "rpg_class": c.get("rpg_class"),
                "is_fallback": bool(c.get("is_fallback")),
            }
        )
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def classify_freeform(hobby_or_job: str) -> Dict[str, Any]:
    """Always returns usable axes/clusters even for unusual free text."""
    tax = load_taxonomy()
    text = hobby_or_job or ""
    axis_scores = score_axes_from_text(text)
    for sub in tax["subjects"]:
        if any(_norm(k) in _norm(text) for k in sub.get("keywords", [])):
            for ax in sub.get("axes", []):
                axis_scores[ax] = axis_scores.get(ax, 0.0) + 0.8
    ranked = sorted(axis_scores.items(), key=lambda x: x[1], reverse=True)
    top_axes = [a for a, s in ranked if s > 0][:3]
    if not top_axes:
        top_axes = ["explore"]
        axis_scores["explore"] = max(axis_scores.get("explore", 0.0), 0.5)
    cluster_scores = score_clusters(axis_scores, subject_ids=[])
    return {
        "input": text,
        "matched_axes": top_axes,
        "axis_scores": axis_scores,
        "likely_clusters": [c["cluster_id"] for c in cluster_scores[:3]],
    }


def suggest_careers(
    *,
    decided_career: Optional[str] = None,
    personality_text: str = "",
    hobbies_text: str = "",
    favorite_subjects: Optional[List[str]] = None,
    subject_grades: Optional[Dict[str, float]] = None,
    top_k: int = 3,
) -> Dict[str, Any]:
    tax = load_taxonomy()
    favorite_subjects = favorite_subjects or []

    if decided_career and decided_career.strip():
        mapped = classify_freeform(decided_career)
        axis = merge_scores(
            score_axes_from_text(decided_career),
            score_axes_from_subjects(favorite_subjects, subject_grades),
        )
        clusters = score_clusters(axis, favorite_subjects)
        primary = clusters[0] if clusters else None
        career = decided_career.strip()
        return {
            "mode": "decided",
            "decided_career": career,
            "message_ja": "進路は決まっています。その方向でクエストと成長ルートを組み立てます。",
            "matched_axes": mapped["matched_axes"],
            "suggestions": [
                {
                    "cluster_id": primary["cluster_id"] if primary else "exploration",
                    "label_ja": primary["label_ja"] if primary else "探索ルート",
                    "reason_ja": "決めた進路『" + career + "』に近いクラスターです。",
                    "example_jobs": [career] + ((primary.get("example_jobs", [])[:2]) if primary else []),
                    "rpg_class": primary.get("rpg_class") if primary else "archer",
                    "score": primary.get("score", 1.0) if primary else 1.0,
                }
            ],
            "rpg_class_hint": (primary or {}).get("rpg_class", "archer"),
            "coverage_note": "未知の職業名でも軸へ写像してルートを作れます。",
        }

    axis = merge_scores(
        score_axes_from_text(personality_text),
        score_axes_from_text(hobbies_text),
        score_axes_from_subjects(favorite_subjects, subject_grades),
    )
    if sum(axis.values()) <= 0:
        axis["explore"] = 1.0
        axis["creative"] = 0.3

    clusters = score_clusters(axis, favorite_subjects)
    non_fb = [c for c in clusters if not c.get("is_fallback")]
    fb = [c for c in clusters if c.get("is_fallback")]
    top = (non_fb + fb)[: max(1, top_k)]

    suggestions = []
    for c in top:
        reasons = []
        for ax_id, sc in sorted(axis.items(), key=lambda x: x[1], reverse=True)[:2]:
            if sc <= 0:
                continue
            label = next(
                (a["label_ja"] for a in tax["personality_axes"] if a["id"] == ax_id),
                ax_id,
            )
            reasons.append(label)
        reason = "・".join(reasons) if reasons else "興味の探索"
        suggestions.append(
            {
                "cluster_id": c["cluster_id"],
                "label_ja": c["label_ja"],
                "reason_ja": reason + "の傾向から提案",
                "example_jobs": c["example_jobs"],
                "rpg_class": c["rpg_class"],
                "score": c["score"],
            }
        )

    freeform = classify_freeform(" ".join([personality_text, hobbies_text]))
    return {
        "mode": "suggest",
        "decided_career": None,
        "message_ja": "まだ進路が未定なので、性格・興味・得意科目から候補を出しました。探索ルートも残せます。",
        "matched_axes": freeform["matched_axes"],
        "axis_scores": axis,
        "suggestions": suggestions,
        "rpg_class_hint": suggestions[0]["rpg_class"] if suggestions else "archer",
        "coverage_note": "未知の趣味・職業名も軸へ写像するため、一覧に無くても提案できます。",
    }


def rpg_class_label(class_id: str) -> str:
    tax = load_taxonomy()
    for c in tax["rpg_classes"]:
        if c["id"] == class_id:
            return c["label_ja"]
    return class_id