"""User life goals: unlimited items with progress tracking."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from life_modules import ensure_life_modules, update_module_structured


def _parse_num(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip().replace(",", "").replace("円", "").replace("%", "")
    try:
        return float(raw)
    except ValueError:
        return default


def _pct(current: float, target: float) -> int:
    if target <= 0:
        return 100 if current > 0 else 0
    return max(0, min(100, int(round((current / target) * 100))))


def ensure_goals_module(user: Dict[str, Any]) -> Dict[str, Any]:
    ensure_life_modules(user)
    modules = user.setdefault("life_modules", {})
    row = modules.setdefault("goals", {})
    row.setdefault("notes", [])
    structured = row.setdefault("structured", {})
    if not isinstance(structured.get("items"), list):
        structured["items"] = []
    row.setdefault("updated_at", None)
    return row


def sanitize_goal_item(payload: Dict[str, Any], *, existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base = dict(existing or {})
    gid = str(payload.get("id") or base.get("id") or uuid.uuid4().hex[:12])
    title = (str(payload.get("title") if "title" in payload else base.get("title") or "").strip())[:80]
    if not title:
        raise ValueError("title is required")
    current = _parse_num(payload.get("current") if "current" in payload else base.get("current"), 0.0)
    target = _parse_num(payload.get("target") if "target" in payload else base.get("target"), 0.0)
    if target < 0:
        target = 0.0
    if current < 0:
        current = 0.0
    unit = (str(payload.get("unit") if "unit" in payload else base.get("unit") or "円").strip())[:12] or "円"
    note = (str(payload.get("note") if "note" in payload else base.get("note") or "").strip())[:200]
    done = bool(target > 0 and current >= target)
    if "done" in payload and payload.get("done") is not None:
        done = bool(payload.get("done"))
    return {
        "id": gid,
        "title": title,
        "current": current,
        "target": target,
        "unit": unit,
        "note": note,
        "pct": _pct(current, target),
        "done": done,
    }


def _items(user: Dict[str, Any]) -> List[Dict[str, Any]]:
    row = ensure_goals_module(user)
    raw = list((row.get("structured") or {}).get("items") or [])
    out: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            out.append(sanitize_goal_item(item, existing=item))
        except ValueError:
            continue
    return out


def goals_dashboard(user: Dict[str, Any]) -> Dict[str, Any]:
    items = _items(user)
    done = sum(1 for g in items if g.get("done") or g.get("pct", 0) >= 100)
    total = len(items)
    return {
        "items": items,
        "done": done,
        "total": total,
        "label": (f"{done}/{total} 達成" if total else "目標なし"),
        "in_progress": max(0, total - done),
    }


def home_goals_summary(user: Dict[str, Any]) -> Dict[str, Any]:
    dash = goals_dashboard(user)
    total = dash["total"]
    done = dash["done"]
    if total == 0:
        label = "目標を追加"
    elif done >= total:
        label = f"{done}/{total} 達成"
    else:
        label = f"{done}/{total} 進行中"
    return {"done": done, "total": total, "label": label}


def add_goal(user: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    items = _items(user)
    item = sanitize_goal_item(payload)
    items.append(item)
    update_module_structured(user, "goals", {"items": items}, note=f"目標追加: {item['title']}")
    return goals_dashboard(user)


def update_goal(user: Dict[str, Any], goal_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    items = _items(user)
    found = False
    for i, item in enumerate(items):
        if item["id"] != goal_id:
            continue
        items[i] = sanitize_goal_item(payload, existing=item)
        found = True
        break
    if not found:
        raise ValueError("goal not found")
    update_module_structured(user, "goals", {"items": items}, note="目標を更新")
    return goals_dashboard(user)


def delete_goal(user: Dict[str, Any], goal_id: str) -> Dict[str, Any]:
    items = _items(user)
    nxt = [g for g in items if g["id"] != goal_id]
    if len(nxt) == len(items):
        raise ValueError("goal not found")
    update_module_structured(user, "goals", {"items": nxt}, note="目標を削除")
    return goals_dashboard(user)
