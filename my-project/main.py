from __future__ import annotations

import os
import uuid
from typing import Optional

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from auth_security import (
    create_access_token,
    get_current_user,
    hash_password,
    require_admin,
    verify_password,
)
from brain_repo import migrate_json_brains_to_db, seed_admin_user, sync_privacy_rules_into_core
from database import get_db, init_db
from models import CoreBrain, User
from schemas import (
    AdminLockRequest,
    AdminResetPasswordRequest,
    AdminUserOut,
    ChatRequest,
    ChatResponse,
    CheckinRequest,
    LoginRequest,
    RegisterRequest,
    SetCompanionNameRequest,
    TokenResponse,
    CareerSuggestRequest,
    CareerSelectRequest,
    RpgQuestStartRequest,
    RpgActivityRequest,
)
from suggestions import get_suggested_replies
from career_engine import load_taxonomy, suggest_careers, rpg_class_label
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
from luna_service import (
    LunaAiError,
    generate_with_retry,
    parse_ai_reply,
    get_brain_status,
    load_user_brain,
    save_user_brain,
    start_user_greeting,
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
        print(f"[WARN] {item} — change before sharing with others")


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
    return RedirectResponse(url="/demo")


@app.get("/health")
def health():
    return {
        "ok": True,
        "env": os.getenv("ENV", "dev"),
        "model": os.getenv("MODEL_NAME", "gemini-2.5-flash"),
        "db": (
            "postgres"
            if "postgres" in os.getenv("DATABASE_URL", "").lower()
            else "mysql"
            if "mysql" in os.getenv("DATABASE_URL", "").lower()
            else "sqlite"
        ),
    }


@app.get("/demo")
def demo_page():
    return FileResponse(_STATIC_DIR / "demo.html")


@app.get("/admin")
def admin_page():
    return FileResponse(_STATIC_DIR / "admin.html")


@app.get("/live2d")
def live2d_demo_page():
    return FileResponse(_STATIC_DIR / "live2d-demo.html")


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
    token = create_access_token(user.public_id, extra={"email": user.email, "is_admin": user.is_admin})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.public_id,
        email=user.email,
        is_admin=user.is_admin,
    )


@app.get("/auth/me")
def auth_me(current: User = Depends(get_current_user)):
    return {
        "user_id": current.public_id,
        "email": current.email,
        "display_name": current.display_name,
        "is_admin": current.is_admin or is_admin(current.public_id),
    }


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
        if is_admin(uid):
            raw = generate_with_retry(uid, req.message or "こんにちは")
        else:
            raw = start_user_greeting(uid)
        dialogue, _ = parse_ai_reply(raw)
        state = get_user_state(uid)
        return ChatResponse(
            dialogue=dialogue,
            game_state=state,
            suggested_replies=get_suggested_replies(uid, state),
            allow_custom_input=True,
            allow_voice_input=True,
        )
    except Exception as e:
        raise _chat_http_error(e)


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, current: User = Depends(get_current_user)):
    uid = _resolve_user_id(req.user_id, current)
    try:
        raw = generate_with_retry(uid, req.message)
        dialogue, _ai_state = parse_ai_reply(raw)
        state = get_user_state(uid)
        return ChatResponse(
            dialogue=dialogue,
            game_state=state,
            suggested_replies=get_suggested_replies(uid, state),
            allow_custom_input=True,
            allow_voice_input=True,
        )
    except Exception as e:
        raise _chat_http_error(e)


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

