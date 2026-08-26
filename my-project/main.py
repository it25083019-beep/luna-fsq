from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from auth_security import (
    create_access_token,
    generate_password_reset_token,
    get_current_user,
    hash_password,
    hash_reset_token,
    password_reset_expiry,
    require_admin,
    verify_password,
)
from brain_repo import migrate_json_brains_to_db, seed_admin_user, sync_privacy_rules_into_core
from database import get_db, init_db
from models import CoreBrain, PasswordResetToken, User
from password_reset_email import send_password_reset_email
from life_modules import MODULE_KEYS, append_module_note, list_modules, summarize_module, update_module_structured
from life_dashboard import (
    health_dashboard,
    mental_status_payload,
    money_dashboard,
    save_health_profile,
    save_mental_checkin,
    save_money_profile,
)
from schedule_service import (
    add_event,
    apply_suggestions,
    complete_event,
    delete_event,
    extend_recurring_horizons,
    home_summary,
    list_events,
    suggest_combined,
    update_event,
)
from schemas import (
    AdminLockRequest,
    AdminResetPasswordRequest,
    AdminUserOut,
    ChatRequest,
    ChatResponse,
    CheckinRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LifeModuleAppendRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SetCompanionNameRequest,
    TokenResponse,
    CareerSuggestRequest,
    CareerSelectRequest,
    RpgQuestStartRequest,
    RpgActivityRequest,
    ScheduleEventCreate,
    ScheduleEventUpdate,
    ScheduleEventComplete,
    ScheduleApplySuggestions,
    ScheduleExtendHorizons,
    LifeDashboardUpdate,
    HealthProfileUpdate,
    HealthMentalCheckin,
    MoneyProfileUpdate,
    JourneySelectRequest,
    JourneyBossChallenge,
    JourneyLessonEnrich,
    TtsSpeakRequest,
)
from suggestions import get_suggested_replies
from career_engine import load_taxonomy, suggest_careers, rpg_class_label
from journey_engine import (
    challenge_boss,
    complete_lesson,
    enrich_lesson_detail,
    get_curriculum,
    get_lesson,
    journey_status,
    list_bosses,
    list_careers,
    list_classes,
    list_journey_map,
    select_journey,
)
from rpg_engine import (
    build_portfolio,
    complete_activity,
    ensure_rpg,
    list_regions,
    load_world,
    start_quest,
)
from store import get_user_state, save_user_state
from exp_engine import add_exp
from tts_service import synthesize_speech
from luna_service import (
    LunaAiError,
    generate_with_retry,
    parse_ai_reply,
    get_brain_status,
    load_user_brain,
    save_user_brain,
    safe_chat_start_reply,
    soft_chat_failure_reply,
    is_admin,
)

app = FastAPI(title="FSQ Luna Backend")

_ALLOWED = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_STATIC_DIR = Path(__file__).resolve().parent / "static"
_STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")



def _warn_insecure_defaults() -> None:
    insecure = []
    jwt = os.getenv("JWT_SECRET", "dev-luna-jwt-secret-change-me")
    if jwt in {"change-me-in-production", "dev-luna-jwt-secret-change-me"} or len(jwt) < 16:
        insecure.append("JWT_SECRET is weak/default")
    admin_pw = os.getenv("ADMIN_PASSWORD", "admin123456")
    if admin_pw in {"admin123456", "password", "admin"}:
        insecure.append("ADMIN_PASSWORD is default")
    if os.getenv("ENV", "dev").lower() in {"prod", "production"} and insecure:
        raise RuntimeError("Refusing to start in production: " + "; ".join(insecure))
    for item in insecure:
        print(f"[WARN] {item} - change before sharing with others")


def _chat_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LunaAiError):
        return HTTPException(
            status_code=exc.status_code,
            detail={
                "message": str(exc),
                "code": exc.code,
                "retry_after_seconds": exc.retry_after_seconds,
            },
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )
    return HTTPException(status_code=500, detail=str(exc))


@app.on_event("startup")
def on_startup() -> None:
    _warn_insecure_defaults()
    init_db()
    migrate_json_brains_to_db()
    sync_privacy_rules_into_core()
    seed_admin_user()
    admin_email = os.getenv("ADMIN_EMAIL", "admin@luna.local").strip().lower()
    print(f"[AUTH] Admin login email: {admin_email} (password from ADMIN_PASSWORD env)")


def _resolve_user_id(requested: Optional[str], current: User) -> str:
    """Use token public_id; body/path user_id only if self or admin."""
    if not requested or requested == current.public_id:
        return current.public_id
    if current.is_admin or is_admin(current.public_id):
        return requested
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Cannot act as another user",
    )


@app.get("/")
def root():
    return RedirectResponse(url="/login")


@app.get("/login")
def login_page():
    return FileResponse(_STATIC_DIR / "login.html")


@app.get("/health")
def health():
    try:
        from llm_client import active_backend_label

        backend = active_backend_label()
    except Exception:
        backend = {"provider": os.getenv("LLM_PROVIDER", "gemini")}
    return {
        "ok": True,
        "env": os.getenv("ENV", "dev"),
        "llm": backend,
        "model": backend.get("model") or os.getenv("MODEL_NAME", "gemini-2.5-flash"),
        "db": (
            "postgres"
            if "postgres" in os.getenv("DATABASE_URL", "").lower()
            else "mysql"
            if "mysql" in os.getenv("DATABASE_URL", "").lower()
            else "sqlite"
        ),
    }


@app.get("/app")
def companion_app_page():
    return FileResponse(_STATIC_DIR / "app.html")


@app.get("/demo")
def demo_page():
    return FileResponse(_STATIC_DIR / "demo.html")


@app.get("/admin")
def admin_page():
    return FileResponse(_STATIC_DIR / "admin.html")


@app.get("/live2d")
def live2d_demo_page():
    return FileResponse(_STATIC_DIR / "live2d-demo.html")


@app.get("/luna-3d")
def luna_3d_page():
    return FileResponse(_STATIC_DIR / "luna-3d-demo.html")


# ----- Auth -----


@app.post("/auth/register", response_model=TokenResponse)
def auth_register(req: RegisterRequest, db: Session = Depends(get_db)):
    email = req.email.strip().lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    public_id = uuid.uuid4().hex
    user = User(
        public_id=public_id,
        email=email,
        password_hash=hash_password(req.password),
        display_name=req.display_name,
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    # Ensure default brain row via save
    brain = load_user_brain(public_id)
    if req.display_name:
        brain["user_display_name"] = req.display_name
    save_user_brain(public_id, brain)
    token = create_access_token(user.public_id, extra={"email": user.email, "is_admin": user.is_admin})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.public_id,
        email=user.email,
        is_admin=user.is_admin,
    )


@app.post("/auth/login", response_model=TokenResponse)
def auth_login(req: LoginRequest, db: Session = Depends(get_db)):
    email = req.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if getattr(user, "is_locked", False):
        raise HTTPException(status_code=403, detail="Account is locked")
    admin_flag = bool(user.is_admin or is_admin(user.public_id))
    token = create_access_token(user.public_id, extra={"email": user.email, "is_admin": admin_flag})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.public_id,
        email=user.email,
        is_admin=admin_flag,
    )


@app.get("/auth/me")
def auth_me(current: User = Depends(get_current_user)):
    return {
        "user_id": current.public_id,
        "email": current.email,
        "display_name": current.display_name,
        "is_admin": current.is_admin or is_admin(current.public_id),
    }


@app.post("/auth/forgot-password", response_model=ForgotPasswordResponse)
def auth_forgot_password(
    req: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Request a password reset link (email if SMTP configured; dev may return link)."""
    generic = "登録済みの場合、パスワード再設定用の案内を送信しました。メールをご確認ください。"
    email = req.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or user.is_admin or getattr(user, "is_locked", False):
        return ForgotPasswordResponse(message=generic)

    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({PasswordResetToken.used_at: datetime.now(timezone.utc)})
    db.commit()

    raw_token = generate_password_reset_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_reset_token(raw_token),
            expires_at=password_reset_expiry(),
        )
    )
    db.commit()

    base = (os.getenv("APP_BASE_URL") or str(request.base_url)).rstrip("/")
    reset_url = f"{base}/login?reset={raw_token}"
    sent = send_password_reset_email(user.email, reset_url)
    dev_mode = os.getenv("ENV", "dev").lower() not in {"prod", "production"}
    return ForgotPasswordResponse(
        message=generic,
        reset_url=reset_url if dev_mode and not sent else None,
    )


@app.post("/auth/reset-password")
def auth_reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = hash_reset_token(req.token.strip())
    now = datetime.now(timezone.utc)
    row = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")
    user = db.query(User).filter(User.id == row.user_id).first()
    if not user or user.is_admin:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")
    if getattr(user, "is_locked", False):
        raise HTTPException(status_code=403, detail="Account is locked")

    user.password_hash = hash_password(req.new_password)
    row.used_at = now
    db.commit()
    return {"message": "Password updated. You can log in now."}


# ----- Me routes (token) -----


@app.get("/state/me")
def get_state_me(current: User = Depends(get_current_user)):
    return get_user_state(current.public_id)


@app.get("/brain/me")
def brain_status_me(current: User = Depends(get_current_user)):
    return get_brain_status(current.public_id)


@app.get("/state/{user_id}")
def get_state(user_id: str, current: User = Depends(get_current_user)):
    uid = _resolve_user_id(user_id, current)
    return get_user_state(uid)


@app.get("/brain/{user_id}")
def brain_status(user_id: str, current: User = Depends(get_current_user)):
    uid = _resolve_user_id(user_id, current)
    return get_brain_status(uid)


@app.post("/user/set-name")
def set_companion_name(
    req: SetCompanionNameRequest,
    current: User = Depends(get_current_user),
):
    uid = _resolve_user_id(req.user_id, current)
    state = load_user_brain(uid)
    state["companion_name"] = req.companion_name.strip()
    if req.user_display_name:
        state["user_display_name"] = req.user_display_name.strip()
    save_user_brain(uid, state)
    return {"ok": True, "state": state, "brain": get_brain_status(uid)}


@app.post("/checkin/morning")
def morning_checkin(req: CheckinRequest, current: User = Depends(get_current_user)):
    uid = _resolve_user_id(req.user_id, current)
    state = get_user_state(uid)
    gain, state = add_exp(state, "morning_checkin")
    state["last_morning_goal"] = req.goal
    save_user_state(uid, state)
    return {"message": "Morning saved", "exp_gain": gain, "state": state}


@app.post("/checkin/evening")
def evening_checkin(req: CheckinRequest, current: User = Depends(get_current_user)):
    uid = _resolve_user_id(req.user_id, current)
    state = get_user_state(uid)
    gain, state = add_exp(state, "evening_checkin")
    save_user_state(uid, state)
    return {"message": "Evening saved", "exp_gain": gain, "state": state}


@app.post("/chat/start", response_model=ChatResponse)
def chat_start(req: ChatRequest, current: User = Depends(get_current_user)):
    """AI greets first for normal users. Admin gets a short LUNA hello."""
    uid = _resolve_user_id(req.user_id, current)
    try:
        raw = safe_chat_start_reply(uid, req.message or "")
        dialogue, ai_state = parse_ai_reply(raw)
        if not (dialogue or "").strip():
            dialogue = "こんにちは。LUNAです。今日も一緒にがんばろうね。"
        state = get_user_state(uid)
        if isinstance(ai_state, dict) and ai_state.get("emotion"):
            state = dict(state)
            state["emotion"] = ai_state["emotion"]
        return ChatResponse(
            dialogue=dialogue,
            game_state=state,
            suggested_replies=get_suggested_replies(uid, state),
            allow_custom_input=True,
            allow_voice_input=True,
        )
    except Exception as e:
        # Speak-first: never leave the bubble empty on start.
        state = get_user_state(uid)
        dialogue, _ = parse_ai_reply(soft_chat_failure_reply(e))
        return ChatResponse(
            dialogue=dialogue or "こんにちは。LUNAです。話しかけてくださいね。",
            game_state=state,
            suggested_replies=get_suggested_replies(uid, state),
            allow_custom_input=True,
            allow_voice_input=True,
        )


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, current: User = Depends(get_current_user)):
    uid = _resolve_user_id(req.user_id, current)
    try:
        raw = generate_with_retry(uid, req.message)
        dialogue, ai_state = parse_ai_reply(raw)
        if not (dialogue or "").strip():
            dialogue = "うん、聞こえてるよ。もう少し詳しく教えてくれる？"
        state = get_user_state(uid)
        if isinstance(ai_state, dict) and ai_state.get("emotion"):
            state = dict(state)
            state["emotion"] = ai_state["emotion"]
        return ChatResponse(
            dialogue=dialogue,
            game_state=state,
            suggested_replies=get_suggested_replies(uid, state),
            allow_custom_input=True,
            allow_voice_input=True,
        )
    except Exception as e:
        # Keep bubble speaking even when Gemini is down / quota hit.
        state = get_user_state(uid)
        dialogue, _ = parse_ai_reply(soft_chat_failure_reply(e))
        return ChatResponse(
            dialogue=dialogue or "少し待ってから、もう一度話しかけてね。",
            game_state=state,
            suggested_replies=["もう一度送る", "元気？", "今日の予定は？"],
            allow_custom_input=True,
            allow_voice_input=True,
        )


@app.post("/tts/speak")
def tts_speak(req: TtsSpeakRequest, current: User = Depends(get_current_user)):
    del current
    try:
        wav = synthesize_speech(req.text)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not wav:
        raise HTTPException(status_code=400, detail="empty text")
    return Response(content=wav, media_type="audio/wav")


# ----- Life modules (health / money / schedule) -----


@app.get("/life/modules")
def life_modules_list(current: User = Depends(get_current_user)):
    brain = load_user_brain(current.public_id)
    return list_modules(brain)


@app.get("/life/health/dashboard")
def life_health_dashboard(current: User = Depends(get_current_user)):
    brain = load_user_brain(current.public_id)
    result = health_dashboard(brain)
    # Persist reminder notification if evaluation set it.
    if brain.get("pending_notification") and result.get("mental_reminder"):
        save_user_brain(current.public_id, brain)
    return result


@app.get("/life/health/mental/status")
def life_health_mental_status(current: User = Depends(get_current_user)):
    brain = load_user_brain(current.public_id)
    result = mental_status_payload(brain)
    if result.get("reminder"):
        save_user_brain(current.public_id, brain)
    return result


@app.post("/life/health/mental")
def life_health_mental_checkin(
    req: HealthMentalCheckin,
    current: User = Depends(get_current_user),
):
    brain = load_user_brain(current.public_id)
    try:
        dash = save_mental_checkin(brain, req.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    save_user_brain(current.public_id, brain)
    return {"ok": True, "dashboard": dash}


@app.patch("/life/health/profile")
def life_health_profile_update(
    req: HealthProfileUpdate,
    current: User = Depends(get_current_user),
):
    brain = load_user_brain(current.public_id)
    payload = req.model_dump(exclude_unset=True)
    note = payload.pop("note", None)
    try:
        dash = save_health_profile(brain, payload, note=note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    save_user_brain(current.public_id, brain)
    return {"ok": True, "dashboard": dash}


@app.get("/life/money/dashboard")
def life_money_dashboard(current: User = Depends(get_current_user)):
    brain = load_user_brain(current.public_id)
    return money_dashboard(brain)


@app.patch("/life/money/profile")
def life_money_profile_update(
    req: MoneyProfileUpdate,
    current: User = Depends(get_current_user),
):
    brain = load_user_brain(current.public_id)
    payload = req.model_dump(exclude_unset=True)
    note = payload.pop("note", None)
    try:
        dash = save_money_profile(brain, payload, note=note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    save_user_brain(current.public_id, brain)
    return {"ok": True, "dashboard": dash}


@app.patch("/life/{module}/dashboard")
def life_dashboard_update(
    module: str,
    req: LifeDashboardUpdate,
    current: User = Depends(get_current_user),
):
    if module not in ("health", "money"):
        raise HTTPException(status_code=404, detail="Unknown module")
    brain = load_user_brain(current.public_id)
    try:
        if module == "health":
            dash = save_health_profile(brain, req.structured or {}, note=req.note)
            save_user_brain(current.public_id, brain)
            return {"ok": True, "dashboard": dash}
        if module == "money":
            dash = save_money_profile(brain, req.structured or {}, note=req.note)
            save_user_brain(current.public_id, brain)
            return {"ok": True, "dashboard": dash}
        update_module_structured(brain, module, req.structured, req.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    save_user_brain(current.public_id, brain)
    return {"ok": True, "dashboard": money_dashboard(brain)}


@app.get("/life/{module}")
def life_module_get(module: str, current: User = Depends(get_current_user)):
    if module not in MODULE_KEYS:
        raise HTTPException(status_code=404, detail="Unknown module")
    brain = load_user_brain(current.public_id)
    return summarize_module(brain, module)


@app.post("/life/{module}")
def life_module_append(
    module: str,
    req: LifeModuleAppendRequest,
    current: User = Depends(get_current_user),
):
    if module not in MODULE_KEYS:
        raise HTTPException(status_code=404, detail="Unknown module")
    brain = load_user_brain(current.public_id)
    try:
        summary = append_module_note(brain, module, req.note, req.structured)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    save_user_brain(current.public_id, brain)
    return {"ok": True, "module": summary}


# ----- Schedule / calendar -----


@app.get("/home/summary")
def get_home_summary(current: User = Depends(get_current_user)):
    brain = load_user_brain(current.public_id)
    result = home_summary(brain)
    if brain.pop("_schedule_dirty", False) or result.get("health", {}).get("mental_reminder"):
        save_user_brain(current.public_id, brain)
    return result


@app.get("/schedule/events")
def schedule_list(date: Optional[str] = None, current: User = Depends(get_current_user)):
    brain = load_user_brain(current.public_id)
    result = list_events(brain, on_date=date)
    # Only persist when cleanup mutated schedule data (avoid lag on every open).
    if brain.pop("_schedule_dirty", False):
        save_user_brain(current.public_id, brain)
    return result


@app.post("/schedule/events")
def schedule_create(req: ScheduleEventCreate, current: User = Depends(get_current_user)):
    brain = load_user_brain(current.public_id)
    try:
        ev = add_event(
            brain,
            title=req.title,
            event_date=req.date,
            event_time=req.time,
            event_end_time=req.end_time,
            note=req.note,
            recurrence=req.recurrence,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    save_user_brain(current.public_id, brain)
    return {"ok": True, "event": ev}


@app.patch("/schedule/events/{event_id}")
def schedule_update(event_id: str, req: ScheduleEventUpdate, current: User = Depends(get_current_user)):
    brain = load_user_brain(current.public_id)
    try:
        ev = update_event(
            brain,
            event_id,
            title=req.title,
            event_date=req.date,
            event_time=req.time,
            event_end_time=req.end_time,
            note=req.note,
            done=req.done,
            scope=req.scope or "this",
        )
    except ValueError as e:
        raise HTTPException(status_code=404 if "not found" in str(e) else 400, detail=str(e))
    save_user_brain(current.public_id, brain)
    return {"ok": True, "event": ev}


@app.post("/schedule/events/{event_id}/complete")
def schedule_complete(
    event_id: str,
    req: ScheduleEventComplete,
    current: User = Depends(get_current_user),
):
    brain = load_user_brain(current.public_id)
    try:
        ev = complete_event(brain, event_id, done=req.done)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    save_user_brain(current.public_id, brain)
    return {"ok": True, "event": ev}


@app.delete("/schedule/events/{event_id}")
def schedule_delete(
    event_id: str,
    scope: str = "this",
    current: User = Depends(get_current_user),
):
    brain = load_user_brain(current.public_id)
    try:
        delete_event(brain, event_id, scope=scope or "this")
    except ValueError as e:
        raise HTTPException(status_code=404 if "not found" in str(e) else 400, detail=str(e))
    save_user_brain(current.public_id, brain)
    return {"ok": True}


@app.get("/schedule/suggestions")
def schedule_suggestions(current: User = Depends(get_current_user)):
    brain = load_user_brain(current.public_id)
    return suggest_combined(brain)


@app.post("/schedule/suggestions/apply")
def schedule_apply_suggestions(
    req: ScheduleApplySuggestions,
    current: User = Depends(get_current_user),
):
    brain = load_user_brain(current.public_id)
    combined = suggest_combined(brain)
    suggestions = combined["suggestions"]
    to_apply = suggestions if req.apply_all else [suggestions[i] for i in (req.indices or []) if 0 <= i < len(suggestions)]
    created = apply_suggestions(brain, to_apply)
    save_user_brain(current.public_id, brain)
    return {"ok": True, "created": created, "count": len(created)}


@app.post("/schedule/recurring/extend")
def schedule_extend_horizons(
    req: ScheduleExtendHorizons,
    current: User = Depends(get_current_user),
):
    brain = load_user_brain(current.public_id)
    result = extend_recurring_horizons(
        brain,
        template_ids=req.template_ids,
        days=req.days,
    )
    if result.get("count"):
        save_user_brain(current.public_id, brain)
    return result


# ----- Admin -----


def _user_to_admin_out(user: User) -> AdminUserOut:
    brain = {}
    try:
        if user.brain and user.brain.state_json:
            import json as _json
            brain = _json.loads(user.brain.state_json)
    except Exception:
        brain = {}
    created = user.created_at.isoformat() if user.created_at else None
    return AdminUserOut(
        user_id=user.public_id,
        email=user.email,
        display_name=user.display_name or brain.get("user_display_name"),
        is_admin=bool(user.is_admin or is_admin(user.public_id)),
        is_locked=bool(getattr(user, "is_locked", False)),
        created_at=created,
        companion_name=brain.get("companion_name"),
        profile_complete=bool(brain.get("profile_complete")),
    )


@app.get("/admin/users", response_model=list[AdminUserOut])
def admin_list_users(
    current: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [_user_to_admin_out(u) for u in users]


@app.post("/admin/users/{user_id}/reset-password")
def admin_reset_password(
    user_id: str,
    req: AdminResetPasswordRequest,
    current: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.public_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = hash_password(req.new_password)
    db.commit()
    return {"ok": True, "user_id": user_id}


@app.post("/admin/users/{user_id}/lock")
def admin_set_lock(
    user_id: str,
    req: AdminLockRequest,
    current: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.public_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.public_id == current.public_id and req.locked:
        raise HTTPException(status_code=400, detail="Cannot lock your own admin account")
    user.is_locked = bool(req.locked)
    db.commit()
    return {"ok": True, "user_id": user_id, "is_locked": user.is_locked}


@app.get("/admin/export")
def admin_export(
    current: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Full backup JSON for Postgres Free expiry / migration."""
    import json as _json
    from datetime import datetime, timezone

    users_out = []
    for u in db.query(User).order_by(User.id.asc()).all():
        brain_raw = u.brain.state_json if u.brain else "{}"
        try:
            brain = _json.loads(brain_raw)
        except Exception:
            brain = {"_raw": brain_raw}
        users_out.append(
            {
                "public_id": u.public_id,
                "email": u.email,
                "password_hash": u.password_hash,
                "display_name": u.display_name,
                "is_admin": u.is_admin,
                "is_locked": getattr(u, "is_locked", False),
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "brain": brain,
            }
        )
    core_row = db.query(CoreBrain).filter_by(id=1).first()
    core = {}
    if core_row and core_row.state_json:
        try:
            core = _json.loads(core_row.state_json)
        except Exception:
            core = {"_raw": core_row.state_json}
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user_count": len(users_out),
        "users": users_out,
        "core_brain": core,
    }


# ----- Career RPG orientation -----


@app.get("/journey/careers")
def journey_careers(current: User = Depends(get_current_user)):
    return {"classes": list_classes(), "careers": list_careers()}


@app.get("/journey/status")
def journey_get_status(current: User = Depends(get_current_user)):
    brain = load_user_brain(current.public_id)
    return journey_status(brain)


@app.post("/journey/select")
def journey_select(req: JourneySelectRequest, current: User = Depends(get_current_user)):
    brain = load_user_brain(current.public_id)
    try:
        status = select_journey(brain, class_id=req.class_id, career_id=req.career_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    save_user_brain(current.public_id, brain)
    return {"ok": True, "status": status, "map": list_journey_map(brain)}


@app.get("/journey/map")
def journey_map(current: User = Depends(get_current_user)):
    brain = load_user_brain(current.public_id)
    return list_journey_map(brain)


@app.get("/journey/lessons/{lesson_id}")
def journey_get_lesson(lesson_id: str, current: User = Depends(get_current_user)):
    brain = load_user_brain(current.public_id)
    try:
        return get_lesson(brain, lesson_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/journey/lessons/{lesson_id}/complete")
def journey_complete_lesson(lesson_id: str, current: User = Depends(get_current_user)):
    brain = load_user_brain(current.public_id)
    try:
        result = complete_lesson(brain, lesson_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    save_user_brain(current.public_id, brain)
    return result


@app.get("/journey/bosses")
def journey_bosses(current: User = Depends(get_current_user)):
    brain = load_user_brain(current.public_id)
    return {"bosses": list_bosses(brain)}


@app.post("/journey/bosses/{boss_id}/challenge")
def journey_boss_challenge(
    boss_id: str,
    req: JourneyBossChallenge,
    current: User = Depends(get_current_user),
):
    brain = load_user_brain(current.public_id)
    try:
        result = challenge_boss(brain, boss_id, success=req.success)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    save_user_brain(current.public_id, brain)
    return result


@app.post("/journey/lessons/{lesson_id}/enrich")
def journey_lesson_enrich(
    lesson_id: str,
    req: JourneyLessonEnrich,
    current: User = Depends(get_current_user),
):
    brain = load_user_brain(current.public_id)
    j = journey_status(brain)
    if not j.get("selected"):
        raise HTTPException(status_code=400, detail="journey not selected")
    detail = (req.detail_ja or "").strip()
    if not detail:
        # Build from curriculum title + AI optional
        cur = get_curriculum(j["career_id"])
        les = next((x for x in (cur.get("lessons") or []) if x["id"] == lesson_id), None)
        if not les:
            raise HTTPException(status_code=404, detail="lesson not found")
        try:
            from luna_service import generate_json_task

            prompt = (
                "Return JSON {\"detail_ja\": \"...\"} only. "
                "Write a short Japanese study tip (3-5 sentences) for this lesson. "
                f"Career: {j.get('career_title_ja')}. Lesson: {les.get('title_ja')}."
            )
            data = generate_json_task(
                "You enrich learning tips. Do not invent new rewards or skills.",
                prompt,
            )
            if isinstance(data, dict):
                detail = str(data.get("detail_ja") or "").strip()
        except Exception:
            detail = ""
        if not detail:
            title = les.get("title_ja") or lesson_id
            detail = (
                f"「{title}」に取り組もう。"
                "小さな目標を決めて、今日できるところまで進めてみよう。"
            )
    try:
        result = enrich_lesson_detail(brain, lesson_id, detail)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    save_user_brain(current.public_id, brain)
    return result


@app.get("/career/taxonomy")
def career_taxonomy(current: User = Depends(get_current_user)):
    return load_taxonomy()


@app.post("/career/suggest")
def career_suggest(req: CareerSuggestRequest, current: User = Depends(get_current_user)):
    result = suggest_careers(
        decided_career=req.decided_career,
        personality_text=req.personality_text,
        hobbies_text=req.hobbies_text,
        favorite_subjects=req.favorite_subjects,
        subject_grades=req.subject_grades,
        top_k=req.top_k,
    )
    if req.save:
        state = load_user_brain(current.public_id)
        cp = state.setdefault("career_path", {})
        cp["decided"] = bool(req.decided_career and req.decided_career.strip())
        cp["decided_career"] = (req.decided_career or "").strip() or None
        cp["personality_note"] = req.personality_text or cp.get("personality_note")
        cp["hobbies_note"] = req.hobbies_text or cp.get("hobbies_note")
        cp["favorite_subjects"] = req.favorite_subjects or cp.get("favorite_subjects") or []
        cp["last_suggestions"] = result.get("suggestions", [])
        if result.get("mode") == "decided" and result.get("suggestions"):
            top = result["suggestions"][0]
            cp["cluster_id"] = top.get("cluster_id")
            cp["rpg_class"] = top.get("rpg_class")
            rpg = state.setdefault("rpg", {})
            rpg["class_id"] = top.get("rpg_class")
        save_user_brain(current.public_id, state)
        result["saved"] = True
        result["rpg_class_label_ja"] = rpg_class_label(result.get("rpg_class_hint") or "")
    return result


@app.post("/career/select")
def career_select(req: CareerSelectRequest, current: User = Depends(get_current_user)):
    state = load_user_brain(current.public_id)
    cp = state.setdefault("career_path", {})
    tax = load_taxonomy()
    cluster = next((c for c in tax["career_clusters"] if c["id"] == req.cluster_id), None)
    if not cluster:
        raise HTTPException(status_code=400, detail="Unknown cluster_id")
    cp["cluster_id"] = req.cluster_id
    if req.decided_career:
        cp["decided"] = True
        cp["decided_career"] = req.decided_career.strip()
    else:
        cp["decided"] = False
    class_id = req.rpg_class or cluster.get("rpg_class")
    cp["rpg_class"] = class_id
    rpg = state.setdefault("rpg", {})
    rpg["class_id"] = class_id
    save_user_brain(current.public_id, state)
    return {
        "ok": True,
        "career_path": cp,
        "rpg": rpg,
        "rpg_class_label_ja": rpg_class_label(class_id or ""),
    }


@app.get("/career/me")
def career_me(current: User = Depends(get_current_user)):
    state = load_user_brain(current.public_id)
    return {
        "career_path": state.get("career_path") or {},
        "rpg": state.get("rpg") or {},
    }


# ----- RPG learning loop -----


@app.get("/rpg/world")
def rpg_world(current: User = Depends(get_current_user)):
    state = load_user_brain(current.public_id)
    return {"world": load_world(), "regions": list_regions(state), "rpg": ensure_rpg(state)}


@app.get("/rpg/me")
def rpg_me(current: User = Depends(get_current_user)):
    state = load_user_brain(current.public_id)
    return {
        "level": state.get("current_level", 1),
        "total_exp": state.get("total_exp", 0),
        "daily_exp": state.get("daily_exp", 0),
        "rpg": ensure_rpg(state),
        "regions": list_regions(state),
    }


@app.post("/rpg/quest/start")
def rpg_quest_start(req: RpgQuestStartRequest, current: User = Depends(get_current_user)):
    state = load_user_brain(current.public_id)
    try:
        q = start_quest(
            state,
            title=req.title,
            quest_type=req.quest_type,
            subject=req.subject,
            note=req.note,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    save_user_brain(current.public_id, state)
    return {"ok": True, "quest": q, "rpg": ensure_rpg(state)}


@app.post("/rpg/activity/complete")
def rpg_activity_complete(req: RpgActivityRequest, current: User = Depends(get_current_user)):
    state = load_user_brain(current.public_id)
    try:
        result = complete_activity(
            state,
            quest_type=req.quest_type,
            title=req.title,
            subject=req.subject,
            score=req.score,
            note=req.note,
            quest_id=req.quest_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    save_user_brain(current.public_id, state)
    return {"ok": True, **result, "rpg": ensure_rpg(state)}


@app.get("/rpg/portfolio")
def rpg_portfolio(current: User = Depends(get_current_user)):
    state = load_user_brain(current.public_id)
    return build_portfolio(state)

