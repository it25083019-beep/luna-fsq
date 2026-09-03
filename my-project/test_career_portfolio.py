# -*- coding: utf-8 -*-
from career_portfolio import build_career_portfolio, record_study_evidence
from journey_engine import select_journey


def test_empty_then_evidence():
    state = {
        "total_exp": 0,
        "current_level": 1,
        "daily_exp": 0,
        "rpg": {},
        "user_display_name": "アオイ",
    }
    empty = build_career_portfolio(state)
    assert empty["ok"] is True
    assert empty["evidence"] == []
    assert empty["job_ready"] is False

    select_journey(state, class_id="swordsman", career_id="software_engineer")
    record_study_evidence(
        state,
        kind="lesson",
        item_id="se_l1",
        title_ja="学習の土台",
        answer="input と print で日付の学習ログを1行にまとめた。",
        score=0.82,
    )
    pf = build_career_portfolio(state)
    assert pf["career_title_ja"]
    assert pf["evidence"][0]["id"] == "se_l1"
    assert any("学習" in b or "スキル" in b or "input" in b or "土台" in b for b in pf["self_pr"])
    print("OK portfolio")


if __name__ == "__main__":
    test_empty_then_evidence()
    print("ALL career_portfolio tests passed")
