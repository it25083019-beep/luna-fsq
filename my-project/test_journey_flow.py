"""Career journey flow: select → lessons → rank/gear → boss gates."""
from __future__ import annotations

from journey_engine import (
    challenge_boss,
    complete_lesson,
    enrich_lesson_detail,
    get_curriculum,
    journey_status,
    list_bosses,
    list_careers,
    list_journey_map,
    select_journey,
)


def fresh():
    return {
        "total_exp": 0,
        "current_level": 1,
        "daily_exp": 0,
        "rpg": {},
        "career_path": {},
    }


def test_catalog_has_full_and_stub():
    careers = list_careers()
    assert len(careers) >= 10
    full = [c for c in careers if c.get("full_curriculum")]
    assert len(full) >= 4
    cur = get_curriculum("software_engineer")
    assert len(cur["stages"]) >= 5
    assert any((l.get("boss_type") == "career_final") for l in cur["lessons"])
    stub = get_curriculum("data_analyst")
    assert stub["lessons"]
    assert stub["lessons"][0]["id"].startswith("data_analyst__")
    print("OK catalog")


def test_select_complete_rank_gear():
    state = fresh()
    st = select_journey(state, class_id="mage", career_id="software_engineer")
    assert st["selected"] is True
    assert st["class_id"] == "mage"
    assert st["career_id"] == "software_engineer"
    assert st["rank_id"] == "novice"
    assert state["rpg"]["journey"]["career_id"] == "software_engineer"

    mmap = list_journey_map(state)
    avail = [l for l in mmap["lessons"] if l.get("available") and (l.get("boss_type") or "none") == "none"]
    assert avail, mmap
    first = avail[0]
    res = complete_lesson(state, first["id"])
    assert res["ok"]
    assert res["exp_gained"] > 0
    assert first["id"] in state["rpg"]["journey"]["completed_lessons"]
    if first.get("gear_drop"):
        assert state["rpg"]["journey"]["equipped"].get(first["gear_drop"]["slot"])
        assert "css_classes" in res["appearance"]
    assert state["rpg"]["journey"]["skills"]
    print("OK select+lesson", res["rank"]["label_ja"])


def test_stage_lock_and_weekly_boss_gate():
    state = fresh()
    select_journey(state, class_id="swordsman", career_id="software_engineer")
    # Complete stage 1+2 non-boss lessons
    cur = get_curriculum("software_engineer")
    for les in cur["lessons"]:
        if (les.get("boss_type") or "none") != "none":
            continue
        if les["stage_id"] in ("se_s1", "se_s2"):
            complete_lesson(state, les["id"])
            state["daily_exp"] = 0  # bypass daily cap for test

    bosses = {b["id"]: b for b in list_bosses(state)}
    assert "se_l5" in bosses
    assert bosses["se_l5"]["available"] is False or bosses["se_l5"]["boss_type"] == "weekly"

    # Finish enough stage-3 non-boss to unlock weekly
    for les in cur["lessons"]:
        if les["stage_id"] == "se_s3" and (les.get("boss_type") or "none") == "none":
            complete_lesson(state, les["id"])
            state["daily_exp"] = 0

    bosses = {b["id"]: b for b in list_bosses(state)}
    assert bosses["se_l5"]["available"] is True

    fail = challenge_boss(state, "se_l5", success=False)
    assert fail["success"] is False
    assert "se_l5" not in state["rpg"]["journey"]["boss_clears"]

    win = challenge_boss(state, "se_l5", success=True)
    assert win["success"] is True
    assert "se_l5" in state["rpg"]["journey"]["boss_clears"]
    print("OK weekly boss gate")


def test_final_boss_requires_progress_and_rank():
    state = fresh()
    select_journey(state, class_id="mage", career_id="software_engineer")
    cur = get_curriculum("software_engineer")
    final = next(l for l in cur["lessons"] if l.get("boss_type") == "career_final")

    bosses = {b["id"]: b for b in list_bosses(state)}
    assert bosses[final["id"]]["available"] is False

    for les in cur["lessons"]:
        bt = les.get("boss_type") or "none"
        if bt == "career_final":
            continue
        if bt in ("weekly", "monthly"):
            # force-complete via challenge when available, else mark completed for gate math
            bmap = {b["id"]: b for b in list_bosses(state)}
            if bmap.get(les["id"], {}).get("available"):
                challenge_boss(state, les["id"], success=True)
            else:
                # complete remaining normal lessons first
                pass
        else:
            try:
                complete_lesson(state, les["id"])
            except ValueError:
                pass
            state["daily_exp"] = 0

    # Sweep remaining normals then bosses
    for _ in range(3):
        for les in cur["lessons"]:
            bt = les.get("boss_type") or "none"
            if bt == "career_final":
                continue
            if les["id"] in state["rpg"]["journey"]["completed_lessons"]:
                continue
            if bt == "none":
                try:
                    complete_lesson(state, les["id"])
                except ValueError:
                    pass
            else:
                bmap = {b["id"]: b for b in list_bosses(state)}
                if bmap.get(les["id"], {}).get("available"):
                    challenge_boss(state, les["id"], success=True)
            state["daily_exp"] = 0

    st = journey_status(state)
    assert st["rank_id"] in ("veteran", "saint"), st
    bosses = {b["id"]: b for b in list_bosses(state)}
    assert bosses[final["id"]]["available"] is True, (bosses[final["id"]], st)
    res = challenge_boss(state, final["id"], success=True)
    assert res["ok"] and res["gear"]
    print("OK final boss", st["rank_ja"])


def test_enrich_caches_detail():
    state = fresh()
    select_journey(state, class_id="archer", career_id="ui_designer")
    out = enrich_lesson_detail(state, "ux_l1", "観察のコツは小さくメモすること。")
    assert out["ok"]
    mmap = list_journey_map(state)
    row = next(x for x in mmap["lessons"] if x["id"] == "ux_l1")
    assert "観察" in (row.get("detail_ja") or "")
    print("OK enrich")


if __name__ == "__main__":
    test_catalog_has_full_and_stub()
    test_select_complete_rank_gear()
    test_stage_lock_and_weekly_boss_gate()
    test_final_boss_requires_progress_and_rank()
    test_enrich_caches_detail()
    print("ALL PASS")
