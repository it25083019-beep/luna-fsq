# -*- coding: utf-8 -*-
"""Memory Drama — remember turning points, remind later. Never store raw secrets."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from privacy_vault import looks_secret


def remember_milestone(user: Dict[str, Any], kind: str, label_ja: str) -> None:
    text = (label_ja or "").strip()[:80]
    if not text or looks_secret(text):
        return
    today = date.today().isoformat()
    log = list(user.get("emotion_milestones") or [])
    if log and log[-1].get("label_ja") == text and str(log[-1].get("on") or "")[:10] == today:
        return
    log.append({"kind": kind, "label_ja": text, "on": today})
    user["emotion_milestones"] = log[-24:]


def note_mood_shift(user: Dict[str, Any], previous: Optional[str], current: Optional[str]) -> None:
    prev = str(previous or "")
    cur = str(current or "")
    if prev in ("落ち込み", "不安", "疲れ") and cur in ("普通", "元気"):
        remember_milestone(user, "rise", f"「{prev}」の日から、また立てた")


def drama_line(user: Dict[str, Any]) -> str:
    health = ((user.get("life_modules") or {}).get("health") or {}).get("structured") or {}
    mental = str(health.get("mental_status") or "")
    marks: List[Dict[str, Any]] = [x for x in (user.get("emotion_milestones") or []) if isinstance(x, dict)]
    if not marks:
        return ""
    latest = marks[-1]
    label = latest.get("label_ja") or ""
    if looks_secret(label):
        return ""
    if mental in ("落ち込み", "不安", "疲れ"):
        return f"覚えているよ。{label}。あのときも、戻れた。"
    if latest.get("kind") == "rise":
        return f"前に一度、夜を越えたよね。{label}。"
    return f"覚えてる。{label}。"


def drama_prompt_block(user: Dict[str, Any]) -> str:
    line = drama_line(user)
    if not line:
        return ""
    return f"MEMORY DRAMA (may use once, never invent extra facts): {line}"
