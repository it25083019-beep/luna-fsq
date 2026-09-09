# -*- coding: utf-8 -*-
"""Pull todos from mail (paste or Gmail OAuth) and add them to the schedule.

Never stores raw inbox bodies. OAuth only — no email passwords.
"""
from __future__ import annotations

import base64
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import requests

from day_coach import JST

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
_OAUTH_PATH = Path(__file__).resolve().parent / "data" / "google_oauth.json"

_WEEKDAY_JA = {
    "月": 0,
    "火": 1,
    "水": 2,
    "木": 3,
    "金": 4,
    "土": 5,
    "日": 6,
}
_TASK_HINT = re.compile(
    r"提出|課題|レポート|発表|試験|テスト|会議|ミーティング|打ち合わせ|"
    r"面接|予約|締切|締め切り|出席|登校|休講|授業変更|課題提出|"
    r"meeting|deadline|interview|assignment|exam|submit",
    re.I,
)
_SKIP_HINT = re.compile(
    r"配信停止|unsubscribe|newsletter|広告|セール|promo|キャンペーン|"
    r"no-reply|noreply|メルマガ|領収|receipt|invoice|shipping|delivered|"
    r"ポイントが|クーポン|お得な情報",
    re.I,
)
_URGENT_HINT = re.compile(
    r"至急|緊急|今日中|本日中|asap|締切|締め切り|deadline|必ず|important|urgent",
    re.I,
)
_PLACE_HINT = re.compile(
    r"(?:場所|会場|集合)[:：]\s*([^\s。\n]{2,40})"
    r"|(教室\s*[A-Za-z0-9０-９\-ー]{1,12})"
    r"|(会議室\s*[A-Za-z0-9０-９\-ー]{0,12})"
    r"|([A-Za-zＡ-Ｚ]棟[0-9０-９]{1,5})"
    r"|(?:にて)\s*([^\s。\n]{2,40})"
)


def _oauth_file() -> Dict[str, Any]:
    try:
        data = json.loads(_OAUTH_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _core_oauth() -> Dict[str, Any]:
    try:
        from luna_service import load_core_brain

        core = load_core_brain() or {}
        row = core.get("google_oauth")
        return row if isinstance(row, dict) else {}
    except Exception:
        return {}


def oauth_client_id() -> str:
    return (
        (os.getenv("GOOGLE_OAUTH_CLIENT_ID") or "").strip()
        or str(_oauth_file().get("client_id") or "").strip()
        or str(_core_oauth().get("client_id") or "").strip()
    )


def oauth_client_secret() -> str:
    return (
        (os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or "").strip()
        or str(_oauth_file().get("client_secret") or "").strip()
        or str(_core_oauth().get("client_secret") or "").strip()
    )


def oauth_configured() -> bool:
    return bool(oauth_client_id())


def save_oauth_app_credentials(client_id: str, client_secret: str = "") -> Dict[str, Any]:
    cid = (client_id or "").strip()
    if not cid:
        raise ValueError("client_id is required")
    data = _oauth_file()
    data["client_id"] = cid
    secret = (client_secret or "").strip()
    if secret:
        data["client_secret"] = secret
    _OAUTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OAUTH_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    try:
        from luna_service import load_core_brain, save_core_brain

        core = load_core_brain() or {}
        row = dict(core.get("google_oauth") or {})
        row["client_id"] = cid
        if secret:
            row["client_secret"] = secret
        core["google_oauth"] = row
        save_core_brain(core)
    except Exception:
        pass
    return {"client_id": cid, "has_secret": bool(oauth_client_secret())}


def oauth_redirect_uri(base_url: str) -> str:
    return (base_url or "").rstrip("/") + "/mail/google/callback"


def oauth_authorize_url(*, state: str, base_url: str) -> str:
    client_id = oauth_client_id()
    params = {
        "client_id": client_id,
        "redirect_uri": oauth_redirect_uri(base_url),
        "response_type": "code",
        "scope": GMAIL_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return AUTH_URL + "?" + urlencode(params)


def exchange_code(code: str, *, base_url: str) -> Dict[str, Any]:
    client_id = oauth_client_id()
    client_secret = oauth_client_secret()
    if not client_id:
        raise ValueError("Gmailの連携に失敗しました")
    payload = {
        "code": code,
        "client_id": client_id,
        "redirect_uri": oauth_redirect_uri(base_url),
        "grant_type": "authorization_code",
    }
    if client_secret:
        payload["client_secret"] = client_secret
    res = requests.post(TOKEN_URL, data=payload, timeout=20)
    if res.status_code >= 400:
        raise ValueError("Gmailの連携に失敗しました")
    data = res.json()
    if not data.get("refresh_token") and not data.get("access_token"):
        raise ValueError("Gmailのトークンを取得できませんでした")
    return data


def _refresh_access(user: Dict[str, Any]) -> Optional[str]:
    link = user.get("mail_link") or {}
    token = str(link.get("access_token") or "")
    exp = str(link.get("expires_at") or "")
    try:
        if token and exp:
            when = datetime.fromisoformat(exp.replace("Z", "+00:00"))
            if when > datetime.now(timezone.utc) + timedelta(minutes=2):
                return token
    except ValueError:
        pass
    refresh = str(link.get("refresh_token") or "")
    if not refresh:
        return token or None
    res = requests.post(
        TOKEN_URL,
        data={
            "client_id": oauth_client_id(),
            "client_secret": oauth_client_secret(),
            "refresh_token": refresh,
            "grant_type": "refresh_token",
        },
        timeout=20,
    )
    if res.status_code >= 400:
        return None
    data = res.json()
    access = data.get("access_token")
    if not access:
        return None
    link["access_token"] = access
    secs = int(data.get("expires_in") or 3500)
    link["expires_at"] = (datetime.now(timezone.utc) + timedelta(seconds=secs)).isoformat()
    if data.get("refresh_token"):
        link["refresh_token"] = data["refresh_token"]
    user["mail_link"] = link
    return access


def save_mail_tokens(user: Dict[str, Any], token_payload: Dict[str, Any]) -> None:
    link = dict(user.get("mail_link") or {})
    if token_payload.get("refresh_token"):
        link["refresh_token"] = token_payload["refresh_token"]
    if token_payload.get("access_token"):
        link["access_token"] = token_payload["access_token"]
        secs = int(token_payload.get("expires_in") or 3500)
        link["expires_at"] = (datetime.now(timezone.utc) + timedelta(seconds=secs)).isoformat()
    link["provider"] = "google"
    link["connected_at"] = datetime.now(timezone.utc).isoformat()
    user["mail_link"] = link


def disconnect_mail(user: Dict[str, Any]) -> None:
    user["mail_link"] = {}


def make_oauth_state(public_id: str) -> str:
    from datetime import datetime, timedelta, timezone as tz

    from jose import jwt

    from auth_security import JWT_ALGORITHM, JWT_SECRET

    exp = datetime.now(tz.utc) + timedelta(minutes=20)
    return jwt.encode(
        {"sub": public_id, "purpose": "gmail", "exp": exp},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def read_oauth_state(state: str) -> str:
    from jose import JWTError, jwt

    from auth_security import JWT_ALGORITHM, JWT_SECRET

    try:
        payload = jwt.decode(state or "", JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as e:
        raise ValueError("invalid state") from e
    if payload.get("purpose") != "gmail":
        raise ValueError("invalid state")
    public_id = payload.get("sub")
    if not public_id:
        raise ValueError("invalid state")
    return str(public_id)


def mail_status(user: Dict[str, Any], *, public_base: str = "") -> Dict[str, Any]:
    link = user.get("mail_link") or {}
    connected = bool(link.get("refresh_token") or link.get("access_token"))
    base = (public_base or os.getenv("APP_BASE_URL") or "").rstrip("/")
    return {
        "oauth_ready": oauth_configured(),
        "has_secret": bool(oauth_client_secret()),
        "client_id": oauth_client_id(),
        "connected": connected,
        "provider": link.get("provider") if connected else None,
        "last_sync": link.get("last_sync"),
        "imported_total": int(link.get("imported_total") or 0),
        "js_origin": base,
        "redirect_uri": oauth_redirect_uri(base) if base else "",
    }


def _today() -> date:
    return datetime.now(JST).date()


def _norm_urgency(raw: Optional[str], *, text: str = "") -> str:
    val = (raw or "").strip().lower()
    if val in ("high", "urgent", "至急"):
        return "high"
    if val in ("low",):
        return "low"
    if _URGENT_HINT.search(text or ""):
        return "high"
    return "normal"


def parse_when(text: str, *, today: Optional[date] = None) -> Tuple[str, Optional[str]]:
    """Return (YYYY-MM-DD, HH:MM or None) from Japanese/English mail text."""
    today = today or _today()
    blob = text or ""
    day = today

    if re.search(r"明後日", blob):
        day = today + timedelta(days=2)
    elif re.search(r"明日", blob):
        day = today + timedelta(days=1)
    elif re.search(r"今日|本日", blob):
        day = today

    m = re.search(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日", blob)
    if m:
        day = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    else:
        m = re.search(r"(\d{1,2})月\s*(\d{1,2})日", blob)
        if m:
            month, d = int(m.group(1)), int(m.group(2))
            year = today.year
            try:
                day = date(year, month, d)
            except ValueError:
                day = today
            if day < today - timedelta(days=14):
                try:
                    day = date(year + 1, month, d)
                except ValueError:
                    pass
        else:
            m = re.search(r"来週の?([月火水木金土日])", blob)
            if m:
                target = _WEEKDAY_JA.get(m.group(1), today.weekday())
                delta = (target - today.weekday()) % 7
                day = today + timedelta(days=delta + 7)

    clock: Optional[str] = None
    m = re.search(r"(?:午後|pm)\s*(\d{1,2})(?:[:：時](\d{2}))?", blob, re.I)
    if m:
        h = int(m.group(1))
        if h < 12:
            h += 12
        mi = int(m.group(2) or 0)
        clock = f"{h:02d}:{mi:02d}"
    else:
        m = re.search(r"(?:午前|am)\s*(\d{1,2})(?:[:：時](\d{2}))?", blob, re.I)
        if m:
            h = int(m.group(1)) % 12
            mi = int(m.group(2) or 0)
            clock = f"{h:02d}:{mi:02d}"
        else:
            m = re.search(r"(\d{1,2})[:：](\d{2})", blob)
            if m:
                h, mi = int(m.group(1)), int(m.group(2))
                if 0 <= h <= 23 and 0 <= mi <= 59:
                    clock = f"{h:02d}:{mi:02d}"
            else:
                m = re.search(r"(\d{1,2})時(?:(\d{1,2})分)?", blob)
                if m:
                    h = int(m.group(1))
                    mi = int(m.group(2) or 0)
                    if 0 <= h <= 23:
                        clock = f"{h:02d}:{mi:02d}"

    if clock is None:
        return day.isoformat(), None
    return day.isoformat(), clock


def parse_location(text: str) -> Optional[str]:
    m = _PLACE_HINT.search(text or "")
    if not m:
        return None
    loc = next((g for g in m.groups() if g), "")
    loc = loc.strip(" 　「」『』")
    return loc[:80] or None


def _action_title(subject: str, body: str) -> str:
    blob = (subject or "") + " " + (body or "")
    if re.search(r"面接|interview", blob, re.I):
        return "面接"
    if re.search(r"会議|ミーティング|打ち合わせ|meeting", blob, re.I):
        return "打ち合わせ"
    if re.search(r"提出|課題|assignment|レポート", blob, re.I):
        return "課題提出"
    if re.search(r"試験|テスト|exam", blob, re.I):
        return "試験"
    if re.search(r"予約", blob):
        return "予約"
    sub = re.sub(r"^(re|fwd|fw|返信|転送)[:：\s]+", "", (subject or "").strip(), flags=re.I)
    sub = re.sub(r"[\r\n]+", " ", sub).strip()
    return (sub or "用事")[:40]


def _urgency_from_when(
    event_date: str,
    event_time: Optional[str],
    text: str,
    *,
    today: Optional[date] = None,
) -> str:
    if _URGENT_HINT.search(text or ""):
        return "high"
    today = today or _today()
    try:
        day = date.fromisoformat(event_date[:10])
    except ValueError:
        return "normal"
    clock = None
    if event_time and ":" in event_time:
        try:
            parts = event_time.split(":")
            clock = datetime.combine(day, datetime.min.time().replace(hour=int(parts[0]), minute=int(parts[1])), tzinfo=JST)
        except (TypeError, ValueError):
            clock = None
    now = datetime.now(JST)
    if clock:
        hours = (clock - now).total_seconds() / 3600
        if hours <= 12:
            return "high"
        if hours <= 48:
            return "normal"
        return "low"
    delta_days = (day - today).days
    if delta_days <= 0:
        return "high"
    if delta_days <= 1:
        return "normal"
    return "low"


def extract_tasks_from_text(
    raw: str,
    *,
    subject: str = "",
    today: Optional[date] = None,
) -> List[Dict[str, Any]]:
    blob = ((subject or "") + "\n" + (raw or "")).strip()
    if len(blob) < 4:
        return []
    if _SKIP_HINT.search(blob) and not _TASK_HINT.search(blob):
        return []
    if not _TASK_HINT.search(blob):
        return []
    event_date, event_time = parse_when(blob, today=today)
    loc = parse_location(blob)
    urgency = _urgency_from_when(event_date, event_time, blob, today=today)
    title = _action_title(subject, raw)
    return [
        {
            "title": title,
            "date": event_date,
            "time": event_time,
            "location": loc,
            "urgency": urgency,
            "note": None,
            "source": "email",
        }
    ]


def _might_be_task(subject: str, body: str) -> bool:
    blob = (subject or "") + "\n" + (body or "")
    if _SKIP_HINT.search(blob) and not _TASK_HINT.search(blob):
        return False
    return bool(_TASK_HINT.search(blob))


def _refine_with_llm(
    candidates: List[Dict[str, str]],
    *,
    today: Optional[date] = None,
) -> Dict[int, Dict[str, Any]]:
    """Map candidate index → understood task. Empty dict on failure."""
    if not candidates:
        return {}
    today = today or _today()
    try:
        from luna_service import generate_json_task
    except Exception:
        return {}
    if generate_json_task is None:
        return {}
    payload = []
    for i, row in enumerate(candidates[:8]):
        payload.append(
            {
                "i": i,
                "subject": (row.get("subject") or "")[:120],
                "body": (row.get("body") or "")[:500],
            }
        )
    system = (
        "学生の予定係。メールから本人がやる用事だけ取り出す。"
        "JSONのみ。形式: {\"items\":[{\"i\":0,\"task\":true,\"action\":\"課題を提出する\","
        "\"date\":\"YYYY-MM-DD\",\"time\":\"HH:MM\",\"location\":\"教室B\",\"urgency\":\"high\"}]}"
        "task=false は広告・お知らせ・領収・お礼・メルマガ。"
        "actionは短い日本語（何をするか）。件名のコピペ禁止。"
        "urgency: 12時間以内や至急/今日中なら high。2日以内なら normal。それ以外 low。"
        f"今日は{today.isoformat()}。"
        "date/time不明なら null。"
    )
    parsed = generate_json_task(
        system,
        json.dumps({"today": today.isoformat(), "mails": payload}, ensure_ascii=False),
        max_tokens=900,
    )
    if not isinstance(parsed, dict):
        return {}
    items = parsed.get("items") or parsed.get("tasks") or []
    out: Dict[int, Dict[str, Any]] = {}
    if not isinstance(items, list):
        return {}
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("i") if item.get("i") is not None else item.get("subject_index") or -1)
        except (TypeError, ValueError):
            continue
        if idx < 0 or idx >= len(candidates):
            continue
        task_flag = item.get("task", item.get("is_task"))
        if task_flag is False or str(task_flag).lower() in ("false", "no", "0"):
            out[idx] = {"skip": True}
            continue
        action = str(item.get("action") or item.get("title") or "").strip()[:40]
        if task_flag is not True and str(task_flag).lower() not in ("true", "1", "yes"):
            if not action:
                out[idx] = {"skip": True}
                continue
        elif not action:
            out[idx] = {"skip": True}
            continue
        ds = str(item.get("date") or "").strip()[:10]
        if ds.lower() in ("null", "none"):
            ds = ""
        tm = str(item.get("time") or "").strip() or None
        if tm and tm.lower() in ("null", "none"):
            tm = None
        if tm and not re.match(r"^\d{2}:\d{2}$", tm):
            tm = None
        if not ds:
            heur = extract_tasks_from_text(
                candidates[idx].get("body") or "",
                subject=candidates[idx].get("subject") or "",
                today=today,
            )
            if heur:
                ds = heur[0]["date"]
                tm = tm or heur[0].get("time")
            else:
                out[idx] = {"skip": True}
                continue
        urg = str(item.get("urgency") or "normal").lower()
        if urg not in ("high", "normal", "low"):
            urg = "normal"
        out[idx] = {
            "title": action,
            "date": ds,
            "time": tm,
            "location": (str(item.get("location") or "").strip()[:80] or None),
            "urgency": urg,
            "note": None,
            "source": "email",
        }
    return out


def import_extracted_tasks(user: Dict[str, Any], tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from schedule_service import add_event, event_exists

    added: List[Dict[str, Any]] = []
    for task in tasks:
        title = (task.get("title") or "").strip()
        ds = (task.get("date") or "")[:10]
        if not title or not ds:
            continue
        if event_exists(user, title, ds, task.get("time")):
            continue
        try:
            ev = add_event(
                user,
                title=title,
                event_date=ds,
                event_time=task.get("time"),
                note=task.get("note"),
                location=task.get("location"),
                urgency=task.get("urgency") or "normal",
                source=task.get("source") or "email",
            )
        except ValueError:
            continue
        added.append(ev)
    return added


def import_pasted_mail(user: Dict[str, Any], raw: str, *, subject: str = "") -> Dict[str, Any]:
    tasks = extract_tasks_from_text(raw, subject=subject)
    added = import_extracted_tasks(user, tasks)
    return {"ok": True, "found": len(tasks), "added": added, "count": len(added)}


def _decode_b64(data: str) -> str:
    pad = "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(data + pad).decode("utf-8", "replace")
    except Exception:
        return ""


def _gmail_plain(payload: Dict[str, Any]) -> str:
    if not payload:
        return ""
    mime = (payload.get("mimeType") or "").lower()
    body = payload.get("body") or {}
    data = body.get("data")
    if mime.startswith("text/plain") and data:
        return _decode_b64(data)
    if mime.startswith("text/html") and data and not payload.get("parts"):
        html = _decode_b64(data)
        return re.sub(r"<[^>]+>", " ", html)
    chunks = []
    for part in payload.get("parts") or []:
        text = _gmail_plain(part)
        if text:
            chunks.append(text)
    return "\n".join(chunks)


def _gmail_headers(payload: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for row in (payload or {}).get("headers") or []:
        name = str(row.get("name") or "").lower()
        if name in ("subject", "from", "date"):
            out[name] = str(row.get("value") or "")
    return out


def sync_gmail(user: Dict[str, Any], *, max_messages: int = 12) -> Dict[str, Any]:
    access = _refresh_access(user)
    if not access:
        if not oauth_configured():
            return {"ok": False, "error": "oauth_not_configured", "added": [], "count": 0}
        return {"ok": False, "error": "not_connected", "added": [], "count": 0}
    headers = {"Authorization": f"Bearer {access}"}
    try:
        listing = requests.get(
            f"{GMAIL_API}/messages",
            headers=headers,
            params={"q": "newer_than:4d -category:promotions -category:social", "maxResults": max_messages},
            timeout=20,
        )
    except requests.RequestException:
        return {"ok": False, "error": "network", "added": [], "count": 0}
    if listing.status_code == 401:
        return {"ok": False, "error": "auth", "added": [], "count": 0}
    if listing.status_code >= 400:
        return {"ok": False, "error": "gmail", "added": [], "count": 0}
    ids = [m.get("id") for m in (listing.json().get("messages") or []) if m.get("id")]
    link = dict(user.get("mail_link") or {})
    seen = list(link.get("seen_ids") or [])
    seen_set = set(seen)
    candidates: List[Dict[str, str]] = []
    for mid in ids:
        if mid in seen_set:
            continue
        try:
            msg = requests.get(
                f"{GMAIL_API}/messages/{mid}",
                headers=headers,
                params={"format": "full"},
                timeout=20,
            )
        except requests.RequestException:
            continue
        if msg.status_code >= 400:
            continue
        data = msg.json()
        payload = data.get("payload") or {}
        meta = _gmail_headers(payload)
        subject = meta.get("subject") or ""
        body = _gmail_plain(payload) or (data.get("snippet") or "")
        seen.append(mid)
        seen_set.add(mid)
        if not _might_be_task(subject, body):
            continue
        candidates.append({"id": mid, "subject": subject, "body": body})
        if len(candidates) >= 8:
            break
    refined = _refine_with_llm(candidates)
    tasks: List[Dict[str, Any]] = []
    for i, cand in enumerate(candidates):
        row = refined.get(i) if refined else None
        if row and row.get("skip"):
            continue
        if row and not row.get("skip"):
            tasks.append(row)
            continue
        tasks.extend(extract_tasks_from_text(cand.get("body") or "", subject=cand.get("subject") or ""))
    added = import_extracted_tasks(user, tasks)
    link["seen_ids"] = seen[-80:]
    link["last_sync"] = datetime.now(timezone.utc).isoformat()
    link["imported_total"] = int(link.get("imported_total") or 0) + len(added)
    user["mail_link"] = link
    return {"ok": True, "added": added, "count": len(added), "scanned": len(ids)}
