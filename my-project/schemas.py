from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
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


class ForgotPasswordRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def email_ok(cls, v: str) -> str:
        return _normalize_email(v)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20)
    new_password: str = Field(min_length=6)


class ForgotPasswordResponse(BaseModel):
    message: str
    reset_url: Optional[str] = None


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


class LifeModuleAppendRequest(BaseModel):
    note: str = Field(min_length=1, max_length=2000)
    structured: Optional[Dict[str, Any]] = None


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


class RpgQuestStartRequest(BaseModel):
    title: str
    quest_type: str = "daily_study"
    subject: Optional[str] = None
    note: Optional[str] = None


class RpgActivityRequest(BaseModel):
    title: str
    quest_type: str = "daily_study"
    subject: Optional[str] = None
    score: Optional[float] = None
    note: Optional[str] = None
    quest_id: Optional[str] = None


class ScheduleEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    date: str = Field(description="YYYY-MM-DD")
    time: Optional[str] = Field(default=None, max_length=5, description="start HH:MM")
    end_time: Optional[str] = Field(default=None, max_length=5, description="end HH:MM")
    note: Optional[str] = Field(default=None, max_length=500)
    recurrence: Optional[str] = Field(default=None, description="weekly or monthly")


class ScheduleEventUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    date: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    time: Optional[str] = Field(default=None, max_length=5, description="start HH:MM")
    end_time: Optional[str] = Field(default=None, max_length=5, description="end HH:MM")
    note: Optional[str] = Field(default=None, max_length=500)
    done: Optional[bool] = None
    scope: Optional[str] = Field(
        default="this",
        description="this = only this occurrence; all = whole recurring series",
    )


class ScheduleEventComplete(BaseModel):
    done: bool = True


class ScheduleApplySuggestions(BaseModel):
    indices: Optional[List[int]] = None
    apply_all: bool = False


class ScheduleExtendHorizons(BaseModel):
    """Extend recurring generation windows by another year."""
    template_ids: Optional[List[str]] = None
    days: int = Field(default=365, ge=30, le=800)


class LifeDashboardUpdate(BaseModel):
    """Manual override for health / money structured metrics."""
    structured: dict = Field(default_factory=dict)
    note: Optional[str] = Field(default=None, max_length=2000)


class HealthProfileUpdate(BaseModel):
    age: Optional[int] = Field(default=None, ge=5, le=120)
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    target_weight_kg: Optional[float] = None
    target_height_cm: Optional[float] = None
    sleep_hours: Optional[float] = None
    wake_time: Optional[str] = Field(default=None, max_length=5)
    bedtime: Optional[str] = Field(default=None, max_length=5)
    hobbies: Optional[str] = Field(default=None, max_length=300)
    school_hours: Optional[float] = None
    study_hours: Optional[float] = None
    relax_hours: Optional[float] = None
    exercise_plan: Optional[str] = Field(default=None, max_length=500)
    note: Optional[str] = Field(default=None, max_length=2000)


class HealthMentalCheckin(BaseModel):
    status: str = Field(min_length=1, max_length=20)


class MoneyProfileUpdate(BaseModel):
    monthly_income: Optional[int] = Field(default=None, ge=0)
    monthly_expense: Optional[int] = Field(default=None, ge=0)
    purchase_name: Optional[str] = Field(default=None, max_length=80)
    purchase_current: Optional[int] = Field(default=None, ge=0)
    purchase_target: Optional[int] = Field(default=None, ge=0)
    emergency_current: Optional[int] = Field(default=None, ge=0)
    emergency_target: Optional[int] = Field(default=None, ge=0)
    reserve_current: Optional[int] = Field(default=None, ge=0)
    reserve_target: Optional[int] = Field(default=None, ge=0)
    invest_current: Optional[int] = Field(default=None, ge=0)
    invest_target: Optional[int] = Field(default=None, ge=0)
    note: Optional[str] = Field(default=None, max_length=2000)


class JourneySelectRequest(BaseModel):
    class_id: str = Field(min_length=1, max_length=32)
    career_id: str = Field(min_length=1, max_length=64)


class JourneyBossChallenge(BaseModel):
    success: bool = True


class JourneyLessonEnrich(BaseModel):
    detail_ja: Optional[str] = Field(default=None, max_length=1200)
