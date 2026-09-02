"""Extract and validate user display names from free-text onboarding/chat."""
from __future__ import annotations

import re
from typing import Optional

# Phrases that must never become a stored display name.
_BLOCKED_NAME = re.compile(
    r"相談|consult|体調|お金|予定|健康に|支出|貯金|help\s*me|quiero|question|"
    r"教えて|整理|元気|疲れ|バイト|勉強",
    re.I,
)

_NAME_PATTERNS = [
  re.compile(r"(?:me\s+llamo|mi\s+nombre\s+es|soy)\s+(.+)", re.I),
  re.compile(r"(?:my\s+name\s+is|i\s*['']?m|i\s+am)\s+(.+)", re.I),
  re.compile(r"(?:私の名前は|僕の名前は|俺の名前は|名前は|なまえは)\s*[、,:]?\s*(.+)", re.I),
  re.compile(r"^(?:私は|僕は|俺は|わたしは)\s*(.+)", re.I),
  re.compile(r"^(.+?)\s+(?:です|だよ|だ|といいます|と申します|って言います|っていいます|と言います)$", re.I),
]


def extract_display_name(raw: Optional[str]) -> str:
    """Pull a short personal name from onboarding / intro sentences."""
    text = (raw or "").strip()
    if not text:
        return ""

    for pat in _NAME_PATTERNS:
        m = pat.match(text)
        if m:
            text = (m.group(1) or "").strip()
            break

    text = re.sub(r"^(?:私は|僕は|俺は|わたしは|名前は|自分は|呼び名は)", "", text)
    m = re.match(r"^(.+?)(?:でいい|で良い|がいい|が良い|にして|でお願い|でお願いします).*$", text)
    if m:
        text = m.group(1)

    text = re.sub(
        r"(?:です|だよ|だ|といいます|と申します|っていうの|って呼ばれてる|と言います).*$",
        "",
        text,
    )
    text = text.strip(" 　。.、,!！?？「」『』\"'")

    if "、" in text or "," in text:
        for part in re.split(r"[、,]", text):
            part = part.strip()
            if part and len(part) <= 20 and not _BLOCKED_NAME.search(part):
                text = part
                break

    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 20:
        text = text[:20].strip()
    return text


def is_valid_display_name(name: Optional[str]) -> bool:
    n = (name or "").strip()
    if not n or len(n) > 20:
        return False
    if _BLOCKED_NAME.search(n):
        return False
    if re.search(r"[。!?？]{1,}", n):
        return False
    if len(n.split()) > 4:
        return False
    return True


def sanitize_display_name(raw: Optional[str]) -> str:
    """Return cleaned name or empty string if unusable."""
    cleaned = extract_display_name(raw)
    return cleaned if is_valid_display_name(cleaned) else ""
