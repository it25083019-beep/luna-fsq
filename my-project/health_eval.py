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
    "age",
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


def _parse_age(value: Any) -> Optional[int]:
    n = _parse_float(value)
    if n is None:
        return None
    age = int(round(n))
    if age < 5 or age > 120:
        return None
    return age


def _bmi_bands(age: Optional[int]) -> Tuple[float, float, float, float]:
    """Return (ok_lo, ok_hi, warn_lo, warn_hi) for age-aware BMI."""
    if age is None:
        return 18.5, 24.9, 17.0, 27.5
    if age < 18:
        # Teens: growth phase — slightly wider "ok", avoid harsh low cuts.
        return 17.0, 24.5, 15.5, 27.0
    if age < 40:
        return 18.5, 24.9, 17.0, 27.5
    if age < 65:
        # Mid-adult: slightly higher upper range is often safer.
        return 18.5, 26.0, 17.0, 29.0
    # Older adults: underweight risk rises; allow a bit higher BMI.
    return 20.0, 27.0, 18.0, 30.0


def _age_label(age: Optional[int]) -> str:
    if age is None:
        return "年齢未設定"
    if age < 18:
        return f"{age}歳（成長期）"
    if age < 40:
        return f"{age}歳"
    if age < 65:
        return f"{age}歳（中年）"
    return f"{age}歳（シニア）"


def _parse_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace(" ", "")
    # Support EU/VN decimal comma: 6,5 → 6.5 (after removing thousands commas carefully)
    raw = str(value).strip().replace(" ", "")
    if "," in raw and "." not in raw:
        raw = raw.replace(",", ".")
    else:
        raw = raw.replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return default


def _parse_time(value: Any) -> Optional[time]:
    text = (str(value or "").strip())[:5]
    if not text:
        return None
    if text == "24:00":
        return time(0, 0)
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
    age = _parse_age(s.get("age"))
    if w is None and h is None:
        return 65.0, "身体データ未入力"
    bmi = _bmi(w, h)
    score = 70.0
    note = "身体データ不足"
    ok_lo, ok_hi, warn_lo, warn_hi = _bmi_bands(age)
    if bmi is not None:
        age_bit = f"・{_age_label(age)}" if age is not None else ""
        if ok_lo <= bmi <= ok_hi:
            score = 92.0
            note = f"BMI {bmi:.1f}（年齢に合った標準）{age_bit}"
        elif warn_lo <= bmi < ok_lo or ok_hi < bmi <= warn_hi:
            score = 72.0
            note = f"BMI {bmi:.1f}（やや注意）{age_bit}"
        else:
            score = 48.0
            note = f"BMI {bmi:.1f}（要ケア）{age_bit}"
        if age is not None and age < 18 and th is not None and h is not None and h + 2 < th:
            note += "・身長は成長中なので無理な減量は避けて"
    if w is not None and tw is not None and tw > 0:
        gap = abs(w - tw) / tw
        # Safer weekly pace hint is in suggestions; score only gap size.
        if gap <= 0.05:
            score = min(100.0, score + 8)
            note += "・目標体重に近い"
        elif gap <= 0.12:
            score = min(100.0, score + 3)
        else:
            score = max(30.0, score - 6)
            note += "・目標体重との差あり"
            if age is not None and age < 18 and tw < (w or 0):
                score = max(30.0, score - 4)
                note += "・成長期の減量は慎重に"
    if h is not None and th is not None and th > 0:
        if abs(h - th) <= 3:
            score = min(100.0, score + 3)
        elif age is not None and age >= 18 and th > h + 5:
            # Adult height target usually not actionable.
            note += "・成人後の身長目標は参考程度に"
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


def _build_coaching(
    s: Dict[str, Any],
    *,
    body: float,
    sleep: float,
    balance: float,
    mental: float,
    exercise: float,
) -> Dict[str, List[str]]:
    """Goal + exercise suggestions from profile, targets, and age."""
    age = _parse_age(s.get("age"))
    w = _parse_float(s.get("weight_kg"))
    h = _parse_float(s.get("height_cm"))
    tw = _parse_float(s.get("target_weight_kg"))
    th = _parse_float(s.get("target_height_cm"))
    bmi = _bmi(w, h)
    ok_lo, ok_hi, _, _ = _bmi_bands(age)
    hobbies = (s.get("hobbies") or "").strip()
    plan = (s.get("exercise_plan") or "").strip()
    sleep_h = _parse_float(s.get("sleep_hours"))
    if sleep_h is None:
        sleep_h = _sleep_hours_from_bed_wake(_parse_time(s.get("bedtime")), _parse_time(s.get("wake_time")))
    relax = _parse_float(s.get("relax_hours"), 0.0) or 0.0
    study = _parse_float(s.get("study_hours"), 0.0) or 0.0
    mental_st = (s.get("mental_status") or "").strip()

    goals: List[str] = []
    exercises: List[str] = []

    if age is None:
        goals.append("年齢を入力すると、BMI判定と運動強度をもっと正確にできるよ")

    if w is not None and tw is not None and abs(w - tw) >= 0.5:
        delta = tw - w
        # Safe pace: teens milder; adults ~0.25–0.5 kg/week
        weekly = 0.25 if (age is not None and age < 18) else 0.4
        weeks = max(1, int(round(abs(delta) / weekly)))
        if delta < 0:
            if age is not None and age < 18:
                goals.append(
                    f"目標体重まで約{abs(delta):.1f}kg。成長期なので急な減量は避け、"
                    f"まず食生活と軽い運動で{weeks}週かけてゆっくり近づこう"
                )
            else:
                goals.append(
                    f"目標体重 {tw:.1f}kg まで約 {abs(delta):.1f}kg。"
                    f"目安は週{weekly}kgペースで約{weeks}週"
                )
        else:
            goals.append(
                f"目標体重まであと約{delta:.1f}kg増やす想定。"
                f"たんぱく質と筋力トレを組み合わせて約{weeks}週で段階的に"
            )
    elif w is not None and tw is not None:
        goals.append("体重は目標にかなり近いよ。今の習慣をキープしよう")

    if h is not None and th is not None and th > h + 3:
        if age is not None and age < 18:
            goals.append("身長目標は睡眠・栄養・姿勢を整える成長サポートとして考えよう")
        else:
            goals.append("成人後の身長はほぼ固定なので、目標は姿勢・柔軟・見た目のコンディションに置き換えよう")

    if bmi is not None:
        if bmi < ok_lo:
            goals.append("BMIが低め。栄養バランスを優先し、無理な有酸素の増やしすぎに注意")
        elif bmi > ok_hi:
            goals.append("BMIが高め。食事の見直し＋週150分程度の有酸素を目標にしよう")

    if sleep_h is not None and not (7 <= sleep_h <= 9):
        target_sleep = 8 if (age is None or age >= 13) else 9
        goals.append(f"睡眠の目標：まず1日{target_sleep}時間前後を目指そう（今は約{sleep_h:.1f}時間）")
    if relax < 0.5:
        goals.append("リラックス目標：毎日最低30分、趣味や休憩の時間を確保しよう")
    if study > 4 and relax < 1:
        goals.append("自学が多め。勉強ブロックの合間に5〜10分のストレッチ休憩を入れてみて")
    if mental_st in ("疲れ", "落ち込み", "不安"):
        goals.append("気分ケア目標：今日は負荷を下げ、短い散歩か深呼吸から始めよう")

    # Exercise suggestions by age + BMI + hobbies
    hobby_l = hobbies.lower()
    likes_walk = any(k in hobby_l for k in ("散歩", "walk", "đi bộ", "音楽", "music", "osake", "酒"))
    # light alcohol hobby → suggest healthier swap softly
    if any(k in hobby_l for k in ("osake", "酒", "beer", "アルコール")):
        exercises.append("飲酒の日は翌日に軽い散歩15分＋水を多めに取るリセット習慣がおすすめ")

    if age is not None and age < 18:
        exercises.append("成長期向け：外遊び・球技・縄跳びなど楽しい有酸素を週3〜4回、各20〜30分")
        exercises.append("筋トレは自重（スクワット・プランク）を短時間でOK。無理な重量は避けて")
    elif age is not None and age >= 65:
        exercises.append("シニア向け：毎日の散歩15〜30分＋椅子スクワットで下半身を維持")
        exercises.append("バランス運動（片足立ち10秒×3）で転倒予防を意識して")
    else:
        if bmi is not None and bmi > ok_hi:
            exercises.append("体脂肪ケア：早歩きまたは軽いジョギングを週3回×25〜40分")
            exercises.append("週2回の全身筋トレ（スクワット・腕立て・行ってこい）で代謝アップ")
        elif bmi is not None and bmi < ok_lo:
            exercises.append("筋力優先：週3回の筋トレ（下半身＋背中）とたんぱく質を意識")
            exercises.append("有酸素は歩き中心で短めに。消費カロリーを増やしすぎないで")
        else:
            exercises.append("維持メニュー：週150分の有酸素（早歩き・自転車）＋週2回筋トレ")

    if likes_walk or "散歩" in hobbies:
        exercises.append("趣味の散歩を活かして、帰宅後にコースを5分だけ延ばしてみよう")
    if plan:
        exercises.append(f"いまのプラン「{plan[:40]}」を続けるなら、週のうち1日は休養日を入れよう")
    else:
        exercises.append("運動プラン欄に「週〇回・何分」と書いておくと、継続しやすくなるよ")

    if mental_st in ("落ち込み", "不安"):
        exercises.insert(0, "気分が重い日はヨガ・ストレッチ・ゆっくり散歩など低強度からで十分")
    if mental_st == "疲れ":
        exercises.insert(0, "疲れが強い日は本格トレを休み、10分のストレッチだけにしよう")

    # Deduplicate while preserving order
    def uniq(items: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for x in items:
            if x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out[:5]

    return {
        "goal_suggestions": uniq(goals),
        "exercise_suggestions": uniq(exercises),
    }


def evaluate_health(structured: Optional[Dict[str, Any]] = None, *, today: Optional[date] = None) -> Dict[str, Any]:
    s = dict(structured or {})
    today = today or date.today()
    body, body_n = _body_score(s)
    sleep, sleep_n = _sleep_score(s)
    balance, balance_n = _time_balance_score(s)
    mental, mental_n = _mental_score(s, today=today)
    exercise, exercise_n = _exercise_score(s)
    coaching = _build_coaching(
        s, body=body, sleep=sleep, balance=balance, mental=mental, exercise=exercise
    )

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
    tips.extend(coaching["goal_suggestions"][:2])
    if sleep < 70 and not any("睡眠" in t for t in tips):
        tips.append("睡眠を7〜9時間に整えてみよう")
    if mental < 70:
        tips.append("今日の気持ちをLUNAに話してみてね")

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
    age = _parse_age(s.get("age"))
    return {
        "score": score,
        "status_ja": status,
        "message_ja": message,
        "breakdown": breakdown,
        "tips_ja": tips[:3],
        "bmi": round(_bmi(_parse_float(s.get("weight_kg")), _parse_float(s.get("height_cm"))) or 0, 1) or None,
        "age": age,
        "bmi_range_ja": (
            f"目安BMI {_bmi_bands(age)[0]:.1f}〜{_bmi_bands(age)[1]:.1f}（{_age_label(age)}）"
        ),
        "goal_suggestions": coaching["goal_suggestions"],
        "exercise_suggestions": coaching["exercise_suggestions"],
    }


def sanitize_health_profile(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize user-editable health fields for storage."""
    out: Dict[str, Any] = {}
    if "age" in payload:
        out["age"] = _parse_age(payload.get("age"))
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
    structured["goal_suggestions"] = ev.get("goal_suggestions") or []
    structured["exercise_suggestions"] = ev.get("exercise_suggestions") or []
    structured["bmi_range_ja"] = ev.get("bmi_range_ja")
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
