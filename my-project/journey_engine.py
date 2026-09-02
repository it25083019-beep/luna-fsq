"""Career journey: class + career path, lessons, gear look, evolution, bosses."""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from exp_engine import DAILY_CAP
from rpg_engine import ensure_rpg

_ROOT = Path(__file__).resolve().parent / "config"
_CATALOG: Optional[Dict[str, Any]] = None
_CURRICULA: Optional[Dict[str, Any]] = None
_APPEARANCE: Optional[Dict[str, Any]] = None
_MATERIALS: Optional[Dict[str, Any]] = None

CLASS_IDS = ("swordsman", "mage", "archer")


def _load_json(name: str) -> Dict[str, Any]:
    with open(_ROOT / name, "r", encoding="utf-8") as f:
        return json.load(f)


def load_catalog() -> Dict[str, Any]:
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = _load_json("career_catalog.json")
    return _CATALOG


def load_curricula() -> Dict[str, Any]:
    global _CURRICULA
    if _CURRICULA is None:
        _CURRICULA = _load_json("career_curricula.json")
    return _CURRICULA


def load_appearance() -> Dict[str, Any]:
    global _APPEARANCE
    if _APPEARANCE is None:
        _APPEARANCE = _load_json("rpg_appearance.json")
    return _APPEARANCE


def load_materials() -> Dict[str, Any]:
    global _MATERIALS
    if _MATERIALS is None:
        path = _ROOT / "lesson_materials.json"
        if path.exists():
            _MATERIALS = _load_json("lesson_materials.json")
        else:
            _MATERIALS = {"materials": {}}
    return _MATERIALS


def get_lesson_material(lesson_id: str) -> Dict[str, Any]:
    mats = load_materials().get("materials") or {}
    row = mats.get(lesson_id)
    if row:
        return dict(row)
    # stub lessons: career__stub_l1
    if "__" in lesson_id:
        base = lesson_id.split("__", 1)[-1]
        row = mats.get(base)
        if row:
            return dict(row)
    return {
        "summary_ja": "このレッスンの学習メモを読んで、小さな実践をしてから記録しよう。",
        "theory_ja": [
            "まずテーマの基本用語を調べ、自分の言葉で定義する。",
            "次に、今日の範囲で『何ができればよいか』を1文で書く。",
        ],
        "goals_ja": ["要点を3つメモする", "今日できる実践を1つ行う"],
        "steps": [
            {"title_ja": "理論", "body_ja": "タイトルの内容を調べ、わからない言葉を1つ調べる。"},
            {"title_ja": "実践", "body_ja": "ノートに今日の学びを3行書く。"},
        ],
        "practice_steps": [
            {"title_ja": "理論", "body_ja": "タイトルの内容を調べ、わからない言葉を1つ調べる。"},
            {"title_ja": "実践", "body_ja": "ノートに今日の学びを3行書く。"},
        ],
        "practice_ja": "3行メモを書いたら学習記録できるよ。",
        "checklist_ja": ["用語を調べた", "3行メモを書いた"],
        "estimated_minutes": 30,
        "resources": [],
    }


def _attach_material(lesson: Dict[str, Any], *, career_id: Optional[str] = None) -> Dict[str, Any]:
    out = dict(lesson)
    mat = get_lesson_material(lesson["id"])
    out["summary_ja"] = mat.get("summary_ja")
    out["theory_ja"] = mat.get("theory_ja") or []
    out["goals_ja"] = mat.get("goals_ja") or []
    out["steps"] = mat.get("steps") or []
    out["practice_steps"] = mat.get("practice_steps") or out["steps"]
    out["practice_ja"] = mat.get("practice_ja")
    out["checklist_ja"] = mat.get("checklist_ja") or []
    out["estimated_minutes"] = mat.get("estimated_minutes") or 30
    out["resources"] = mat.get("resources") or []
    # Paiza-like fields (additive; derived in study_workspace)
    try:
        from study_workspace import attach_study_fields

        out = attach_study_fields(out, career_id=career_id)
    except Exception:
        pass
    return out


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _apply_exp(state: Dict[str, Any], gain: int) -> int:
    import math

    remain = max(0, DAILY_CAP - int(state.get("daily_exp", 0)))
    gain = min(max(0, int(gain)), remain)
    state["daily_exp"] = int(state.get("daily_exp", 0)) + gain
    state["total_exp"] = int(state.get("total_exp", 0)) + gain
    state["current_level"] = int(math.floor(1 + math.sqrt(state["total_exp"] / 100)))
    return gain


def get_curriculum(career_id: str) -> Dict[str, Any]:
    data = load_curricula()
    full = (data.get("curricula") or {}).get(career_id)
    if full:
        return dict(full)
    stub = dict(data.get("stub_template") or {})
    stub["career_id"] = career_id
    skills = []
    for sk in stub.get("skills") or []:
        skills.append({"id": f"{career_id}__{sk['id']}", "label_ja": sk["label_ja"]})
    stub["skills"] = skills
    lessons = []
    for les in stub.get("lessons") or []:
        row = dict(les)
        row["id"] = f"{career_id}__{les['id']}"
        row["skill_ids"] = [f"{career_id}__{sid}" for sid in (les.get("skill_ids") or [])]
        if row.get("gear_drop") and row["gear_drop"].get("item_id"):
            g = dict(row["gear_drop"])
            g["item_id"] = f"{career_id}__{g['item_id']}"
            row["gear_drop"] = g
        lessons.append(row)
    stub["lessons"] = lessons
    return stub


def _is_boss(les: Dict[str, Any]) -> bool:
    return (les.get("boss_type") or "none") != "none"


def _stage_learning_lessons(cur: Dict[str, Any], stage_id: str) -> List[Dict[str, Any]]:
    return [
        x
        for x in (cur.get("lessons") or [])
        if x.get("stage_id") == stage_id and not _is_boss(x)
    ]


def _compute_stages(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    j = ensure_journey(state)
    cur = get_curriculum(j["career_id"])
    completed = set(j.get("completed_lessons") or [])
    stages_out = []
    for st in sorted(cur.get("stages") or [], key=lambda s: s.get("order", 0)):
        stage_lessons = [x for x in (cur.get("lessons") or []) if x.get("stage_id") == st["id"]]
        learning = _stage_learning_lessons(cur, st["id"])
        done_learning = sum(1 for x in learning if x["id"] in completed)
        done_all = sum(1 for x in stage_lessons if x["id"] in completed)
        unlocked = st.get("order", 0) == 1
        if st.get("order", 0) > 1:
            prev = [s for s in cur["stages"] if s.get("order") == st["order"] - 1]
            if prev:
                prev_learning = _stage_learning_lessons(cur, prev[0]["id"])
                # Learning path unlocks when previous stage's study lessons are done
                # (weekly/monthly bosses are side challenges, not hard blockers).
                unlocked = (not prev_learning) or all(x["id"] in completed for x in prev_learning)
        stages_out.append(
            {
                **st,
                "unlocked": unlocked,
                "current": st["id"] == j.get("stage_id"),
                "cleared": bool(learning) and all(x["id"] in completed for x in learning),
                "progress": f"{done_learning}/{len(learning)}" if learning else f"{done_all}/{len(stage_lessons)}",
                "stars": min(3, done_learning if learning else done_all),
            }
        )
    return stages_out


def list_careers() -> List[Dict[str, Any]]:
    cat = load_catalog()
    out = []
    for c in cat.get("careers") or []:
        row = dict(c)
        row["has_full_curriculum"] = bool(c.get("full_curriculum"))
        out.append(row)
    return out


def list_classes() -> List[Dict[str, Any]]:
    return list(load_catalog().get("classes") or [])


def list_ranks() -> List[Dict[str, Any]]:
    return list(load_catalog().get("ranks") or [])


def ensure_journey(state: Dict[str, Any]) -> Dict[str, Any]:
    rpg = ensure_rpg(state)
    j = rpg.setdefault("journey", {})
    j.setdefault("class_id", None)
    j.setdefault("career_id", None)
    j.setdefault("rank_id", "novice")
    j.setdefault("stage_id", None)
    j.setdefault("completed_lessons", [])
    j.setdefault("skills", [])
    j.setdefault("inventory", [])
    j.setdefault("equipped", {"weapon": None, "armor": None, "accessory": None, "artifact": None})
    j.setdefault("boss_clears", [])
    j.setdefault("journey_exp", 0)
    j.setdefault("lesson_enrich", {})
    j.setdefault("lesson_attempts", {})
    j.setdefault("boss_attempts", {})
    j.setdefault("selected_at", None)
    return j


def _career_meta(career_id: str) -> Optional[Dict[str, Any]]:
    for c in load_catalog().get("careers") or []:
        if c.get("id") == career_id:
            return c
    return None


def _compute_rank(completed_count: int, journey_exp: int) -> Dict[str, Any]:
    ranks = list_ranks()
    current = ranks[0]
    for r in ranks:
        if completed_count >= int(r.get("min_lessons", 0)) and journey_exp >= int(r.get("min_exp", 0)):
            current = r
    return current


def _build_appearance(class_id: str, equipped: Dict[str, Any], rank_id: str, inventory: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    app = load_appearance()
    base = (app.get("class_base") or {}).get(class_id) or {
        "sprite": "/static/live2d/luna-expressions/luna-neutral.png",
        "css_class": "class-swordsman",
        "label_ja": class_id,
    }
    mods = app.get("gear_modifiers") or {}
    layers = [base.get("css_class") or "class-swordsman"]
    aura = (app.get("rank_aura") or {}).get(rank_id) or "rank-novice"
    layers.append(aura)
    tints = []
    inv_by_id = {str(i.get("id")): i for i in (inventory or [])}
    equipped_details = []
    for slot, item_id in (equipped or {}).items():
        if not item_id:
            continue
        lookup = item_id.split("__")[-1] if "__" in str(item_id) else str(item_id)
        mod = mods.get(str(item_id)) or mods.get(lookup)
        if mod:
            if mod.get("css"):
                layers.append(mod["css"])
            if mod.get("tint"):
                tints.append(mod["tint"])
        meta = inv_by_id.get(str(item_id)) or {}
        equipped_details.append(
            {
                "slot": slot,
                "item_id": item_id,
                "label_ja": meta.get("label_ja") or lookup,
            }
        )
    evo_cfg = app.get("character_evolution") or {}
    evo_sprites = (evo_cfg.get("sprites") or {}).get(class_id) or {}
    evolution_sprite = evo_sprites.get(rank_id) or evo_sprites.get("novice")
    rank_labels = evo_cfg.get("rank_labels") or {}
    rank_desc = evo_cfg.get("rank_desc") or {}
    display_sprite = evolution_sprite or base.get("sprite")
    return {
        "sprite": display_sprite,
        "evolution_sprite": evolution_sprite,
        "fallback_sprite": base.get("sprite"),
        "css_classes": " ".join(layers),
        "class_label_ja": base.get("label_ja"),
        "class_emblem_ja": base.get("emblem_ja") or (base.get("label_ja") or "")[:1],
        "class_motif_ja": base.get("motif_ja") or "",
        "class_id": class_id,
        "rank_id": rank_id,
        "rank_label_ja": rank_labels.get(rank_id),
        "rank_desc_ja": rank_desc.get(rank_id),
        "tints": tints,
        "equipped_details": equipped_details,
    }


def select_journey(state: Dict[str, Any], *, class_id: str, career_id: str) -> Dict[str, Any]:
    if class_id not in CLASS_IDS:
        raise ValueError("invalid class_id")
    meta = _career_meta(career_id)
    if not meta:
        raise ValueError("unknown career_id")
    cur = get_curriculum(career_id)
    stages = sorted(cur.get("stages") or [], key=lambda s: s.get("order", 0))
    if not stages:
        raise ValueError("curriculum has no stages")

    rpg = ensure_rpg(state)
    j = ensure_journey(state)
    j["class_id"] = class_id
    j["career_id"] = career_id
    j["rank_id"] = "novice"
    j["stage_id"] = stages[0]["id"]
    j["completed_lessons"] = []
    j["skills"] = []
    j["inventory"] = []
    j["equipped"] = {"weapon": None, "armor": None, "accessory": None, "artifact": None}
    j["boss_clears"] = []
    j["journey_exp"] = 0
    j["lesson_enrich"] = {}
    j["selected_at"] = _utcnow()
    rpg["class_id"] = class_id
    state.setdefault("career_path", {})
    state["career_path"]["cluster_id"] = meta.get("cluster_id")
    state["career_path"]["career_id"] = career_id
    state["career_path"]["title_ja"] = meta.get("title_ja")
    state["career_path"]["rpg_class"] = class_id
    return journey_status(state)


def journey_status(state: Dict[str, Any]) -> Dict[str, Any]:
    j = ensure_journey(state)
    cat_classes = {c["id"]: c for c in list_classes()}
    ranks = {r["id"]: r for r in list_ranks()}
    career = _career_meta(j.get("career_id") or "") if j.get("career_id") else None
    cur = get_curriculum(j["career_id"]) if j.get("career_id") else None
    completed = set(j.get("completed_lessons") or [])
    mmap = list_journey_map(state) if j.get("career_id") else {"lessons": [], "bosses": []}
    next_lesson = None
    for les in mmap.get("lessons") or []:
        if les.get("available") and not _is_boss(les):
            next_lesson = les
            break
    next_boss = None
    for b in mmap.get("bosses") or []:
        if b.get("available") and not b.get("cleared"):
            next_boss = b
            break
    appearance = _build_appearance(
        j.get("class_id") or "swordsman",
        j.get("equipped") or {},
        j.get("rank_id") or "novice",
        j.get("inventory") or [],
    )
    from life_link import life_quests_for_fsq

    life_quests = life_quests_for_fsq(state) if j.get("career_id") else []
    return {
        "selected": bool(j.get("class_id") and j.get("career_id")),
        "class_id": j.get("class_id"),
        "class_ja": (cat_classes.get(j.get("class_id") or "") or {}).get("label_ja"),
        "career_id": j.get("career_id"),
        "career_title_ja": (career or {}).get("title_ja"),
        "rank_id": j.get("rank_id"),
        "rank_ja": (ranks.get(j.get("rank_id") or "novice") or {}).get("label_ja"),
        "stage_id": j.get("stage_id"),
        "journey_exp": int(j.get("journey_exp") or 0),
        "total_exp": int(state.get("total_exp") or 0),
        "level": int(state.get("current_level") or 1),
        "completed_count": len(completed),
        "skills": j.get("skills") or [],
        "inventory": j.get("inventory") or [],
        "equipped": j.get("equipped") or {},
        "appearance": appearance,
        "next_lesson": next_lesson,
        "next_boss": next_boss,
        "boss_clears": j.get("boss_clears") or [],
        "classes": list_classes(),
        "careers": list_careers(),
        "ranks": list_ranks(),
        "life_quests": life_quests,
    }


def list_journey_map(state: Dict[str, Any]) -> Dict[str, Any]:
    j = ensure_journey(state)
    if not j.get("career_id"):
        return {"selected": False, "stages": [], "lessons": [], "bosses": []}
    cur = get_curriculum(j["career_id"])
    completed = set(j.get("completed_lessons") or [])
    stages_out = _compute_stages(state)
    lessons_out = []
    for les in cur.get("lessons") or []:
        stage = next((s for s in stages_out if s["id"] == les.get("stage_id")), None)
        row = _attach_material(les, career_id=j.get("career_id"))
        row["completed"] = les["id"] in completed
        row["available"] = bool(stage and stage.get("unlocked")) and les["id"] not in completed
        row["detail_ja"] = (j.get("lesson_enrich") or {}).get(les["id"])
        lessons_out.append(row)
    bosses = list_bosses(state)
    return {
        "selected": True,
        "career_id": j["career_id"],
        "stages": stages_out,
        "lessons": lessons_out,
        "skills_catalog": cur.get("skills") or [],
        "bosses": bosses,
    }


def get_lesson(state: Dict[str, Any], lesson_id: str) -> Dict[str, Any]:
    j = ensure_journey(state)
    if not j.get("career_id"):
        raise ValueError("journey not selected")
    mmap = list_journey_map(state)
    row = next((x for x in mmap["lessons"] if x["id"] == lesson_id), None)
    if not row:
        # boss entries live in lessons too
        raise ValueError("lesson not found")
    return row


def _equip_gear(j: Dict[str, Any], gear: Dict[str, Any]) -> None:
    slot = gear.get("slot") or "accessory"
    item = {
        "id": gear.get("item_id") or uuid.uuid4().hex[:10],
        "slot": slot,
        "label_ja": gear.get("label_ja") or "アイテム",
        "at": _utcnow(),
    }
    inv = j.setdefault("inventory", [])
    inv.append(item)
    equipped = j.setdefault("equipped", {})
    # Auto-equip newest for slot
    equipped[slot] = item["id"]


def _unlock_skills(j: Dict[str, Any], cur: Dict[str, Any], skill_ids: List[str]) -> List[Dict[str, Any]]:
    catalog = {s["id"]: s for s in (cur.get("skills") or [])}
    have = {s.get("id") for s in (j.get("skills") or [])}
    gained = []
    for sid in skill_ids or []:
        if sid in have:
            continue
        meta = catalog.get(sid) or {"id": sid, "label_ja": sid}
        row = {"id": meta["id"], "label_ja": meta.get("label_ja") or sid, "at": _utcnow()}
        j.setdefault("skills", []).append(row)
        gained.append(row)
        have.add(sid)
    return gained


def _advance_stage(j: Dict[str, Any], cur: Dict[str, Any]) -> None:
    completed = set(j.get("completed_lessons") or [])
    stages = sorted(cur.get("stages") or [], key=lambda s: s.get("order", 0))
    for st in stages:
        lessons = _stage_learning_lessons(cur, st["id"])
        if not lessons:
            lessons = [x for x in (cur.get("lessons") or []) if x.get("stage_id") == st["id"] and not _is_boss(x)]
        if lessons and all(x["id"] in completed for x in lessons):
            continue
        j["stage_id"] = st["id"]
        return
    if stages:
        j["stage_id"] = stages[-1]["id"]


def complete_lesson(state: Dict[str, Any], lesson_id: str) -> Dict[str, Any]:
    j = ensure_journey(state)
    if not j.get("career_id"):
        raise ValueError("journey not selected")
    cur = get_curriculum(j["career_id"])
    les = next((x for x in (cur.get("lessons") or []) if x["id"] == lesson_id), None)
    if not les:
        raise ValueError("lesson not found")
    if lesson_id in (j.get("completed_lessons") or []):
        raise ValueError("lesson already completed")

    mmap = list_journey_map(state)
    row = next((x for x in mmap["lessons"] if x["id"] == lesson_id), None)
    if not row or not row.get("available"):
        stage = next((s for s in mmap["stages"] if s["id"] == les.get("stage_id")), None)
        if not stage or not stage.get("unlocked"):
            raise ValueError("lesson locked")

    boss_type = les.get("boss_type") or "none"
    if boss_type in ("weekly", "monthly", "career_final"):
        raise ValueError("use boss challenge endpoint for boss lessons")

    raw_exp = int(les.get("exp") or 10)
    gained_exp = _apply_exp(state, raw_exp)
    j["journey_exp"] = int(j.get("journey_exp") or 0) + raw_exp
    j.setdefault("completed_lessons", []).append(lesson_id)
    skills = _unlock_skills(j, cur, les.get("skill_ids") or [])
    gear = None
    if les.get("gear_drop"):
        _equip_gear(j, les["gear_drop"])
        gear = les["gear_drop"]
    rank = _compute_rank(len(j["completed_lessons"]), j["journey_exp"])
    j["rank_id"] = rank["id"]
    _advance_stage(j, cur)
    appearance = _build_appearance(j["class_id"], j.get("equipped") or {}, j["rank_id"], j.get("inventory") or [])

    from life_link import on_lesson_complete

    life_link = on_lesson_complete(state, les, exp_gained=gained_exp)

    rpg = ensure_rpg(state)
    if gear:
        rpg.setdefault("equipment", []).append(
            {"id": gear.get("item_id"), "slot": gear.get("slot"), "label_ja": gear.get("label_ja"), "at": _utcnow()}
        )

    return {
        "ok": True,
        "lesson": _attach_material(les, career_id=j.get("career_id")),
        "exp_gained": gained_exp,
        "journey_exp_gained": raw_exp,
        "skills_gained": skills,
        "gear": gear,
        "rank": rank,
        "appearance": appearance,
        "status": journey_status(state),
        "map": list_journey_map(state),
        "luna_message": life_link.get("luna_message"),
        "life_effects": life_link.get("life_effects") or [],
        "quest_story": life_link.get("quest_story"),
    }


def list_bosses(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    j = ensure_journey(state)
    if not j.get("career_id"):
        return []
    cur = get_curriculum(j["career_id"])
    completed = set(j.get("completed_lessons") or [])
    clears = set(j.get("boss_clears") or [])
    rank_id = j.get("rank_id") or "novice"
    rank_order = {r["id"]: i for i, r in enumerate(list_ranks())}
    out = []
    for les in cur.get("lessons") or []:
        bt = les.get("boss_type") or "none"
        if bt == "none":
            continue
        available = False
        reason = ""
        if bt == "weekly":
            # Need at least 2 non-boss lessons completed in same stage or overall >= 2
            stage_lessons = [
                x
                for x in cur["lessons"]
                if x.get("stage_id") == les.get("stage_id") and (x.get("boss_type") or "none") == "none"
            ]
            done = sum(1 for x in stage_lessons if x["id"] in completed)
            available = done >= max(1, len(stage_lessons) // 2) and les["id"] not in completed
            reason = "ステージ学習を半分以上クリア"
        elif bt == "monthly":
            stages = sorted(cur.get("stages") or [], key=lambda s: s.get("order", 0))
            # unlock after stage 3 mostly done
            early = [s for s in stages if s.get("order", 0) <= 3]
            ok = True
            for st in early[:-1]:
                sl = [x for x in cur["lessons"] if x.get("stage_id") == st["id"] and (x.get("boss_type") or "none") == "none"]
                if sl and not all(x["id"] in completed for x in sl):
                    ok = False
            available = ok and les["id"] not in completed
            reason = "前半ステージの学習クリア"
        elif bt == "career_final":
            non_final = [x for x in cur["lessons"] if (x.get("boss_type") or "none") != "career_final"]
            need = max(1, int(len(non_final) * 0.75))
            available = len(completed) >= need and rank_order.get(rank_id, 0) >= rank_order.get("veteran", 2) and les["id"] not in completed
            reason = "学習の大部分クリア＋熟練ランク以上"
        out.append(
            {
                "id": les["id"],
                "title_ja": les.get("title_ja"),
                "boss_type": bt,
                "stage_id": les.get("stage_id"),
                "available": available,
                "cleared": les["id"] in clears or les["id"] in completed,
                "requirement_ja": reason,
                "exp": les.get("exp"),
                "gear_drop": les.get("gear_drop"),
            }
        )
    return out


def challenge_boss(state: Dict[str, Any], boss_id: str, *, success: bool = True) -> Dict[str, Any]:
    j = ensure_journey(state)
    if not j.get("career_id"):
        raise ValueError("journey not selected")
    bosses = {b["id"]: b for b in list_bosses(state)}
    info = bosses.get(boss_id)
    if not info:
        raise ValueError("boss not found")
    if info.get("cleared"):
        raise ValueError("boss already cleared")
    if not info.get("available"):
        raise ValueError("boss locked: " + (info.get("requirement_ja") or ""))

    cur = get_curriculum(j["career_id"])
    les = next((x for x in (cur.get("lessons") or []) if x["id"] == boss_id), None)
    if not les:
        raise ValueError("boss lesson missing")

    if not success:
        return {"ok": False, "success": False, "message_ja": "今回は退却…でも旅は続くよ。準備して再挑戦しよう。", "status": journey_status(state)}

    raw_exp = int(les.get("exp") or 40)
    gained_exp = _apply_exp(state, raw_exp)
    j["journey_exp"] = int(j.get("journey_exp") or 0) + raw_exp
    if boss_id not in (j.get("completed_lessons") or []):
        j.setdefault("completed_lessons", []).append(boss_id)
    j.setdefault("boss_clears", []).append(boss_id)
    skills = _unlock_skills(j, cur, les.get("skill_ids") or [])
    gear = None
    if les.get("gear_drop"):
        _equip_gear(j, les["gear_drop"])
        gear = les["gear_drop"]
    rank = _compute_rank(len(j["completed_lessons"]), j["journey_exp"])
    j["rank_id"] = rank["id"]
    _advance_stage(j, cur)

    rpg = ensure_rpg(state)
    rpg.setdefault("boss_clears", []).append(
        {"id": boss_id, "title_ja": les.get("title_ja"), "boss_type": les.get("boss_type"), "at": _utcnow()}
    )

    return {
        "ok": True,
        "success": True,
        "message_ja": "ボス討伐成功！装備と経験を手に入れたよ。",
        "exp_gained": gained_exp,
        "journey_exp_gained": raw_exp,
        "skills_gained": skills,
        "gear": gear,
        "rank": rank,
        "appearance": _build_appearance(j["class_id"], j.get("equipped") or {}, j["rank_id"], j.get("inventory") or []),
        "status": journey_status(state),
        "map": list_journey_map(state),
    }


def enrich_lesson_detail(state: Dict[str, Any], lesson_id: str, detail_ja: str) -> Dict[str, Any]:
    j = ensure_journey(state)
    if not j.get("career_id"):
        raise ValueError("journey not selected")
    text = (detail_ja or "").strip()[:1200]
    if not text:
        raise ValueError("detail required")
    j.setdefault("lesson_enrich", {})[lesson_id] = text
    return {"ok": True, "lesson_id": lesson_id, "detail_ja": text}
