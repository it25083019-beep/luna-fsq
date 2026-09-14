# -*- coding: utf-8 -*-
from companion_presence import exam_fail_advice, feel_user_text, hud_line
from crisis_switch_service import build_crisis_protocol
from journey_engine import complete_lesson, list_bosses, list_journey_map, select_journey
from study_workspace import build_boss_exam, submit_boss_exam


def test_feel_and_hud():
    sad = feel_user_text("今日はつらい、疲れた")
    assert sad["emotion"] == "sad"
    joy = feel_user_text("やった、合格できた！")
    assert joy["emotion"] == "cheer"
    user = {"companion_id": "luno", "user_display_name": "試験"}
    proto = build_crisis_protocol(user)
    assert proto["companion_id"] == "luno"
    assert proto["sprites"]["sad"]
    assert len(proto["steps"]) == 3
    assert "ルノ" in proto["lead_ja"] or "ルノ" in proto["steps"][0]["line_ja"]
    line = hud_line(user, "suspect")
    assert line["emotion"] == "think"
    print("OK presence")


def test_exam_fail_returns_coach():
    state = {
        "total_exp": 0,
        "current_level": 1,
        "daily_exp": 0,
        "rpg": {},
        "career_path": {},
        "user_display_name": "テスト学習者",
        "companion_id": "ren",
    }
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
    assert bosses
    exam = build_boss_exam(state, bosses[0]["id"])
    fail = submit_boss_exam(state, bosses[0]["id"], {q["id"]: "短" for q in exam["questions"]})
    assert fail.get("success") is False
    assert fail.get("coach")
    assert fail["coach"].get("line_ja")
    assert "進捗" in fail["coach"]["line_ja"] or "残" in fail["coach"]["line_ja"]
    advice = exam_fail_advice(state, ["変数"], 0.2)
    assert "変数" in advice["line_ja"]
    print("OK exam coach")


if __name__ == "__main__":
    test_feel_and_hud()
    test_exam_fail_returns_coach()
    print("ALL companion presence tests passed")
