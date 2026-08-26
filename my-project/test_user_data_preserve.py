"""User data must never be wiped by stale / partial saves."""
from __future__ import annotations

from brain_merge import merge_life_modules, safe_merge_for_save


def _empty_brain(uid: str) -> dict:
    return {
        "user_id": uid,
        "current_level": 1,
        "total_exp": 0,
        "user_display_name": None,
        "chat_history": [],
        "trained_knowledge": [],
        "schedule_reminders": [],
        "life_profile": {},
        "life_modules": {
            "health": {"notes": [], "structured": {}, "updated_at": None},
            "money": {"notes": [], "structured": {}, "updated_at": None},
            "schedule": {"notes": [], "structured": {}, "updated_at": None},
        },
        "career_path": {},
        "rpg": {"class_id": None, "active_quests": []},
    }


def test_stale_save_cannot_wipe_health_and_schedule():
    existing = _empty_brain("u1")
    existing["life_modules"]["health"]["structured"] = {
        "age": 17,
        "weight_kg": 55,
        "sleep_hours": 7,
    }
    existing["life_modules"]["schedule"]["structured"] = {
        "events": [{"id": "e1", "title": "数学", "date": "2026-08-26"}]
    }
    existing["chat_history"] = [{"role": "user", "content": "hello"}]
    existing["rpg"] = {
        "class_id": "swordsman",
        "journey": {
            "career_id": "software_engineer",
            "completed_lessons": ["se_l1", "se_l2"],
            "inventory": [{"id": "acc_notebook", "slot": "accessory"}],
            "journey_exp": 30,
        },
    }
    existing["total_exp"] = 40
    existing["user_display_name"] = "太郎"

    incoming = _empty_brain("u1")
    incoming["rpg"] = {"class_id": "swordsman", "active_quests": []}
    incoming["total_exp"] = 10
    incoming["user_display_name"] = None

    merged = safe_merge_for_save(existing, incoming)
    health = merged["life_modules"]["health"]["structured"]
    assert health.get("age") == 17
    assert health.get("weight_kg") == 55
    events = merged["life_modules"]["schedule"]["structured"]["events"]
    assert len(events) == 1 and events[0]["title"] == "数学"
    assert merged["chat_history"]
    assert merged["rpg"]["journey"]["completed_lessons"] == ["se_l1", "se_l2"]
    assert merged["total_exp"] == 40
    assert merged["user_display_name"] == "太郎"
    print("OK stale save protect")


def test_merge_life_keeps_health_when_incoming_empty():
    base = {
        "health": {"structured": {"age": 16}, "notes": ["a"], "updated_at": "t"},
        "money": {"structured": {}, "notes": [], "updated_at": None},
    }
    out = merge_life_modules(base, {"health": {"structured": {}, "notes": []}})
    assert out["health"]["structured"]["age"] == 16
    assert out["health"]["notes"] == ["a"]
    print("OK life merge")


if __name__ == "__main__":
    test_stale_save_cannot_wipe_health_and_schedule()
    test_merge_life_keeps_health_when_incoming_empty()
    print("ALL PASS")
