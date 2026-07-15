"""Learning-linked mini RPG: quests, gear, treasure, bosses, portfolio."""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from exp_engine import DAILY_CAP

_WORLD_PATH = Path(__file__).resolve().parent / "config" / "rpg_world.json"
_WORLD: Optional[Dict[str, Any]] = None


def load_world() -> Dict[str, Any]:
    global _WORLD
    if _WORLD is None:
        import json
        with open(_WORLD_PATH, "r", encoding="utf-8") as f:
            _WORLD = json.load(f)
    return _WORLD


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_rpg(state: Dict[str, Any]) -> Dict[str, Any]:
    rpg = state.setdefault("rpg", {})
    rpg.setdefault("class_id", None)
    rpg.setdefault("region_id", "tutorial_plains")
    rpg.setdefault("equipment", [])
    rpg.setdefault("quest_log", [])
    rpg.setdefault("boss_clears", [])
    rpg.setdefault("treasure_finds", [])
    rpg.setdefault("active_quests", [])
    return rpg


def _apply_exp(state: Dict[str, Any], gain: int) -> int:
    remain = max(0, DAILY_CAP - int(state.get("daily_exp", 0)))
    gain = min(max(0, int(gain)), remain)
    state["daily_exp"] = int(state.get("daily_exp", 0)) + gain
    state["total_exp"] = int(state.get("total_exp", 0)) + gain
    state["current_level"] = int(math.floor(1 + math.sqrt(state["total_exp"] / 100)))
    return gain


def _maybe_unlock_region(state: Dict[str, Any]) -> Optional[str]:
    world = load_world()
    rpg = ensure_rpg(state)
    level = int(state.get("current_level", 1))
    current = rpg.get("region_id") or "tutorial_plains"
    regions = sorted(world["regions"], key=lambda r: r["order"])
    unlocked = None
    for r in regions:
        if level >= int(r.get("unlock_level", 1)):
            unlocked = r["id"]
    if unlocked and unlocked != current:
        cur_order = next((x["order"] for x in regions if x["id"] == current), 1)
        new_order = next((x["order"] for x in regions if x["id"] == unlocked), 1)
        if new_order > cur_order:
            rpg["region_id"] = unlocked
            return unlocked
    return None


def list_regions(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    world = load_world()
    level = int(state.get("current_level", 1))
    rpg = ensure_rpg(state)
    out = []
    for r in sorted(world["regions"], key=lambda x: x["order"]):
        out.append({
            **r,
            "unlocked": level >= int(r.get("unlock_level", 1)),
            "current": r["id"] == rpg.get("region_id"),
        })
    return out


def start_quest(state, *, title, quest_type="daily_study", subject=None, note=None):
    world = load_world()
    if quest_type not in world["quest_types"]:
        raise ValueError("Unknown quest_type")
    rpg = ensure_rpg(state)
    q = {
        "id": uuid.uuid4().hex[:12],
        "title": title.strip() or world["quest_types"][quest_type]["label_ja"],
        "quest_type": quest_type,
        "subject": subject,
        "note": note,
        "region_id": rpg.get("region_id"),
        "status": "active",
        "created_at": _utcnow(),
    }
    rpg.setdefault("active_quests", []).append(q)
    return q


def complete_activity(state, *, quest_type, title, subject=None, score=None, note=None, quest_id=None):
    world = load_world()
    meta = world["quest_types"].get(quest_type)
    if not meta:
        raise ValueError("Unknown quest_type")
    rpg = ensure_rpg(state)
    gain = _apply_exp(state, int(meta["exp"]))
    kind = meta["log_kind"]
    entry = {
        "id": uuid.uuid4().hex[:12],
        "title": (title or meta["label_ja"]).strip(),
        "quest_type": quest_type,
        "kind": kind,
        "subject": subject,
        "score": score,
        "note": note,
        "region_id": rpg.get("region_id"),
        "exp_gain": gain,
        "completed_at": _utcnow(),
    }
    if quest_id:
        active = rpg.get("active_quests") or []
        kept = []
        for q in active:
            if q.get("id") == quest_id:
                entry["title"] = q.get("title") or entry["title"]
                entry["subject"] = entry["subject"] or q.get("subject")
            else:
                kept.append(q)
        rpg["active_quests"] = kept
    rpg.setdefault("quest_log", []).append(entry)
    reward = None
    if kind == "equipment":
        rarity = "rare" if (score or 0) >= 80 else "common"
        gear = {
            "id": uuid.uuid4().hex[:10],
            "name": entry["title"] + "の証",
            "slot": "weapon",
            "rarity": rarity,
            "from_activity": entry["id"],
            "subject": subject,
            "obtained_at": _utcnow(),
        }
        rpg.setdefault("equipment", []).append(gear)
        reward = {"type": "equipment", "item": gear}
    elif kind == "treasure":
        chest = {
            "id": uuid.uuid4().hex[:10],
            "name": "抜き打ち宝箱",
            "title": entry["title"],
            "subject": subject,
            "score": score,
            "obtained_at": _utcnow(),
        }
        rpg.setdefault("treasure_finds", []).append(chest)
        reward = {"type": "treasure", "item": chest}
    elif kind == "boss":
        boss = {
            "id": uuid.uuid4().hex[:10],
            "name": entry["title"],
            "quest_type": quest_type,
            "subject": subject,
            "score": score,
            "cleared_at": _utcnow(),
            "region_id": rpg.get("region_id"),
        }
        rpg.setdefault("boss_clears", []).append(boss)
        art = {
            "id": uuid.uuid4().hex[:10],
            "name": entry["title"] + "クリア徽章",
            "slot": "artifact",
            "rarity": "epic" if quest_type == "final_exam" else "rare",
            "from_activity": entry["id"],
            "subject": subject,
            "obtained_at": _utcnow(),
        }
        rpg.setdefault("equipment", []).append(art)
        reward = {"type": "boss", "item": boss, "artifact": art}
    new_region = _maybe_unlock_region(state)
    return {
        "entry": entry,
        "exp_gain": gain,
        "level": state.get("current_level"),
        "reward": reward,
        "region_unlocked": new_region,
        "region_id": rpg.get("region_id"),
    }


def build_portfolio(state: Dict[str, Any]) -> Dict[str, Any]:
    rpg = ensure_rpg(state)
    cp = state.get("career_path") or {}
    logs = rpg.get("quest_log") or []
    by_subject: Dict[str, int] = {}
    for e in logs:
        sub = e.get("subject") or "general"
        by_subject[sub] = by_subject.get(sub, 0) + 1
    name = state.get("user_display_name") or "冒険者"
    level = state.get("current_level", 1)
    top = sorted(by_subject.items(), key=lambda x: x[1], reverse=True)
    focus = top[0][0] if top else "学習全般"
    bosses = len(rpg.get("boss_clears") or [])
    story = (
        f"{name}はLv.{level}まで成長しました。"
        f"特に『{focus}』のクエストを積み重ね、"
        f"ボス討伐（大きな試験）を{bosses}回達成しています。"
        "日々の課題・小テスト・期末への挑戦は、将来のポートフォリオそのものです。"
    )
    return {
        "generated_at": _utcnow(),
        "adventurer": {
            "name": state.get("user_display_name"),
            "level": state.get("current_level", 1),
            "total_exp": state.get("total_exp", 0),
            "companion": state.get("companion_name"),
            "class_id": rpg.get("class_id"),
            "region_id": rpg.get("region_id"),
        },
        "career": {
            "decided": cp.get("decided"),
            "decided_career": cp.get("decided_career"),
            "cluster_id": cp.get("cluster_id"),
        },
        "summary": {
            "quests_completed": len([x for x in logs if x.get("kind") == "quest"]),
            "tests_equipment": len(rpg.get("equipment") or []),
            "treasures": len(rpg.get("treasure_finds") or []),
            "bosses_cleared": len(rpg.get("boss_clears") or []),
            "by_subject": by_subject,
        },
        "recent_quests": list(reversed(logs))[:20],
        "equipment": rpg.get("equipment") or [],
        "treasures": rpg.get("treasure_finds") or [],
        "bosses": rpg.get("boss_clears") or [],
        "story_ja": story,
    }

