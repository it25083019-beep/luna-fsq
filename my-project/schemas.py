from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any
import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(v: str) -> str:
    v = (v or "").strip().lower()
    if not _EMAIL_RE.match(v):
        raise ValueError("Invalid email address")
    return v


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    display_name: Optional[str] = None

    @field_validator("email")
    @classmethod
    def email_ok(cls, v: str) -> str:
        return _normalize_email(v)


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def email_ok(cls, v: str) -> str:
        return _normalize_email(v)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    is_admin: bool = False


class ChatRequest(BaseModel):
    user_id: Optional[str] = None
    message: str = ""


class CheckinRequest(BaseModel):
    user_id: Optional[str] = None
    goal: Optional[str] = None


class SetCompanionNameRequest(BaseModel):
    user_id: Optional[str] = None
    companion_name: str
    user_display_name: Optional[str] = None


class ChatResponse(BaseModel):
    dialogue: str
    game_state: Dict[str, Any]
    suggested_replies: list[str] = []
    allow_custom_input: bool = True
    allow_voice_input: bool = True
