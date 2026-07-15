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
    verify_password,
)
from brain_repo import migrate_json_brains_to_db, seed_admin_user
from database import get_db, init_db
from models import User
from schemas import (
    ChatRequest,
    ChatResponse,
    CheckinRequest,
    LoginRequest,
    RegisterRequest,
    SetCompanionNameRequest,
    TokenResponse,
)
from suggestions import get_suggested_replies
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
        "db": "mysql" if "mysql" in os.getenv("DATABASE_URL", "").lower() else "sqlite",
    }


@app.get("/demo")
def demo_page():
    return FileResponse(_STATIC_DIR / "demo.html")


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
