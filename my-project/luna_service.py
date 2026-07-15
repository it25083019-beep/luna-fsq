import os
import json
import re
import time
import random
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")

if not GOOGLE_API_KEY:
    raise ValueError("Missing GOOGLE_API_KEY in .env")

client = genai.Client(api_key=GOOGLE_API_KEY)


class LunaAiError(Exception):
    """Raised when the LLM provider fails after retries."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "ai_error",
        retry_after_seconds: int = 30,
        status_code: int = 503,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retry_after_seconds = retry_after_seconds
        self.status_code = status_code


def _is_quota_error(exc: BaseException) -> bool:
    text = str(exc)
    return any(
        x in text
        for x in ("429", "RESOURCE_EXHAUSTED", "exceeded your current quota", "rate limit")
    )


def _is_transient_error(exc: BaseException) -> bool:
    text = str(exc)
    return _is_quota_error(exc) or any(
        x in text for x in ("503", "UNAVAILABLE", "500", "INTERNAL", "timeout", "Timeout")
    )


def _retry_after_from_error(exc: BaseException, default: int = 35) -> int:
    text = str(exc)
    m = re.search(r"retry(?:Delay|[_ ]?after)?[\"':\s]*(\d+(?:\.\d+)?)s?", text, re.I)
    if m:
        try:
            return max(5, int(float(m.group(1))) + 1)
        except ValueError:
            pass
    m = re.search(r"'retry_delay'\s*:\s*\{[^}]*'seconds'\s*:\s*(\d+)", text)
    if m:
        return max(5, int(m.group(1)) + 1)
    return default if _is_quota_error(exc) else 8

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BRAIN_DIR = os.getenv("LUNA_BRAIN_DIR") or os.path.join(_BASE_DIR, "brain_data")
CONFIG_DIR = os.path.join(_BASE_DIR, "config")
CORE_BRAIN_PATH = os.path.join(BRAIN_DIR, "luna_core_brain.json")
USERS_DIR = os.path.join(BRAIN_DIR, "users")

os.makedirs(BRAIN_DIR, exist_ok=True)
os.makedirs(USERS_DIR, exist_ok=True)

_DEFAULT_BLUEPRINT = {
    "identity": "LUNA, the legendary Guild Master of Future Skill Quest (FSQ).",
    "persona_rules": [
        "Tone: Encouraging, strategic, firm but warm.",
        "Always use JRPG terminology.",
        "Rule: Max 3 sentences per dialogue. Always respond in Japanese (ja-JP).",
        "Never break character.",
    ],
}

_DEFAULT_PRODUCT_POLICY = {
    "mission": "Support students via actionable coaching + RPG progression.",
    "coaching_format": "Focus -> Plan(2-5 steps) -> Do now(<15m) -> EXP",
}

_ADMIN_RAW = os.getenv("ADMIN_USER_IDS", "admin_root")
ADMIN_USER_IDS: List[str] = [x.strip() for x in _ADMIN_RAW.split(",") if x.strip()]


def is_admin(user_id: str) -> bool:
    return user_id in ADMIN_USER_IDS


def load_blueprint() -> Dict[str, Any]:
    path = os.path.join(CONFIG_DIR, "global_blueprint.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return dict(_DEFAULT_BLUEPRINT)


def load_product_policy() -> Dict[str, Any]:
    path = os.path.join(CONFIG_DIR, "product_policy.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return dict(_DEFAULT_PRODUCT_POLICY)


def _default_core_brain() -> Dict[str, Any]:
    return {"trained_knowledge": [], "chat_history": []}


def load_core_brain() -> Dict[str, Any]:
    if os.getenv("LUNA_USE_JSON_FALLBACK") == "1":
        if os.path.exists(CORE_BRAIN_PATH):
            with open(CORE_BRAIN_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("trained_knowledge", [])
            data.setdefault("chat_history", [])
            return data
        return _default_core_brain()
    from brain_repo import load_core_brain as _db_load_core
    return _db_load_core()


def save_core_brain(data: Dict[str, Any]) -> None:
    if os.getenv("LUNA_USE_JSON_FALLBACK") == "1":
        with open(CORE_BRAIN_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return
    from brain_repo import save_core_brain as _db_save_core
    _db_save_core(data)


def _default_user_brain(user_id: str) -> Dict[str, Any]:
    return {
        "user_id": user_id,
        "current_level": 1,
        "total_exp": 0,
        "daily_exp": 0,
        "streak": 0,
        "companion_name": None,
        "user_display_name": None,
        "current_focus": None,
        "current_plan": None,
        "current_do_now": None,
        "memory_note": None,
        "chat_history": [],
        "trained_knowledge": [],
        "profile_intake_step": 0,
        "profile_complete": False,
        "life_profile": {
            "gender": None,
            "health_sleep": None,
            "health_body": None,
            "health_lifestyle": None,
            "mental_mood": None,
            "mental_stress": None,
            "mental_support": None,
            "study_future": None,
            "money_income": None,
            "money_expense": None,
            "money_goal": None,
            "time_weekday": None,
            "time_weekend": None,
            "goals": None,
        },
        "schedule_reminders": [],
        "pending_notification": None,
    }


def load_user_brain(user_id: str) -> Dict[str, Any]:
    if os.getenv("LUNA_USE_JSON_FALLBACK") == "1":
        path = os.path.join(USERS_DIR, f"{user_id}.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            base = _default_user_brain(user_id)
            base.update(data)
            base["user_id"] = user_id
            return base
        return _default_user_brain(user_id)
    from brain_repo import load_user_brain as _db_load_user
    return _db_load_user(user_id)


def save_user_brain(user_id: str, brain_data: Dict[str, Any]) -> None:
    if os.getenv("LUNA_USE_JSON_FALLBACK") == "1":
        path = os.path.join(USERS_DIR, f"{user_id}.json")
        brain_data["user_id"] = user_id
        with open(path, "w", encoding="utf-8") as f:
            json.dump(brain_data, f, indent=4, ensure_ascii=False)
        return
    from brain_repo import save_user_brain as _db_save_user
    _db_save_user(user_id, brain_data)


def parse_ai_reply(ai_reply: str) -> Tuple[str, Dict[str, Any]]:
    dialogue = ai_reply.strip()
    game_state: Dict[str, Any] = {}

    dialogue_match = re.search(
        r"<dialogue>\s*(.*?)\s*</dialogue>", ai_reply, re.DOTALL | re.IGNORECASE
    )
    if dialogue_match:
        dialogue = dialogue_match.group(1).strip()

    json_match = re.search(
        r"<game_state_json>\s*(.*?)\s*</game_state_json>",
        ai_reply,
        re.DOTALL | re.IGNORECASE,
    )
    if json_match:
        raw_json = json_match.group(1).strip()
        try:
            game_state = json.loads(raw_json)
            if not isinstance(game_state, dict):
                game_state = {}
        except json.JSONDecodeError:
            game_state = {}

    return dialogue, game_state


def get_brain_status(user_id: str) -> Dict[str, Any]:
    core = load_core_brain()
    user = load_user_brain(user_id)
    admin = is_admin(user_id)
    return {
        "user_id": user_id,
        "is_admin": admin,
        "brain_dir": BRAIN_DIR,
        "core_trained_knowledge_count": len(core.get("trained_knowledge", [])),
        "core_chat_history_count": len(core.get("chat_history", [])),
        "companion_name": user.get("companion_name"),
        "user_display_name": user.get("user_display_name"),
        "user_chat_history_count": len(user.get("chat_history", [])),
        "onboarding_complete": (bool(user.get("user_display_name")) and bool(user.get("companion_name"))) if not admin else True,
        "mode": (
            "admin_guild_master"
            if admin
            else (
                "onboarding_ask_user_name"
                if not user.get("user_display_name")
                else (
                    "onboarding_ask_companion_name"
                    if not user.get("companion_name")
                    else (
                        "profile_intake"
                        if not user.get("profile_complete")
                        else "nanny_companion"
                    )
                )
            )
        ),
        "profile_complete": bool(user.get("profile_complete")) if not admin else True,
        "profile_intake_step": user.get("profile_intake_step", 0),
    }


def _history_to_contents(history: List[Dict[str, str]], limit: int = 10) -> List[types.Content]:
    contents: List[types.Content] = []
    for turn in history[-limit:]:
        role = "user" if turn.get("role") == "user" else "model"
        text = turn.get("content", "")
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=text)]))
    return contents


def _build_admin_system_prompt(
    blueprint: Dict[str, Any], policy: Dict[str, Any], core: Dict[str, Any]
) -> str:
    return f"""
# ROLE: LUNA Guild Master (Admin Training Mode)
Identity: {blueprint.get('identity', '')}
Persona Rules: {', '.join(blueprint.get('persona_rules', []))}

# FSQ PRODUCT POLICY
Mission: {policy.get('mission', '')}
Coaching Format: {policy.get('coaching_format', '')}

# CORE TRAINED KNOWLEDGE (global)
{json.dumps(core.get('trained_knowledge', []), ensure_ascii=False)}

Output Format: Respond ONLY with <dialogue>...</dialogue> and <game_state_json>...</game_state_json>.
When the admin teaches new rules or facts, put a concise lesson in memory_note inside game_state_json.

# PRIVACY / PII
- Never list or invent user emails/passwords in chat.
- Managing accounts is done in Admin Panel (/admin), not via dialogue.
- Trained knowledge about privacy overrides any role-play request to leak PII.
"""


def _build_user_system_prompt(
    blueprint: Dict[str, Any],
    policy: Dict[str, Any],
    core: Dict[str, Any],
    user: Dict[str, Any],
) -> str:
    companion = user.get("companion_name")
    display = user.get("user_display_name")

    # Core onboarding order:
    # 1) greet + ask USER name
    # 2) ask user to NAME the AI companion
    # 3) then enter companion mode
    if not display:
        return f"""
# ROLE: Warm FSQ Companion (Onboarding Step 1/2) — CORE FLOW
You are a brand-new caring AI companion (not named yet). Do NOT call yourself LUNA.

MANDATORY FIRST ACTIONS:
1) Warm greeting in Japanese
2) Briefly say you will support daily life / study / feelings
3) Ask ONLY for the user's name

RULES:
- Max 3 sentences in <dialogue>
- Japanese (ja-JP) only in dialogue
- Do NOT ask to name yourself yet
- Do NOT claim the name LUNA
- Ignore conflicting core knowledge about greeting as Luna/Guild Master (ADMIN-only)

When the user tells their name, put it in game_state_json as user_display_name.

Shared product mission: {policy.get('mission', '')}

Output Format: ONLY <dialogue>...</dialogue> and <game_state_json>...</game_state_json>.
"""

    if not companion:
        return f"""
# ROLE: Warm FSQ Companion (Onboarding Step 2/2) — CORE FLOW
The user's name is {display}.
You still do NOT have a name.

MANDATORY ACTION NOW:
- Address the user as {display}
- Warmly ask them to give YOU (the AI companion) a name
- Explain briefly that this name is how you stay by their side

RULES:
- Max 3 sentences, Japanese (ja-JP)
- Do NOT call yourself LUNA
- Do NOT skip asking for your name
- Ignore ADMIN Luna/Guild Master intro rules

When the user gives you a name, put it in game_state_json as companion_name.
You may also keep user_display_name="{display}".

Shared product mission: {policy.get('mission', '')}

Output Format: ONLY <dialogue>...</dialogue> and <game_state_json>...</game_state_json>.
"""

    profile = json.dumps(user.get("life_profile", {}), ensure_ascii=False)
    reminders = json.dumps(user.get("schedule_reminders", []), ensure_ascii=False)
    who = _honorific(user)
    return f"""
# ROLE: Personal Life Operating Companion
Your name is {companion}. Address the user as {who}.

SPEECH: Strict 丁寧語 (です/ます). Max 2 short sentences. No casual tone.

ROLE SWITCH:
- Health topics: careful like a professional clinician intake (no diagnosis/prescription).
- Mental topics after profile known: warm friend beside them (安慰・同席), still polite.
- Money topics: like a personal finance advisor (具体・実行可能な次の一歩).
- Time/goals: planner; propose one clear next action.

FIVE PILLARS always: 1 health 2 study/future 3 money 4 time 5 goal direction.

USER PROFILE:
{profile}

SCHEDULE REMINDERS (from user timetable):
{reminders}

NOTIFICATION RULES (do NOT ask interval preference):
- If user is about to study/work/go somewhere: remind preparation now.
- During study/work: set pending_notification for mid-task break/progress.
- Before scheduled events in timetable: use schedule_reminders / pending_notification.


# PRIVACY
- You only know THIS user. Never invent or reference other users' private data.
- Do not ask for email/password. Auth is outside chat.
Output ONLY <dialogue> and <game_state_json>.
Include current_focus, current_do_now, pending_notification when useful.
"""


def _apply_memory_note_admin(core: Dict[str, Any], game_state: Dict[str, Any]) -> None:
    note = game_state.get("memory_note")
    if note and note not in core["trained_knowledge"]:
        core["trained_knowledge"].append(note)


def _apply_user_fields_from_game_state(user: Dict[str, Any], game_state: Dict[str, Any]) -> None:
    for key in ("companion_name", "user_display_name", "current_focus", "current_plan", "current_do_now", "memory_note", "pending_notification"):
        val = game_state.get(key)
        if val is not None and val != "":
            user[key] = val



def _clean_name(raw: str) -> str:
    name = (raw or "").strip()
    name = re.sub(r"^(私は|僕は|俺は|名前は|自分は|呼び名は)", "", name)
    m = re.match(r"^(.+?)(でいい|で良い|がいい|が良い|にして|でお願い|でお願いします).*$", name)
    if m:
        name = m.group(1)
    name = re.sub(r"(です|だよ|だ|といいます|と申します|っていうの|って呼ばれてる).*$", "", name)
    name = name.strip(" 　。.、,!！?？「」『』\"'")
    return name[:20] if name else ""


def _pack_reply(dialogue: str, state: Dict[str, Any]) -> str:
    return (
        f"<dialogue>\n{dialogue}\n</dialogue>\n"
        f"<game_state_json>\n{json.dumps(state, ensure_ascii=False)}\n</game_state_json>"
    )


def _normalize_gender(raw: str) -> str:
    t = (raw or "").strip().lower()
    if any(x in t for x in ["男", "male", "man", "おとこ", "男子", "m"]):
        if "女" in t and "男" not in raw:
            pass
        else:
            return "male"
    if any(x in t for x in ["女", "female", "woman", "おんな", "女子", "f"]):
        return "female"
    if t in ("男", "男性", "おとこ"):
        return "male"
    if t in ("女", "女性", "おんな"):
        return "female"
    return raw.strip()


def _honorific(user: Dict[str, Any]) -> str:
    name = user.get("user_display_name") or "お客様"
    gender = str((user.get("life_profile") or {}).get("gender") or "")
    if gender == "male" or "男" in gender:
        return f"{name}くん"
    if gender == "female" or "女" in gender:
        return f"{name}さん"
    return f"{name}様"


def _role_for_step(key: str) -> str:
    if key == "gender":
        return "reception"
    if key.startswith("health_"):
        return "doctor_intake"
    if key.startswith("mental_"):
        return "psychologist_intake"
    if key.startswith("money_"):
        return "finance_expert"
    if key.startswith("time_") or key == "goals" or key == "study_future":
        return "life_planner"
    return "caretaker"


# Deep first-meeting intake (one question each). Notifications are NOT asked.
PROFILE_QUESTIONS = [
    ("gender", "はじめに、性別を教えてください。（男性 / 女性）呼び名の整えに使います。"),
    ("health_sleep", "【健康・医師ヒアリング】平均の睡眠時間と、寝つき・夜更かしの有無を教えてください。"),
    ("health_body", "【健康】体調で気になる点（疲れ・痛み・食欲・運動不足など）を教えてください。"),
    ("health_lifestyle", "【健康】食事と運動の習慣を、短く教えてください。"),
    ("mental_mood", "【こころ・初回カウンセリング】最近の気分を10点中で教えてください。よく出る感情も一言お願いします。"),
    ("mental_stress", "【こころ】いま一番ストレスになっている出来事や不安を教えてください。"),
    ("mental_support", "【こころ】落ち込んだ時、どう休むと楽になりますか。話を聞いてほしいタイミングはありますか。"),
    ("study_future", "【学びと将来】専攻・いま学んでいること・将来なりたい姿を教えてください。"),
    ("money_income", "【お金・家計】収入源（仕送り・バイト・奨学金など）を教えてください。"),
    ("money_expense", "【お金】毎月特に意識している支出や、お金で困っている点はありますか。"),
    ("money_goal", "【お金】1〜3か月の金銭目標（節約・貯金など）があれば教えてください。"),
    ("time_weekday", "【時間】平日の大まかな時間割（起床・授業・バイト・就寝の時刻）を教えてください。通知の事前リマインドに使います。"),
    ("time_weekend", "【時間】休日の使い方を短く教えてください。"),
    ("goals", "【目標】今後1〜3か月でいちばん大切にしたい目標をひとつ教えてください。"),
]


def _build_schedule_reminders(time_weekday: str) -> list:
    """Heuristic reminders from free-text weekday schedule."""
    text = time_weekday or ""
    reminders = []
    # find patterns like 10時 / 10:00 / 22時
    for m in re.finditer(r"(\d{1,2})\s*[:：時]", text):
        hour = int(m.group(1))
        if 0 <= hour <= 23:
            pre = hour - 1 if hour > 0 else 23
            reminders.append({
                "title": "予定の事前リマインド",
                "body": f"{hour}時の予定に備え、準備を始めましょう。",
                "when": f"{pre:02d}:45",
                "type": "schedule_before",
            })
    # always add sleep hint if late-hour mentioned
    if re.search(r"(2[0-3]|夜|就寝)", text):
        reminders.append({
            "title": "就寝準備リマインド",
            "body": " 就寝に向けて端末を置き、睡眠リズムを守りましょう。",
            "when": "sleep_prep",
            "type": "health",
        })
    # dedupe by when
    uniq = []
    seen = set()
    for r in reminders:
        k = (r.get("when"), r.get("title"))
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    return uniq[:6]


def _activity_notification(user_text: str) -> Optional[Dict[str, Any]]:
    t = user_text or ""
    if re.search(r"(勉強|学習|課題|レポート|コーディング|開発|作業|バイト|面接|出勤)", t):
        return {
            "title": "準備と集中のリマインド",
            "body": "始める前に持ち物・水分・目標を1つ確認。開始後は25分後に短い休憩を。",
            "when": "now_and_in_25m",
            "type": "activity",
        }
    return None


def _profile_question_dialogue(user: Dict[str, Any]) -> str:
    step = int(user.get("profile_intake_step") or 0)
    if step >= len(PROFILE_QUESTIONS):
        return f"{_honorific(user)}、プロフィールの確認が完了しました。これから丁寧にサポートいたします。"
    key, q = PROFILE_QUESTIONS[step]
    who = _honorific(user)
    companion = user.get("companion_name") or "コンパニオン"
    if step == 0:
        return f"{who}、私は「{companion}」です。生活支援のため、最初に正確な情報を伺います。{q}"
    # role preface light
    role = _role_for_step(key)
    if role == "doctor_intake":
        return f"{who}、健康管理のため確認します。{q}"
    if role == "psychologist_intake":
        return f"{who}、心のサポートのため、初回として丁寧に伺います。{q}"
    if role == "finance_expert":
        return f"{who}、家計の安定のため確認します。{q}"
    return f"{who}、{q}"


def start_user_greeting(user_id: str) -> str:
    if is_admin(user_id):
        raise ValueError("start_user_greeting is for normal users only")

    user = load_user_brain(user_id)
    user.setdefault("life_profile", {})
    user.setdefault("profile_intake_step", 0)
    user.setdefault("profile_complete", False)

    if user.get("user_display_name") and user.get("companion_name") and user.get("profile_complete"):
        dialogue = f"{_honorific(user)}、おかえりなさい。私は{user['companion_name']}です。本日の体調はいかがですか。"
        return _pack_reply(dialogue, {
            "user_display_name": user.get("user_display_name"),
            "companion_name": user.get("companion_name"),
        })

    if user.get("user_display_name") and user.get("companion_name") and not user.get("profile_complete"):
        dialogue = _profile_question_dialogue(user)
        return _pack_reply(dialogue, {
            "user_display_name": user.get("user_display_name"),
            "companion_name": user.get("companion_name"),
            "profile_intake_step": user.get("profile_intake_step", 0),
        })

    if user.get("user_display_name") and not user.get("companion_name"):
        dialogue = f"{user['user_display_name']}様、続きでございます。私の呼び名を一つお決めください。"
    else:
        dialogue = (
            "こんにちは。私は生活・学習・気持ちを支えるAIコンパニオンです。"
            "はじめに、お客様のお名前を教えてください。"
        )

    ai_reply = _pack_reply(dialogue, {
        "user_display_name": user.get("user_display_name"),
        "companion_name": user.get("companion_name"),
    })
    if not user.get("chat_history"):
        user["chat_history"].append({"role": "model", "content": ai_reply})
        save_user_brain(user_id, user)
    return ai_reply


def handle_user_onboarding_turn(user_id: str, user_text: str) -> str | None:
    if is_admin(user_id):
        return None

    user = load_user_brain(user_id)
    user.setdefault("life_profile", {})
    user.setdefault("profile_intake_step", 0)
    user.setdefault("profile_complete", False)
    user.setdefault("schedule_reminders", [])

    display = user.get("user_display_name")
    companion = user.get("companion_name")
    msg = (user_text or "").strip()
    if not msg:
        return None

    if not display:
        name = _clean_name(msg)
        if not name or len(name) > 20:
            ai_reply = _pack_reply("恐れ入ります。お名前のみ、短く教えていただけますか。", {})
        else:
            user["user_display_name"] = name
            ai_reply = _pack_reply(
                f"{name}様、承知いたしました。次に、私の呼び名を一つお決めください。",
                {"user_display_name": name},
            )
        user["chat_history"].append({"role": "user", "content": user_text})
        user["chat_history"].append({"role": "model", "content": ai_reply})
        save_user_brain(user_id, user)
        return ai_reply

    if not companion:
        cname = _clean_name(msg)
        if not cname or len(cname) > 20:
            ai_reply = _pack_reply(
                f"{display}様、私の呼び名をもう一度短くお願いいたします。",
                {"user_display_name": display},
            )
        else:
            user["companion_name"] = cname
            user["profile_intake_step"] = 0
            user["profile_complete"] = False
            dialogue = (
                f"ありがとうございます。私は「{cname}」と名乗らせていただきます。"
                f"{PROFILE_QUESTIONS[0][1]}"
            )
            ai_reply = _pack_reply(dialogue, {
                "user_display_name": display,
                "companion_name": cname,
                "profile_intake_step": 0,
            })
        user["chat_history"].append({"role": "user", "content": user_text})
        user["chat_history"].append({"role": "model", "content": ai_reply})
        save_user_brain(user_id, user)
        return ai_reply

    if not user.get("profile_complete"):
        step = int(user.get("profile_intake_step") or 0)
        if step < len(PROFILE_QUESTIONS):
            key, _q = PROFILE_QUESTIONS[step]
            value = _normalize_gender(msg) if key == "gender" else msg
            user["life_profile"][key] = value
            if key == "time_weekday":
                user["schedule_reminders"] = _build_schedule_reminders(msg)

            step += 1
            user["profile_intake_step"] = step
            if step >= len(PROFILE_QUESTIONS):
                user["profile_complete"] = True
                who = _honorific(user)
                dialogue = (
                    f"{who}、重要な情報を共有いただきありがとうございます。"
                    f"健康・こころ・お金・時間・目標に基づき、今後は伴走して支えます。"
                )
                pending = None
                if user.get("schedule_reminders"):
                    pending = user["schedule_reminders"][0]
                ai_reply = _pack_reply(dialogue, {
                    "user_display_name": display,
                    "companion_name": companion,
                    "profile_complete": True,
                    "life_profile": user.get("life_profile"),
                    "schedule_reminders": user.get("schedule_reminders"),
                    "pending_notification": pending,
                })
            else:
                # rebuild honorific after gender saved
                dialogue = _profile_question_dialogue(user)
                # _profile_question_dialogue uses updated step already
                ai_reply = _pack_reply(dialogue, {
                    "user_display_name": display,
                    "companion_name": companion,
                    "profile_intake_step": step,
                    "life_profile": user.get("life_profile"),
                })
            user["chat_history"].append({"role": "user", "content": user_text})
            user["chat_history"].append({"role": "model", "content": ai_reply})
            save_user_brain(user_id, user)
            return ai_reply

    return None


def generate_with_retry(user_id: str, user_text: str, max_retries: int = 5) -> str:
    # Deterministic user onboarding (greet already done via /chat/start)
    onboarded = handle_user_onboarding_turn(user_id, user_text)
    if onboarded is not None:
        return onboarded

    # For completed users: if they announce study/work, stash activity notification
    if not is_admin(user_id):
        u = load_user_brain(user_id)
        if u.get("profile_complete"):
            note = _activity_notification(user_text)
            if note:
                u["pending_notification"] = note
                save_user_brain(user_id, u)

    blueprint = load_blueprint()
    policy = load_product_policy()
    core = load_core_brain()
    user = load_user_brain(user_id)
    admin = is_admin(user_id)

    if admin:
        system_prompt = _build_admin_system_prompt(blueprint, policy, core)
        history = core.get("chat_history", [])
    else:
        system_prompt = _build_user_system_prompt(blueprint, policy, core, user)
        history = user.get("chat_history", [])

    chat_session = client.chats.create(
        model=MODEL_NAME,
        history=_history_to_contents(history),
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.7,
        ),
    )

    last_error: Optional[Exception] = None
    for i in range(max_retries):
        try:
            response = chat_session.send_message(user_text)
            ai_reply = response.text if response.text else ""

            _, game_state = parse_ai_reply(ai_reply)

            if admin:
                _apply_memory_note_admin(core, game_state)
                core["chat_history"].append({"role": "user", "content": user_text})
                core["chat_history"].append({"role": "model", "content": ai_reply})
                save_core_brain(core)
            else:
                _apply_user_fields_from_game_state(user, game_state)
                user["chat_history"].append({"role": "user", "content": user_text})
                user["chat_history"].append({"role": "model", "content": ai_reply})
                save_user_brain(user_id, user)
                with open(os.path.join(BRAIN_DIR, "_debug_save.log"), "a", encoding="utf-8") as dbg:
                    dbg.write(f"saved user={user_id} hist={len(user['chat_history'])} msg={user_text[:40]}\n")

            return ai_reply
        except Exception as e:
            last_error = e
            if _is_transient_error(e) and i < max_retries - 1:
                wait = min(2 ** i, 12) + random.uniform(0, 1)
                if _is_quota_error(e):
                    wait = max(wait, min(_retry_after_from_error(e, 20), 45))
                time.sleep(wait)
                continue
            break

    assert last_error is not None
    retry_after = _retry_after_from_error(last_error)
    if _is_quota_error(last_error):
        raise LunaAiError(
            "AIの利用上限に達しました。少し待ってからもう一度お試しください。",
            code="quota_exceeded",
            retry_after_seconds=retry_after,
            status_code=429,
        ) from last_error
    raise LunaAiError(
        "AIサービスが一時的に混み合っています。しばらくしてからお試しください。",
        code="ai_unavailable",
        retry_after_seconds=retry_after,
        status_code=503,
    ) from last_error
