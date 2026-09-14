# -*- coding: utf-8 -*-
"""60-second Crisis Switch — breathe, ground, one next step. Local only."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from care_timeline import append_care_event


STEPS = [
    {
        "id": "breathe",
        "sec": 20,
        "title_ja": "呼吸",
        "line_ja": "鼻から4、止めて2、口から6。今はこれだけでいい。",
    },
    {
        "id": "ground",
        "sec": 20,
        "title_ja": "接地",
        "line_ja": "足の裏、椅子、今聞こえる音。一つだけ触って確認して。",
    },
    {
        "id": "one",
        "sec": 20,
        "title_ja": "ひとつだけ",
        "line_ja": "次は水を一杯か、目を閉じる。それ以外はやらなくていい。",
    },
]


def build_crisis_protocol(user: Dict[str, Any]) -> Dict[str, Any]:
    who = user.get("user_display_name") or ""
    honor = f"{who}さん、" if who else ""
    return {
        "ok": True,
        "id": "cs_" + uuid4().hex[:8],
        "seconds": 60,
        "title_ja": "60秒レスキュー",
        "lead_ja": f"{honor}いまは助ける番。60秒だけ、一緒に戻ろう。",
        "hotline_ja": "つらいときは いのちの電話 0570-783-556",
        "steps": STEPS,
    }


def complete_crisis_switch(user: Dict[str, Any]) -> Dict[str, Any]:
    today = datetime.now(timezone.utc).date().isoformat()
    user["last_crisis_switch_on"] = today
    append_care_event(user, "care", "60秒レスキューを終えた", detail="呼吸→接地→ひとつ")
    from memory_drama_service import remember_milestone

    remember_milestone(user, "crisis", "前の嵐を、60秒で乗り越えた")
    return {"ok": True, "saved": True}
