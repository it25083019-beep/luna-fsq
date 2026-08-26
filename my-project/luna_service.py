import os
import json
import re
import time
import random
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

from llm_client import active_backend_label, complete_chat, provider_name

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")

# Gemini client is optional when using openai_compatible / groq / ollama.
client = None
if provider_name() == "gemini":
    if not GOOGLE_API_KEY:
        raise ValueError("Missing GOOGLE_API_KEY in .env (or set LLM_PROVIDER=groq/ollama/openai_compatible)")
    from google import genai

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
        "life_modules": {
            "health": {"notes": [], "structured": {}, "updated_at": None},
            "money": {"notes": [], "structured": {}, "updated_at": None},
            "schedule": {"notes": [], "structured": {}, "updated_at": None},
        },
        "schedule_reminders": [],
        "pending_notification": None,
    }


def load_user_brain(user_id: str) -> Dict[str, Any]:
    if os.getenv("LUNA_USE_JSON_FALLBACK") == "1":
        from brain_repo import _parse_state

        path = os.path.join(USERS_DIR, f"{user_id}.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            base = _parse_state(json.dumps(data, ensure_ascii=False), _default_user_brain(user_id))
            base["user_id"] = user_id
            return base
        return _default_user_brain(user_id)
    from brain_repo import load_user_brain as _db_load_user
    return _db_load_user(user_id)


def save_user_brain(user_id: str, brain_data: Dict[str, Any]) -> None:
    # Ephemeral runtime flags must never be persisted.
    brain_data.pop("_schedule_dirty", None)
    if os.getenv("LUNA_USE_JSON_FALLBACK") == "1":
        from brain_merge import safe_merge_for_save

        path = os.path.join(USERS_DIR, f"{user_id}.json")
        existing = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    existing = json.load(f) or {}
            except (json.JSONDecodeError, OSError):
                existing = {}
        payload = safe_merge_for_save(existing, dict(brain_data))
        payload["user_id"] = user_id
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)
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

    # VTuber-style [emotion] tags → expression hint for frontend
    emo_match = re.match(
        r"^\[(neutral|joy|happy|sadness|sad|surprise|surprised|think|cheer|wave)\]\s*",
        dialogue,
        re.IGNORECASE,
    )
    if emo_match:
        game_state["emotion"] = emo_match.group(1).lower()
        dialogue = dialogue[emo_match.end() :].strip()

    json_match = re.search(
        r"<game_state_json>\s*(.*?)\s*</game_state_json>",
        ai_reply,
        re.DOTALL | re.IGNORECASE,
    )
    if json_match:
        raw_json = json_match.group(1).strip()
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, dict):
                # keep emotion from tag if JSON didn't set it
                if "emotion" in game_state and "emotion" not in parsed:
                    parsed["emotion"] = game_state["emotion"]
                game_state = parsed
            else:
                game_state = {}
        except json.JSONDecodeError:
            pass

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


def _history_to_contents(history: List[Dict[str, str]], limit: int = 6):
    """Gemini Content list; empty when not using gemini."""
    if provider_name() != "gemini":
        return []
    from google.genai import types

    contents = []
    for turn in history[-limit:]:
        role = "user" if turn.get("role") == "user" else "model"
        text = turn.get("content", "")
        if "<dialogue>" in text:
            m = re.search(r"<dialogue>\s*(.*?)\s*</dialogue>", text, re.DOTALL | re.IGNORECASE)
            if m:
                text = m.group(1).strip()
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
    from life_modules import modules_prompt_block

    modules_block = modules_prompt_block(user)
    who = _honorific(user)
    return f"""
# ROLE: Personal Life Operating Companion
Your name is {companion}. Address the user as {who}.

{_speech_style_block(user)}
- Max 2 short sentences in <dialogue>.

ROLE SWITCH:
- Health topics: careful like a professional clinician intake (no diagnosis/prescription).
- Mental topics after profile known: warm friend beside them (安慰・同席), still polite.
- Money topics: like a personal finance advisor (具体・実行可能な次の一歩).
- Time/goals: planner; propose one clear next action.

THREE LIFE MODULES (first-meeting questions are only a baseline; user can add more later):
1) 健康 health  2) お金 money  3) スケジュール schedule

{modules_block}

FIVE PILLARS always: 1 health 2 study/future 3 money 4 time 5 goal direction.

EMOTION TAGS (like VTuber emotionMap — put ONE tag at the start of dialogue when fitting):
[neutral] [joy] [sadness] [surprise] [think] [cheer] [wave] [happy]
Example: [cheer]よくできました。次は短い休憩を。

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



def _detect_user_speech_style(text: str) -> str:
    """Rough detect: polite / casual / mixed from user message."""
    t = (text or "").strip()
    if not t:
        return "polite"
    casual_hits = len(re.findall(r"(だよ|だね|じゃん|かな\?|っす|やん|まじ|w+|www|！{2,}|タメ|おっけー|うん|ええ)", t))
    polite_hits = len(re.findall(r"(です|ます|ございます|いたします|ください|お願い|恐れ入ります)", t))
    if casual_hits >= 2 and casual_hits > polite_hits:
        return "casual"
    if casual_hits >= 1 and polite_hits >= 1:
        return "mixed"
    if polite_hits >= 1:
        return "polite"
    return "mixed"


def _relationship_level(user: Dict[str, Any]) -> int:
    try:
        return max(1, min(3, int(user.get("relationship_level") or 1)))
    except (TypeError, ValueError):
        return 1


def _update_relationship(user: Dict[str, Any], user_text: str) -> None:
    """Increase familiarity over time; mirror user tone. Admin excluded by caller."""
    user.setdefault("chat_turn_count", 0)
    user["chat_turn_count"] = int(user.get("chat_turn_count") or 0) + 1
    turns = user["chat_turn_count"]
    style = _detect_user_speech_style(user_text)
    prev = user.get("user_speech_style") or "polite"
    if style == "casual" or (style == "mixed" and prev != "polite"):
        user["user_speech_style"] = style
    elif style == "mixed":
        user["user_speech_style"] = "mixed"
    else:
        user["user_speech_style"] = prev if prev != "casual" else "mixed"

    level = 1
    if user.get("profile_complete") and turns >= 8:
        level = 2
    if turns >= 25 or int(user.get("streak") or 0) >= 5:
        level = max(level, 2)
    if turns >= 50 and user.get("user_speech_style") in ("casual", "mixed"):
        level = 3
    if turns >= 80:
        level = 3
    user["relationship_level"] = level


def _speech_style_block(user: Dict[str, Any]) -> str:
    level = _relationship_level(user)
    style = user.get("user_speech_style") or "polite"
    if level == 1:
        return (
            "SPEECH (relationship=NEW): Warm 丁寧語（です・ます）. Natural and soft, NOT stiff business keigo. "
            "Avoid excessive 敬語・堅い表現. Max 2 short sentences. Sound like a kind companion, not a call center."
        )
    if level == 2:
        return (
            "SPEECH (relationship=FAMILIAR): Still polite base, but softer and closer. "
            "You may use gentle endings (〜ね、〜よ、〜かな). Mirror the user's energy lightly. "
            f"User style hint: {style}. No rude slang, no commands."
        )
    return (
        "SPEECH (relationship=CLOSE): Friendly close tone. If user is casual, you may use light casual Japanese "
        "(〜だね、〜しよう、〜かも) while staying supportive. Avoid heavy keigo chains. "
        f"Match user style: {style}. Never insult, never baby-talk unless user prefers it."
    )


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


# Deep first-meeting intake (baseline only). User can add more later per module.
PROFILE_QUESTIONS = [
    ("gender", "はじめに、性別を教えてください。（男性 / 女性）呼び名の整えに使います。"),
    ("health_sleep", "【1/3 健康】平均の睡眠時間と、寝つき・夜更かしの有無を教えてください。（後から追記できます）"),
    ("health_body", "【1/3 健康】体調で気になる点（疲れ・痛み・食欲・運動不足など）を教えてください。"),
    ("health_lifestyle", "【1/3 健康】食事と運動の習慣を、短く教えてください。"),
    ("mental_mood", "【1/3 健康・こころ】最近の気分を10点中で教えてください。よく出る感情も一言お願いします。"),
    ("mental_stress", "【1/3 健康・こころ】いま一番ストレスになっている出来事や不安を教えてください。"),
    ("mental_support", "【1/3 健康・こころ】落ち込んだ時、どう休むと楽になりますか。"),
    ("study_future", "【3/3 スケジュール準備】専攻・いま学んでいること・将来なりたい姿を教えてください。"),
    ("money_income", "【2/3 お金】収入源（仕送り・バイト時給・奨学金など）を教えてください。（後から追記可）"),
    ("money_expense", "【2/3 お金】毎月特に意識している支出や、お金で困っている点はありますか。"),
    ("money_goal", "【2/3 お金】1〜3か月の金銭目標や、欲しいものがあれば教えてください。"),
    ("time_weekday", "【3/3 スケジュール】平日の大まかな時間割（起床・授業・バイト・就寝）を教えてください。"),
    ("time_weekend", "【3/3 スケジュール】休日の使い方を短く教えてください。"),
    ("goals", "【まとめ】今後1〜3か月でいちばん大切にしたい目標をひとつ教えてください。"),
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
        lv = _relationship_level(user)
        cname = user['companion_name']
        who = _honorific(user)
        if lv >= 3:
            dialogue = f"{who}、おかえり。{cname}だよ。今日の調子はどう？"
        elif lv >= 2:
            dialogue = f"{who}、おかえりなさい。{cname}です。今日の体調はどうですか？"
        else:
            dialogue = f"{who}、おかえりなさい。私は{cname}です。本日の体調はいかがですか。"
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


def safe_chat_start_reply(user_id: str, message: str = "") -> str:
    """Always return a speak-first greeting; never raise for normal UX path."""
    try:
        if is_admin(user_id):
            try:
                return generate_with_retry(user_id, message or "こんにちは", max_retries=2)
            except Exception:
                return _pack_reply(
                    "Hoang-sama、ギルドマスターのLUNAです。本日もご指示をどうぞ。",
                    {},
                )
        return start_user_greeting(user_id)
    except Exception:
        return _pack_reply(
            "こんにちは。LUNAです。今日も一緒にがんばろうね。何か話しかけてください。",
            {},
        )


def soft_chat_failure_reply(exc: BaseException) -> str:
    """Turn AI outages into a spoken line so the bubble is never empty."""
    if _is_quota_error(exc) or (isinstance(exc, LunaAiError) and getattr(exc, "code", "") == "quota_exceeded"):
        msg = "少し混み合っているみたいだけど、ちゃんと話は聞いているよ。もう一度短く話しかけてね。"
    elif isinstance(exc, LunaAiError):
        msg = str(exc)
    else:
        msg = "少し混み合っているみたい。もう一度話しかけてくれる？"
    return _pack_reply(msg, {"emotion": "think"})


# When Gemini quota is hit, skip API for a while and answer locally (no 30s wait).
_quota_block_until: float = 0.0


def _quota_blocked() -> bool:
    return time.time() < _quota_block_until


def _mark_quota_block(seconds: int = 90) -> None:
    global _quota_block_until
    _quota_block_until = time.time() + max(45, min(int(seconds or 90), 180))


def _local_companion_reply(user: Dict[str, Any], user_text: str) -> str:
    """Instant Japanese companion lines without Gemini (mood / daily care)."""
    msg = (user_text or "").strip()
    who = _honorific(user) if user.get("user_display_name") else "あなた"
    cname = user.get("companion_name") or "LUNA"
    emotion = "happy"

    if re.search(r"疲れ|つらい|しんど|眠い|疲れた|mệt|tired|exhausted", msg, re.I):
        dialogue = (
            f"{who}、お疲れさま。無理はしないでね。"
            f"水を一口飲んで、肩の力を抜いて深呼吸しよう。{cname}がそばにいるよ。"
        )
        emotion = "sad"
    elif re.search(r"元気|調子いい|嬉しい|たのしい|楽しい|やった", msg):
        dialogue = f"{who}、それはうれしいな！その調子だよ。今日の小さな成功もちゃんと褒めてあげてね。"
        emotion = "cheer"
    elif re.search(r"おはよう|こんにちは|こんばんは|はじめまして|よろしく", msg):
        dialogue = f"{who}、こんにちは。{cname}だよ。今日も一緒にいこうね。体調はどう？"
        emotion = "wave"
    elif re.search(r"眠|寝|眠れ", msg):
        dialogue = f"{who}、眠いときは体が休めサインを出してるよ。可能なら短く横になって、明日に備えよう。"
        emotion = "think"
    elif re.search(r"お金|財布|節約|使った", msg):
        dialogue = f"{who}、お金の話も大事だね。今日はいくら使ったか、短くメモするだけでも安心につながるよ。"
        emotion = "think"
    elif re.search(r"勉強|宿題|テスト|授業", msg):
        dialogue = f"{who}、勉強がんばってるね。まずは15分だけ集中→休憩、のリズムがおすすめだよ。"
        emotion = "cheer"
    elif re.search(r"予定|スケジュール|バイト", msg):
        dialogue = f"{who}、予定を見せてくれてありがとう。無理のない順に並べて、一つずつ進めよう。"
        emotion = "think"
    elif len(msg) <= 40:
        dialogue = (
            f"{who}、話してくれてありがとう。ちゃんと受け取ったよ。"
            f"今は少し混み合っているけど、{cname}はそばにいるからね。"
        )
        emotion = "happy"
    else:
        dialogue = (
            f"{who}、長い話もありがとう。要点だけ整理すると楽になるよ。"
            f"一番つらい点を一言で教えてくれる？"
        )
        emotion = "think"

    return _pack_reply(
        dialogue,
        {
            "emotion": emotion,
            "user_display_name": user.get("user_display_name"),
            "companion_name": user.get("companion_name"),
        },
    )


def _persist_local_turn(user_id: str, user: Dict[str, Any], user_text: str, ai_reply: str) -> str:
    user.setdefault("chat_history", [])
    user["chat_history"].append({"role": "user", "content": user_text})
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
                    f"{who}、初回の基本情報ありがとうございます。"
                    f"これは入り口だけです。あとから【健康】【お金】【スケジュール】の各項目に追記できます。"
                    f"生活を一緒に整えていきましょう。"
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


def generate_with_retry(user_id: str, user_text: str, max_retries: int = 1) -> str:
    # Deterministic user onboarding (greet already done via /chat/start)
    onboarded = handle_user_onboarding_turn(user_id, user_text)
    if onboarded is not None:
        return onboarded

    user = load_user_brain(user_id)
    admin = is_admin(user_id)
    text_in = (user_text or "").strip()

    # Instant local care for common short moods (no Gemini wait).
    if not admin and text_in and re.search(
        r"疲れ|つらい|しんど|眠い|疲れた|mệt|tired|exhausted|おはよう|こんにちは|こんばんは",
        text_in,
        re.I,
    ):
        _update_relationship(user, text_in)
        return _persist_local_turn(user_id, user, text_in, _local_companion_reply(user, text_in))

    # Quota cooldown: answer locally instead of waiting ~30s on Gemini.
    if not admin and _quota_blocked():
        if text_in:
            _update_relationship(user, text_in)
        return _persist_local_turn(user_id, user, text_in, _local_companion_reply(user, text_in))

    blueprint = load_blueprint()
    policy = load_product_policy()
    core = load_core_brain()

    if not admin and text_in:
        _update_relationship(user, text_in)
        if user.get("profile_complete"):
            note = _activity_notification(text_in)
            if note:
                user["pending_notification"] = note

    if admin:
        system_prompt = _build_admin_system_prompt(blueprint, policy, core)
        history = core.get("chat_history", [])
    else:
        system_prompt = _build_user_system_prompt(blueprint, policy, core, user)
        history = user.get("chat_history", [])

    chat_session = None  # legacy var unused; routed via llm_client
    last_error: Optional[Exception] = None
    for i in range(max_retries):
        try:
            ai_reply = complete_chat(
                system_prompt,
                history_dicts=history,
                history_contents=_history_to_contents(history, limit=6),
                user_text=user_text,
                temperature=0.6,
                max_tokens=180,
            )

            # If provider returned plain Japanese without XML tags, wrap it.
            if ai_reply and "<dialogue>" not in ai_reply:
                ai_reply = _pack_reply(ai_reply, {})

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

            return ai_reply
        except Exception as e:
            last_error = e
            # Never sleep on quota — fail over to local companion immediately.
            if _is_quota_error(e):
                _mark_quota_block(_retry_after_from_error(e, 90))
                if not admin:
                    return _persist_local_turn(
                        user_id, user, text_in, _local_companion_reply(user, text_in)
                    )
                break
            if _is_transient_error(e) and i < max_retries - 1:
                time.sleep(0.8 + random.uniform(0, 0.4))
                continue
            break

    assert last_error is not None
    if not admin:
        return _persist_local_turn(user_id, user, text_in, _local_companion_reply(user, text_in))
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


def generate_json_task(system_instruction: str, user_prompt: str) -> Optional[Any]:
    """One-shot JSON completion (no chat history). Returns None on failure."""
    try:
        if provider_name() == "openai_compatible":
            raw = complete_chat(
                system_instruction + "\nRespond with JSON only.",
                history_dicts=[],
                user_text=user_prompt,
                temperature=0.35,
                max_tokens=400,
            )
            text = (raw or "").strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
            return json.loads(text) if text else None

        from google.genai import types

        gclient = client
        if gclient is None:
            from llm_client import _get_gemini

            gclient = _get_gemini()
        response = gclient.models.generate_content(
            model=MODEL_NAME,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.35,
                response_mime_type="application/json",
            ),
        )
        text = (response.text or "").strip()
        if not text:
            return None
        return json.loads(text)
    except Exception:
        return None
