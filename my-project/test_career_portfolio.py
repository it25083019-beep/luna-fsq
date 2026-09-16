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
    assert "input" in (pf["evidence"][0]["snippet"] or "")
    assert any("学習" in b or "スキル" in b or "input" in b or "土台" in b for b in pf["self_pr"])
    print("OK portfolio")


def test_code_evidence_becomes_blurb():
    from career_portfolio import evidence_blurb

    raw = "n = int(input()) text = '\\n'.join(input() for _ in range(n)) # TODO import sys def count_href()"
    out = evidence_blurb("小さな静的ページを完成させる", raw)
    assert "def " not in out
    assert "小さな静的ページ" in out
    prose = evidence_blurb("自己紹介", "家族の店を楽にするためにアプリを作りました。")
    assert "アプリ" in prose
    print("OK evidence blurb")


if __name__ == "__main__":
    test_empty_then_evidence()
    test_code_evidence_becomes_blurb()
    print("ALL career_portfolio tests passed")
