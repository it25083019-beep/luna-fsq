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



class AdminUserOut(BaseModel):
    user_id: str
    email: str
    display_name: Optional[str] = None
    is_admin: bool = False
    is_locked: bool = False
    created_at: Optional[str] = None
    companion_name: Optional[str] = None
    profile_complete: bool = False


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=6)


class AdminLockRequest(BaseModel):
    locked: bool = True


class CareerSuggestRequest(BaseModel):
    decided_career: Optional[str] = None
    personality_text: str = ""
    hobbies_text: str = ""
    favorite_subjects: list[str] = []
    subject_grades: Dict[str, float] = {}
    top_k: int = 3
    save: bool = True


class CareerSelectRequest(BaseModel):
    cluster_id: str
    decided_career: Optional[str] = None
    rpg_class: Optional[str] = None
