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
    "お金の相談",
    "予定を整理したい",
    "健康に追記したい",
    "欲しいものがある",
]


_CONSULT_CHIPS = {
    "health": ["睡眠を教える", "気分は普通", "明日また報告する"],
    "money": ["支出を記録", "今日ランチ800円", "明日また報告する"],
}


def get_suggested_replies(user_id: str, state: dict) -> list[str]:
    """Return tap-to-send suggestion chips for the current brain mode / intake step."""
    from luna_service import load_user_brain

    brain_user = load_user_brain(user_id)
    consult = brain_user.get("consult_mode")
    if consult in _CONSULT_CHIPS:
        return list(_CONSULT_CHIPS[consult])

    brain = get_brain_status(user_id)
    mode = brain.get("mode") or ""

    if mode == "onboarding_ask_user_name":
        return ["山田", "ナム", "みたか"]

    if mode == "onboarding_ask_companion_name":
        return ["ルナ", "ミカ", "CorJJ", "その他（自分で入力）"]

    if mode == "profile_intake":
        if (
            not brain_user.get("first_class_saved")
            and int(brain_user.get("profile_intake_step") or 0) == 0
            and not (brain_user.get("life_profile") or {})
        ):
            return ["9:00", "10:30", "13:00"]
        step = int(brain.get("profile_intake_step") or state.get("profile_intake_step") or 0)
        if 0 <= step < len(PROFILE_QUESTIONS):
            key = PROFILE_QUESTIONS[step][0]
            chips = _PROFILE_CHIPS.get(key)
            if chips:
                return list(chips)
        return list(_NANNY_DEFAULT)

    if mode == "nanny_companion":
        return _chips_with_agenda(brain_user)

    return _chips_with_agenda(brain_user)


def _chips_with_agenda(user: dict, now=None) -> list[str]:
    """Answers to the question just asked. The home chat does not offer quests."""
    try:
        from day_coach import _now_jst, clock_care_now

        now = now or _now_jst()
        if user.get("care_one") == "wait":
            from care_turn import ONE_BURDEN_CHIPS

            return list(ONE_BURDEN_CHIPS)
        if clock_care_now(user, now=now):
            return ["大丈夫", "疲れた", "何かあった"]
        from care_turn import (
            before_first_class,
            check_back_due,
            day_word_ask_due,
            day_word_morning_due,
            day_word_waiting,
        )

        back = user.get("check_back") if isinstance(user.get("check_back"), dict) else {}
        if check_back_due(user, now=now) or (back.get("asked") and not back.get("answered")):
            from care_turn import tell_chips

            return tell_chips(str(back.get("title") or ""))
        quoted_on = str((user.get("day_word") or {}).get("quoted_on") or "")[:10]
        if day_word_morning_due(user, now) or (
            quoted_on == now.date().isoformat() and before_first_class(user, now)
        ):
            return ["大丈夫", "まだ残ってる", "話したい"]
        if day_word_waiting(user, now) or day_word_ask_due(user, now):
            return ["今日はここまで", "疲れた", "話したい"]
        ask_key = str(user.get("daily_ask_key") or "")
        if (
            ask_key
            and str(user.get("daily_ask_on") or "")[:10] == now.date().isoformat()
            and str(user.get("daily_answered_on") or "")[:10] != now.date().isoformat()
        ):
            return list(_PROFILE_CHIPS.get(ask_key) or ["あとで言う", "普通", "特になし"])
        if now.hour >= 22 or now.hour < 6:
            return ["眠れない", "何かあった", "大丈夫"]
    except Exception:
        pass
    if isinstance(user.get("care_recall"), dict) and user["care_recall"].get("note"):
        return ["少し楽になった", "まだ疲れてる", "大丈夫"]
    return ["大丈夫", "疲れた", "話したいことがある"]
