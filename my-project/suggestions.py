"""Context-aware suggested reply chips for the chat UI."""
from __future__ import annotations

from luna_service import PROFILE_QUESTIONS, get_brain_status

# Profile step key -> chip labels
_PROFILE_CHIPS: dict[str, list[str]] = {
    "gender": ["男性", "女性"],
    "health_sleep": ["6時間", "7時間", "8時間あまり眠れない"],
    "mental_mood": ["3点・落ち込み", "5点・普通", "8点・元気"],
    "money_income": ["仕送りあり", "バイトあり", "特になし"],
    "money_expense": ["仕送りあり", "バイトあり", "特になし"],
    "money_goal": ["仕送りあり", "バイトあり", "特になし"],
    "time_weekday": ["授業中心", "バイト多め", "自由時間少ない"],
    "time_weekend": ["授業中心", "バイト多め", "自由時間少ない"],
    "goals": ["資格取得", "就活対策", "生活リズム改善"],
}

_NANNY_DEFAULT = [
    "体調を相談したい",
    "勉強を始めたい",
    "お金の相談",
    "今日の予定を整理したい",
    "今の気分を話したい",
]


def get_suggested_replies(user_id: str, state: dict) -> list[str]:
    """Return tap-to-send suggestion chips for the current brain mode / intake step."""
    brain = get_brain_status(user_id)
    mode = brain.get("mode") or ""

    if mode == "onboarding_ask_user_name":
        return ["山田", "ナム", "みたか"]

    if mode == "onboarding_ask_companion_name":
        return ["ルナ", "ミカ", "CorJJ", "その他（自分で入力）"]

    if mode == "profile_intake":
        step = int(brain.get("profile_intake_step") or state.get("profile_intake_step") or 0)
        if 0 <= step < len(PROFILE_QUESTIONS):
            key = PROFILE_QUESTIONS[step][0]
            chips = _PROFILE_CHIPS.get(key)
            if chips:
                return list(chips)
        return list(_NANNY_DEFAULT)

    if mode == "nanny_companion":
        return list(_NANNY_DEFAULT)

    return list(_NANNY_DEFAULT)
