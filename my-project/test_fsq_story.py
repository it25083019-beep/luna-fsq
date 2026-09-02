"""Tests for FSQ weekly dynamic story."""
from datetime import date

from fsq_story import build_fsq_weekly_story, mini_quest_story, _local_weekly_story


def test_local_story_no_lessons():
    facts = {
        "display_name": "太郎",
        "class_id": "swordsman",
        "class_ja": "剣士",
        "rank_ja": "見習い",
        "lesson_titles": [],
        "lesson_count": 0,
        "week_exp": 0,
        "care_count": 0,
        "next_lesson": "HTML入門",
        "mood": None,
        "boss_clears": 0,
    }
    s = _local_weekly_story(facts)
    assert "HTML入門" in s
    assert "太郎" in s
    print("OK empty week story")


def test_local_story_with_lessons():
    facts = {
        "display_name": "花子",
        "class_id": "mage",
        "class_ja": "魔法使い",
        "rank_ja": "中級",
        "lesson_titles": ["変数", "関数"],
        "lesson_count": 2,
        "week_exp": 25,
        "care_count": 1,
        "next_lesson": "ループ",
        "mood": "元気",
        "boss_clears": 0,
    }
    s = _local_weekly_story(facts)
    assert "変数" in s and "関数" in s
    print("OK lesson week story")


def test_build_weekly_story_selected():
    state = {
        "user_display_name": "太郎",
        "rpg": {
            "journey": {
                "class_id": "swordsman",
                "career_id": "se",
                "rank_id": "novice",
                "completion_log": [
                    {"at": "2026-09-02T10:00:00+00:00", "title_ja": "HTML基礎", "detail": "+10 EXP"}
                ],
            }
        },
        "life_modules": {"health": {"structured": {"mental_status": "普通"}}},
    }
    status = {
        "class_ja": "剣士",
        "career_title_ja": "Webエンジニア",
        "next_lesson": {"title_ja": "CSS入門"},
    }
    story = build_fsq_weekly_story(state, status=status, today=date(2026, 9, 2))
    assert story and story.get("story_ja")
    assert "HTML基礎" in story["story_ja"] or "太郎" in story["story_ja"]
    assert state.get("fsq_weekly_story")
    print("OK build weekly", story["source"])


def test_mini_quest_story():
    state = {"user_display_name": "太郎", "rpg": {"journey": {"class_id": "archer"}}}
    line = mini_quest_story(state, {"title_ja": "Git入門"}, exp=12)
    assert "Git入門" in line
    print("OK mini quest")


if __name__ == "__main__":
    test_local_story_no_lessons()
    test_local_story_with_lessons()
    test_build_weekly_story_selected()
    test_mini_quest_story()
    print("ALL fsq_story tests OK")
