import math

# 各アクションで獲得できるEXP（経験値）の定義
ACTION_EXP = {
    "morning_checkin": 8,
    "evening_checkin": 12
}
DAILY_CAP = 140  # 1日あたりの獲得上限

def level_from_exp(total_exp: int) -> int:
    return int(math.floor(1 + math.sqrt(max(0, int(total_exp or 0)) / 100)))


def grant_exp(state: dict, gain: int):
    remain = max(0, DAILY_CAP - int(state.get("daily_exp") or 0))
    gain = min(max(0, int(gain or 0)), remain)
    state["daily_exp"] = int(state.get("daily_exp") or 0) + gain
    state["total_exp"] = int(state.get("total_exp") or 0) + gain
    state["current_level"] = level_from_exp(state["total_exp"])
    return gain, state


def add_exp(state: dict, action: str):
    return grant_exp(state, ACTION_EXP.get(action, 0))