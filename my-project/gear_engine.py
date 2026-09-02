"""Cosmetic gear / glamour system — FFXIV & 武侠-inspired appearance only (no stat power)."""
from __future__ import annotations

import random
import uuid
from typing import Any, Dict, List, Optional, Tuple

from journey_engine import _career_meta, load_appearance

SLOTS = ("weapon", "armor", "accessory", "artifact", "cloak")

RARITIES: Dict[str, Dict[str, Any]] = {
    "common": {"label_ja": "コモン", "color": "#9aa0b8", "weight": 52, "glow": 0},
    "uncommon": {"label_ja": "アンコモン", "color": "#3ecf7a", "weight": 28, "glow": 0.15},
    "rare": {"label_ja": "レア", "color": "#4a9eff", "weight": 14, "glow": 0.35},
    "epic": {"label_ja": "エピック", "color": "#b47aff", "weight": 5, "glow": 0.55},
    "legendary": {"label_ja": "レジェンド", "color": "#ffd27a", "weight": 1, "glow": 0.85},
}

# Career-cluster themed cosmetic loot (appearance only)
_LOOT_BY_CLUSTER: Dict[str, List[Dict[str, Any]]] = {
    "it_engineering": [
        {"slot": "weapon", "item_id": "wpn_rusty_keyboard", "label_ja": "錆びたキーボード", "css": "gear-weapon-tech", "tint": "#8a8a9a", "rarity": "common"},
        {"slot": "armor", "item_id": "arm_intern_hoodie", "label_ja": "インターンのパーカー", "css": "gear-armor-hoodie", "tint": "#5b6abf", "rarity": "common"},
        {"slot": "accessory", "item_id": "acc_usb_badge", "label_ja": "USBバッジ", "css": "gear-acc-glow", "tint": "#497cff", "rarity": "common"},
        {"slot": "cloak", "item_id": "clk_debug_cloak", "label_ja": "デバッグの薄衣", "css": "gear-cloak-soft", "tint": "#3a4270", "rarity": "uncommon"},
        {"slot": "weapon", "item_id": "wpn_mechanical_blade", "label_ja": "メカニカルブレード", "css": "gear-weapon-tech", "tint": "#497cff", "rarity": "rare"},
        {"slot": "armor", "item_id": "arm_dev_vest", "label_ja": "エンジニアベスト", "css": "gear-armor-vest", "tint": "#2f4a8a", "rarity": "rare"},
        {"slot": "cloak", "item_id": "clk_cloud_mantle", "label_ja": "クラウドマント", "css": "gear-armor-cloak", "tint": "#1f7a6e", "rarity": "epic"},
        {"slot": "artifact", "item_id": "art_senior_sigil", "label_ja": "シニアの証", "css": "gear-artifact", "tint": "#ffd27a", "rarity": "legendary"},
    ],
    "design_creative": [
        {"slot": "weapon", "item_id": "wpn_charcoal", "label_ja": "木炭の筆", "css": "gear-weapon-brush", "tint": "#6a5a4a", "rarity": "common"},
        {"slot": "armor", "item_id": "arm_paint_apron", "label_ja": "絵のエプロン", "css": "gear-armor-apron", "tint": "#e07a8a", "rarity": "common"},
        {"slot": "accessory", "item_id": "acc_color_chip", "label_ja": "カラーチップ", "css": "gear-acc-glow", "tint": "#f0a8c8", "rarity": "uncommon"},
        {"slot": "cloak", "item_id": "clk_canvas_robe", "label_ja": "キャンバスの衣", "css": "gear-cloak-soft", "tint": "#c45d7a", "rarity": "uncommon"},
        {"slot": "weapon", "item_id": "wpn_golden_stylus", "label_ja": "黄金のスタイラス", "css": "gear-weapon-brush", "tint": "#ffd27a", "rarity": "epic"},
        {"slot": "artifact", "item_id": "art_master_palette", "label_ja": "巨匠のパレット", "css": "gear-artifact", "tint": "#ff9ec8", "rarity": "legendary"},
    ],
    "care_helping": [
        {"slot": "weapon", "item_id": "wpn_care_rod", "label_ja": "癒しの杖", "css": "gear-weapon-staff", "tint": "#6ec9b8", "rarity": "common"},
        {"slot": "armor", "item_id": "arm_soft_scrubs", "label_ja": "やわらかスクラブ", "css": "gear-armor-uniform", "tint": "#5bb8a8", "rarity": "common"},
        {"slot": "cloak", "item_id": "clk_healer_shawl", "label_ja": "癒しのショール", "css": "gear-cloak-soft", "tint": "#2f8a7a", "rarity": "rare"},
        {"slot": "accessory", "item_id": "acc_heart_locket", "label_ja": "ハートのロケット", "css": "gear-acc-glow", "tint": "#e07a8a", "rarity": "rare"},
        {"slot": "artifact", "item_id": "art_angel_wing", "label_ja": "天使の羽飾り", "css": "gear-artifact", "tint": "#ffd27a", "rarity": "legendary"},
    ],
    "education": [
        {"slot": "weapon", "item_id": "wpn_chalk_wand", "label_ja": "チョークの杖", "css": "gear-weapon-blade", "tint": "#e8b86d", "rarity": "common"},
        {"slot": "armor", "item_id": "arm_teacher_vest", "label_ja": "先生のベスト", "css": "gear-armor-vest", "tint": "#8b6ad4", "rarity": "common"},
        {"slot": "cloak", "item_id": "clk_scholar_robe", "label_ja": "学者のローブ", "css": "gear-armor-cloak", "tint": "#6a4fbf", "rarity": "rare"},
        {"slot": "artifact", "item_id": "art_wisdom_scroll", "label_ja": "知恵の巻物", "css": "gear-artifact", "tint": "#ffd27a", "rarity": "legendary"},
    ],
    "hands_on_making": [
        {"slot": "weapon", "item_id": "wpn_craft_hammer", "label_ja": "職人の槌", "css": "gear-weapon-blade", "tint": "#c9a227", "rarity": "common"},
        {"slot": "armor", "item_id": "arm_work_apron", "label_ja": "作業エプロン", "css": "gear-armor-apron", "tint": "#8b6914", "rarity": "common"},
        {"slot": "cloak", "item_id": "clk_artisan_cape", "label_ja": "匠のケープ", "css": "gear-cloak-soft", "tint": "#6a4e12", "rarity": "epic"},
        {"slot": "artifact", "item_id": "art_master_tool", "label_ja": "名匠の道具", "css": "gear-artifact", "tint": "#ffd27a", "rarity": "legendary"},
    ],
    "business_social": [
        {"slot": "weapon", "item_id": "wpn_pitch_mic", "label_ja": "ピッチマイク", "css": "gear-weapon-tech", "tint": "#ff6fae", "rarity": "common"},
        {"slot": "armor", "item_id": "arm_smart_blazer", "label_ja": "スマートブレザー", "css": "gear-armor-vest", "tint": "#2f4a6a", "rarity": "uncommon"},
        {"slot": "cloak", "item_id": "clk_brand_mantle", "label_ja": "ブランドマント", "css": "gear-armor-cloak", "tint": "#c45d9a", "rarity": "epic"},
    ],
    "science_research": [
        {"slot": "weapon", "item_id": "wpn_lab_pipette", "label_ja": "研究室ピペット", "css": "gear-weapon-staff", "tint": "#6ec9b8", "rarity": "common"},
        {"slot": "armor", "item_id": "arm_lab_coat", "label_ja": "白衣コート", "css": "gear-armor-uniform", "tint": "#e8f4ff", "rarity": "common"},
        {"slot": "cloak", "item_id": "clk_research_hood", "label_ja": "研究のフード", "css": "gear-cloak-soft", "tint": "#497cff", "rarity": "rare"},
        {"slot": "artifact", "item_id": "art_discovery_lens", "label_ja": "発見のレンズ", "css": "gear-artifact", "tint": "#ffd27a", "rarity": "legendary"},
    ],
    "default": [
        {"slot": "weapon", "item_id": "wpn_starter", "label_ja": "見習いの武器", "css": "gear-weapon-blade", "tint": "#9aa0b8", "rarity": "common"},
        {"slot": "armor", "item_id": "arm_traveler", "label_ja": "旅人の服", "css": "gear-armor-hoodie", "tint": "#5b6abf", "rarity": "common"},
        {"slot": "cloak", "item_id": "clk_wanderer", "label_ja": "放浪者の外套", "css": "gear-cloak-soft", "tint": "#3a2f8a", "rarity": "uncommon"},
        {"slot": "accessory", "item_id": "acc_map", "label_ja": "探索マップ", "css": "gear-acc-glow", "tint": "#b4aee8", "rarity": "common"},
        {"slot": "artifact", "item_id": "art_stub", "label_ja": "冒険の証", "css": "gear-artifact", "tint": "#ffd27a", "rarity": "rare"},
    ],
}

# Drop rate tuned by career difficulty (longer path = slightly better odds at high tiers)
_CAREER_DIFFICULTY: Dict[str, int] = {
    "software_engineer": 4,
    "data_analyst": 4,
    "ui_designer": 3,
    "nurse": 4,
    "teacher": 3,
    "game_creator": 3,
    "architect": 4,
    "marketer": 2,
    "researcher": 5,
    "chef": 3,
    "pilot": 4,
    "entrepreneur": 4,
}


def _cluster_for_career(career_id: str) -> str:
    meta = _career_meta(career_id) or {}
    return str(meta.get("cluster_id") or "default")


def _loot_pool(cluster_id: str) -> List[Dict[str, Any]]:
    return list(_LOOT_BY_CLUSTER.get(cluster_id) or _LOOT_BY_CLUSTER["default"])


def roll_rarity(*, boss: bool = False, difficulty: int = 2, bonus: int = 0) -> str:
    weights = {k: v["weight"] for k, v in RARITIES.items()}
    if boss:
        weights["rare"] += 8
        weights["epic"] += 5
        weights["legendary"] += 2
        weights["common"] -= 10
    weights["uncommon"] += difficulty
    weights["rare"] += max(0, difficulty - 2)
    if bonus:
        weights["epic"] += bonus
    total = sum(max(0, w) for w in weights.values())
    r = random.randint(1, max(1, total))
    acc = 0
    for rid, w in weights.items():
        acc += max(0, w)
        if r <= acc:
            return rid
    return "common"


def roll_monster_loot(
    career_id: str,
    *,
    boss: bool = False,
    lesson_index: int = 0,
) -> Optional[Dict[str, Any]]:
    """Random cosmetic drop from study combat. Returns None if no drop."""
    difficulty = _CAREER_DIFFICULTY.get(career_id, 2)
    base_chance = 0.42 if boss else 0.28
    base_chance += min(0.12, lesson_index * 0.004)
    base_chance += difficulty * 0.02
    if random.random() > base_chance:
        return None

    cluster = _cluster_for_career(career_id)
    pool = _loot_pool(cluster)
    rarity = roll_rarity(boss=boss, difficulty=difficulty)
    candidates = [x for x in pool if x.get("rarity") == rarity]
    if not candidates:
        candidates = [x for x in pool if x.get("rarity") in ("common", "uncommon")]
    if not candidates:
        candidates = pool
    base = dict(random.choice(candidates))
    base["rarity"] = rarity
    base["rarity_ja"] = RARITIES[rarity]["label_ja"]
    base["rarity_color"] = RARITIES[rarity]["color"]
    base["cosmetic_only"] = True
    return base


def ensure_gear_state(j: Dict[str, Any]) -> None:
    j.setdefault("inventory", [])
    empty = {s: None for s in SLOTS}
    j.setdefault("equipped", dict(empty))
    j.setdefault("glamour", dict(empty))


def grant_loot(j: Dict[str, Any], gear: Dict[str, Any], *, auto_equip_if_empty: bool = True) -> Dict[str, Any]:
    """Add cosmetic item to inventory; optional auto-equip when slot is empty."""
    ensure_gear_state(j)
    slot = gear.get("slot") or "accessory"
    if slot not in SLOTS:
        slot = "accessory"
    item_id = gear.get("item_id") or uuid.uuid4().hex[:10]
    rarity = gear.get("rarity") or "common"
    row = {
        "uid": uuid.uuid4().hex[:12],
        "id": item_id,
        "slot": slot,
        "label_ja": gear.get("label_ja") or "装備",
        "rarity": rarity,
        "rarity_ja": gear.get("rarity_ja") or RARITIES.get(rarity, {}).get("label_ja", rarity),
        "rarity_color": gear.get("rarity_color") or RARITIES.get(rarity, {}).get("color", "#9aa0b8"),
        "css": gear.get("css"),
        "tint": gear.get("tint"),
        "cosmetic_only": True,
        "at": gear.get("at"),
    }
    j["inventory"].append(row)
    j["inventory"] = j["inventory"][-80:]
    equipped = j["equipped"]
    if auto_equip_if_empty and not equipped.get(slot):
        equipped[slot] = row["uid"]
    return row


def effective_display_map(j: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Glamour overrides equipped for appearance (FFXIV-style)."""
    ensure_gear_state(j)
    out: Dict[str, Optional[str]] = {}
    for slot in SLOTS:
        glam = (j.get("glamour") or {}).get(slot)
        eq = (j.get("equipped") or {}).get(slot)
        out[slot] = glam or eq
    return out


def _item_by_uid(j: Dict[str, Any], uid: Optional[str]) -> Optional[Dict[str, Any]]:
    if not uid:
        return None
    for it in j.get("inventory") or []:
        if str(it.get("uid")) == str(uid) or str(it.get("id")) == str(uid):
            return it
    return None


def set_glamour(j: Dict[str, Any], item_uid: str) -> Dict[str, Any]:
    item = _item_by_uid(j, item_uid)
    if not item:
        raise ValueError("item not found")
    ensure_gear_state(j)
    slot = item.get("slot") or "accessory"
    j["glamour"][slot] = item["uid"]
    return item


def set_equipped(j: Dict[str, Any], item_uid: str) -> Dict[str, Any]:
    item = _item_by_uid(j, item_uid)
    if not item:
        raise ValueError("item not found")
    ensure_gear_state(j)
    slot = item.get("slot") or "accessory"
    j["equipped"][slot] = item["uid"]
    return item


def clear_glamour_slot(j: Dict[str, Any], slot: str) -> None:
    ensure_gear_state(j)
    if slot in j["glamour"]:
        j["glamour"][slot] = None


def inventory_for_client(j: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list(j.get("inventory") or [])


def rarity_meta(rarity: str) -> Dict[str, Any]:
    return dict(RARITIES.get(rarity) or RARITIES["common"])
