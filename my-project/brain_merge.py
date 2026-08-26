"""Pure merge helpers to protect user brain data on load/save."""
from __future__ import annotations

from typing import Any, Dict


def meaningful_structured(structured: Any) -> bool:
    if not isinstance(structured, dict):
        return False
    for v in structured.values():
        if v is None or v == "" or v == [] or v == {}:
            continue
        return True
    return False


def merge_life_modules(base_lm: Dict[str, Any], incoming: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    base_lm = base_lm if isinstance(base_lm, dict) else {}
    incoming = incoming if isinstance(incoming, dict) else {}
    keys = set(base_lm) | set(incoming)
    for key in keys:
        b = (
            base_lm.get(key)
            if isinstance(base_lm.get(key), dict)
            else {"notes": [], "structured": {}, "updated_at": None}
        )
        g = incoming.get(key) if isinstance(incoming.get(key), dict) else {}
        b_notes = list(b.get("notes") or []) if isinstance(b.get("notes"), list) else []
        g_notes = list(g.get("notes") or []) if isinstance(g.get("notes"), list) else None
        if g_notes is None:
            notes = b_notes
        elif g_notes:
            notes = g_notes
        else:
            notes = b_notes
        row = {
            "notes": notes,
            "structured": dict(b.get("structured") or {}),
            "updated_at": g.get("updated_at", b.get("updated_at")),
        }
        row["structured"].update(g.get("structured") or {})
        if key == "schedule":
            b_ev = (b.get("structured") or {}).get("events")
            g_ev = (g.get("structured") or {}).get("events")
            if isinstance(b_ev, list) and b_ev and (not isinstance(g_ev, list) or len(g_ev) == 0):
                row["structured"]["events"] = list(b_ev)
                if not g.get("updated_at"):
                    row["updated_at"] = b.get("updated_at")
        if key == "goals":
            b_items = (b.get("structured") or {}).get("items")
            g_items = (g.get("structured") or {}).get("items")
            if isinstance(b_items, list) and b_items and (not isinstance(g_items, list) or len(g_items) == 0):
                row["structured"]["items"] = list(b_items)
                if not g.get("updated_at"):
                    row["updated_at"] = b.get("updated_at")
        if key == "money":
            b_log = (b.get("structured") or {}).get("spend_log")
            g_log = (g.get("structured") or {}).get("spend_log")
            if isinstance(b_log, list) and b_log and (not isinstance(g_log, list) or len(g_log) == 0):
                row["structured"]["spend_log"] = list(b_log)
                if not g.get("updated_at"):
                    row["updated_at"] = b.get("updated_at")
        if not meaningful_structured(row["structured"]) and meaningful_structured(b.get("structured")):
            row["structured"] = dict(b.get("structured") or {})
            row["updated_at"] = b.get("updated_at")
            if not row["notes"] and b_notes:
                row["notes"] = b_notes
        out[key] = row
    return out


def preserve_nonempty_list(existing: Any, incoming: Any) -> Any:
    if isinstance(incoming, list) and incoming:
        return incoming
    if isinstance(existing, list) and existing and (not incoming):
        return existing
    if isinstance(incoming, list):
        return incoming
    return existing if isinstance(existing, list) else []


def preserve_scalar(existing: Any, incoming: Any) -> Any:
    if incoming is None or incoming == "":
        return existing if existing not in (None, "") else incoming
    return incoming


def safe_merge_for_save(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """Merge incoming brain onto existing DB state without wiping user data."""
    existing = existing if isinstance(existing, dict) else {}
    payload = dict(incoming or {})
    payload.pop("_schedule_dirty", None)

    payload["life_modules"] = merge_life_modules(
        existing.get("life_modules") if isinstance(existing.get("life_modules"), dict) else {},
        payload.get("life_modules"),
    )

    ex_lp = existing.get("life_profile") if isinstance(existing.get("life_profile"), dict) else {}
    in_lp = payload.get("life_profile") if isinstance(payload.get("life_profile"), dict) else {}
    merged_lp = dict(ex_lp)
    for k, v in in_lp.items():
        merged_lp[k] = preserve_scalar(ex_lp.get(k), v)
    payload["life_profile"] = merged_lp

    ex_cp = existing.get("career_path") if isinstance(existing.get("career_path"), dict) else {}
    in_cp = payload.get("career_path") if isinstance(payload.get("career_path"), dict) else {}
    merged_cp = dict(ex_cp)
    merged_cp.update(in_cp)
    payload["career_path"] = merged_cp

    existing_rpg = existing.get("rpg") if isinstance(existing.get("rpg"), dict) else {}
    incoming_rpg = payload.get("rpg") if isinstance(payload.get("rpg"), dict) else {}
    merged_rpg = dict(existing_rpg)
    merged_rpg.update(incoming_rpg)
    if isinstance(incoming_rpg.get("journey"), dict):
        merged_rpg["journey"] = dict(incoming_rpg["journey"])
    elif isinstance(existing_rpg.get("journey"), dict) and "journey" not in incoming_rpg:
        merged_rpg["journey"] = existing_rpg["journey"]
    payload["rpg"] = merged_rpg

    for list_key in ("chat_history", "trained_knowledge", "schedule_reminders"):
        payload[list_key] = preserve_nonempty_list(existing.get(list_key), payload.get(list_key))

    for scalar_key in (
        "user_display_name",
        "companion_name",
        "current_focus",
        "current_plan",
        "current_do_now",
        "memory_note",
    ):
        payload[scalar_key] = preserve_scalar(existing.get(scalar_key), payload.get(scalar_key))

    try:
        payload["total_exp"] = max(int(existing.get("total_exp") or 0), int(payload.get("total_exp") or 0))
    except (TypeError, ValueError):
        payload["total_exp"] = existing.get("total_exp", payload.get("total_exp", 0))
    try:
        payload["current_level"] = max(
            int(existing.get("current_level") or 1), int(payload.get("current_level") or 1)
        )
    except (TypeError, ValueError):
        payload["current_level"] = existing.get("current_level", payload.get("current_level", 1))

    return payload
