"""Lightweight care memory — recall what mattered last time, suggest next steps."""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional


def touch_care_memory(
    user: Dict[str, Any],
    topic: str,
    user_text: str,
    applied: Optional[List[str]] = None,
) -> None:
    cm = user.setdefault("care_memory", {})
    today = date.today().isoformat()
    cm["last_topic"] = topic
    cm["last_touch"] = today
    snippet = (user_text or "").strip()
    if snippet:
        cm[f"last_{topic}_message"] = snippet[:160]
    for tag in applied or []:
        if tag.startswith("気分"):
            cm["last_health_concern"] = tag.replace("気分→", "")
        if tag.startswith("支出"):
            cm["last_money_note"] = tag
    if snippet:
        notes = list(cm.get("notes") or [])
        notes.append({"d": today, "t": topic, "s": snippet[:100]})
        cm["notes"] = notes[-12:]

    from care_timeline import append_care_event

    for tag in applied or []:
        if tag.startswith("気分→"):
            append_care_event(user, "health", f"気分「{tag.replace('気分→', '')}」を記録")
        elif tag.startswith("支出+"):
            append_care_event(user, "money", f"支出 {tag.replace('支出+', '')}")
        elif tag == "予定を追加":
            append_care_event(user, "schedule", "予定を追加したよ")
        elif tag.endswith("メモ"):
            append_care_event(user, "care", tag)


def care_recall_prefix(user: Dict[str, Any], topic: str) -> str:
    """Short warm callback to prior concern — companion tone, not formal."""
    cm = user.get("care_memory") or {}
    if topic == "health":
        concern = cm.get("last_health_concern")
        if concern:
            return f"前に「{concern}」って話してくれたよね。"
        if cm.get("last_topic") == "health" and cm.get("last_health_message"):
            return "前回の体調のこと、気になってたよ。"
    else:
        if cm.get("last_money_note"):
            return "前に支出の話、一緒に見たね。"
        if cm.get("last_topic") == "money" and cm.get("last_money_message"):
            return "前回のお金のこと、続きも聞けるよ。"
    return ""


def format_recorded(applied: List[str]) -> str:
    if not applied:
        return ""
    bits: List[str] = []
    for tag in applied[:3]:
        if tag.startswith("気分→"):
            bits.append(f"気分「{tag.replace('気分→', '')}」")
        elif tag.startswith("支出+"):
            bits.append(f"支出{tag.replace('支出+', '')}")
        elif tag == "予定を追加":
            bits.append("予定")
        elif tag.endswith("メモ"):
            bits.append("メモ")
        else:
            bits.append(tag[:24])
    return "、".join(bits)


def build_care_quests(user: Dict[str, Any]) -> List[Dict[str, str]]:
    """Daily care quests from real module data."""
    from health_eval import mental_needed, mental_reminder_due

    quests: List[Dict[str, str]] = []
    health = (user.get("life_modules") or {}).get("health", {}).get("structured") or {}
    money = (user.get("life_modules") or {}).get("money", {}).get("structured") or {}
    today = date.today().isoformat()

    if mental_needed(health) or mental_reminder_due(health):
        quests.append({"id": "mood", "label": "今日の気分を教える", "chip": "元気"})
    sleeps = health.get("sleep_hours")
    if not sleeps:
        quests.append({"id": "sleep", "label": "睡眠を記録する", "chip": "体調を相談したい"})

    from money_eval import spend_rows_on

    if not spend_rows_on(money, today):
        quests.append({"id": "spend", "label": "今日の支出を記録", "chip": "お金の相談"})

    cm = user.get("care_memory") or {}
    if cm.get("last_health_concern") and not quests:
        quests.append({"id": "follow_health", "label": "体調の続きを話す", "chip": "体調を相談したい"})

    return quests[:3]


def build_care_prompt(user: Dict[str, Any]) -> Optional[str]:
    """One proactive line for home banner."""
    quests = build_care_quests(user)
    if not quests:
        return None
    first = quests[0]["label"]
    return f"今日は「{first}」から始めようか。"
