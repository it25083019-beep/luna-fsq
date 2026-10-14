# -*- coding: utf-8 -*-
"""Friends by a one-time QR, or by a coarse nearby hint.

Exact coordinates are never stored, never returned, and never exported.
A presence row keeps only a geohash cell for a few minutes, and only after
the person turns the feature on.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
_CELL_PRECISION = 6
_CODE_MINUTES = 10
_PRESENCE_MINUTES = 20
_MAX_NEARBY = 8
_MAX_TEXT = 200
_MAX_THREAD = 40

Loader = Callable[[str], Dict[str, Any]]
Saver = Callable[[str, Dict[str, Any]], None]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat()


def _parse(raw: Any) -> Optional[datetime]:
    try:
        moment = datetime.fromisoformat(str(raw or ""))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def social_row(user: Dict[str, Any]) -> Dict[str, Any]:
    row = user.get("social")
    if not isinstance(row, dict):
        row = {}
        user["social"] = row
    row.setdefault("friends", [])
    row.setdefault("inbox", [])
    row.setdefault("threads", {})
    if "show_rpg" not in row:
        row["show_rpg"] = True
    if "show_portfolio" not in row:
        row["show_portfolio"] = True
    return row


def _name(user: Dict[str, Any]) -> str:
    return str(user.get("user_display_name") or "なまえ未設定")[:40]


def _friends(user: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [row for row in social_row(user).get("friends") or [] if isinstance(row, dict)]


def is_friend(user: Dict[str, Any], other_id: str) -> bool:
    return any(str(row.get("id") or "") == other_id for row in _friends(user))


def geohash(lat: float, lng: float, precision: int = _CELL_PRECISION) -> str:
    """Rough cell. Precision 6 is about a kilometer, not a street address."""
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        raise ValueError("位置が範囲の外です")
    lat_r = [-90.0, 90.0]
    lng_r = [-180.0, 180.0]
    bits = (16, 8, 4, 2, 1)
    even = True
    bit = 0
    ch = 0
    out: List[str] = []
    while len(out) < precision:
        if even:
            mid = (lng_r[0] + lng_r[1]) / 2
            if lng >= mid:
                ch |= bits[bit]
                lng_r[0] = mid
            else:
                lng_r[1] = mid
        else:
            mid = (lat_r[0] + lat_r[1]) / 2
            if lat >= mid:
                ch |= bits[bit]
                lat_r[0] = mid
            else:
                lat_r[1] = mid
        even = not even
        if bit < 4:
            bit += 1
        else:
            out.append(_BASE32[ch])
            bit = 0
            ch = 0
    return "".join(out)


def _cell_center(cell: str) -> tuple[float, float]:
    lat_r = [-90.0, 90.0]
    lng_r = [-180.0, 180.0]
    even = True
    for ch in cell:
        idx = _BASE32.find(ch)
        if idx < 0:
            break
        for mask in (16, 8, 4, 2, 1):
            if even:
                mid = (lng_r[0] + lng_r[1]) / 2
                if idx & mask:
                    lng_r[0] = mid
                else:
                    lng_r[1] = mid
            else:
                mid = (lat_r[0] + lat_r[1]) / 2
                if idx & mask:
                    lat_r[0] = mid
                else:
                    lat_r[1] = mid
            even = not even
    return (lat_r[0] + lat_r[1]) / 2, (lng_r[0] + lng_r[1]) / 2


def neighbor_cells(cell: str) -> set[str]:
    lat, lng = _cell_center(cell)
    found = set()
    for dy in (-0.012, 0.0, 0.012):
        for dx in (-0.016, 0.0, 0.016):
            found.add(geohash(lat + dy, lng + dx, len(cell)))
    found.add(cell)
    return found


def _hash_code(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_code(user: Dict[str, Any]) -> Dict[str, str]:
    token = secrets.token_urlsafe(6)
    row = social_row(user)
    row["code_hash"] = _hash_code(token)
    row["code_exp"] = _iso(_now() + timedelta(minutes=_CODE_MINUTES))
    row["code_used"] = False
    return {"token": token, "payload": f"LUNA:{token}", "expires_at": row["code_exp"]}


def qr_svg(payload: str) -> str:
    try:
        import segno
    except ImportError:
        return ""
    return segno.make(payload, error="m").svg_inline(scale=4, border=2)


def _link(left_id: str, left: Dict[str, Any], right_id: str, right: Dict[str, Any]) -> None:
    def _add(owner: Dict[str, Any], other_id: str, other: Dict[str, Any]) -> None:
        row = social_row(owner)
        friends = [item for item in row["friends"] if str(item.get("id") or "") != other_id]
        friends.append({"id": other_id, "name": _name(other), "at": _iso(_now())})
        row["friends"] = friends[-40:]
        row["inbox"] = [item for item in row["inbox"] if str(item.get("id") or "") != other_id]

    _add(left, right_id, right)
    _add(right, left_id, left)


def redeem_code(
    scanner_id: str,
    scanner: Dict[str, Any],
    token: str,
    *,
    load: Loader,
    save: Saver,
    ids: List[str],
) -> Dict[str, str]:
    raw = str(token or "").strip()
    if raw.upper().startswith("LUNA:"):
        raw = raw.split(":", 1)[1].strip()
    if len(raw) < 6 or len(raw) > 24:
        raise ValueError("コードが違います")
    digest = _hash_code(raw)
    for other_id in ids:
        if other_id == scanner_id:
            continue
        other = load(other_id)
        row = other.get("social") if isinstance(other.get("social"), dict) else {}
        saved = str(row.get("code_hash") or "")
        if not saved or not hmac.compare_digest(saved, digest):
            continue
        if row.get("code_used"):
            raise ValueError("このコードはもう使われています")
        exp = _parse(row.get("code_exp"))
        if exp is None or exp < _now():
            raise ValueError("コードの期限が切れています")
        row["code_used"] = True
        other["social"] = row
        _link(scanner_id, scanner, other_id, other)
        save(other_id, other)
        save(scanner_id, scanner)
        return {"id": other_id, "name": _name(other)}
    raise ValueError("コードが見つかりません")


def _presence_fresh(row: Dict[str, Any]) -> bool:
    if not row.get("on") or not row.get("cell"):
        return False
    moment = _parse(row.get("at"))
    if moment is None:
        return False
    return _now() - moment <= timedelta(minutes=_PRESENCE_MINUTES)


def set_presence(user: Dict[str, Any], lat: float, lng: float) -> None:
    """Keep a coarse cell only. The coordinates themselves are dropped."""
    cell = geohash(float(lat), float(lng), _CELL_PRECISION)
    social_row(user)["presence"] = {"on": True, "cell": cell, "at": _iso(_now())}


def clear_presence(user: Dict[str, Any]) -> None:
    social_row(user)["presence"] = {"on": False, "cell": "", "at": ""}


def nearby_people(
    me_id: str,
    me: Dict[str, Any],
    *,
    load: Loader,
    ids: List[str],
) -> List[Dict[str, str]]:
    mine = (social_row(me).get("presence") or {}) if isinstance(social_row(me).get("presence"), dict) else {}
    if not _presence_fresh(mine):
        return []
    cells = neighbor_cells(str(mine.get("cell")))
    friend_ids = {str(row.get("id") or "") for row in _friends(me)}
    found: List[Dict[str, str]] = []
    for other_id in ids:
        if other_id == me_id or other_id in friend_ids:
            continue
        other = load(other_id)
        presence = (other.get("social") or {}).get("presence") if isinstance(other.get("social"), dict) else None
        if not isinstance(presence, dict) or not _presence_fresh(presence):
            continue
        if str(presence.get("cell") or "") not in cells:
            continue
        found.append({"id": other_id, "name": _name(other)})
        if len(found) >= _MAX_NEARBY:
            break
    return found


def request_friend(
    me_id: str,
    me: Dict[str, Any],
    other_id: str,
    *,
    load: Loader,
    save: Saver,
    ids: List[str],
) -> None:
    if other_id == me_id or not other_id:
        raise ValueError("その人には頼めません")
    near_ids = {row["id"] for row in nearby_people(me_id, me, load=load, ids=ids)}
    if other_id not in near_ids:
        raise ValueError("近くにいない人には、ここから頼めません")
    other = load(other_id)
    row = social_row(other)
    if is_friend(other, me_id):
        return
    inbox = [item for item in row["inbox"] if str(item.get("id") or "") != me_id]
    inbox.append({"id": me_id, "name": _name(me), "at": _iso(_now())})
    row["inbox"] = inbox[-20:]
    save(other_id, other)


def accept_friend(
    me_id: str,
    me: Dict[str, Any],
    other_id: str,
    *,
    load: Loader,
    save: Saver,
) -> Dict[str, str]:
    row = social_row(me)
    if not any(str(item.get("id") or "") == other_id for item in row["inbox"]):
        raise ValueError("そのお願いはありません")
    other = load(other_id)
    _link(me_id, me, other_id, other)
    save(other_id, other)
    save(me_id, me)
    return {"id": other_id, "name": _name(other)}


def remove_friend(
    me_id: str,
    me: Dict[str, Any],
    other_id: str,
    *,
    load: Loader,
    save: Saver,
) -> None:
    def _drop(owner: Dict[str, Any], gone: str) -> None:
        row = social_row(owner)
        row["friends"] = [item for item in row["friends"] if str(item.get("id") or "") != gone]
        row["inbox"] = [item for item in row["inbox"] if str(item.get("id") or "") != gone]
        threads = row.get("threads") if isinstance(row.get("threads"), dict) else {}
        threads.pop(gone, None)
        row["threads"] = threads

    _drop(me, other_id)
    try:
        other = load(other_id)
    except Exception:
        other = None
    if isinstance(other, dict):
        _drop(other, me_id)
        save(other_id, other)
    save(me_id, me)


def public_card(me: Dict[str, Any], other_id: str, other: Dict[str, Any]) -> Dict[str, Any]:
    if not is_friend(me, other_id):
        raise ValueError("友だちだけが見られます")
    row = social_row(other)
    card: Dict[str, Any] = {"id": other_id, "name": _name(other)}
    if row.get("show_rpg", True):
        card["level"] = int(other.get("current_level") or 1)
        card["companion"] = str(other.get("companion_name") or "")
        title = ""
        rank = ""
        try:
            from career_portfolio import build_career_portfolio

            built = build_career_portfolio(other)
            title = str(built.get("career_title_ja") or "")
            rank = str(built.get("rank_ja") or "")
        except Exception:
            title = ""
        card["path"] = title
        card["rank"] = rank
    if row.get("show_portfolio", True):
        journey = ((other.get("rpg") or {}).get("journey") or {})
        card["works"] = len(journey.get("portfolio_evidence") or [])
        card["lessons"] = len(journey.get("completed_lessons") or [])
    return card


def set_showcase(user: Dict[str, Any], *, show_rpg: bool, show_portfolio: bool) -> None:
    row = social_row(user)
    row["show_rpg"] = bool(show_rpg)
    row["show_portfolio"] = bool(show_portfolio)


def _thread(user: Dict[str, Any], other_id: str) -> List[Dict[str, Any]]:
    threads = social_row(user).get("threads")
    if not isinstance(threads, dict):
        return []
    rows = threads.get(other_id) or []
    return [row for row in rows if isinstance(row, dict)]


def read_chat(me: Dict[str, Any], other_id: str) -> List[Dict[str, str]]:
    if not is_friend(me, other_id):
        raise ValueError("友だちだけが話せます")
    out = []
    for row in _thread(me, other_id):
        out.append(
            {
                "mine": bool(row.get("mine")),
                "text": str(row.get("text") or ""),
                "at": str(row.get("at") or ""),
            }
        )
    return out


def send_chat(
    me_id: str,
    me: Dict[str, Any],
    other_id: str,
    text: str,
    *,
    load: Loader,
    save: Saver,
) -> Dict[str, str]:
    if not is_friend(me, other_id):
        raise ValueError("友だちだけが話せます")
    body = " ".join(str(text or "").split())
    if not body:
        raise ValueError("文が空です")
    body = body[:_MAX_TEXT]
    stamp = _iso(_now())
    other = load(other_id)
    if not is_friend(other, me_id):
        raise ValueError("友だちだけが話せます")

    def _append(owner: Dict[str, Any], peer: str, mine: bool) -> None:
        row = social_row(owner)
        threads = row.get("threads") if isinstance(row.get("threads"), dict) else {}
        thread = [item for item in (threads.get(peer) or []) if isinstance(item, dict)]
        thread.append({"mine": mine, "text": body, "at": stamp})
        threads[peer] = thread[-_MAX_THREAD:]
        row["threads"] = threads

    _append(me, other_id, True)
    _append(other, me_id, False)
    save(other_id, other)
    save(me_id, me)
    return {"text": body, "at": stamp}


def summary(user: Dict[str, Any]) -> Dict[str, Any]:
    row = social_row(user)
    presence = row.get("presence") if isinstance(row.get("presence"), dict) else {}
    return {
        "friends": [{"id": str(item.get("id") or ""), "name": str(item.get("name") or "")} for item in _friends(user)],
        "inbox": [
            {"id": str(item.get("id") or ""), "name": str(item.get("name") or "")}
            for item in row.get("inbox") or []
            if isinstance(item, dict)
        ],
        "nearby_on": _presence_fresh(presence),
        "show_rpg": bool(row.get("show_rpg", True)),
        "show_portfolio": bool(row.get("show_portfolio", True)),
    }
