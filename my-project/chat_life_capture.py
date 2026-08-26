"""Capture life facts from chat and apply them additively to user brain.

Never deletes existing schedule/money/health/goals data — only append or update fields.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from health_eval import MENTAL_CHOICES, record_mental_status
from life_modules import append_module_note, ensure_life_modules


def _today() -> date:
    return date.today()


def _parse_amount_yen(text: str) -> Optional[int]:
    """Find a yen amount when spend context is present."""
    t = text or ""
    if not re.search(
        r"(円|¥|使った|使っ|買った|払った|支出|ランチ|昼食|夕飯|夜ごはん|カフェ|交通|電車|バス|"
        r"tiêu|tieu|spent|pay|bought|chi)",
        t,
        re.I,
    ):
        return None
    # Prefer explicit 円 / ¥ amounts
    m = re.search(r"(?:¥|￥)\s*([0-9]{2,7})|([0-9]{2,7})\s*円", t)
    if m:
        raw = m.group(1) or m.group(2)
        try:
            n = int(raw)
            if 10 <= n <= 9_999_999:
                return n
        except ValueError:
            return None
    m2 = re.search(
        r"(?:使った|買った|払った|tiêu|tieu|spent)\s*([0-9]{2,7})",
        t,
        re.I,
    )
    if m2:
        try:
            n = int(m2.group(1))
            if 10 <= n <= 9_999_999:
                return n
        except ValueError:
            return None
    return None


def _detect_mental(text: str) -> Optional[str]:
    t = (text or "").strip()
    if not t:
        return None
    # Explicit choice words first
    for choice in MENTAL_CHOICES:
        if choice in t:
            return choice
    rules = [
        ("落ち込み", r"落ち込|悲しい|つらい|うつ|泣|mệt quá|buồn"),
        ("不安", r"不安|心配|怖い|焦慮|lo lắng|anxious"),
        ("疲れ", r"疲れ|しんど|眠い|exhausted|tired|mệt"),
        ("元気", r"元気|調子いい|うれしい|嬉しい|楽しい|やった|happy"),
        ("普通", r"普通|まあまあ|ふつう|bình thường"),
    ]
    for label, pat in rules:
        if re.search(pat, t, re.I):
            return label
    return None


def _resolve_date_hint(text: str, *, today: Optional[date] = None) -> Optional[str]:
    today = today or _today()
    t = text or ""
    m = re.search(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})", t)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            pass
    m2 = re.search(r"(?<!\d)(\d{1,2})[/月](\d{1,2})日?", t)
    if m2:
        try:
            return date(today.year, int(m2.group(1)), int(m2.group(2))).isoformat()
        except ValueError:
            pass
    if re.search(r"明後日|あさって", t):
        return (today + timedelta(days=2)).isoformat()
    if re.search(r"明日|あした|mai\b|tomorrow", t, re.I):
        return (today + timedelta(days=1)).isoformat()
    if re.search(r"今日|きょう|hôm nay|today", t, re.I):
        return today.isoformat()
    return None


def _extract_schedule_title(text: str) -> Optional[str]:
    t = (text or "").strip()
    has_schedule_word = bool(
        re.search(
            r"予定|スケジュール|入れて|追加|バイト|会議|テスト|授業|面接|締切|deadline|meeting|カレンダー",
            t,
            re.I,
        )
    )
    has_day = bool(re.search(r"明日|あした|明後日|あさって|今日|きょう|tomorrow", t, re.I))
    # Need a clear schedule cue — day alone + spend/mood is NOT a schedule
    if not has_schedule_word:
        return None
    if not has_day and not re.search(r"20\d{2}|\d{1,2}[/月]\d{1,2}", t):
        # allow "バイトを予定に追加" without day → today via caller
        if not re.search(r"予定|スケジュール|追加|入れて", t):
            return None
    # Strip date/time words to leave a title-ish fragment
    cleaned = re.sub(
        r"(今日|きょう|明日|あした|明後日|あさって|予定に|予定を|スケジュールに|入れて|追加して|追加|入れておいて|に入れて)",
        " ",
        t,
    )
    cleaned = re.sub(r"(20\d{2}[-/年]\d{1,2}[-/月]\d{1,2}日?|\d{1,2}[/月]\d{1,2}日?)", " ", cleaned)
    cleaned = re.sub(r"([01]?\d|2[0-3])[:：]([0-5]\d)", " ", cleaned)
    cleaned = re.sub(r"[、。！？\s]+", " ", cleaned).strip(" 　。.、")
    if len(cleaned) < 2:
        for key in ("バイト", "テスト", "会議", "授業", "面接"):
            if key in t:
                return key
        return None
    return cleaned[:40]


def _extract_time(text: str) -> Optional[str]:
    m = re.search(r"([01]?\d|2[0-3])[:：]([0-5]\d)", text or "")
    if not m:
        return None
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def extract_life_hints_from_text(user_text: str, *, today: Optional[date] = None) -> Dict[str, Any]:
    """Heuristic extraction from the user's message only."""
    today = today or _today()
    t = (user_text or "").strip()
    out: Dict[str, Any] = {}
    if not t:
        return out

    mental = _detect_mental(t)
    if mental:
        out["mental_status"] = mental

    amount = _parse_amount_yen(t)
    if amount is not None:
        note = t[:80]
        out["spend"] = {"amount": amount, "note": note, "date": today.isoformat()}

    title = _extract_schedule_title(t)
    if title:
        ds = _resolve_date_hint(t, today=today) or today.isoformat()
        out["schedule_add"] = {
            "title": title,
            "date": ds,
            "time": _extract_time(t),
            "note": "チャットから追加",
        }

    # Goal wish: 欲しい + optional amount
    if re.search(r"欲しい|ほしい|目標は|貯めたい|貯金したい", t):
        gtitle = re.sub(r"(欲しい|ほしい|目標は|貯めたい|貯金したい|円|¥|￥|[0-9]+)", " ", t)
        gtitle = re.sub(r"\s+", " ", gtitle).strip(" 　。.、")[:40] or "欲しいもの"
        goal: Dict[str, Any] = {"title": gtitle, "unit": "円", "current": 0}
        if amount is not None and "spend" not in out:
            goal["target"] = amount
        elif amount is not None and re.search(r"欲しい|目標", t):
            goal["target"] = amount
            # Prefer goal over spend if clearly a wish price
            if re.search(r"欲しい|ほしい|目標", t) and not re.search(r"使った|買った|払った", t):
                out.pop("spend", None)
                goal["target"] = amount
        out["goal_add"] = goal

    return out


def _merge_updates(base: Dict[str, Any], extra: Any) -> Dict[str, Any]:
    if not isinstance(extra, dict):
        return base
    out = dict(base)
    for k, v in extra.items():
        if v is None or v == "" or v == {}:
            continue
        if k not in out or out[k] in (None, "", {}):
            out[k] = v
        elif isinstance(out[k], dict) and isinstance(v, dict):
            merged = dict(out[k])
            merged.update({kk: vv for kk, vv in v.items() if vv not in (None, "")})
            out[k] = merged
        else:
            # Prefer explicit LLM structured value when both present
            out[k] = v
    return out


def apply_life_updates(user: Dict[str, Any], updates: Dict[str, Any]) -> List[str]:
    """Apply captured updates additively. Returns Japanese summary tags of what changed."""
    if not updates:
        return []
    ensure_life_modules(user)
    applied: List[str] = []

    # Mood / mental
    mental = updates.get("mental_status")
    if isinstance(mental, str) and mental.strip() in MENTAL_CHOICES:
        try:
            from life_modules import update_module_structured

            row = user["life_modules"]["health"]
            structured = dict(row.get("structured") or {})
            record_mental_status(structured, mental.strip())
            update_module_structured(
                user,
                "health",
                structured,
                note=f"チャット気分: {mental.strip()}",
            )
            applied.append(f"気分→{mental.strip()}")
        except Exception:
            pass

    # Spend today (append only)
    spend = updates.get("spend")
    if isinstance(spend, dict):
        try:
            from life_dashboard import add_money_spend

            amt = int(spend.get("amount") or 0)
            if amt > 0:
                add_money_spend(
                    user,
                    amount=amt,
                    note=str(spend.get("note") or "チャット記録")[:200],
                    on_date=str(spend.get("date") or "")[:10] or None,
                )
                applied.append(f"支出+{amt:,}円")
        except Exception:
            pass

    # Schedule event (add only — never wipe calendar)
    sched = updates.get("schedule_add")
    if isinstance(sched, dict) and (sched.get("title") or "").strip():
        try:
            from schedule_service import add_event

            add_event(
                user,
                title=str(sched.get("title")).strip()[:80],
                event_date=str(sched.get("date") or _today().isoformat())[:10],
                event_time=sched.get("time"),
                event_end_time=sched.get("end_time"),
                note=str(sched.get("note") or "チャットから追加")[:200],
                recurrence=None,
            )
            applied.append("予定を追加")
        except Exception:
            pass

    # Goal add (append)
    goal = updates.get("goal_add")
    if isinstance(goal, dict) and (goal.get("title") or "").strip():
        try:
            from goals_service import add_goal, goals_dashboard

            title = str(goal.get("title")).strip()[:80]
            existing = goals_dashboard(user).get("items") or []
            if not any(g.get("title") == title for g in existing):
                add_goal(
                    user,
                    {
                        "title": title,
                        "current": goal.get("current") or 0,
                        "target": goal.get("target") or 0,
                        "unit": goal.get("unit") or "円",
                        "note": goal.get("note") or "チャットから追加",
                    },
                )
                applied.append(f"目標「{title}」")
        except Exception:
            pass

    # Goal progress by title or id
    gprog = updates.get("goal_progress")
    if isinstance(gprog, dict):
        try:
            from goals_service import goals_dashboard, update_goal

            items = goals_dashboard(user).get("items") or []
            target = None
            gid = str(gprog.get("id") or "")
            title = str(gprog.get("title") or "").strip()
            for g in items:
                if gid and g["id"] == gid:
                    target = g
                    break
                if title and g.get("title") == title:
                    target = g
                    break
            if target and gprog.get("current") is not None:
                update_goal(user, target["id"], {"current": gprog.get("current")})
                applied.append("目標の進捗")
        except Exception:
            pass

    # Free-form notes per module (append)
    notes = updates.get("notes")
    if isinstance(notes, dict):
        for mod, text in notes.items():
            if mod not in ("health", "money", "schedule", "goals"):
                continue
            body = (str(text or "")).strip()
            if not body:
                continue
            try:
                append_module_note(user, mod, f"チャットメモ: {body[:500]}")
                applied.append(f"{mod}メモ")
            except Exception:
                pass

    return applied


def capture_life_from_chat(
    user: Dict[str, Any],
    user_text: str,
    game_state: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Extract from user text + optional LLM life_updates; apply additively."""
    hints = extract_life_hints_from_text(user_text)
    llm_updates = None
    if isinstance(game_state, dict):
        llm_updates = game_state.get("life_updates")
    merged = _merge_updates(hints, llm_updates)
    return apply_life_updates(user, merged)


def compose_companion_dialogue(
    user: Dict[str, Any],
    user_text: str,
    applied: Optional[List[str]] = None,
) -> Dict[str, str]:
    """Warm companion line: acknowledge save (if any) + empathize + one suggestion.

    Returns {{dialogue, emotion}}.
    """
    name = (user.get("user_display_name") or "").strip()
    gender = str((user.get("life_profile") or {}).get("gender") or "")
    if name:
        if gender == "male" or "男" in gender:
            who = f"{name}くん"
        elif gender == "female" or "女" in gender:
            who = f"{name}さん"
        else:
            who = f"{name}さん"
    else:
        who = "あなた"
    cname = user.get("companion_name") or "LUNA"
    msg = (user_text or "").strip()
    applied = applied or []
    emotion = "happy"

    # What we recorded (spoken Japanese)
    ack_bits: List[str] = []
    for tag in applied:
        if tag.startswith("気分→"):
            ack_bits.append(f"今日の気分「{tag.replace('気分→', '')}」を残したよ")
        elif tag.startswith("支出+"):
            ack_bits.append(f"{tag.replace('支出+', '')}の支出を記録したよ")
        elif tag == "予定を追加":
            ack_bits.append("予定に追加したよ")
        elif tag.startswith("目標「"):
            ack_bits.append(f"{tag}を目標リストに入れたよ")
        elif tag == "目標の進捗":
            ack_bits.append("目標の進捗を更新したよ")
        elif tag.endswith("メモ"):
            ack_bits.append("メモも残したよ")
    ack = "。".join(ack_bits[:2])
    if ack:
        ack = ack + "。"

    # Empathy + suggestion by topic
    if re.search(r"疲れ|つらい|しんど|眠い|疲れた|落ち込み|不安|mệt|tired|buồn", msg, re.I):
        body = (
            f"{who}、話してくれてありがとう。無理しないでね。"
            f"今は深呼吸を1回、水を一口。少し横になれるなら10分だけ休もう。{cname}がそばにいるよ。"
        )
        emotion = "sad"
    elif re.search(r"元気|調子いい|嬉しい|たのしい|楽しい|やった|happy", msg, re.I):
        body = (
            f"{who}、それ聞いてこちらまでうれしいよ！"
            f"その勢いのまま、今日のごほうびを一つ決めてみない？"
        )
        emotion = "cheer"
    elif re.search(r"使った|買った|払った|円|支出|tiêu|spent", msg, re.I):
        body = (
            f"{who}、お金の話もちゃんと受け止めたよ。"
            f"今月の残り日数を意識して、今日はこのあとは飲み物だけにする、みたいな小さなルールがおすすめだよ。"
        )
        emotion = "think"
    elif re.search(r"予定|スケジュール|バイト|会議|テスト|授業", msg, re.I):
        body = (
            f"{who}、予定を共有してくれてありがとう。"
            f"始める30分前に持ち物チェックだけ入れておくと安心だよ。一緒に進めよう。"
        )
        emotion = "think"
    elif re.search(r"欲しい|目標|貯金", msg, re.I):
        body = (
            f"{who}、その目標いいね。"
            f"まずは今週、小さな金額でも一歩進めると気持ちが続くよ。応援してる。"
        )
        emotion = "cheer"
    elif re.search(r"勉強|宿題", msg, re.I):
        body = (
            f"{who}、勉強がんばってるね。"
            f"15分集中→3分休憩、を1セットやってみよう。終わったら教えてね。"
        )
        emotion = "cheer"
    elif re.search(r"おはよう|こんにちは|こんばんは", msg):
        body = f"{who}、こんにちは。{cname}だよ。今日の調子、短くでも聞かせてくれる？"
        emotion = "wave"
    else:
        body = (
            f"{who}、話してくれてありがとう。ちゃんと受け取ったよ。"
            f"いちばん気になることを一つだけ教えてくれたら、一緒に次の一歩を考えよう。"
        )
        emotion = "happy"

    if ack:
        # Record confirm first, then companion reaction (feels like a real partner)
        dialogue = f"{ack}{body}"
    else:
        dialogue = body

    # Keep readable length
    if len(dialogue) > 160:
        dialogue = dialogue[:157] + "…"
    return {"dialogue": dialogue, "emotion": emotion}


def enrich_dialogue_with_capture(
    dialogue: str,
    user: Dict[str, Any],
    user_text: str,
    applied: List[str],
) -> str:
    """If we saved facts but the model forgot to acknowledge, prepend a soft ack + keep warmth."""
    text = (dialogue or "").strip()
    if not applied:
        return text
    if re.search(r"記録|メモ|残した|入れた|更新した|わかったよ|ノート", text):
        return text
    composed = compose_companion_dialogue(user, user_text, applied)
    # Prefer our companion line when capture happened — clearer partner feel
    return composed["dialogue"]
