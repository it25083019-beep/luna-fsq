"""Health profile evaluation and daily mental check-in helpers."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any, Dict, List, Optional, Tuple

MENTAL_CHOICES = ("元気", "普通", "疲れ", "落ち込み", "不安")

MENTAL_SCORES = {
    "元気": 95,
    "普通": 78,
    "疲れ": 55,
    "落ち込み": 35,
    "不安": 40,
}

PROFILE_KEYS = (
    "weight_kg",
    "height_cm",
    "target_weight_kg",
    "target_height_cm",
    "sleep_hours",
    "wake_time",
    "bedtime",
    "hobbies",
    "school_hours",
    "study_hours",
    "relax_hours",
    "exercise_plan",
)


def _parse_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    try:
        return float(text)
    except ValueError:
        return default


def _parse_time(value: Any) -> Optional[time]:
    text = (str(value or "").strip())[:5]
    if not text:
        return None
    try:
        return datetime.strptime(text, "%H:%M").time()
    except ValueError:
        return None


def _norm_time_str(value: Any) -> Optional[str]:
    t = _parse_time(value)
    return t.strftime("%H:%M") if t else None


def mental_needed(structured: Dict[str, Any], *, today: Optional[date] = None) -> bool:
    today = today or date.today()
    checked = (structured.get("mental_checked_on") or "")[:10]
    return checked != today.isoformat()


def mental_reminder_due(structured: Dict[str, Any], *, now: Optional[datetime] = None) -> bool:
    """True when today's mental check is missing and local hour >= 16."""
    now = now or datetime.now(timezone.utc).astimezone()
    if not mental_needed(structured, today=now.date()):
        return False
    return now.hour >= 16


def _bmi(weight_kg: Optional[float], height_cm: Optional[float]) -> Optional[float]:
    if not weight_kg or not height_cm or height_cm <= 0:
        return None
    h = height_cm / 100.0
    if h <= 0:
        return None
    return weight_kg / (h * h)


def _body_score(s: Dict[str, Any]) -> Tuple[float, str]:
    w = _parse_float(s.get("weight_kg"))
    h = _parse_float(s.get("height_cm"))
    tw = _parse_float(s.get("target_weight_kg"))
    th = _parse_float(s.get("target_height_cm"))
    if w is None and h is None:
        return 65.0, "身体データ未入力"
    bmi = _bmi(w, h)
    score = 70.0
    note = "身体データ不足"
    if bmi is not None:
        if 18.5 <= bmi <= 24.9:
            score = 92.0
            note = f"BMI {bmi:.1f}（標準）"
        elif 17.0 <= bmi < 18.5 or 24.9 < bmi <= 27.5:
            score = 72.0
            note = f"BMI {bmi:.1f}（やや注意）"
        else:
            score = 48.0
            note = f"BMI {bmi:.1f}（要ケア）"
    if w is not None and tw is not None and tw > 0:
        gap = abs(w - tw) / tw
        if gap <= 0.05:
            score = min(100.0, score + 8)
            note += "・目標体重に近い"
        elif gap <= 0.12:
            score = min(100.0, score + 3)
        else:
            score = max(30.0, score - 6)
            note += "・目標体重との差あり"
    if h is not None and th is not None and th > 0:
        if abs(h - th) <= 3:
            score = min(100.0, score + 3)
    return score, note


def _sleep_hours_from_bed_wake(bed: Optional[time], wake: Optional[time]) -> Optional[float]:
    if not bed or not wake:
        return None
    b = bed.hour * 60 + bed.minute
    w = wake.hour * 60 + wake.minute
    mins = (w - b) % (24 * 60)
    if mins == 0:
        return None
    return mins / 60.0


def _sleep_score(s: Dict[str, Any]) -> Tuple[float, str]:
    hours = _parse_float(s.get("sleep_hours"))
    bed = _parse_time(s.get("bedtime"))
    wake = _parse_time(s.get("wake_time"))
    derived = _sleep_hours_from_bed_wake(bed, wake)
    if hours is None and derived is not None:
        hours = derived
    if hours is None and bed is None and wake is None:
        return 65.0, "睡眠データ未入力"
    score = 70.0
    note = "睡眠データ不足"
    if hours is not None:
        if 7.0 <= hours <= 9.0:
            score = 94.0
            note = f"睡眠 {hours:.1f}時間（良好）"
        elif 6.0 <= hours < 7.0 or 9.0 < hours <= 10.0:
            score = 72.0
            note = f"睡眠 {hours:.1f}時間（やや注意）"
        else:
            score = 45.0
            note = f"睡眠 {hours:.1f}時間（要ケア）"
    if bed is not None:
        # Prefer bedtime before midnight (or early morning after late night = lower).
        if bed.hour >= 21 or bed.hour <= 0:
            score = min(100.0, score + 4)
        elif bed.hour >= 1 and bed.hour <= 4:
            score = max(30.0, score - 10)
            note += "・就寝が遅い"
    if wake is not None and 5 <= wake.hour <= 9:
        score = min(100.0, score + 3)
    return score, note


def _time_balance_score(s: Dict[str, Any]) -> Tuple[float, str]:
    school = _parse_float(s.get("school_hours"), 0.0) or 0.0
    study = _parse_float(s.get("study_hours"), 0.0) or 0.0
    relax = _parse_float(s.get("relax_hours"), 0.0) or 0.0
    sleep = _parse_float(s.get("sleep_hours"))
    if sleep is None:
        sleep = _sleep_hours_from_bed_wake(_parse_time(s.get("bedtime")), _parse_time(s.get("wake_time"))) or 0.0
    total = school + study + relax + sleep
    filled = any(
        [
            s.get("school_hours") not in (None, ""),
            s.get("study_hours") not in (None, ""),
            s.get("relax_hours") not in (None, ""),
        ]
    )
    if not filled and sleep == 0:
        return 65.0, "生活時間未入力"
    score = 75.0
    note = "生活リズム"
    if total > 20:
        score = 40.0
        note = f"合計約{total:.0f}時間（過密）"
    elif total > 18:
        score = 58.0
        note = f"合計約{total:.0f}時間（やや過密）"
    elif 10 <= total <= 18:
        score = 88.0
        note = f"合計約{total:.0f}時間（バランス良好）"
    else:
        score = 70.0
        note = f"合計約{total:.0f}時間"
    if relax >= 0.5:
        score = min(100.0, score + 5)
    else:
        score = max(30.0, score - 8)
        note += "・リラックス不足"
    if study >= 0.5:
        score = min(100.0, score + 3)
    return score, note


def _mental_score(s: Dict[str, Any], *, today: Optional[date] = None) -> Tuple[float, str]:
    today = today or date.today()
    status = (s.get("mental_status") or "").strip()
    if mental_needed(s, today=today):
        if status and status in MENTAL_SCORES:
            base = MENTAL_SCORES[status] - 12
            return max(25.0, float(base)), f"昨日の気分「{status}」（今日未回答）"
        return 55.0, "今日の気分未回答"
    if status not in MENTAL_SCORES:
        return 60.0, "気分データ不足"
    return float(MENTAL_SCORES[status]), f"今日の気分「{status}」"


def _exercise_score(s: Dict[str, Any]) -> Tuple[float, str]:
    plan = (s.get("exercise_plan") or "").strip()
    if not plan:
        return 70.0, "運動習慣なし（中立）"
    return 88.0, "運動プランあり"


def evaluate_health(structured: Optional[Dict[str, Any]] = None, *, today: Optional[date] = None) -> Dict[str, Any]:
    s = dict(structured or {})
    today = today or date.today()
    body, body_n = _body_score(s)
    sleep, sleep_n = _sleep_score(s)
    balance, balance_n = _time_balance_score(s)
    mental, mental_n = _mental_score(s, today=today)
    exercise, exercise_n = _exercise_score(s)

    score = int(
        round(
            body * 0.25
            + sleep * 0.25
            + balance * 0.20
            + mental * 0.20
            + exercise * 0.10
        )
    )
    score = max(0, min(100, score))
    if score >= 80:
        status = "良好"
    elif score >= 60:
        status = "注意"
    else:
        status = "要ケア"

    tips: List[str] = []
    if body < 70:
        tips.append("体重・身長の目標に少しずつ近づこう")
    if sleep < 70:
        tips.append("睡眠を7〜9時間に整えてみよう")
    if balance < 70:
        tips.append("勉強とリラックスのバランスを見直そう")
    if mental < 70:
        tips.append("今日の気持ちをLUNAに話してみてね")
    if exercise < 80 and not (s.get("exercise_plan") or "").strip():
        tips.append("無理のない運動を1つ決めてみよう")

    if status == "良好":
        message = "いい調子だよ！このバランスを大切にしてね。"
    elif status == "注意":
        message = "少し気になる点があるよ。" + (tips[0] if tips else "無理せず整えていこう。")
    else:
        message = "今日はケアが必要かも。" + (tips[0] if tips else "LUNAに相談してね。")

    breakdown = [
        {"key": "body", "label_ja": "身体", "score": int(round(body)), "note": body_n},
        {"key": "sleep", "label_ja": "睡眠", "score": int(round(sleep)), "note": sleep_n},
        {"key": "balance", "label_ja": "生活時間", "score": int(round(balance)), "note": balance_n},
        {"key": "mental", "label_ja": "気分", "score": int(round(mental)), "note": mental_n},
        {"key": "exercise", "label_ja": "運動", "score": int(round(exercise)), "note": exercise_n},
    ]
    return {
        "score": score,
        "status_ja": status,
        "message_ja": message,
        "breakdown": breakdown,
        "tips_ja": tips[:3],
        "bmi": round(_bmi(_parse_float(s.get("weight_kg")), _parse_float(s.get("height_cm"))) or 0, 1) or None,
    }


def sanitize_health_profile(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize user-editable health fields for storage."""
    out: Dict[str, Any] = {}
    for key in ("weight_kg", "height_cm", "target_weight_kg", "target_height_cm", "sleep_hours", "school_hours", "study_hours", "relax_hours"):
        if key not in payload:
            continue
        val = _parse_float(payload.get(key))
        if val is None:
            out[key] = None
            continue
        if key.endswith("_cm"):
            out[key] = max(50.0, min(250.0, val))
        elif key.endswith("_kg"):
            out[key] = max(20.0, min(300.0, val))
        elif key == "sleep_hours":
            out[key] = max(0.0, min(24.0, val))
        else:
            out[key] = max(0.0, min(24.0, val))
    for key in ("wake_time", "bedtime"):
        if key in payload:
            out[key] = _norm_time_str(payload.get(key))
    if "hobbies" in payload:
        out["hobbies"] = (str(payload.get("hobbies") or "").strip())[:300] or None
    if "exercise_plan" in payload:
        out["exercise_plan"] = (str(payload.get("exercise_plan") or "").strip())[:500] or None
    return out


def apply_health_evaluation(structured: Dict[str, Any], *, today: Optional[date] = None) -> Dict[str, Any]:
    ev = evaluate_health(structured, today=today)
    structured["score"] = ev["score"]
    structured["status_ja"] = ev["status_ja"]
    structured["message_ja"] = ev["message_ja"]
    structured["breakdown"] = ev["breakdown"]
    structured["bmi"] = ev.get("bmi")
    return ev


def record_mental_status(
    structured: Dict[str, Any],
    status: str,
    *,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    today = today or date.today()
    text = (status or "").strip()
    if text not in MENTAL_CHOICES:
        raise ValueError("invalid mental status")
    structured["mental_status"] = text
    structured["mental_checked_on"] = today.isoformat()
    return apply_health_evaluation(structured, today=today)


def profile_snapshot(structured: Dict[str, Any]) -> Dict[str, Any]:
    snap = {k: structured.get(k) for k in PROFILE_KEYS}
    snap["mental_status"] = structured.get("mental_status")
    snap["mental_checked_on"] = structured.get("mental_checked_on")
    snap["bmi"] = structured.get("bmi")
    return snap
