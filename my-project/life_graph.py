# -*- coding: utf-8 -*-
"""A few life facts that grow with use: sleep, money, a plan, a goal, last tired day.

Not a chat transcript. Each node is one thing LUNA can cite or act on.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


_SOURCE_JA = {
    "chat": "話したこと",
    "health": "健康の記録",
    "money": "お金の記録",
    "calendar": "予定",
    "goal": "目標",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _nodes(user: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = (user.get("life_graph") or {}).get("nodes")
    if not isinstance(raw, list):
        return []
    return [n for n in raw if isinstance(n, dict) and n.get("id")]


def upsert_node(
    user: Dict[str, Any],
    node_id: str,
    *,
    kind: str,
    label: str,
    value: str,
    source: str,
) -> None:
    value = (value or "").strip()[:40]
    if not value:
        return
    kept = [n for n in _nodes(user) if n.get("id") != node_id]
    kept.append(
        {
            "id": node_id,
            "kind": kind,
            "label": label,
            "value": value,
            "source": source,
            "at": _now(),
        }
    )
    user["life_graph"] = {"nodes": kept[-6:]}


def remember_applied(user: Dict[str, Any], applied: List[str], text: str = "") -> None:
    """Write graph nodes from a chat that already saved a fact."""
    blob = text or ""
    for tag in applied or []:
        if tag.startswith("睡眠→"):
            upsert_node(
                user, "sleep", kind="habit", label="睡眠", value=tag.replace("睡眠→", ""), source="health"
            )
        elif tag.startswith("支出+"):
            upsert_node(
                user, "spend", kind="constraint", label="支出", value=tag.replace("支出+", ""), source="money"
            )
        elif tag == "予定を追加":
            upsert_node(user, "plan", kind="habit", label="予定", value=_plan_value(blob), source="calendar")
        elif tag.startswith("目標"):
            title = tag
            if "「" in tag and "」" in tag:
                title = tag.split("「", 1)[1].split("」", 1)[0]
            upsert_node(user, "goal", kind="goal", label="目標", value=title, source="goal")
        elif tag.startswith("気分→"):
            upsert_node(
                user, "mood", kind="decision", label="気分", value=tag.replace("気分→", ""), source="chat"
            )
    if "眠れない" in blob or "眠れなか" in blob:
        upsert_node(user, "night", kind="decision", label="夜", value="眠れないと言った", source="chat")


def _plan_value(text: str) -> str:
    for key in ("課題提出", "課題", "バイト", "授業", "会議", "テスト", "面接", "予約"):
        if key in (text or ""):
            return key
    cleaned = (text or "").strip()
    return cleaned[:24] or "予定"


def done_sentence(applied: List[str]) -> str:
    """One short confirmation that the chat wrote something down."""
    bits: List[str] = []
    for tag in applied or []:
        if tag.startswith("支出+"):
            bits.append(f"{tag.replace('支出+', '')}、記録した。")
        elif tag == "予定を追加":
            bits.append("予定に入れた。")
        elif tag.startswith("睡眠→"):
            bits.append(f"睡眠{tag.replace('睡眠→', '')}、残した。")
        elif tag.startswith("目標「"):
            bits.append("目標に入れた。")
        if len(bits) == 2:
            break
    return "".join(bits)


def sync_life_graph(user: Dict[str, Any]) -> bool:
    """Refresh nodes from saved modules. Returns True when the graph changed."""
    import json

    before = json.dumps(user.get("life_graph") or {}, ensure_ascii=False, sort_keys=True)
    health = ((user.get("life_modules") or {}).get("health") or {}).get("structured") or {}
    money = ((user.get("life_modules") or {}).get("money") or {}).get("structured") or {}
    sleep = health.get("sleep_hours")
    try:
        sleep_n = float(sleep) if sleep not in (None, "") else None
    except (TypeError, ValueError):
        sleep_n = None
    if sleep_n is not None and 0 < sleep_n <= 14:
        upsert_node(user, "sleep", kind="habit", label="睡眠", value=f"{sleep_n:g}時間", source="health")
    mental = str(health.get("mental_status") or "").strip()
    if mental in ("疲れ", "落ち込み", "不安", "元気", "普通"):
        upsert_node(user, "mood", kind="decision", label="気分", value=mental, source="chat")
    income, expense = _yen_pair(money)
    if expense > 0 and expense > income:
        upsert_node(
            user, "money", kind="constraint", label="お金", value="支出が収入より多い", source="money"
        )
    elif income > 0 or expense > 0:
        upsert_node(user, "money", kind="constraint", label="お金", value="収支の数字がある", source="money")
    plan = _next_plan(user)
    if plan:
        upsert_node(user, "plan", kind="habit", label="予定", value=plan, source="calendar")
    goal = _first_goal(user)
    if goal:
        upsert_node(user, "goal", kind="goal", label="目標", value=goal, source="goal")
    after = json.dumps(user.get("life_graph") or {}, ensure_ascii=False, sort_keys=True)
    changed = before != after
    if changed:
        user["_graph_dirty"] = True
    return changed


def memory_cards(user: Dict[str, Any]) -> List[Dict[str, str]]:
    cards: List[Dict[str, str]] = []
    for node in reversed(_nodes(user)):
        cards.append(
            {
                "label": str(node.get("label") or ""),
                "value": str(node.get("value") or ""),
                "source": _SOURCE_JA.get(str(node.get("source") or ""), "記録"),
            }
        )
        if len(cards) == 4:
            break
    return cards


def money_trust(money: Dict[str, Any]) -> str:
    """One clause: the saved numbers, or a request for one number."""
    income, expense = _yen_pair(money or {})
    if income <= 0 and expense <= 0:
        return "収入と支出の数字がまだない。一つだけ教えて。"
    if expense > income:
        return "今月の記録だと、支出が収入を超えてる。"
    return "お金の記録を見てる。"


def sleep_trust(hours: Optional[float]) -> str:
    if hours is None:
        return ""
    return f"記録だと睡眠は{hours:g}時間。"


def mood_trust(mental: str) -> str:
    mental = (mental or "").strip()
    if not mental:
        return ""
    return f"気分は「{mental}」って記録がある。"


def _yen_pair(money: Dict[str, Any]) -> tuple:
    from money_eval import _parse_yen

    income = _parse_yen(money.get("monthly_income")) or 0
    expense = _parse_yen(money.get("monthly_expense")) or 0
    return income, expense


def _next_plan(user: Dict[str, Any]) -> str:
    try:
        from schedule_service import list_events
        from day_coach import _today_jst

        sched = list_events(user, on_date=_today_jst().isoformat())
    except Exception:
        return ""
    items = list(sched.get("today_open") or [])
    if not items:
        return ""
    ev = items[0]
    title = str(ev.get("title") or "").strip()
    clock = str(ev.get("time") or "").strip()
    if clock and title:
        return f"{title} {clock}"[:40]
    return title[:40]


def _first_goal(user: Dict[str, Any]) -> str:
    try:
        from goals_service import goals_dashboard

        items = goals_dashboard(user).get("items") or []
    except Exception:
        return ""
    if not items:
        return ""
    return str(items[0].get("title") or "").strip()[:40]
