"""Password hashing and JWT auth helpers."""
from __future__ import annotations

from dotenv import load_dotenv

_env_dir = __import__("pathlib").Path(__file__).resolve().parent
load_dotenv(_env_dir / ".env")
load_dotenv()

import hashlib
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=True)

JWT_SECRET = os.getenv("JWT_SECRET", "dev-luna-jwt-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", str(60 * 24 * 7)))
PASSWORD_RESET_EXPIRE_MINUTES = int(os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "60"))
MIN_PASSWORD_LENGTH = 10
LOGIN_MAX_FAILS = 8
LOGIN_LOCK_MINUTES = 15
LOGIN_LOCK_MESSAGE = "ログイン試行が多すぎます。15分ほど待ってからもう一度。"
_LOGIN_FAILS: dict[str, list[float]] = {}


def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72] if isinstance(password, str) else password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain[:72] if isinstance(plain, str) else plain, hashed)
    except Exception:
        return False


def generate_password_reset_token() -> str:
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def password_reset_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES)


def create_access_token(
    subject: str,
    extra: Optional[dict[str, Any]] = None,
    token_version: int = 0,
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload: dict[str, Any] = {"sub": subject, "exp": expire, "tv": int(token_version or 0)}
    if extra:
        payload.update(extra)
        payload["tv"] = int(token_version or 0)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def token_version_matches(payload: dict[str, Any], user: User) -> bool:
    try:
        claimed = int(payload.get("tv", 0) or 0)
    except (TypeError, ValueError):
        claimed = 0
    current = int(getattr(user, "token_version", 0) or 0)
    return claimed == current


def bump_token_version(user: User) -> int:
    user.token_version = int(getattr(user, "token_version", 0) or 0) + 1
    return user.token_version


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def clear_login_throttle(email: Optional[str] = None) -> None:
    if email:
        _LOGIN_FAILS.pop(email.strip().lower(), None)
    else:
        _LOGIN_FAILS.clear()


def _recent_fails(email: str) -> list[float]:
    now = time.time()
    window = LOGIN_LOCK_MINUTES * 60
    hits = [t for t in _LOGIN_FAILS.get(email, []) if now - t < window]
    _LOGIN_FAILS[email] = hits
    return hits


def login_throttled(email: str, user: Optional[User] = None) -> bool:
    key = (email or "").strip().lower()
    if len(_recent_fails(key)) >= LOGIN_MAX_FAILS:
        return True
    until = getattr(user, "login_locked_until", None) if user else None
    if until and _as_utc(until) > datetime.now(timezone.utc):
        return True
    return False


def record_login_failure(email: str, user: Optional[User] = None) -> None:
    key = (email or "").strip().lower()
    _LOGIN_FAILS.setdefault(key, []).append(time.time())
    _recent_fails(key)
    if not user:
        return
    until = getattr(user, "login_locked_until", None)
    if until and _as_utc(until) <= datetime.now(timezone.utc):
        user.login_fail_count = 0
        user.login_locked_until = None
    user.login_fail_count = int(getattr(user, "login_fail_count", 0) or 0) + 1
    if user.login_fail_count >= LOGIN_MAX_FAILS:
        user.login_locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOGIN_LOCK_MINUTES)


def record_login_success(email: str, user: User) -> None:
    clear_login_throttle(email)
    user.login_fail_count = 0
    user.login_locked_until = None


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        public_id = payload.get("sub")
        if not public_id:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user = db.query(User).filter(User.public_id == public_id).first()
    if not user or not token_version_matches(payload, user):
        raise credentials_exc
    if getattr(user, "is_locked", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is locked",
        )
    return user


def require_admin(current: User = Depends(get_current_user)) -> User:
    from luna_service import is_admin

    if current.is_admin or is_admin(current.public_id):
        return current
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
