# -*- coding: utf-8 -*-
"""Risk Radar — burnout / miss-goal / spend / study, each with a 24h rescue quest."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from care_timeline import append_care_event
from exp_engine import grant_exp
from future_twin_service import collect_twin_facts


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_iso(raw: Any) -> Optional[datetime]:
    text = str(raw or "").replace("Z", "+00:00")
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


RESCUES = {
    "burnout": {
        "title_ja": "5分だけ休む",
        "body_ja": "深呼吸かストレッチ。今日は回復がクエスト。",
        "chip": "5分休んだよ",
        "exp": 8,
        "module": "health",
    },
    "overload": {
        "title_ja": "予定を1件片付ける",
        "body_ja": "いちばん近い用事を終わらせて、余白を作ろう。",
        "chip": "予定を1件片付けたよ",
        "exp": 8,
        "module": "schedule",
    },
    "spend": {
        "title_ja": "支出を1件メモする",
        "body_ja": "使った金額を残すだけで、明日のペースが戻る。",
        "chip": "支出をメモしたよ",
        "exp": 6,
        "module": "money",
    },
    "study_slip": {
        "title_ja": "8分だけ次のレッスン",
        "body_ja": "完璧じゃなくていい。短いクエスト1つでリズムが戻る。",
        "chip": "8分学習したよ",
        "exp": 10,
        "module": "study",
    },
    "goal_slip": {
        "title_ja": "目標を1メモリ進める",
        "body_ja": "数字を1つ更新する。小さな前進が遅れを止める。",
        "chip": "目標を進めたよ",
        "exp": 8,
        "module": "goals",
    },
}


def _scan_alerts(facts: Dict[str, Any]) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []
    mental = facts.get("mental")
    load = facts.get("load")
    if load == "recover" or mental in ("落ち込み", "疲れ") and load in ("busy", "heavy", "recover"):
        alerts.append(
            {
                "kind": "burnout",
                "severity": "high" if mental == "落ち込み" or load == "recover" else "mid",
                "title_ja": "燃え尽き注意",
                "body_ja": "心と予定が同時に重いよ。今日は守る番。",
            }
        )
    if load == "heavy":
        alerts.append(
            {
                "kind": "overload",
                "severity": "mid",
                "title_ja": "予定オーバー",
                "body_ja": "今日の枠が満杯。1件片付けると呼吸できる。",
            }
        )
    if facts.get("pace_level") == "warn":
        alerts.append(
            {
                "kind": "spend",
                "severity": "mid",
                "title_ja": "使いすぎ注意",
                "body_ja": "今月のペースが早いよ。記録が先、我慢はあと。",
            }
        )
    if facts.get("career") and int(facts.get("study_week") or 0) == 0:
        alerts.append(
            {
                "kind": "study_slip",
                "severity": "mid",
                "title_ja": "学習リズムが止まってる",
                "body_ja": "今週まだクエスト記録がない。短い一歩で戻そう。",
            }
        )
    if int(facts.get("open_goals") or 0) and int(facts.get("goal_avg") or 0) < 35:
        alerts.append(
            {
                "kind": "goal_slip",
                "severity": "low",
                "title_ja": "目標が遅れそう",
                "body_ja": "進捗が薄い目標がある。1メモリでも今日動かす。",
            }
        )
    if not alerts and load in ("busy",) and int(facts.get("study_week") or 0) == 0:
        alerts.append(
            {
                "kind": "study_slip",
                "severity": "low",
                "title_ja": "今日の余白を学習に",
                "body_ja": "忙しいけど、8分なら未来側に1歩寄せられる。",
            }
        )
    return alerts[:3]


def _prune_quests(user: Dict[str, Any], now: datetime) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    dirty = False
    for row in list(user.get("rescue_quests") or []):
        if not isinstance(row, dict):
            dirty = True
            continue
        exp_at = _parse_iso(row.get("expires_at"))
        if row.get("status") == "open" and exp_at and exp_at < now:
            row = dict(row)
            row["status"] = "expired"
            dirty = True
        kept.append(row)
    user["rescue_quests"] = kept[-24:]
    if dirty:
        user["_radar_dirty"] = True
    return user["rescue_quests"]


def _ensure_quest(user: Dict[str, Any], alert: Dict[str, Any], now: datetime) -> Dict[str, Any]:
    kind = alert["kind"]
    today = now.date().isoformat()
    for row in user.get("rescue_quests") or []:
        if (
            row.get("kind") == kind
            and row.get("status") == "open"
            and str(row.get("created_on") or "")[:10] == today
        ):
            return row
        if (
            row.get("kind") == kind
            and row.get("status") == "done"
            and str(row.get("done_on") or row.get("created_on") or "")[:10] == today
        ):
            return row
    seed = RESCUES[kind]
    quest = {
        "id": "rq_" + uuid4().hex[:10],
        "kind": kind,
        "status": "open",
        "title_ja": seed["title_ja"],
        "body_ja": seed["body_ja"],
        "chip": seed["chip"],
        "exp": seed["exp"],
        "module": seed["module"],
        "created_on": today,
        "expires_at": _iso(now + timedelta(hours=24)),
        "alert_title_ja": alert["title_ja"],
    }
    log = list(user.get("rescue_quests") or [])
    log.append(quest)
    user["rescue_quests"] = log[-24:]
    user["_radar_dirty"] = True
    return quest


def refresh_risk_radar(user: Dict[str, Any], *, now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or _now()
    facts = collect_twin_facts(user)
    alerts = _scan_alerts(facts)
    _prune_quests(user, now)
    quests: List[Dict[str, Any]] = []
    for alert in alerts:
        q = _ensure_quest(user, alert, now)
        row = dict(alert)
        row["rescue"] = q
        quests.append(row)
    open_n = sum(1 for a in quests if (a.get("rescue") or {}).get("status") == "open")
    return {
        "ok": True,
        "title_ja": "リスクレーダー",
        "empty_ja": "今は大きな危険信号なし。この調子で守ろう。",
        "alerts": quests,
        "open_count": open_n,
        "level": "high" if any(a.get("severity") == "high" for a in quests) else ("mid" if quests else "ok"),
    }


def complete_rescue_quest(user: Dict[str, Any], quest_id: str) -> Dict[str, Any]:
    qid = str(quest_id or "").strip()
    now = _now()
    _prune_quests(user, now)
    found = None
    for row in user.get("rescue_quests") or []:
        if row.get("id") == qid:
            found = row
            break
    if not found:
        raise ValueError("rescue quest not found")
    if found.get("status") == "done":
        return {"ok": True, "already": True, "quest": found, "exp_gained": 0}
    if found.get("status") == "expired":
        raise ValueError("rescue quest expired")
    found["status"] = "done"
    found["done_on"] = now.date().isoformat()
    found["done_at"] = _iso(now)
    gain, _ = grant_exp(user, int(found.get("exp") or 6))
    append_care_event(user, "care", f"レスキュー達成：{found.get('title_ja')}", detail=f"+{gain} EXP")
    user["_radar_dirty"] = True
    radar = refresh_risk_radar(user, now=now)
    return {"ok": True, "already": False, "quest": found, "exp_gained": gain, "radar": radar}
