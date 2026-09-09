# -*- coding: utf-8 -*-
"""Web Push so reminders reach a phone after the tab is closed."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

_VAPID_PATH = Path(__file__).resolve().parent / "data" / "vapid.json"


def _b64url(raw: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def vapid_keys() -> Dict[str, str]:
    priv = (os.getenv("VAPID_PRIVATE_KEY") or "").strip()
    pub = (os.getenv("VAPID_PUBLIC_KEY") or "").strip()
    if priv and pub:
        return {"private_key": priv, "public_key": pub}
    if _VAPID_PATH.exists():
        try:
            data = json.loads(_VAPID_PATH.read_text(encoding="utf-8"))
            if data.get("private_key") and data.get("public_key"):
                return {"private_key": data["private_key"], "public_key": data["public_key"]}
        except (OSError, ValueError):
            pass
    key = ec.generate_private_key(ec.SECP256R1())
    priv_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    nums = key.public_key().public_numbers()
    raw = b"\x04" + nums.x.to_bytes(32, "big") + nums.y.to_bytes(32, "big")
    data = {"private_key": priv_pem, "public_key": _b64url(raw)}
    _VAPID_PATH.parent.mkdir(parents=True, exist_ok=True)
    _VAPID_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def public_key() -> str:
    return vapid_keys()["public_key"]


def save_subscription(user: Dict[str, Any], subscription: Dict[str, Any]) -> None:
    endpoint = str((subscription or {}).get("endpoint") or "")
    keys = (subscription or {}).get("keys") or {}
    if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
        raise ValueError("invalid push subscription")
    user["push_subscription"] = {
        "endpoint": endpoint,
        "keys": {"p256dh": keys["p256dh"], "auth": keys["auth"]},
    }


def clear_subscription(user: Dict[str, Any]) -> None:
    user["push_subscription"] = None


def send_push(user: Dict[str, Any], *, title: str, body: str, **extra: Any) -> bool:
    sub = user.get("push_subscription")
    if not isinstance(sub, dict) or not sub.get("endpoint"):
        return False
    try:
        from pywebpush import webpush
    except ImportError:
        return False
    keys = vapid_keys()
    payload = json.dumps(
        {
            "title": title,
            "body": body,
            "id": extra.get("id") or "luna",
            "url": extra.get("url") or "/app",
            "require_interaction": extra.get("require_interaction"),
            "tag": extra.get("id") or "luna",
        },
        ensure_ascii=False,
    )
    claims = {"sub": os.getenv("VAPID_MAILTO") or "mailto:admin@luna.local"}
    try:
        webpush(
            subscription_info=sub,
            data=payload.encode("utf-8"),
            vapid_private_key=keys["private_key"],
            vapid_claims=claims,
        )
        return True
    except Exception as exc:
        text = str(exc)
        if "410" in text or "404" in text:
            clear_subscription(user)
        return False


def flush_due_pushes(user: Dict[str, Any], reminders: Optional[List[Dict[str, Any]]] = None) -> int:
    """Send Web Push for reminders that should already have fired."""
    if not user.get("notify_schedule") or not user.get("push_subscription"):
        return 0
    if reminders is None:
        from day_coach import assess_day_load, build_today_reminders

        reminders = build_today_reminders(user, fit=assess_day_load(user)).get("reminders") or []
    sent = list(user.get("push_sent_ids") or [])
    sent_set = set(sent)
    now = datetime.now(timezone.utc)
    n = 0
    for row in reminders:
        rid = str(row.get("id") or "")
        if not rid or rid in sent_set:
            continue
        raw = str(row.get("fire_at") or "")
        try:
            when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when > now:
            continue
        ok = send_push(
            user,
            title=str(row.get("title") or "LUNA"),
            body=str(row.get("body") or ""),
            id=rid,
            url=row.get("url") or "/app",
            require_interaction=row.get("require_interaction"),
        )
        if ok:
            sent.append(rid)
            sent_set.add(rid)
            n += 1
    if n:
        user["push_sent_ids"] = sent[-80:]
    return n
