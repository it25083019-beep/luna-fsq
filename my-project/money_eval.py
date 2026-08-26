"""Age-aware money buckets: spending room, purchase goal, emergency, reserve, invest."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

FUND_KEYS = (
    "purchase_current",
    "purchase_target",
    "emergency_current",
    "emergency_target",
    "reserve_current",
    "reserve_target",
    "invest_current",
    "invest_target",
)

BASE_KEYS = (
    "monthly_income",
    "monthly_expense",
    "purchase_name",
)


def _parse_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip().replace(" ", "")
    if "," in raw and "." not in raw:
        raw = raw.replace(",", ".")
    else:
        raw = raw.replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return default


def _parse_yen(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return max(0, int(round(float(value))))
    raw = str(value).strip().replace(" ", "").replace("円", "").replace("¥", "")
    # Thousands separators: 12,000 / 12.000
    if raw.count(",") >= 1 and all(p.isdigit() for p in raw.replace(",", "").replace(".", "")):
        parts = raw.replace(".", ",").split(",")
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]) and parts[0].isdigit():
            raw = "".join(parts)
        elif "," in raw and "." not in str(value):
            # decimal comma rare for yen amounts → still allow 12,5
            if len(parts) == 2 and len(parts[1]) <= 2:
                raw = parts[0] + "." + parts[1]
            else:
                raw = raw.replace(",", "")
    try:
        return max(0, int(round(float(raw))))
    except ValueError:
        return None


def resolve_age(user: Dict[str, Any], structured: Optional[Dict[str, Any]] = None) -> Optional[int]:
    """Prefer health profile age; allow money override."""
    s = structured or {}
    for src in (
        s.get("age"),
        (user.get("life_modules") or {}).get("health", {}).get("structured", {}).get("age"),
    ):
        n = _parse_float(src)
        if n is None:
            continue
        age = int(round(n))
        if 5 <= age <= 120:
            return age
    return None


def age_band(age: Optional[int]) -> str:
    if age is None:
        return "unknown"
    if age < 18:
        return "teen"
    if age < 25:
        return "young"
    if age < 40:
        return "adult"
    return "senior"


def band_label_ja(band: str, age: Optional[int]) -> str:
    if band == "teen":
        return f"{age}歳・学生向け" if age is not None else "学生向け"
    if band == "young":
        return f"{age}歳・社会人スタート" if age is not None else "社会人スタート"
    if band == "adult":
        return f"{age}歳・安定形成期" if age is not None else "安定形成期"
    if band == "senior":
        return f"{age}歳・守りと運用" if age is not None else "守りと運用"
    return "年齢未設定（ヘルスケアで年齢を入力すると最適化）"


def bucket_template(band: str, monthly_expense: int) -> List[Dict[str, Any]]:
    """Which funds are active + suggested default targets."""
    exp = max(monthly_expense, 0)
    if band == "teen":
        emergency_months = 0.5
        show_invest = False
    elif band == "young":
        emergency_months = 2.0
        show_invest = True
    elif band == "adult":
        emergency_months = 4.0
        show_invest = True
    elif band == "senior":
        emergency_months = 6.0
        show_invest = True
    else:
        emergency_months = 3.0
        show_invest = True

    emergency_default = int(exp * emergency_months) if exp else (30000 if band == "teen" else 100000)
    reserve_default = int(exp * (1.0 if band == "teen" else 2.0)) if exp else (20000 if band == "teen" else 80000)
    if band == "young":
        invest_default = 50000
    elif band == "adult":
        invest_default = 100000
    elif band == "senior":
        invest_default = 200000
    else:
        invest_default = 30000

    purchase_priority = 1 if band == "teen" else 2 if band == "young" else 3

    funds = [
        {
            "key": "purchase",
            "label_ja": "欲しいもの・目標",
            "enabled": True,
            "priority": purchase_priority,
            "default_target": 30000 if band == "teen" else 50000,
            "hint_ja": "買いたいものや旅行など",
        },
        {
            "key": "emergency",
            "label_ja": "もしもの予備費" if band == "teen" else "緊急用資金",
            "enabled": True,
            "priority": 0,
            "default_target": max(emergency_default, 10000),
            "hint_ja": f"目安：月の支出×{emergency_months:g}",
        },
        {
            "key": "reserve",
            "label_ja": "予備資金",
            "enabled": True,
            "priority": 1,
            "default_target": max(reserve_default, 5000),
            "hint_ja": "近いうちの出費・ゆとり用",
        },
        {
            "key": "invest",
            "label_ja": "投資・積立",
            "enabled": show_invest,
            "priority": 4,
            "default_target": invest_default,
            "hint_ja": "緊急用が足りてから少しずつ",
        },
    ]
    return [f for f in funds if f["enabled"]]


def _pct(current: int, target: int) -> int:
    if target <= 0:
        return 100 if current > 0 else 0
    return max(0, min(100, int(round(current / target * 100))))


def evaluate_money(user: Dict[str, Any], structured: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    s = dict(structured or {})
    age = resolve_age(user, s)
    band = age_band(age)
    income = _parse_yen(s.get("monthly_income")) or 0
    expense = _parse_yen(s.get("monthly_expense")) or 0
    room = income - expense
    purchase_name = (str(s.get("purchase_name") or "").strip())[:80] or "欲しいもの"

    templates = bucket_template(band, expense)
    funds: List[Dict[str, Any]] = []
    for tpl in templates:
        key = tpl["key"]
        cur = _parse_yen(s.get(f"{key}_current")) or 0
        tgt = _parse_yen(s.get(f"{key}_target"))
        if tgt is None or tgt <= 0:
            tgt = int(tpl["default_target"])
        label = tpl["label_ja"]
        if key == "purchase":
            label = f"目標：{purchase_name}"
        funds.append(
            {
                "key": key,
                "label_ja": label,
                "current": cur,
                "target": tgt,
                "pct": _pct(cur, tgt),
                "priority": tpl["priority"],
                "hint_ja": tpl["hint_ja"],
                "filled": cur >= tgt and tgt > 0,
            }
        )

    if income <= 0 and expense <= 0:
        room_score = 55.0
        room_note = "収支未入力"
    elif room >= 0:
        room_score = 90.0 if room >= expense * 0.1 or room >= 5000 else 78.0
        room_note = f"今月の余裕 約{room:,}円"
    else:
        room_score = 40.0
        room_note = f"今月は約{abs(room):,}円オーバー"

    by_key = {f["key"]: f for f in funds}
    emergency = by_key.get("emergency")
    purchase = by_key.get("purchase")
    invest = by_key.get("invest")
    reserve = by_key.get("reserve")

    safety_score = 70.0
    if emergency:
        safety_score = 55 + emergency["pct"] * 0.4
        if emergency["pct"] < 30:
            safety_score = min(safety_score, 50)
    elif reserve:
        safety_score = 60 + reserve["pct"] * 0.3

    goal_score = 70.0
    if purchase:
        goal_score = 50 + purchase["pct"] * 0.45

    invest_score = 72.0
    if invest:
        em_pct = emergency["pct"] if emergency else 100
        if em_pct < 50 and invest["current"] > 0:
            invest_score = 48.0
        else:
            invest_score = 55 + invest["pct"] * 0.35

    score = int(
        round(
            room_score * 0.30
            + safety_score * 0.35
            + goal_score * 0.20
            + invest_score * 0.15
        )
    )
    score = max(0, min(100, score))
    if score >= 80:
        status = "良好"
    elif score >= 60:
        status = "注意"
    else:
        status = "要ケア"

    tips = _coaching_tips(band, age, room, income, expense, by_key)
    if status == "良好":
        message = "お金のバランス、いい感じだよ。" + (tips[0] if tips else "")
    elif status == "注意":
        message = "もう少し整えると安心だよ。" + (tips[0] if tips else "")
    else:
        message = "先に守りを固めよう。" + (tips[0] if tips else "")

    next_focus = None
    for k in ("emergency", "reserve", "purchase", "invest"):
        f = by_key.get(k)
        if f and f["pct"] < 100:
            next_focus = f
            break

    return {
        "score": score,
        "status_ja": status,
        "message_ja": message,
        "tips_ja": tips[:4],
        "age": age,
        "age_band": band,
        "age_label_ja": band_label_ja(band, age),
        "monthly_income": income,
        "monthly_expense": expense,
        "monthly_room": room,
        "room_note_ja": room_note,
        "purchase_name": purchase_name,
        "funds": funds,
        "next_focus": next_focus,
        "rule_ja": "優先順位：緊急用 → 予備 → 欲しいもの → 投資",
    }


def _coaching_tips(
    band: str,
    age: Optional[int],
    room: int,
    income: int,
    expense: int,
    by_key: Dict[str, Dict[str, Any]],
) -> List[str]:
    tips: List[str] = []
    if age is None:
        tips.append("ヘルスケアで年齢を入れると、お金の項目があなた向けに変わるよ")
    if income <= 0:
        tips.append("まずは月の収入（おこづかい・バイト代など）を入力してみて")
    if expense <= 0:
        tips.append("月の支出のざっくり金額もあると、緊急用の目安が分かるよ")
    if room < 0:
        tips.append("支出が収入を超えている月は、欲しいものより先に支出の見直しを優先して")
    elif room > 0:
        tips.append(f"余裕の約{room:,}円は、緊急用→予備→目標の順に分けてみよう")

    em = by_key.get("emergency")
    inv = by_key.get("invest")
    pur = by_key.get("purchase")
    if em and em["pct"] < 50:
        tips.append("「" + em["label_ja"] + "」がまだ半分未満。ここを先に厚くするのがおすすめ")
    if inv and em and em["pct"] < 50 and inv["current"] > 0:
        tips.append("投資より先に緊急用を優先しよう（守り→攻めの順番）")
    if pur and pur["pct"] < 100 and room > 0:
        left = max(0, pur["target"] - pur["current"])
        if left > 0:
            months = max(1, int(round(left / max(room * 0.3, 1))))
            tips.append(
                "「"
                + pur["label_ja"]
                + "」まで残り約"
                + f"{left:,}"
                + "円。余裕の一部なら約"
                + str(months)
                + "ヶ月が目安"
            )
    if band == "teen":
        tips.append("学生のうちは大きな投資より、少額の予備費と目標貯金が大事だよ")
    if band == "senior":
        tips.append("守りの資金（緊急・予備）を厚めにしてから、積立・運用を考えよう")

    seen = set()
    out: List[str] = []
    for t in tips:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def sanitize_money_profile(payload: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key in ("monthly_income", "monthly_expense", *FUND_KEYS):
        if key not in payload:
            continue
        out[key] = _parse_yen(payload.get(key))
    if "purchase_name" in payload:
        out["purchase_name"] = (str(payload.get("purchase_name") or "").strip())[:80] or None
    return out


def profile_snapshot(structured: Dict[str, Any]) -> Dict[str, Any]:
    snap = {k: structured.get(k) for k in (*BASE_KEYS, *FUND_KEYS)}
    return snap


def apply_money_evaluation(user: Dict[str, Any], structured: Dict[str, Any]) -> Dict[str, Any]:
    ev = evaluate_money(user, structured)
    structured["score"] = ev["score"]
    structured["status_ja"] = ev["status_ja"]
    structured["message_ja"] = ev["message_ja"]
    structured["tips_ja"] = ev["tips_ja"]
    structured["funds"] = ev["funds"]
    return ev
