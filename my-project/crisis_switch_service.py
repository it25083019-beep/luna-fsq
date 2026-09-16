# -*- coding: utf-8 -*-
"""60-second Crisis Switch — companion-led, local only."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from care_timeline import append_care_event
from companion_presence import crisis_script
from companions import get_companion
from emergency_contacts import crisis_contact_payload


def build_crisis_protocol(user: Dict[str, Any]) -> Dict[str, Any]:
    script = crisis_script(user)
    row = get_companion(script.get("companion_id"))
    prefix = row.get("prefix") or row.get("id") or "luna"
    base = (row.get("base") or f"/static/live2d/{prefix}-expressions").rstrip("/")
    people = crisis_contact_payload(user)
    return {
        "ok": True,
        "id": "cs_" + uuid4().hex[:8],
        "seconds": 60,
        "title_ja": "60秒レスキュー",
        "lead_ja": script["lead_ja"],
        "done_ja": script["done_ja"],
        "hint_ja": people["hint_ja"],
        "contacts": people["contacts"],
        "companion_id": script["companion_id"],
        "companion_name": script["companion_name"],
        "sprites": {
            "sad": f"{base}/{prefix}-sad.png",
            "think": f"{base}/{prefix}-think.png",
            "happy": f"{base}/{prefix}-happy.png",
            "cheer": f"{base}/{prefix}-cheer.png",
        },
        "steps": script["steps"],
    }


def complete_crisis_switch(user: Dict[str, Any]) -> Dict[str, Any]:
    today = datetime.now(timezone.utc).date().isoformat()
    user["last_crisis_switch_on"] = today
    append_care_event(user, "care", "60秒レスキューを終えた", detail="呼吸→接地→ひとつ")
    from memory_drama_service import remember_milestone

    remember_milestone(user, "crisis", "前の嵐を、60秒で乗り越えた")
    script = crisis_script(user)
    return {"ok": True, "saved": True, "done_ja": script["done_ja"], "emotion": "cheer"}
