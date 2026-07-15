"""Password hashing and JWT auth helpers."""
from __future__ import annotations

from dotenv import load_dotenv

_env_dir = __import__('pathlib').Path(__file__).resolve().parent
load_dotenv(_env_dir / '.env')
load_dotenv()  # also CWD

import os
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


def hash_password(password: str) -> str:
    # bcrypt truncates at 72 bytes
    return pwd_context.hash(password[:72] if isinstance(password, str) else password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain[:72] if isinstance(plain, str) else plain, hashed)
    except Exception:
        return False


def create_access_token(subject: str, extra: Optional[dict[str, Any]] = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload: dict[str, Any] = {"sub": subject, "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


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
    if not user:
        raise credentials_exc
    return user
