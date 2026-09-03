# -*- coding: utf-8 -*-
"""Paiza-like study workspace + boss exam."""
from __future__ import annotations

from career_portfolio import build_career_portfolio
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
        "user_display_name": "テスト学習者",
    }


def _answer_with_keywords(keywords, extra=""):
    kws = [k for k in (keywords or []) if k][:4]
    body = (
        "この課題では学習の手順を自分の言葉で整理した。"
        "まず分かっていることとやることに分け、小さく試して1行ログを残す。"
        "カレンダーに枠を置き、開始トリガーを決めて再開できる仕組みにした。"
    )
    return body + " " + " ".join(kws) + " " + extra


def test_soft_check_min_length():
    r = soft_check_answer("短い", ["学習"], min_chars=24)
    assert r["can_submit"] is False
    r2 = soft_check_answer(
        "学習枠をカレンダーに入れて開始トリガーを決めた記録です。再開できる仕組みも書いた。",
        ["学習", "カレンダー"],
        min_chars=24,
    )
    assert r2["can_submit"] is True
    assert "学習" in r2["matched"] or "カレンダー" in r2["matched"]
    filler = soft_check_answer("あ" * 60, ["学習"], min_chars=24)
    assert filler["can_submit"] is False
    nokw = soft_check_answer(
        "今日はなんとなく頑張ったことを長く書いたけれど単元の言葉は入れていません。",
        ["学習", "カレンダー"],
        min_chars=24,
    )
    assert nokw["can_submit"] is False
    print("OK soft_check")


def test_attempt_hint_submit():
    state = fresh()
    select_journey(state, class_id="swordsman", career_id="software_engineer")
    att = get_attempt(state, "se_l1")
    assert att["study"]["problem_ja"]
    assert att["study"]["method_guides"]
    assert att["study"]["workspace_type"] in ("text", "code")

    ans = _answer_with_keywords(att["study"].get("check_keywords") or ["input", "print"])
    save_attempt(state, "se_l1", ans)
    h1 = reveal_hint(state, "se_l1")
    assert h1["guide"] and h1["hints_used"] == 1
    h2 = reveal_hint(state, "se_l1")
    assert h2["hints_used"] == 2

    res = submit_lesson(state, "se_l1")
    assert res["ok"] is True
    assert "se_l1" in state["rpg"]["journey"]["completed_lessons"]
    assert state["rpg"]["journey"]["lesson_attempts"]["se_l1"]["answer"]
    assert res["skills_gained"] or state["rpg"]["journey"]["skills"]
    pf = build_career_portfolio(state)
    assert pf["evidence"]
    assert pf["self_pr"]
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


def test_submit_rejects_keywordless_filler():
    state = fresh()
    select_journey(state, class_id="mage", career_id="software_engineer")
    save_attempt(
        state,
        "se_l1",
        "今日はとても頑張ったという感想を長めに書いたけれど、課題の用語は使っていない文章です。",
    )
    try:
        submit_lesson(state, "se_l1")
        assert False, "should raise"
    except ValueError:
        pass
    assert "se_l1" not in state["rpg"]["journey"]["completed_lessons"]
    print("OK keywordless reject")


def test_boss_exam_pass_and_fail_preserves_progress():
    state = fresh()
    select_journey(state, class_id="swordsman", career_id="software_engineer")
    for _ in range(20):
        mmap = list_journey_map(state)
        avail = [l for l in mmap["lessons"] if l.get("available") and (l.get("boss_type") or "none") == "none"]
        bosses = [b for b in list_bosses(state) if b.get("available")]
        if bosses:
            break
        if not avail:
            break
        complete_lesson(state, avail[0]["id"])
        state["daily_exp"] = 0

    bosses = [b for b in list_bosses(state) if b.get("available")]
    assert bosses, "expected an unlocked weekly/monthly boss"
    boss_id = bosses[0]["id"]
    before = list(state["rpg"]["journey"]["completed_lessons"])

    exam = build_boss_exam(state, boss_id)
    assert exam["questions"]
    assert len(exam["questions"]) >= 4
    assert exam["exam_label_ja"]
    assert exam["min_answer_chars"] >= 40
    assert exam["pass_ratio"] >= 0.55

    fail = submit_boss_exam(
        state,
        boss_id,
        {q["id"]: "短" for q in exam["questions"]},
    )
    assert fail.get("success") is False
    assert state["rpg"]["journey"]["completed_lessons"] == before
    assert boss_id not in (state["rpg"]["journey"].get("boss_clears") or [])

    answers = {q["id"]: _answer_with_keywords(q.get("check_keywords") or []) for q in exam["questions"]}
    ok = submit_boss_exam(state, boss_id, answers)
    assert ok.get("success") is True, ok
    assert boss_id in state["rpg"]["journey"]["boss_clears"]
    pf = build_career_portfolio(state)
    assert any(x.get("kind") == "exam" for x in pf["evidence"])
    print("OK boss exam", exam["exam_label_ja"], ok.get("score"), "q=", len(exam["questions"]))


if __name__ == "__main__":
    test_soft_check_min_length()
    test_attempt_hint_submit()
    test_submit_rejects_short_answer()
    test_submit_rejects_keywordless_filler()
    test_boss_exam_pass_and_fail_preserves_progress()
    print("ALL study_workspace tests passed")
