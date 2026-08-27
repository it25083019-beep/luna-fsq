# -*- coding: utf-8 -*-
"""Paiza-like study workspace: problem, answer draft, progressive guides, boss exam."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from journey_engine import (
    _attach_material,
    _is_boss,
    _utcnow,
    challenge_boss,
    complete_lesson,
    ensure_journey,
    get_curriculum,
    get_lesson,
    get_lesson_material,
    list_bosses,
    list_journey_map,
)

_MIN_ANSWER_CHARS = 24
_MIN_BOSS_ANSWER_CHARS = 12
_CODE_CAREERS = {"software_engineer", "data_analyst", "web_developer", "security_engineer"}


def _keywords_from_texts(texts: List[str], limit: int = 8) -> List[str]:
    found: List[str] = []
    for t in texts:
        raw = re.sub(r"[「」『』（）()\[\]【】、。・/\s]+", " ", str(t or ""))
        for tok in raw.split():
            tok = tok.strip()
            if len(tok) < 2:
                continue
            if tok not in found:
                found.append(tok)
            if len(found) >= limit:
                return found
    return found


def build_study_payload(lesson: Dict[str, Any], *, career_id: Optional[str] = None) -> Dict[str, Any]:
    """Derive Paiza-like fields from existing materials (additive)."""
    mat = get_lesson_material(lesson["id"]) if lesson.get("id") else {}
    if not mat and lesson.get("summary_ja") is not None:
        mat = lesson

    practice_steps = mat.get("practice_steps") or mat.get("steps") or []
    first_practice = ""
    if practice_steps:
        first = practice_steps[0] or {}
        first_practice = (first.get("body_ja") or first.get("title_ja") or "").strip()

    problem = (
        (mat.get("problem_ja") or "").strip()
        or (mat.get("practice_ja") or "").strip()
        or first_practice
        or (mat.get("summary_ja") or "").strip()
        or "この単元の課題に取り組み、解答欄に考えた内容を書いて提出しよう。"
    )

    workspace_type = (mat.get("workspace_type") or "").strip()
    if workspace_type not in ("text", "code"):
        cid = career_id or ""
        workspace_type = "code" if cid in _CODE_CAREERS else "text"

    guides = mat.get("method_guides")
    if not isinstance(guides, list) or not guides:
        guides = []
        theory = mat.get("theory_ja") or []
        for i, line in enumerate(theory[:4]):
            guides.append(
                {
                    "level": i + 1,
                    "title_ja": f"方法ガイド {i + 1}",
                    "body_ja": str(line),
                    "source_ja": "単元の理論（正しい進め方）",
                }
            )
        for res in (mat.get("resources") or [])[:3]:
            title = res.get("title_ja") or "参考"
            url = res.get("url") or ""
            kind = res.get("kind") or "article"
            guides.append(
                {
                    "level": len(guides) + 1,
                    "title_ja": f"フォーラム／教材の定石：{title}",
                    "body_ja": (
                        f"「{title}」のやり方を確認してから、同じ手順で自分の解答を書いてみよう。"
                        + (f" 参照: {url}" if url else "")
                    ),
                    "source_ja": f"{kind} / 公開教材の定石",
                }
            )
        if not guides:
            guides = [
                {
                    "level": 1,
                    "title_ja": "まず分解する",
                    "body_ja": "課題を『わかっていること』と『やること』に分け、1つずつ書く。",
                    "source_ja": "一般的な学習フォーラムの定石",
                },
                {
                    "level": 2,
                    "title_ja": "小さく試す",
                    "body_ja": "完璧な答えより、短い実験やメモを先に残す。",
                    "source_ja": "一般的な学習フォーラムの定石",
                },
            ]

    keywords = mat.get("check_keywords")
    if not isinstance(keywords, list) or not keywords:
        keywords = _keywords_from_texts(
            list(mat.get("checklist_ja") or []) + list(mat.get("goals_ja") or []) + [problem]
        )

    return {
        "problem_ja": problem,
        "workspace_type": workspace_type,
        "method_guides": guides,
        "check_keywords": keywords,
        "hint_count": len(guides),
        "min_answer_chars": _MIN_ANSWER_CHARS,
    }


def attach_study_fields(lesson: Dict[str, Any], *, career_id: Optional[str] = None) -> Dict[str, Any]:
    out = dict(lesson)
    payload = build_study_payload(out, career_id=career_id)
    out.update(payload)
    return out


def _attempts(j: Dict[str, Any]) -> Dict[str, Any]:
    return j.setdefault("lesson_attempts", {})


def _boss_attempts(j: Dict[str, Any]) -> Dict[str, Any]:
    return j.setdefault("boss_attempts", {})


def get_attempt(state: Dict[str, Any], lesson_id: str) -> Dict[str, Any]:
    j = ensure_journey(state)
    if not j.get("career_id"):
        raise ValueError("journey not selected")
    lesson = get_lesson(state, lesson_id)
    row = dict((_attempts(j).get(lesson_id) or {}))
    study = build_study_payload(lesson, career_id=j.get("career_id"))
    hints_used = int(row.get("hints_used") or 0)
    unlocked = study["method_guides"][: max(0, hints_used)]
    return {
        "ok": True,
        "lesson_id": lesson_id,
        "answer": row.get("answer") or "",
        "hints_used": hints_used,
        "unlocked_guides": unlocked,
        "study": study,
        "completed": lesson_id in (j.get("completed_lessons") or []),
    }


def save_attempt(state: Dict[str, Any], lesson_id: str, answer: str) -> Dict[str, Any]:
    j = ensure_journey(state)
    if not j.get("career_id"):
        raise ValueError("journey not selected")
    get_lesson(state, lesson_id)  # validate exists
    text = (answer or "")[:8000]
    prev = dict(_attempts(j).get(lesson_id) or {})
    prev["answer"] = text
    prev["updated_at"] = _utcnow()
    prev.setdefault("hints_used", 0)
    _attempts(j)[lesson_id] = prev
    return {"ok": True, "lesson_id": lesson_id, "answer": text, "hints_used": int(prev.get("hints_used") or 0)}


def reveal_hint(state: Dict[str, Any], lesson_id: str) -> Dict[str, Any]:
    j = ensure_journey(state)
    if not j.get("career_id"):
        raise ValueError("journey not selected")
    lesson = get_lesson(state, lesson_id)
    study = build_study_payload(lesson, career_id=j.get("career_id"))
    guides = study["method_guides"]
    row = dict(_attempts(j).get(lesson_id) or {})
    used = int(row.get("hints_used") or 0)
    if used >= len(guides):
        return {
            "ok": True,
            "lesson_id": lesson_id,
            "hints_used": used,
            "guide": None,
            "done": True,
            "message_ja": "ガイドはすべて開放済みです。解答欄に自分の言葉で書いて提出しよう。",
            "unlocked_guides": guides,
        }
    guide = guides[used]
    used += 1
    row["hints_used"] = used
    row["updated_at"] = _utcnow()
    row.setdefault("answer", "")
    _attempts(j)[lesson_id] = row
    return {
        "ok": True,
        "lesson_id": lesson_id,
        "hints_used": used,
        "guide": guide,
        "done": used >= len(guides),
        "message_ja": f"ガイド {used}/{len(guides)} を開放しました。",
        "unlocked_guides": guides[:used],
    }


def soft_check_answer(answer: str, keywords: List[str], *, min_chars: int = _MIN_ANSWER_CHARS) -> Dict[str, Any]:
    text = (answer or "").strip()
    warnings: List[str] = []
    ok_len = len(text) >= min_chars
    if not ok_len:
        return {
            "ok": False,
            "can_submit": False,
            "matched": [],
            "warnings": [f"解答は{min_chars}文字以上書いてから提出しよう。"],
            "score": 0.0,
        }
    matched = [k for k in keywords if k and k in text]
    score = 1.0
    if keywords:
        score = len(matched) / max(1, min(3, len(keywords)))
        score = min(1.0, score)
        if not matched:
            warnings.append("キーワードが少ないかも。ガイドやゴールを見ながら、要点を自分の言葉で足してみよう。")
            score = 0.35
    return {
        "ok": True,
        "can_submit": True,
        "matched": matched,
        "warnings": warnings,
        "score": round(score, 2),
    }


def submit_lesson(state: Dict[str, Any], lesson_id: str, answer: Optional[str] = None) -> Dict[str, Any]:
    j = ensure_journey(state)
    if not j.get("career_id"):
        raise ValueError("journey not selected")
    lesson = get_lesson(state, lesson_id)
    if _is_boss(lesson):
        raise ValueError("use boss exam endpoint for boss lessons")

    row = dict(_attempts(j).get(lesson_id) or {})
    text = answer if answer is not None else (row.get("answer") or "")
    text = (text or "").strip()
    study = build_study_payload(lesson, career_id=j.get("career_id"))
    check = soft_check_answer(text, study.get("check_keywords") or [], min_chars=study.get("min_answer_chars") or _MIN_ANSWER_CHARS)
    if not check["can_submit"]:
        raise ValueError(check["warnings"][0] if check["warnings"] else "answer too short")

    row["answer"] = text[:8000]
    row["hints_used"] = int(row.get("hints_used") or 0)
    row["updated_at"] = _utcnow()
    row["submitted_at"] = _utcnow()
    row["last_score"] = check["score"]
    _attempts(j)[lesson_id] = row

    result = complete_lesson(state, lesson_id)
    result["submit"] = {
        "answer_len": len(text),
        "hints_used": row["hints_used"],
        "soft_check": check,
        "message_ja": "提出完了！学習がスキルとして記録されたよ。"
        + (("（" + " / ".join(check["warnings"]) + "）") if check["warnings"] else ""),
    }
    return result


def build_boss_exam(state: Dict[str, Any], boss_id: str) -> Dict[str, Any]:
    j = ensure_journey(state)
    if not j.get("career_id"):
        raise ValueError("journey not selected")
    bosses = {b["id"]: b for b in list_bosses(state)}
    info = bosses.get(boss_id)
    if not info:
        raise ValueError("boss not found")
    cur = get_curriculum(j["career_id"])
    les = next((x for x in (cur.get("lessons") or []) if x["id"] == boss_id), None)
    if not les:
        raise ValueError("boss lesson missing")

    stage_id = les.get("stage_id")
    completed = set(j.get("completed_lessons") or [])
    pool = [
        x
        for x in (cur.get("lessons") or [])
        if not _is_boss(x) and x.get("stage_id") == stage_id and x["id"] in completed
    ]
    if len(pool) < 2:
        pool = [x for x in (cur.get("lessons") or []) if not _is_boss(x) and x["id"] in completed]
    if not pool:
        pool = [x for x in (cur.get("lessons") or []) if not _is_boss(x) and x.get("stage_id") == stage_id][:3]

    questions: List[Dict[str, Any]] = []
    for src in pool[:3]:
        mat = _attach_material(src)
        study = build_study_payload(mat, career_id=j.get("career_id"))
        goals = mat.get("goals_ja") or []
        q = goals[0] if goals else (mat.get("summary_ja") or src.get("title_ja") or "要点を説明せよ")
        questions.append(
            {
                "id": src["id"],
                "prompt_ja": f"「{src.get('title_ja') or src['id']}」について：{q}",
                "check_keywords": study.get("check_keywords") or [],
                "source_title_ja": src.get("title_ja"),
            }
        )

    prev = dict(_boss_attempts(j).get(boss_id) or {})
    return {
        "ok": True,
        "boss": info,
        "title_ja": les.get("title_ja") or info.get("title_ja"),
        "boss_type": info.get("boss_type"),
        "exam_label_ja": {
            "weekly": "週次テスト",
            "monthly": "月次テスト",
            "career_final": "最終試験",
        }.get(info.get("boss_type") or "", "確認テスト"),
        "questions": questions,
        "answers": prev.get("answers") or {},
        "min_answer_chars": _MIN_BOSS_ANSWER_CHARS,
        "pass_ratio": 0.5,
        "available": bool(info.get("available")),
        "cleared": bool(info.get("cleared")),
    }


def submit_boss_exam(
    state: Dict[str, Any],
    boss_id: str,
    answers: Dict[str, str],
) -> Dict[str, Any]:
    exam = build_boss_exam(state, boss_id)
    if exam.get("cleared"):
        raise ValueError("boss already cleared")
    if not exam.get("available"):
        raise ValueError("boss locked")

    questions = exam["questions"]
    if not questions:
        raise ValueError("exam has no questions")

    scores: List[float] = []
    details: List[Dict[str, Any]] = []
    clean_answers: Dict[str, str] = {}
    length_ok = True
    for q in questions:
        qid = q["id"]
        ans = (answers.get(qid) or "").strip()[:4000]
        clean_answers[qid] = ans
        check = soft_check_answer(ans, q.get("check_keywords") or [], min_chars=_MIN_BOSS_ANSWER_CHARS)
        if not check["can_submit"]:
            length_ok = False
        scores.append(float(check["score"] if check["can_submit"] else 0.0))
        details.append({"id": qid, "soft_check": check})

    avg = sum(scores) / max(1, len(scores))
    # Pass if every answer meets minimum length (keyword score is advisory).
    passed = length_ok and avg >= 0.2

    j = ensure_journey(state)
    _boss_attempts(j)[boss_id] = {
        "answers": clean_answers,
        "score": round(avg, 2),
        "passed": passed,
        "updated_at": _utcnow(),
    }

    if not passed:
        return {
            "ok": False,
            "success": False,
            "passed": False,
            "score": round(avg, 2),
            "details": details,
            "message_ja": "テストはもう少し。各問を短くてもよいので具体的に書いてから再挑戦しよう（進捗は消えません）。",
            "exam": exam,
            "status": None,
        }

    result = challenge_boss(state, boss_id, success=True)
    result["passed"] = True
    result["score"] = round(avg, 2)
    result["details"] = details
    result["message_ja"] = (
        exam.get("exam_label_ja") or "確認テスト"
    ) + "クリア！これまでの学習が確認できたよ。"
    return result
