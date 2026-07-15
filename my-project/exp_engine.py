import math

# 各アクションで獲得できるEXP（経験値）の定義
ACTION_EXP = {
    "morning_checkin": 8,
    "evening_checkin": 12
}
DAILY_CAP = 140  # 1日あたりの獲得上限

def add_exp(state: dict, action: str):
    gain = ACTION_EXP.get(action, 0)
    # 本日の獲得上限を超えないように調整
    remain = max(0, DAILY_CAP - state.get("daily_exp", 0))
    gain = min(gain, remain)
    
    # EXPの加算
    state["daily_exp"] = state.get("daily_exp", 0) + gain
    state["total_exp"] = state.get("total_exp", 0) + gain
    
    # レベル計算式（ルート計算によるレベルアップ処理）
    state["current_level"] = int(math.floor(1 + math.sqrt(state["total_exp"] / 100)))
    return gain, state