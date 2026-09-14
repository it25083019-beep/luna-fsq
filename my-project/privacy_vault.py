# -*- coding: utf-8 -*-
"""Vault: user secrets stay on-device in the brain, never leave to LLM/TTS/admin dumps."""
from __future__ import annotations

import base64
import hashlib
import os
import re
from typing import Any, Dict, List, Optional

SECRET_HINT = re.compile(
    r"("
    r"秘密|内緒|内緒だ|だれにも|誰にも|言わないで|言わないでね|黙って|"
    r"暗証|マイナンバー|保険証|クレジットカード|口座番号|パスワード|"
    r"password|passwd|api[_-]?key|secret|confidential|don't tell|do not tell|"
    r"bí mật|đừng nói|đừng kể"
    r")",
    re.I,
)
SEAL_PREFIX = "luna1:"

CRISIS_HINT = re.compile(
    r"死にたい|消えたい|自殺|自傷|kill myself|want to die|suicide|muốn chết|tự tử",
    re.I,
)

REDACTED = "〔秘めごと〕"
CHAT_HISTORY_MAX = 400
LLM_NOTE_MAX = 80

DROP_FROM_CLIENT = {
    "chat_history",
    "trained_knowledge",
    "mail_link",
    "care_memory",
    "google_oauth",
    "push_subscription",
    "schedule_reminders",
    "consult_mode",
    "consult_started_at",
    "consult_turns",
    "recent_companion_lines",
    "last_companion_line",
    "memory_note",
}

DROP_FROM_ADMIN_BRAIN = {
    "mail_link",
    "push_subscription",
    "google_oauth",
}


def _vault_fernet():
    from cryptography.fernet import Fernet

    secret = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY") or "luna-dev-vault"
    digest = hashlib.sha256(f"luna-privacy-vault|{secret}".encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def seal_text(plain: Any) -> str:
    raw = str(plain or "")
    if not raw or raw.startswith(SEAL_PREFIX):
        return raw
    try:
        return SEAL_PREFIX + _vault_fernet().encrypt(raw.encode("utf-8")).decode("ascii")
    except Exception:
        return raw


def unseal_text(raw: Any) -> str:
    text = str(raw or "")
    if not text.startswith(SEAL_PREFIX):
        return text
    try:
        return _vault_fernet().decrypt(text[len(SEAL_PREFIX) :].encode("ascii")).decode("utf-8")
    except Exception:
        return REDACTED


def seal_mail_link(link: Any) -> Dict[str, Any]:
    out = dict(link) if isinstance(link, dict) else {}
    for key in ("access_token", "refresh_token"):
        if out.get(key):
            out[key] = seal_text(out[key])
    return out


def unseal_mail_link(link: Any) -> Dict[str, Any]:
    out = dict(link) if isinstance(link, dict) else {}
    for key in ("access_token", "refresh_token"):
        if out.get(key):
            out[key] = unseal_text(out[key])
    return out


def seal_brain_for_storage(brain: Dict[str, Any]) -> None:
    link = brain.get("mail_link")
    if isinstance(link, dict):
        brain["mail_link"] = seal_mail_link(link)
    hist = brain.get("chat_history")
    if isinstance(hist, list):
        sealed_hist = []
        for row in hist:
            if not isinstance(row, dict):
                sealed_hist.append(row)
                continue
            item = dict(row)
            content = str(item.get("content") or "")
            if item.get("secret") and content and not content.startswith(SEAL_PREFIX):
                item["content"] = seal_text(content)
                item["sealed"] = True
            sealed_hist.append(item)
        brain["chat_history"] = sealed_hist


def unseal_brain_after_load(brain: Dict[str, Any]) -> None:
    link = brain.get("mail_link")
    if isinstance(link, dict):
        brain["mail_link"] = unseal_mail_link(link)


def looks_secret(text: Any) -> bool:
    raw = str(text or "")
    if not raw.strip() or raw.startswith(SEAL_PREFIX):
        return False
    return bool(SECRET_HINT.search(raw) or CRISIS_HINT.search(raw))


def keep_secret_dialogue(user: Optional[Dict[str, Any]] = None) -> str:
    who = str((user or {}).get("user_display_name") or "").strip()
    prefix = f"{who}さん、" if who else ""
    return f"{prefix}受け取った。この話はここだけ。誰にも出さないよ。"


def reminders_for_llm(reminders: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in reminders or []:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "")
        if looks_secret(title):
            continue
        out.append({"when": row.get("when"), "title": title[:40]})
        if len(out) >= 8:
            break
    return out


def redact_text(text: Any) -> str:
    raw = str(text or "")
    if not raw:
        return ""
    if looks_secret(raw):
        return REDACTED
    return raw


def mark_secret_turn(row: Dict[str, Any], text: str) -> Dict[str, Any]:
    out = dict(row)
    if looks_secret(text):
        out["secret"] = True
    return out


def cap_chat_history(store: Dict[str, Any], *, limit: int = CHAT_HISTORY_MAX) -> None:
    hist = store.get("chat_history")
    if isinstance(hist, list) and len(hist) > limit:
        store["chat_history"] = hist[-limit:]


def history_for_llm(history: Any, *, limit: int = 20) -> List[Dict[str, Any]]:
    rows = [x for x in (history or []) if isinstance(x, dict)]
    out: List[Dict[str, Any]] = []
    for row in rows[-limit:]:
        content = str(row.get("content") or "")
        if row.get("secret") or row.get("sealed") or content.startswith(SEAL_PREFIX) or looks_secret(content):
            if row.get("role") == "user":
                out.append({"role": "user", "content": "（秘めごと。内容は繰り返さず、そばにいることだけ。）"})
            continue
        out.append({"role": row.get("role") or "user", "content": content[:1200]})
    return out


def profile_for_llm(profile: Any) -> Dict[str, Any]:
    src = profile if isinstance(profile, dict) else {}
    safe: Dict[str, Any] = {}
    for key, val in src.items():
        if key in ("mental_stress", "mental_support") or looks_secret(val):
            continue
        if key == "mental_mood" and looks_secret(val):
            continue
        safe[key] = val
    return safe


def notes_for_llm(notes: Any) -> List[str]:
    out: List[str] = []
    for row in notes or []:
        text = row.get("text") if isinstance(row, dict) else str(row or "")
        if looks_secret(text):
            continue
        clipped = str(text or "").strip()[:LLM_NOTE_MAX]
        if clipped:
            out.append(clipped)
    return out[-3:]


def structured_for_llm(module: str, structured: Any) -> str:
    data = structured if isinstance(structured, dict) else {}
    if module == "money":
        log = data.get("spend_log") if isinstance(data.get("spend_log"), list) else []
        bits = []
        if data.get("monthly_income"):
            bits.append("income=set")
        if data.get("monthly_expense"):
            bits.append("expense=set")
        bits.append(f"spend_rows={len(log)}")
        return ", ".join(bits) or "(empty)"
    if module == "health":
        keep = {k: data.get(k) for k in ("sleep_hours", "mental_status", "mental_checked_on") if data.get(k)}
        return str(keep) if keep else "(empty)"
    if module == "goals":
        items = data.get("items") if isinstance(data.get("items"), list) else []
        return f"goals={len(items)}"
    return "(omitted)"


def modules_prompt_safe(user: Dict[str, Any]) -> str:
    from life_modules import MODULE_KEYS, MODULE_META, ensure_life_modules

    ensure_life_modules(user)
    profile = user.get("life_profile") or {}
    lines = [
        "LIFE MODULES (safe summary only). Never repeat 〔秘めごと〕 or ask the user to restate a secret.",
        "If the user marked something secret, keep it. Do not quote it back.",
    ]
    for key in MODULE_KEYS:
        meta = MODULE_META[key]
        row = (user.get("life_modules") or {}).get(key) or {}
        lines.append(f"### {meta['title_ja']} ({key})")
        baseline = {k: profile.get(k) for k in meta["profile_keys"] if profile.get(k) and not looks_secret(profile.get(k))}
        if key == "health":
            baseline.pop("mental_stress", None)
            baseline.pop("mental_support", None)
        lines.append("baseline: " + ("; ".join(f"{k}={v}" for k, v in baseline.items()) or "(empty)"))
        safe_notes = notes_for_llm(row.get("notes"))
        if safe_notes:
            lines.append("recent notes: " + " | ".join(safe_notes))
        if key != "schedule":
            lines.append("structured: " + structured_for_llm(key, row.get("structured")))
    return "\n".join(lines)


def privacy_prompt_rules() -> str:
    return (
        "# PRIVACY VAULT (hard)\n"
        "- Secrets the user shares stay between you and them. Never quote them back, never put them in game_state, chips, or memory_note.\n"
        "- Never invent other users. Never ask for passwords, tokens, card numbers, or government IDs.\n"
        "- If they say 秘密/内緒/言わないで: acknowledge once, then stay beside them without details.\n"
        "- Do not send secrets into pending_notification."
    )


def public_client_state(user: Dict[str, Any]) -> Dict[str, Any]:
    src = user if isinstance(user, dict) else {}
    return {
        "user_id": src.get("user_id"),
        "current_level": src.get("current_level") or 1,
        "total_exp": src.get("total_exp") or 0,
        "daily_exp": src.get("daily_exp") or 0,
        "streak": src.get("streak") or 0,
        "companion_id": src.get("companion_id") or "luna",
        "companion_name": src.get("companion_name"),
        "user_display_name": src.get("user_display_name"),
        "ui_theme": src.get("ui_theme") or "lilac",
        "ui_hue": src.get("ui_hue"),
        "advisor_style": src.get("advisor_style") or "auto",
        "luna_mode": src.get("luna_mode") or "auto",
        "night_whisper": bool(src.get("night_whisper")),
        "profile_complete": bool(src.get("profile_complete")),
        "current_focus": src.get("current_focus"),
        "current_do_now": src.get("current_do_now"),
        "pending_notification": None
        if looks_secret(src.get("pending_notification"))
        else src.get("pending_notification"),
    }


def sanitize_admin_export_brain(brain: Any) -> Dict[str, Any]:
    src = dict(brain) if isinstance(brain, dict) else {}
    for key in DROP_FROM_ADMIN_BRAIN:
        src.pop(key, None)
    hist = []
    for row in src.get("chat_history") or []:
        if not isinstance(row, dict):
            continue
        item = dict(row)
        content = str(item.get("content") or "")
        if item.get("secret") or item.get("sealed") or content.startswith(SEAL_PREFIX) or looks_secret(content):
            item["content"] = REDACTED
            item["secret"] = True
            item.pop("sealed", None)
        hist.append(item)
    src["chat_history"] = hist[-80:]
    lp = dict(src.get("life_profile") or {})
    for k in ("mental_stress", "mental_support"):
        if k in lp:
            lp[k] = REDACTED
    src["life_profile"] = lp
    return src


def redact_mail_body(text: Any) -> str:
    raw = str(text or "")[:400]
    return redact_text(raw) if looks_secret(raw) else raw
