# -*- coding: utf-8 -*-
"""Paiza-like study workspace + boss exam."""
from __future__ import annotations

from journey_engine import complete_lesson, list_bosses, list_journey_map, select_journey
from study_workspace import (
    build_boss_exam,
    get_attempt,
    reveal_hint,
    save_attempt,
    soft_check_answer,
    submit_boss_exam,
    submit_lesson,
)


def fresh():
    return {
        "total_exp": 0,
        "current_level": 1,
        "daily_exp": 0,
        "rpg": {},
        "career_path": {},
    }


def test_soft_check_min_length():
    r = soft_check_answer("短い", ["学習"], min_chars=24)
    assert r["can_submit"] is False
    r2 = soft_check_answer("学習枠をカレンダーに入れて開始トリガーを決めた記録です", ["学習", "カレンダー"], min_chars=24)
    assert r2["can_submit"] is True
    assert "学習" in r2["matched"] or "カレンダー" in r2["matched"]
    print("OK soft_check")


def test_attempt_hint_submit():
    state = fresh()
    select_journey(state, class_id="swordsman", career_id="software_engineer")
    att = get_attempt(state, "se_l1")
    assert att["study"]["problem_ja"]
    assert att["study"]["method_guides"]
    assert att["study"]["workspace_type"] in ("text", "code")

    save_attempt(
        state,
        "se_l1",
        "学習枠をカレンダーに入れ、開始トリガーを決めて1行ログを残した。",
    )
    h1 = reveal_hint(state, "se_l1")
    assert h1["guide"] and h1["hints_used"] == 1
    h2 = reveal_hint(state, "se_l1")
    assert h2["hints_used"] == 2

    res = submit_lesson(state, "se_l1")
    assert res["ok"] is True
    assert "se_l1" in state["rpg"]["journey"]["completed_lessons"]
    assert state["rpg"]["journey"]["lesson_attempts"]["se_l1"]["answer"]
    assert res["skills_gained"] or state["rpg"]["journey"]["skills"]
    print("OK attempt+hint+submit")


def test_submit_rejects_short_answer():
    state = fresh()
    select_journey(state, class_id="mage", career_id="software_engineer")
    save_attempt(state, "se_l1", "短い")
    try:
        submit_lesson(state, "se_l1")
        assert False, "should raise"
    except ValueError:
        pass
    assert "se_l1" not in state["rpg"]["journey"]["completed_lessons"]
    print("OK short reject")


def test_boss_exam_pass_and_fail_preserves_progress():
    state = fresh()
    select_journey(state, class_id="swordsman", career_id="software_engineer")
    for _ in range(12):
        mmap = list_journey_map(state)
        avail = [l for l in mmap["lessons"] if l.get("available") and (l.get("boss_type") or "none") == "none"]
        bosses = [b for b in list_bosses(state) if b.get("available")]
        if bosses:
            break
        if not avail:
            break
        complete_lesson(state, avail[0]["id"])

    bosses = [b for b in list_bosses(state) if b.get("available")]
    assert bosses, "expected an unlocked weekly/monthly boss"
    boss_id = bosses[0]["id"]
    before = list(state["rpg"]["journey"]["completed_lessons"])

    exam = build_boss_exam(state, boss_id)
    assert exam["questions"]
    assert exam["exam_label_ja"]

    fail = submit_boss_exam(
        state,
        boss_id,
        {q["id"]: "短" for q in exam["questions"]},
    )
    assert fail.get("success") is False
    assert state["rpg"]["journey"]["completed_lessons"] == before
    assert boss_id not in (state["rpg"]["journey"].get("boss_clears") or [])

    answers = {
        q["id"]: "これは学習の要点と実践ログ、開始の仕組みについての解答です。" + (q.get("prompt_ja") or "")[:20]
        for q in exam["questions"]
    }
    ok = submit_boss_exam(state, boss_id, answers)
    assert ok.get("success") is True
    assert boss_id in state["rpg"]["journey"]["boss_clears"]
    print("OK boss exam", exam["exam_label_ja"], ok.get("score"))


if __name__ == "__main__":
    test_soft_check_min_length()
    test_attempt_hint_submit()
    test_submit_rejects_short_answer()
    test_boss_exam_pass_and_fail_preserves_progress()
    print("ALL study_workspace tests passed")
