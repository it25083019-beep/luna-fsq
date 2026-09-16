# -*- coding: utf-8 -*-
"""Trusted people the user wants to call in a hard moment — not a public hotline."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

RELATIONS = ("family", "friend", "other")
RELATION_JA = {"family": "家族", "friend": "親友", "other": "大切な人"}
RELATION_WEIGHT = {"family": 100, "friend": 50, "other": 10}
MAX_CONTACTS = 6
_TEL_KEEP = re.compile(r"[^\d+]")


def normalize_tel(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    cleaned = _TEL_KEEP.sub("", text)
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) < 8 or len(digits) > 15:
        return ""
    return cleaned[:20]


def normalize_relation(raw: Any) -> str:
    key = str(raw or "friend").strip().lower()
    if key in ("家族", "family", "parent", "母", "父", "両親"):
        return "family"
    if key in ("親友", "friend", "best", "友達", "友人"):
        return "friend"
    if key in RELATIONS:
        return key
    return "other"


def list_emergency_contacts(user: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = list((user or {}).get("emergency_contacts") or [])
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        tel = normalize_tel(row.get("tel") or row.get("phone"))
        if not tel:
            continue
        item = dict(row)
        item["tel"] = tel
        item["relation"] = normalize_relation(item.get("relation"))
        item["relation_ja"] = RELATION_JA.get(item["relation"], "大切な人")
        item["name"] = str(item.get("name") or "大切な人").strip()[:40]
        item["call_count"] = int(item.get("call_count") or 0)
        out.append(item)
    return out


def ranked_emergency_contacts(user: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Family first, then close friends, then how often this app was used to call them."""
    rows = list_emergency_contacts(user)
    rows.sort(
        key=lambda r: (
            RELATION_WEIGHT.get(r.get("relation") or "other", 0),
            int(r.get("call_count") or 0),
            str(r.get("last_called_at") or ""),
        ),
        reverse=True,
    )
    return rows


def add_emergency_contact(
    user: Dict[str, Any],
    *,
    name: str,
    tel: str,
    relation: str = "friend",
) -> Dict[str, Any]:
    phone = normalize_tel(tel)
    if not phone:
        raise ValueError("invalid phone")
    label = (name or "").strip()[:40] or "大切な人"
    rel = normalize_relation(relation)
    rows = user.setdefault("emergency_contacts", [])
    if not isinstance(rows, list):
        rows = []
        user["emergency_contacts"] = rows
    for row in rows:
        if isinstance(row, dict) and normalize_tel(row.get("tel")) == phone:
            row["name"] = label
            row["relation"] = rel
            return dict(row)
    if len(list_emergency_contacts(user)) >= MAX_CONTACTS:
        raise ValueError("too many contacts")
    item = {
        "id": "ec_" + uuid4().hex[:10],
        "name": label,
        "tel": phone,
        "relation": rel,
        "call_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    rows.append(item)
    return item


def delete_emergency_contact(user: Dict[str, Any], contact_id: str) -> bool:
    wanted = str(contact_id or "").strip()
    rows = user.get("emergency_contacts") if isinstance(user.get("emergency_contacts"), list) else []
    keep = [r for r in rows if not (isinstance(r, dict) and r.get("id") == wanted)]
    if len(keep) == len(rows):
        return False
    user["emergency_contacts"] = keep
    return True


def mark_emergency_called(user: Dict[str, Any], contact_id: str) -> Optional[Dict[str, Any]]:
    wanted = str(contact_id or "").strip()
    rows = user.get("emergency_contacts") if isinstance((user or {}).get("emergency_contacts"), list) else []
    for row in rows:
        if isinstance(row, dict) and row.get("id") == wanted:
            row["call_count"] = int(row.get("call_count") or 0) + 1
            row["last_called_at"] = datetime.now(timezone.utc).isoformat()
            return dict(row)
    return None


def public_contact(row: Dict[str, Any]) -> Dict[str, Any]:
    rel = normalize_relation(row.get("relation"))
    return {
        "id": row.get("id"),
        "name": row.get("name") or "大切な人",
        "tel": row.get("tel"),
        "relation": rel,
        "relation_ja": RELATION_JA.get(rel, "大切な人"),
        "call_count": int(row.get("call_count") or 0),
        "call_href": "tel:" + str(row.get("tel") or "").replace(" ", ""),
    }


def crisis_contact_payload(user: Dict[str, Any]) -> Dict[str, Any]:
    ranked = [public_contact(r) for r in ranked_emergency_contacts(user)]
    top = ranked[0] if ranked else None
    if top:
        hint = f"つらいときは、よく話す{top['relation_ja']}の{top['name']}さんにかけていい。"
    else:
        hint = "つらいときは、設定で家族や親友の番号を入れておいて。ここからかけられるよ。"
    return {"contacts": ranked, "hint_ja": hint, "top": top}
