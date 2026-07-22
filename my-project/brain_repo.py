"""DB-backed brain load/save with one-time JSON migration."""
from __future__ import annotations

from dotenv import load_dotenv

_env_dir = __import__('pathlib').Path(__file__).resolve().parent
load_dotenv(_env_dir / '.env')
load_dotenv()  # also CWD

import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from auth_security import hash_password
from database import SessionLocal
from models import CoreBrain, User, UserBrain

_BASE_DIR = Path(__file__).resolve().parent
BRAIN_DIR = Path(os.getenv("LUNA_BRAIN_DIR") or (_BASE_DIR / "brain_data"))
CORE_BRAIN_PATH = BRAIN_DIR / "luna_core_brain.json"
USERS_DIR = BRAIN_DIR / "users"


def default_user_brain(user_id: str) -> Dict[str, Any]:
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
        "relationship_level": 1,
        "chat_turn_count": 0,
        "user_speech_style": "polite",
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
        "schedule_reminders": [],
        "pending_notification": None,
        "career_path": {
            "decided": False,
            "decided_career": None,
            "cluster_id": None,
            "rpg_class": None,
            "personality_note": None,
            "hobbies_note": None,
            "favorite_subjects": [],
            "last_suggestions": [],
        },
        "rpg": {
            "class_id": None,
            "region_id": "tutorial_plains",
            "equipment": [],
            "quest_log": [],
            "boss_clears": [],
            "treasure_finds": [],
            "active_quests": [],
        },
    }


def default_core_brain() -> Dict[str, Any]:
    return {"trained_knowledge": [], "chat_history": []}


def _parse_state(raw: Optional[str], fallback: Dict[str, Any]) -> Dict[str, Any]:
    if not raw:
        return dict(fallback)
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            base = dict(fallback)
            base.update(data)
            return base
    except json.JSONDecodeError:
        pass
    return dict(fallback)


def load_user_brain(public_id: str, db: Optional[Session] = None) -> Dict[str, Any]:
    own = db is None
    session = db or SessionLocal()
    try:
        user = session.query(User).filter(User.public_id == public_id).first()
        if not user or not user.brain:
            return default_user_brain(public_id)
        data = _parse_state(user.brain.state_json, default_user_brain(public_id))
        data["user_id"] = public_id
        return data
    finally:
        if own:
            session.close()


def save_user_brain(public_id: str, data: Dict[str, Any], db: Optional[Session] = None) -> None:
    own = db is None
    session = db or SessionLocal()
    try:
        user = session.query(User).filter(User.public_id == public_id).first()
        if not user:
            # Auto-create shell user so saves never silently drop (legacy ids)
            user = User(
                public_id=public_id,
                email=f"legacy-{public_id}@luna.local",
                password_hash=hash_password(uuid.uuid4().hex),
                display_name=None,
                is_admin=(public_id == "admin_root"),
            )
            session.add(user)
            session.flush()
        payload = dict(data)
        payload["user_id"] = public_id
        raw = json.dumps(payload, ensure_ascii=False)
        if user.brain:
            user.brain.state_json = raw
        else:
            session.add(UserBrain(user_id=user.id, state_json=raw))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        if own:
            session.close()


def load_core_brain(db: Optional[Session] = None) -> Dict[str, Any]:
    own = db is None
    session = db or SessionLocal()
    try:
        row = session.query(CoreBrain).filter(CoreBrain.id == 1).first()
        if not row:
            return default_core_brain()
        data = _parse_state(row.state_json, default_core_brain())
        data.setdefault("trained_knowledge", [])
        data.setdefault("chat_history", [])
        return data
    finally:
        if own:
            session.close()


def save_core_brain(data: Dict[str, Any], db: Optional[Session] = None) -> None:
    own = db is None
    session = db or SessionLocal()
    try:
        raw = json.dumps(data, ensure_ascii=False)
        row = session.query(CoreBrain).filter(CoreBrain.id == 1).first()
        if row:
            row.state_json = raw
        else:
            session.add(CoreBrain(id=1, state_json=raw))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        if own:
            session.close()


def _ensure_user_for_public_id(
    session: Session,
    public_id: str,
    *,
    email: Optional[str] = None,
    password: Optional[str] = None,
    is_admin: bool = False,
    display_name: Optional[str] = None,
) -> User:
    user = session.query(User).filter(User.public_id == public_id).first()
    if user:
        return user
    user = User(
        public_id=public_id,
        email=email or f"migrated-{public_id}@luna.local",
        password_hash=hash_password(password or uuid.uuid4().hex),
        display_name=display_name,
        is_admin=is_admin,
    )
    session.add(user)
    session.flush()
    return user


def migrate_json_brains_to_db() -> Dict[str, Any]:
    """Import brain_data JSON into DB when rows are missing."""
    stats = {"users_migrated": 0, "core_migrated": False, "admin_seeded": False}
    session = SessionLocal()
    try:
        # Core brain
        core_row = session.query(CoreBrain).filter(CoreBrain.id == 1).first()
        if not core_row and CORE_BRAIN_PATH.exists():
            with open(CORE_BRAIN_PATH, "r", encoding="utf-8") as f:
                core_data = json.load(f)
            session.add(CoreBrain(id=1, state_json=json.dumps(core_data, ensure_ascii=False)))
            stats["core_migrated"] = True
        elif not core_row:
            session.add(CoreBrain(id=1, state_json=json.dumps(default_core_brain(), ensure_ascii=False)))
            stats["core_migrated"] = True

        # User brains from JSON files
        if USERS_DIR.exists():
            for path in sorted(USERS_DIR.glob("*.json")):
                public_id = path.stem
                with open(path, "r", encoding="utf-8") as f:
                    brain_data = json.load(f)
                if not isinstance(brain_data, dict):
                    continue
                brain_data["user_id"] = public_id
                user = session.query(User).filter(User.public_id == public_id).first()
                if user and user.brain:
                    continue
                if not user:
                    user = _ensure_user_for_public_id(
                        session,
                        public_id,
                        is_admin=(public_id == "admin_root"),
                    )
                if not user.brain:
                    session.add(
                        UserBrain(
                            user_id=user.id,
                            state_json=json.dumps(brain_data, ensure_ascii=False),
                        )
                    )
                    stats["users_migrated"] += 1

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return stats



def sync_privacy_rules_into_core() -> int:
    """Merge privacy trained_knowledge from JSON into DB core (idempotent)."""
    if not CORE_BRAIN_PATH.exists():
        return 0
    with open(CORE_BRAIN_PATH, "r", encoding="utf-8") as f:
        file_data = json.load(f)
    file_rules = [x for x in file_data.get("trained_knowledge", []) if isinstance(x, str) and x.startswith("PRIVACY:")]
    if not file_rules:
        return 0
    session = SessionLocal()
    try:
        row = session.query(CoreBrain).filter(CoreBrain.id == 1).first()
        if not row:
            return 0
        data = _parse_state(row.state_json, default_core_brain())
        knowledge = list(data.get("trained_knowledge", []))
        added = 0
        for rule in file_rules:
            if rule not in knowledge:
                knowledge.append(rule)
                added += 1
        if added:
            data["trained_knowledge"] = knowledge
            if file_data.get("version"):
                data["version"] = file_data["version"]
            row.state_json = json.dumps(data, ensure_ascii=False)
            session.commit()
        return added
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def seed_admin_user() -> bool:
    """Create/update admin from ADMIN_EMAIL / ADMIN_PASSWORD env."""
    email = os.getenv("ADMIN_EMAIL", "admin@luna.local").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "admin123456")
    public_id = "admin_root"
    session = SessionLocal()
    try:
        by_pub = session.query(User).filter(User.public_id == public_id).first()
        by_email = session.query(User).filter(User.email == email).first()
        user = by_pub or by_email
        created = False
        if not user:
            user = User(
                public_id=public_id,
                email=email,
                password_hash=hash_password(password),
                display_name="Admin",
                is_admin=True,
            )
            session.add(user)
            session.flush()
            created = True
        else:
            # Keep admin_root id for ADMIN_USER_IDS compatibility
            user.public_id = public_id
            user.email = email
            user.password_hash = hash_password(password)
            user.is_admin = True
            if not user.display_name:
                user.display_name = "Admin"

        if not user.brain:
            brain = default_user_brain(public_id)
            # Prefer existing JSON if present
            json_path = USERS_DIR / f"{public_id}.json"
            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    brain.update(loaded)
                    brain["user_id"] = public_id
            session.add(UserBrain(user_id=user.id, state_json=json.dumps(brain, ensure_ascii=False)))

        session.commit()
        return created
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
