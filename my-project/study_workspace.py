# -*- coding: utf-8 -*-
"""Paiza-like study workspace: problem, answer draft, progressive guides, boss exam."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

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
)

_MIN_ANSWER_CHARS = 48
_MIN_BOSS_ANSWER_CHARS = 40
_LESSON_PASS_SCORE = 0.48
_BOSS_EXAM_SPEC = {
    "weekly": {
        "questions": 5,
        "min_chars": 48,
        "pass_ratio": 0.58,
        "match_ratio": 0.4,
        "label_ja": "単元テスト（小テスト〜中間相当）",
        "briefing_ja": "このステージの学習を、自分の言葉で説明できるかを見ます。短い感想や繰り返しでは通りません。",
    },
    "monthly": {
        "questions": 8,
        "min_chars": 72,
        "pass_ratio": 0.66,
        "match_ratio": 0.5,
        "label_ja": "総合テスト（学期末試験相当）",
        "briefing_ja": "複数単元を横断します。用語・手順・理由を具体的に書いてください。不合格でも進捗は消えません。",
    },
    "career_final": {
        "questions": 10,
        "min_chars": 90,
        "pass_ratio": 0.75,
        "match_ratio": 0.6,
        "label_ja": "認定試験（資格・卒業試験相当）",
        "briefing_ja": "進路の最終関門です。実務で説明できる粒度まで書いてください。合格記録は就活ポートフォリオに残ります。",
    },
}
_CODE_CAREERS = {"software_engineer", "data_analyst", "web_developer", "security_engineer"}
_PAIZA: Optional[Dict[str, Any]] = None


def load_paiza_problems() -> Dict[str, Any]:
    global _PAIZA
    if _PAIZA is None:
        path = Path(__file__).resolve().parent / "config" / "paiza_problems.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                _PAIZA = json.load(f)
        else:
            _PAIZA = {"problems": {}}
    return _PAIZA


def get_paiza_problem(lesson_id: str) -> Dict[str, Any]:
    probs = load_paiza_problems().get("problems") or {}
    row = probs.get(lesson_id)
    if row:
        return dict(row)
    if "__" in lesson_id:
        base = lesson_id.split("__", 1)[-1]
        row = probs.get(base)
        if row:
            return dict(row)
    return {}


def _compose_problem_text(paiza: Dict[str, Any], fallback: str) -> str:
    if not paiza:
        return fallback
    parts: List[str] = []
    title = (paiza.get("problem_title_ja") or "").strip()
    body = (paiza.get("problem_ja") or "").strip()
    if title:
        parts.append(title)
    if body:
        parts.append(body)
    if paiza.get("input_format_ja"):
        parts.append("【入力】\n" + str(paiza["input_format_ja"]).strip())
    if paiza.get("output_format_ja"):
        parts.append("【出力】\n" + str(paiza["output_format_ja"]).strip())
    if paiza.get("constraints_ja"):
        parts.append("【条件】\n" + str(paiza["constraints_ja"]).strip())
    text = "\n\n".join(parts).strip()
    return text or fallback


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
    """Derive Paiza-like fields from materials + paiza_problems bank (additive)."""
    lid = lesson.get("id") or ""
    mat = get_lesson_material(lid) if lid else {}
    if not mat and lesson.get("summary_ja") is not None:
        mat = lesson
    paiza = get_paiza_problem(lid)

    practice_steps = mat.get("practice_steps") or mat.get("steps") or []
    first_practice = ""
    if practice_steps:
        first = practice_steps[0] or {}
        first_practice = (first.get("body_ja") or first.get("title_ja") or "").strip()

    title_ja = (lesson.get("title_ja") or "").strip()
    fallback = (
        (mat.get("problem_ja") or "").strip()
        or (mat.get("practice_ja") or "").strip()
        or first_practice
        or (mat.get("summary_ja") or "").strip()
        or (
            f"「{title_ja}」の課題に取り組み、解答スペースに書いて提出しよう。"
            if title_ja
            else "この単元の課題に取り組み、解答欄に考えた内容を書いて提出しよう。"
        )
    )
    problem = _compose_problem_text(paiza, fallback)

    workspace_type = (paiza.get("workspace_type") or mat.get("workspace_type") or "").strip()
    if workspace_type not in ("text", "code"):
        cid = career_id or ""
        workspace_type = "code" if cid in _CODE_CAREERS or lid.startswith("se_") else "text"

    guides = paiza.get("method_guides") or mat.get("method_guides")
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

    keywords = paiza.get("check_keywords") or mat.get("check_keywords")
    if not isinstance(keywords, list) or not keywords:
        keywords = _keywords_from_texts(
            list(mat.get("checklist_ja") or []) + list(mat.get("goals_ja") or []) + [problem]
        )

    min_chars = int(paiza.get("min_answer_chars") or mat.get("min_answer_chars") or _MIN_ANSWER_CHARS)
    starter = paiza.get("starter_code") if isinstance(paiza.get("starter_code"), dict) else {}
    samples = paiza.get("samples") if isinstance(paiza.get("samples"), list) else []

    return {
        "problem_ja": problem,
        "problem_title_ja": paiza.get("problem_title_ja") or lesson.get("title_ja") or "",
        "workspace_type": workspace_type,
        "method_guides": guides,
        "check_keywords": keywords,
        "hint_count": len(guides),
        "min_answer_chars": min_chars,
        "input_format_ja": paiza.get("input_format_ja") or "",
        "output_format_ja": paiza.get("output_format_ja") or "",
        "constraints_ja": paiza.get("constraints_ja") or "",
        "samples": samples,
        "starter_code": starter,
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


def _looks_like_filler(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    if len(set(compact)) < 8:
        return True
    if len(compact) >= 24 and len(set(compact)) / max(1, len(compact)) < 0.12:
        return True
    return False


def _copied_prompt(text: str, prompts: List[str]) -> bool:
    src = re.sub(r"\s+", "", text)
    if len(src) < 20:
        return False
    for p in prompts:
        raw = re.sub(r"\s+", "", str(p or ""))
        if len(raw) < 24:
            continue
        if src == raw:
            return True
        if raw in src and len(src) - len(raw) < 20:
            return True
        if src in raw and len(raw) - len(src) < 8:
            return True
    return False


def soft_check_answer(
    answer: str,
    keywords: List[str],
    *,
    min_chars: int = _MIN_ANSWER_CHARS,
    require_keyword: bool = True,
    reject_prompts: Optional[List[str]] = None,
) -> Dict[str, Any]:
    text = (answer or "").strip()
    warnings: List[str] = []
    if len(text) < min_chars:
        return {
            "ok": False,
            "can_submit": False,
            "matched": [],
            "warnings": [f"解答は{min_chars}文字以上、用語と手順を入れて書いてから提出しよう。"],
            "score": 0.0,
        }
    if _looks_like_filler(text):
        return {
            "ok": False,
            "can_submit": False,
            "matched": [],
            "warnings": ["同じ文字の繰り返しや意味のない文字列では提出できません。自分の言葉で説明しよう。"],
            "score": 0.0,
        }
    if reject_prompts and _copied_prompt(text, reject_prompts):
        return {
            "ok": False,
            "can_submit": False,
            "matched": [],
            "warnings": ["課題文のコピーだけでは通りません。理解した内容を自分の言葉で書き直そう。"],
            "score": 0.0,
        }
    matched = [k for k in keywords if k and str(k) in text]
    if require_keyword and keywords and not matched:
        return {
            "ok": False,
            "can_submit": False,
            "matched": [],
            "warnings": ["単元の用語が足りません。ガイドとゴールを見て、要点を自分の言葉で足そう。"],
            "score": 0.15,
        }
    coverage = 1.0
    if keywords:
        coverage = len(matched) / max(1, min(4, len(keywords)))
        coverage = min(1.0, coverage)
    length_bonus = min(0.2, max(0.0, (len(text) - min_chars) / 500))
    score = min(1.0, 0.55 * coverage + 0.3 + length_bonus)
    if coverage < 0.5:
        warnings.append("用語カバーがまだ薄い。チェックリストの言葉を使って具体化しよう。")
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
    min_chars = max(_MIN_ANSWER_CHARS, int(study.get("min_answer_chars") or _MIN_ANSWER_CHARS))
    check = soft_check_answer(
        text,
        study.get("check_keywords") or [],
        min_chars=min_chars,
        require_keyword=True,
        reject_prompts=[
            study.get("problem_ja") or "",
            study.get("problem_title_ja") or "",
            lesson.get("title_ja") or "",
        ],
    )
    if not check["can_submit"] or float(check.get("score") or 0) < _LESSON_PASS_SCORE:
        raise ValueError(
            (check["warnings"][0] if check.get("warnings") else "解答の習熟が足りません。ガイドを見て書き直そう。")
        )

    row["answer"] = text[:8000]
    row["hints_used"] = int(row.get("hints_used") or 0)
    row["updated_at"] = _utcnow()
    row["submitted_at"] = _utcnow()
    row["last_score"] = check["score"]
    _attempts(j)[lesson_id] = row

    from career_portfolio import record_study_evidence

    record_study_evidence(
        state,
        kind="lesson",
        item_id=lesson_id,
        title_ja=lesson.get("title_ja") or lesson_id,
        answer=text,
        score=check["score"],
    )

    result = complete_lesson(state, lesson_id)
    result["submit"] = {
        "answer_len": len(text),
        "hints_used": row["hints_used"],
        "soft_check": check,
        "message_ja": "提出完了！解答がスキルと就活記録に残ったよ。"
        + (("（" + " / ".join(check["warnings"]) + "）") if check["warnings"] else ""),
    }
    return result


def _boss_spec(boss_type: str) -> Dict[str, Any]:
    return dict(_BOSS_EXAM_SPEC.get(boss_type) or {
        "questions": 5,
        "min_chars": _MIN_BOSS_ANSWER_CHARS,
        "pass_ratio": 0.6,
        "match_ratio": 0.4,
        "label_ja": "確認テスト",
        "briefing_ja": "学習した内容を自分の言葉で説明してください。",
    })


def _collect_exam_questions(
    cur: Dict[str, Any],
    *,
    career_id: Optional[str],
    completed: set,
    stage_id: str,
    boss_type: str,
    want: int,
) -> List[Dict[str, Any]]:
    lessons = [x for x in (cur.get("lessons") or []) if not _is_boss(x)]
    same = [x for x in lessons if x.get("stage_id") == stage_id and x["id"] in completed]
    others = [x for x in lessons if x["id"] in completed and x.get("stage_id") != stage_id]
    if boss_type == "weekly":
        pool = same or others
    elif boss_type == "monthly":
        pool = same + others
    else:
        pool = others + same
        pool = list(reversed(pool))
    if not pool:
        pool = [x for x in lessons if x.get("stage_id") == stage_id][:want]

    questions: List[Dict[str, Any]] = []
    seen: set = set()
    for src in pool:
        mat = _attach_material(src)
        study = build_study_payload(mat, career_id=career_id)
        prompts: List[str] = []
        for g in (mat.get("goals_ja") or [])[:2]:
            if g:
                prompts.append(str(g))
        for c in (mat.get("checklist_ja") or [])[:1]:
            if c:
                prompts.append(str(c))
        if not prompts:
            prompts.append(mat.get("summary_ja") or src.get("title_ja") or "要点を説明せよ")
        kws = study.get("check_keywords") or []
        for i, prompt in enumerate(prompts):
            qid = src["id"] if i == 0 else f"{src['id']}__q{i + 1}"
            if qid in seen:
                continue
            seen.add(qid)
            questions.append(
                {
                    "id": qid,
                    "prompt_ja": f"「{src.get('title_ja') or src['id']}」について：{prompt}",
                    "check_keywords": kws,
                    "source_title_ja": src.get("title_ja"),
                    "source_lesson_id": src["id"],
                }
            )
            if len(questions) >= want:
                return questions
    return questions


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

    spec = _boss_spec(info.get("boss_type") or "")
    completed = set(j.get("completed_lessons") or [])
    questions = _collect_exam_questions(
        cur,
        career_id=j.get("career_id"),
        completed=completed,
        stage_id=les.get("stage_id") or "",
        boss_type=info.get("boss_type") or "",
        want=int(spec["questions"]),
    )

    prev = dict(_boss_attempts(j).get(boss_id) or {})
    return {
        "ok": True,
        "boss": info,
        "title_ja": les.get("title_ja") or info.get("title_ja"),
        "boss_type": info.get("boss_type"),
        "exam_label_ja": spec["label_ja"],
        "briefing_ja": spec["briefing_ja"],
        "questions": questions,
        "answers": prev.get("answers") or {},
        "min_answer_chars": int(spec["min_chars"]),
        "pass_ratio": float(spec["pass_ratio"]),
        "match_ratio": float(spec["match_ratio"]),
        "available": bool(info.get("available")),
        "cleared": bool(info.get("cleared")),
        "duration_hint_ja": {
            "weekly": "目安 25〜40分。途中保存はありません。各問を具体的に。",
            "monthly": "目安 50〜80分。学期末試験と同じ集中で。",
            "career_final": "目安 90〜120分。資格試験と同じ覚悟で。",
        }.get(info.get("boss_type") or "", "各問を具体的に書いて提出しよう。"),
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

    min_chars = int(exam.get("min_answer_chars") or _MIN_BOSS_ANSWER_CHARS)
    pass_ratio = float(exam.get("pass_ratio") or 0.6)
    match_ratio = float(exam.get("match_ratio") or 0.4)
    scores: List[float] = []
    details: List[Dict[str, Any]] = []
    clean_answers: Dict[str, str] = {}
    all_ok = True
    matched_n = 0
    for q in questions:
        qid = q["id"]
        ans = (answers.get(qid) or "").strip()[:4000]
        clean_answers[qid] = ans
        check = soft_check_answer(
            ans,
            q.get("check_keywords") or [],
            min_chars=min_chars,
            require_keyword=True,
            reject_prompts=[q.get("prompt_ja") or ""],
        )
        if not check["can_submit"]:
            all_ok = False
        if check.get("matched"):
            matched_n += 1
        scores.append(float(check["score"] if check["can_submit"] else 0.0))
        details.append({"id": qid, "soft_check": check})

    avg = sum(scores) / max(1, len(scores))
    need_match = max(1, int(len(questions) * match_ratio + 0.999))
    passed = all_ok and avg >= pass_ratio and matched_n >= need_match

    j = ensure_journey(state)
    _boss_attempts(j)[boss_id] = {
        "answers": clean_answers,
        "score": round(avg, 2),
        "passed": passed,
        "boss_type": exam.get("boss_type"),
        "updated_at": _utcnow(),
    }

    if not passed:
        return {
            "ok": False,
            "success": False,
            "passed": False,
            "score": round(avg, 2),
            "details": details,
            "need_match": need_match,
            "matched_questions": matched_n,
            "message_ja": (
                "不合格。各問を"
                + str(min_chars)
                + "文字以上、単元の用語を入れて書き直そう（進捗は消えません）。合格ライン "
                + str(int(pass_ratio * 100))
                + "%。"
            ),
            "exam": exam,
            "status": None,
        }

    from career_portfolio import record_study_evidence

    joined = "\n".join(clean_answers.values())
    record_study_evidence(
        state,
        kind="exam",
        item_id=boss_id,
        title_ja=exam.get("title_ja") or boss_id,
        answer=joined,
        score=avg,
        extra={"boss_type": exam.get("boss_type")},
    )

    result = challenge_boss(state, boss_id, success=True)
    result["passed"] = True
    result["score"] = round(avg, 2)
    result["details"] = details
    result["message_ja"] = (exam.get("exam_label_ja") or "確認テスト") + "合格！記録がポートフォリオに残ったよ。"
    return result
