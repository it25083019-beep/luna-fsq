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

# A packed reply carries the dialogue plus a game_state JSON block, so the
# budget has to cover both or the tail gets cut off mid-sentence.
CHAT_REPLY_TOKENS = int(os.getenv("CHAT_REPLY_TOKENS") or 700)
CHAT_CONTEXT_TURNS = int(os.getenv("CHAT_CONTEXT_TURNS") or 20)

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
    # Legacy ephemeral name; the repeat guard now persists last_companion_line.
    brain_data.pop("_last_companion_line", None)
    # consult_mode is persisted so multi-turn companion care continues; it
    # expires via _consult_session_active so chat returns to the model.
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


EMOTION_TAGS = "neutral|joy|happy|sadness|sad|surprise|surprised|think|cheer|wave"


def _today_iso() -> str:
    from datetime import date

    return date.today().isoformat()


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def append_turns(store: Dict[str, Any], user_text: str, ai_reply: str) -> None:
    """Record one exchange. Timestamps let the history screen group by day."""
    history = store.setdefault("chat_history", [])
    stamp = _now_iso()
    if (user_text or "").strip():
        history.append({"role": "user", "content": user_text, "at": stamp})
    history.append({"role": "model", "content": ai_reply, "at": stamp})


def get_chat_history(
    user_id: str, *, limit: int = 60, before: Optional[int] = None
) -> Dict[str, Any]:
    """Newest-last page of readable turns, walking backwards from `before`.

    Stored assistant turns hold the packed protocol payload, so each one is run
    through the parser to recover plain text. Turns saved before timestamps
    existed simply have no `at`.
    """
    user = load_user_brain(user_id)
    history = user.get("chat_history")
    if not isinstance(history, list):
        history = []
    total = len(history)

    end = total if before is None else max(0, min(int(before), total))
    start = max(0, end - max(1, int(limit)))

    rows = []
    for idx in range(start, end):
        turn = history[idx]
        if not isinstance(turn, dict):
            continue
        role = "user" if turn.get("role") == "user" else "luna"
        content = turn.get("content") or ""
        if role == "luna":
            text, _ = parse_ai_reply(content)
        else:
            text = str(content).strip()
        if not text:
            continue
        rows.append({"index": idx, "role": role, "text": text, "at": turn.get("at")})

    return {
        "total": total,
        "turns": rows,
        "next_before": start if start > 0 else None,
        "has_more": start > 0,
    }


def _extract_game_state(ai_reply: str) -> Dict[str, Any]:
    """Read the state JSON, tolerating a missing closing tag."""
    for pattern in (
        r"<game_state_json>\s*(.*?)\s*</game_state_json>",
        r"<game_state_json>\s*(\{.*)",
    ):
        match = re.search(pattern, ai_reply, re.DOTALL | re.IGNORECASE)
        if not match:
            continue
        raw = match.group(1).strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            # A truncated reply leaves unbalanced braces; recover the longest
            # prefix that still parses so captured life data is not lost.
            for end in range(len(raw), 1, -1):
                if raw[end - 1] != "}":
                    continue
                try:
                    parsed = json.loads(raw[:end])
                    break
                except json.JSONDecodeError:
                    continue
            else:
                continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _clean_dialogue(text: str) -> str:
    """Strip any stray protocol markup so it can never reach the chat bubble."""
    out = re.sub(
        r"<game_state_json>.*?(</game_state_json>|$)",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    out = re.sub(r"</?dialogue>", "\n", out, flags=re.IGNORECASE)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def parse_ai_reply(ai_reply: str) -> Tuple[str, Dict[str, Any]]:
    raw = (ai_reply or "").strip()
    game_state: Dict[str, Any] = {}

    # Prefer a well-formed block, then an unclosed one (truncated reply), then
    # treat the whole payload as dialogue.
    closed = re.search(r"<dialogue>\s*(.*?)\s*</dialogue>", raw, re.DOTALL | re.IGNORECASE)
    if closed:
        dialogue = closed.group(1)
    else:
        open_only = re.search(r"<dialogue>\s*(.*)", raw, re.DOTALL | re.IGNORECASE)
        dialogue = open_only.group(1) if open_only else raw

    dialogue = _clean_dialogue(dialogue)

    # The emotion tag can land before or after the wrapper, so sweep the head
    # of the text rather than anchoring strictly at position 0.
    emo = re.match(rf"\s*\[({EMOTION_TAGS})\]\s*", dialogue, re.IGNORECASE)
    if emo:
        game_state["emotion"] = emo.group(1).lower()
        dialogue = dialogue[emo.end() :].strip()
    dialogue = re.sub(rf"\[({EMOTION_TAGS})\]", "", dialogue, flags=re.IGNORECASE).strip()

    parsed = _extract_game_state(raw)
    if parsed:
        if "emotion" in game_state and "emotion" not in parsed:
            parsed["emotion"] = game_state["emotion"]
        game_state = parsed

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
- Usually 2–3 short sentences in <dialogue> (warm companion, not a form bot).

COMPANION REPLY SHAPE (important):
1) If you saved any life fact, first say you noted it (例:「今日の気分、メモしたよ」「800円の支出、記録したよ」).
2) Then react to what they said like a close companion — comfort, celebrate, or plan with them.
3) End with ONE concrete next step / suggestion tied to their words (rest, budget tip, schedule prep, etc.).
Never sound like a dry system log. Speak as {companion} beside {who}.

ROLE SWITCH:
- Health topics: careful like a professional clinician intake (no diagnosis/prescription).
- Mental topics after profile known: warm friend beside them (安慰・同席), still polite.
- Money topics: like a personal finance advisor (具体・実行可能な次の一歩).
- Time/goals: planner; propose one clear next action.

THREE LIFE MODULES (first-meeting questions are only a baseline; user can add more later):
1) 健康 health  2) お金 money  3) スケジュール schedule

{modules_block}

FIVE PILLARS always: 1 health 2 study/future 3 money 4 time 5 goal direction.

EMOTION TAGS (like VTuber emotionMap — put ONE tag right after <dialogue> when fitting):
[neutral] [joy] [sadness] [surprise] [think] [cheer] [wave] [happy]

USER PROFILE:
{profile}

SCHEDULE REMINDERS (from user timetable):
{reminders}

NOTIFICATION RULES (do NOT ask interval preference):
- If user is about to study/work/go somewhere: remind preparation now.
- During study/work: set pending_notification for mid-task break/progress.
- Before scheduled events in timetable: use schedule_reminders / pending_notification.

LIFE DATA CAPTURE (additive — never delete existing user data):
TODAY IS {_today_iso()}. Never guess a date — derive every date from TODAY.
When the user mentions facts about mood, spending, schedule, or goals, put them in game_state_json under life_updates.
Use ONLY these keys when confident:
- mental_status: one of 元気/普通/疲れ/落ち込み/不安
- spend: {{"amount": number, "note": "short", "date": "YYYY-MM-DD"}}  (today's spending)
- schedule_add: {{"title": "...", "date": "YYYY-MM-DD", "time": "HH:MM" or null}}
- goal_add: {{"title": "...", "target": number, "current": 0, "unit": "円"}}
- goal_progress: {{"title": "...", "current": number}}
- notes: {{"health"|"money"|"schedule"|"goals": "free text memo"}}
If unsure, omit life_updates. Never wipe calendars, funds, or goals.


# PRIVACY
- You only know THIS user. Never invent or reference other users' private data.
- Do not ask for email/password. Auth is outside chat.

# SAFETY
{chr(10).join("- " + r for r in (policy.get("safety_rules") or [])) or "- No medical/mental diagnosis. If crisis signals appear: empathize and suggest contacting a trusted person or professional support immediately."}
- If the user wants to die or harm themselves: do not diagnose. Stay with them, urge them to contact a trusted person or いのちの電話 0570-783-556 now.

# OUTPUT FORMAT (follow exactly — no text outside these two blocks)
<dialogue>
[cheer]よくできました。次は短い休憩を取りましょう。
</dialogue>
<game_state_json>
{{"emotion": "cheer", "current_do_now": "5分休憩"}}
</game_state_json>

Hard rules:
- ALWAYS close both tags. Never emit a second <dialogue> block.
- Keep the dialogue to 2-3 short sentences so both blocks fit in the reply.
- game_state_json must be one valid JSON object, even if empty: {{}}
- Include current_focus, current_do_now, pending_notification when useful.
"""


def _apply_memory_note_admin(core: Dict[str, Any], game_state: Dict[str, Any]) -> None:
    note = game_state.get("memory_note")
    if note and note not in core["trained_knowledge"]:
        core["trained_knowledge"].append(note)


def _apply_user_fields_from_game_state(user: Dict[str, Any], game_state: Dict[str, Any]) -> None:
    from name_utils import sanitize_display_name

    for key in ("companion_name", "user_display_name", "current_focus", "current_plan", "current_do_now", "memory_note", "pending_notification"):
        val = game_state.get(key)
        if val is None or val == "":
            continue
        if key in ("user_display_name", "companion_name"):
            cleaned = sanitize_display_name(str(val))
            if cleaned:
                user[key] = cleaned
            continue
        user[key] = val



def _clean_name(raw: str) -> str:
    from name_utils import sanitize_display_name

    return sanitize_display_name(raw) or ""


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


def _activity_notification(user_text: str) -> Optional[str]:
    t = user_text or ""
    if re.search(r"(勉強|学習|課題|レポート|コーディング|開発|作業|バイト|面接|出勤)", t):
        return "始める前に持ち物・水分・目標を1つ確認。開始後は25分後に短い休憩を。"
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
        from care_memory import greeting_care_line

        lv = _relationship_level(user)
        cname = user['companion_name']
        who = _honorific(user)
        care_line = greeting_care_line(user)
        if care_line:
            dialogue = f"{who}、おかえり。{care_line}"
        elif lv >= 3:
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
        append_turns(user, "", ai_reply)
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
        msg = "ごめんね、いまちょっと返事が遅れてる。でも聞いてるから、もう一度ゆっくり話してくれる？"
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


def _consult_topic_from_chip(text: str) -> Optional[str]:
    """Detect health/money consult chip taps (start of care companion session)."""
    t = (text or "").strip()
    if not t:
        return None
    if re.search(r"体調|健康", t, re.I) and re.search(r"相談", t):
        return "health"
    if re.search(r"お金|家計|支出|貯金", t, re.I) and re.search(r"相談|整理", t):
        return "money"
    return None


# Longest first so that stripping 疲れた does not leave a stray た behind.
MOOD_PING_WORDS = [
    "exhausted",
    "こんばんは",
    "こんにちは",
    "おはよう",
    "しんど",
    "つらい",
    "疲れた",
    "tired",
    "眠い",
    "疲れ",
    "mệt",
]
MOOD_PING_RE = re.compile("|".join(MOOD_PING_WORDS), re.I)
# Anything longer than this left over is real content the model should answer.
MOOD_PING_SLACK = 6


def _is_bare_mood_ping(text: str) -> bool:
    """True when the message is only a greeting or mood note.

    The check used to be a bare `re.search`, so 「おはよう、今日テストがある」
    matched on the greeting and got a canned hello while the actual news about
    the test went unanswered. Only messages that carry nothing beyond the
    greeting take the instant local path now.
    """
    stripped = MOOD_PING_RE.sub("", text or "")
    # Drop punctuation, spaces and ASCII so only substantive characters remain.
    remainder = re.sub(r"[\s\W_]|[a-zA-Z0-9]", "", stripped, flags=re.UNICODE)
    return bool(MOOD_PING_RE.search(text or "")) and len(remainder) < MOOD_PING_SLACK


CRISIS_RE = re.compile(
    r"死にたい|消えたい|自殺|死んでしま|自傷|生きていたくない|もういない方が|"
    r"kill myself|want to die|suicide|"
    r"muốn chết|tự tử",
    re.I,
)


def _is_crisis_message(text: str) -> bool:
    return bool(CRISIS_RE.search(text or ""))


def _crisis_reply(user: Dict[str, Any]) -> str:
    """Local safety path — never wait on the model for a crisis line."""
    who = _honorific(user)
    cname = user.get("companion_name") or "LUNA"
    dialogue = (
        f"{who}、いまの気持ち、ちゃんと受け取ったよ。{cname}はそばにいる。"
        f"ひとりで抱えなくていい。信頼できる人か、いのちの電話（0570-783-556）に今すぐつながってほしい。"
        f"診断はできないけど、あなたが大切だよ。"
    )
    return _pack_reply(dialogue, {"emotion": "sad", "crisis": True})


CONSULT_MAX_TURNS = 4
CONSULT_TTL_MINUTES = 20


def _end_consult_session(user: Dict[str, Any]) -> None:
    for key in ("consult_mode", "consult_started_at", "consult_turns"):
        user.pop(key, None)


def _consult_session_active(user: Dict[str, Any]) -> bool:
    """True while a care session should keep answering locally.

    Without an expiry the flag stayed set forever, so every later message was
    answered by templates and never reached the model again.
    """
    if not user.get("consult_mode"):
        return False

    try:
        turns = int(user.get("consult_turns") or 0)
    except (TypeError, ValueError):
        turns = 0
    if turns >= CONSULT_MAX_TURNS:
        _end_consult_session(user)
        return False

    started = user.get("consult_started_at")
    if started:
        from datetime import datetime, timedelta, timezone

        try:
            begun = datetime.fromisoformat(str(started))
        except ValueError:
            begun = None
        if begun is not None:
            if begun.tzinfo is None:
                begun = begun.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - begun > timedelta(minutes=CONSULT_TTL_MINUTES):
                _end_consult_session(user)
                return False
    return True


def _begin_consult_session(user: Dict[str, Any], topic: str) -> str:
    """Open companion care on home chat: listen first, capture, advise — stay on chat."""
    from care_memory import care_recall_prefix

    user["consult_mode"] = topic
    user["consult_started_at"] = _now_iso()
    user["consult_turns"] = 0
    who = _honorific(user)
    cname = user.get("companion_name") or "LUNA"
    recall = care_recall_prefix(user, topic)
    if topic == "health":
        dialogue = (
            f"{recall}{who}、体調のこと？ {cname}が聞くね。"
            f"いまどんな感じ？眠れてる・食べられてる・気分…なんでもいいから、"
            f"思ったことをそのまま教えて。一緒に整理するし、メモも残しておくよ。"
        )
    else:
        dialogue = (
            f"{recall}{who}、お金のこと、気になってるんだね。"
            f"支出でも貯金でも欲しいものでも、いまいちばん心に引っかかってることを教えて。"
            f"話しながら一緒に整理していこう。"
        )
    return _pack_reply(dialogue, {"emotion": "think", "consult_mode": topic})


def _consult_next_step(topic: str, applied: List[str], msg: str) -> str:
    """One gentle next step — walk alongside, not lecture."""
    if topic == "health":
        if any(a.startswith("睡眠") for a in applied):
            return "今夜は就寝を15分早めるだけでも楽になるかも。明日また教えてね。"
        if any(a.startswith("気分") for a in applied):
            return "今夜はゆっくり休もう。明日の朝、またちょっとだけ教えてくれる？"
        if re.search(r"眠|睡眠|寝", msg):
            return "睡眠の時間も教えてもらえると記録できるよ。明日は起床を15分遅らせてみて。"
        if re.search(r"痛|熱|咳|吐|めまい", msg):
            return "無理しないで。水分とって、悪化したら病院や相談窓口へ。また教えてね。"
        if applied:
            return "今夜は休息優先で。明日また様子聞かせて。"
        return "睡眠・気分・食欲、どれか一つだけでも大丈夫。ゆっくりでいいよ。"
    if any(a.startswith("支出") for a in applied):
        return "今週は外食をあと1回に抑える、みたいな小さなルールから始めよう。"
    if re.search(r"貯金|欲しい", msg):
        return "週に一度、一緒に進捗見直そう。"
    if applied:
        return "週末に残り予算、一緒に確認しよう。"
    return "金額が分かれば記録できるよ。『今日ランチ800円』みたいに送っても大丈夫。"


def _companion_consult_followup(user: Dict[str, Any], user_text: str) -> str:
    """Continue care companion: capture facts, empathize, suggest one next step."""
    from care_memory import format_recorded, touch_care_memory
    from chat_life_capture import capture_life_from_chat, compose_companion_dialogue

    topic = str(user.get("consult_mode") or "health")
    try:
        user["consult_turns"] = int(user.get("consult_turns") or 0) + 1
    except (TypeError, ValueError):
        user["consult_turns"] = 1
    applied = capture_life_from_chat(user, user_text, None)
    touch_care_memory(user, topic, user_text, applied)
    composed = compose_companion_dialogue(user, user_text, applied, include_ack=False)
    recorded = format_recorded(applied)
    next_step = _consult_next_step(topic, applied, user_text)
    parts: List[str] = []
    if recorded:
        parts.append(f"【記録】{recorded}。")
    else:
        parts.append("【記録】いまは数値の記録はなし。話は残したよ。")
    body = (composed.get("dialogue") or "").strip()
    if body and body not in " ".join(parts):
        parts.append(body if body.endswith(("。", "？", "！", "よ")) else body + "。")
    if next_step and next_step not in " ".join(parts):
        parts.append(next_step)
    dialogue = "".join(parts)
    dialogue = _avoid_repeat_dialogue(user, dialogue)
    return _pack_reply(
        dialogue,
        {
            "emotion": composed.get("emotion") or "think",
            "consult_mode": topic,
            "life_saved": applied,
        },
    )


def _local_consult_reply(user: Dict[str, Any], user_text: str) -> Optional[str]:
    """Start care companion on chip tap — chat only, no module redirect."""
    topic = _consult_topic_from_chip(user_text)
    if topic:
        return _begin_consult_session(user, topic)
    return None


def _dialogue_similar(a: str, b: str) -> bool:
    a = re.sub(r"\s+", "", (a or "").strip())
    b = re.sub(r"\s+", "", (b or "").strip())
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return shorter in longer and len(shorter) >= max(12, int(len(longer) * 0.55))


_REPEAT_NUDGES = (
    "{who}、うん、聞いてるよ。もう少しだけ詳しく教えてくれる？",
    "{who}、それってどんな感じだった？よかったら続きを聞かせて。",
    "{who}、なるほどね。今いちばん気になってるのはどのあたり？",
)


RECENT_LINE_MEMORY = 4


def _avoid_repeat_dialogue(user: Dict[str, Any], dialogue: str) -> str:
    """Stop the companion repeating lines it has just said.

    Two things kept this from working. The previous line was held in
    `_last_companion_line`, which save_user_brain strips as an ephemeral flag,
    so every turn compared against an empty string. And comparing against only
    the single last line let a repeated sentence alternate straight back in
    once a nudge had displaced it, so the user still saw A, nudge, A, nudge.
    """
    recent = [str(x) for x in (user.get("recent_companion_lines") or []) if x]
    text = (dialogue or "").strip()
    if text and any(_dialogue_similar(prev, text) for prev in recent):
        try:
            n = int(user.get("repeat_nudge_i") or 0)
        except (TypeError, ValueError):
            n = 0
        # Rotate, so someone who repeats themselves is not deflected with the
        # very same sentence each time.
        user["repeat_nudge_i"] = (n + 1) % len(_REPEAT_NUDGES)
        text = _REPEAT_NUDGES[n % len(_REPEAT_NUDGES)].format(who=_honorific(user))
    if text:
        user["recent_companion_lines"] = (recent + [text[:200]])[-RECENT_LINE_MEMORY:]
    return text


def _local_companion_reply(user: Dict[str, Any], user_text: str) -> str:
    """Instant Japanese companion lines without Gemini (mood / daily care)."""
    from chat_life_capture import capture_life_from_chat, compose_companion_dialogue

    # Capture first so the spoken line can confirm what we saved.
    try:
        applied = capture_life_from_chat(user, user_text or "", None)
    except Exception:
        applied = []
    composed = compose_companion_dialogue(user, user_text or "", applied)
    dialogue = _avoid_repeat_dialogue(user, composed["dialogue"])
    return _pack_reply(
        dialogue,
        {
            "emotion": composed.get("emotion") or "happy",
            "user_display_name": user.get("user_display_name"),
            "companion_name": user.get("companion_name"),
            "life_saved": applied,
        },
    )


def _persist_local_turn(user_id: str, user: Dict[str, Any], user_text: str, ai_reply: str) -> str:
    """Persist a local companion turn. Capture is done inside _local_companion_reply."""
    user.setdefault("chat_history", [])
    append_turns(user, user_text, ai_reply)
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

    if _consult_topic_from_chip(msg):
        return None

    if not display:
        from name_utils import is_valid_display_name

        if re.search(r"相談|consult|体調|お金|予定|健康に|支出", msg, re.I):
            ai_reply = _pack_reply(
                "お名前の登録の前に、まず短いお名前だけ教えてください。（例：太郎）",
                {},
            )
        else:
            name = _clean_name(msg)
            if not is_valid_display_name(name):
                ai_reply = _pack_reply("恐れ入ります。お名前のみ、短く教えていただけますか。（例：太郎 / Paula）", {})
            else:
                user["user_display_name"] = name
                ai_reply = _pack_reply(
                    f"{name}様、承知いたしました。次に、私の呼び名を一つお決めください。",
                    {"user_display_name": name},
                )
        append_turns(user, user_text, ai_reply)
        save_user_brain(user_id, user)
        return ai_reply

    if not companion:
        cname = _clean_name(msg)
        from name_utils import is_valid_display_name

        if not is_valid_display_name(cname):
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
        append_turns(user, user_text, ai_reply)
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
            append_turns(user, user_text, ai_reply)
            save_user_brain(user_id, user)
            return ai_reply

    return None


def handle_chat_message(user_id: str, user_text: str) -> str:
    """Main /chat handler — consult & care always work without LLM."""
    text_in = (user_text or "").strip()
    if text_in and _is_crisis_message(text_in):
        user = load_user_brain(user_id)
        return _persist_local_turn(user_id, user, text_in, _crisis_reply(user))

    onboarded = handle_user_onboarding_turn(user_id, user_text)
    if onboarded is not None:
        return onboarded

    user = load_user_brain(user_id)
    admin = is_admin(user_id)

    # Consult chips + follow-up: all users (including admin) — never depend on Gemini.
    if text_in:
        topic = _consult_topic_from_chip(text_in)
        if topic:
            reply = _begin_consult_session(user, topic)
            _update_relationship(user, text_in)
            return _persist_local_turn(user_id, user, text_in, reply)
        if _consult_session_active(user):
            _update_relationship(user, text_in)
            return _persist_local_turn(user_id, user, text_in, _companion_consult_followup(user, text_in))

    try:
        return generate_with_retry(user_id, user_text, skip_onboarding=True)
    except Exception:
        user = load_user_brain(user_id)
        if admin:
            who = _honorific(user)
            return _pack_reply(
                f"{who}、聞いてるよ。いまの状況をもう少し教えてくれる？",
                {"emotion": "think"},
            )
        return _persist_local_turn(user_id, user, text_in, _local_companion_reply(user, text_in))


def generate_with_retry(user_id: str, user_text: str, max_retries: int = 1, *, skip_onboarding: bool = False) -> str:
    text_in = (user_text or "").strip()
    if text_in and _is_crisis_message(text_in):
        user = load_user_brain(user_id)
        return _persist_local_turn(user_id, user, text_in, _crisis_reply(user))

    if not skip_onboarding:
        onboarded = handle_user_onboarding_turn(user_id, user_text)
        if onboarded is not None:
            return onboarded

    user = load_user_brain(user_id)
    admin = is_admin(user_id)

    if text_in:
        topic = _consult_topic_from_chip(text_in)
        if topic:
            reply = _begin_consult_session(user, topic)
            _update_relationship(user, text_in)
            return _persist_local_turn(user_id, user, text_in, reply)

    if text_in and _consult_session_active(user) and not _consult_topic_from_chip(text_in):
        _update_relationship(user, text_in)
        return _persist_local_turn(user_id, user, text_in, _companion_consult_followup(user, text_in))

    from llm_client import llm_configured

    if not admin and text_in and not llm_configured():
        _update_relationship(user, text_in)
        return _persist_local_turn(user_id, user, text_in, _local_companion_reply(user, text_in))

    # Instant local care for a bare greeting or mood ping (no Gemini wait).
    if not admin and text_in and _is_bare_mood_ping(text_in):
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
            from care_memory import maybe_daily_care_notification

            note = _activity_notification(text_in)
            if note and str(user.get("care_notified_on") or "")[:10] != _today_iso():
                user["pending_notification"] = note
                user["care_notified_on"] = _today_iso()
            else:
                maybe_daily_care_notification(user)

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
                history_contents=_history_to_contents(history, limit=CHAT_CONTEXT_TURNS),
                user_text=user_text,
                temperature=0.6,
                max_tokens=CHAT_REPLY_TOKENS,
                history_limit=CHAT_CONTEXT_TURNS,
            )

            # Normalise whatever shape the model used into our packed format so
            # a missing or unclosed tag can never leak into the chat bubble.
            dialogue, game_state = parse_ai_reply(ai_reply)
            ai_reply = _pack_reply(dialogue, game_state)

            if admin:
                _apply_memory_note_admin(core, game_state)
                append_turns(core, user_text, ai_reply)
                save_core_brain(core)
            else:
                _apply_user_fields_from_game_state(user, game_state)
                applied: list = []
                try:
                    from chat_life_capture import capture_life_from_chat, enrich_dialogue_with_capture

                    applied = capture_life_from_chat(user, user_text or "", game_state)
                    if applied:
                        dialogue, gs = parse_ai_reply(ai_reply)
                        dialogue = enrich_dialogue_with_capture(
                            dialogue, user, user_text or "", applied
                        )
                        dialogue = _avoid_repeat_dialogue(user, dialogue)
                        gs = dict(gs or {})
                        gs["life_saved"] = applied
                        if "emotion" not in gs:
                            gs["emotion"] = "happy"
                        ai_reply = _pack_reply(dialogue, gs)
                except Exception:
                    pass
                try:
                    dialogue, gs = parse_ai_reply(ai_reply)
                    dialogue = _avoid_repeat_dialogue(user, dialogue)
                    gs = dict(gs or {})
                    ai_reply = _pack_reply(dialogue, gs)
                except Exception:
                    pass
                append_turns(user, user_text, ai_reply)
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
            if not admin and text_in:
                return _persist_local_turn(
                    user_id, user, text_in, _local_companion_reply(user, text_in)
                )
            break

    assert last_error is not None
    if not admin:
        return _persist_local_turn(user_id, user, text_in, _local_companion_reply(user, text_in))
    retry_after = _retry_after_from_error(last_error)
    if _is_quota_error(last_error):
        return _pack_reply(
            "少し混み合っているみたいだけど、ちゃんと話は聞いているよ。もう一度短く話しかけてね。",
            {"emotion": "think"},
        )
    return _pack_reply(
        "ごめんね、いまちょっと返事が遅れてる。でも聞いてるから、もう一度ゆっくり話してくれる？",
        {"emotion": "think"},
    )


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
