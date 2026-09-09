# -*- coding: utf-8 -*-
"""Switchable 2D companions that share Luna's expression / gesture set."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_EXPRS = ("neutral", "happy", "sad", "surprised", "talk", "blink", "wave", "cheer", "think")
_CACHE: Optional[Dict[str, Any]] = None


def _path() -> Path:
    return Path(__file__).resolve().parent / "config" / "companions.json"


def load_companions() -> Dict[str, Any]:
    global _CACHE
    if _CACHE is None:
        with open(_path(), "r", encoding="utf-8") as f:
            _CACHE = json.load(f)
    return _CACHE


def list_companions() -> List[Dict[str, Any]]:
    data = load_companions()
    out: List[Dict[str, Any]] = []
    for row in data.get("companions") or []:
        item = dict(row)
        prefix = item.get("prefix") or item["id"]
        base = (item.get("base") or "").rstrip("/")
        item["preview"] = f"{base}/{prefix}-neutral.png"
        item["expressions"] = {name: f"{base}/{prefix}-{name}.png" for name in _EXPRS}
        item["themes"] = {
            "health": f"/static/ui/health-{item['id']}.png",
            "money": f"/static/ui/money-{item['id']}.png",
            "schedule": f"/static/ui/schedule-{item['id']}.png",
        }
        out.append(item)
    return out


def get_companion(companion_id: Optional[str]) -> Dict[str, Any]:
    data = load_companions()
    wanted = (companion_id or data.get("default_id") or "luna").strip().lower()
    by_id = {c["id"]: c for c in list_companions()}
    return by_id.get(wanted) or by_id["luna"]


def normalize_companion_id(companion_id: Optional[str]) -> str:
    return get_companion(companion_id)["id"]
