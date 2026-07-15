"""SQLite (default) / MySQL (PyMySQL) / Postgres-ready SQLAlchemy setup."""
from __future__ import annotations

from dotenv import load_dotenv

_env_dir = __import__("pathlib").Path(__file__).resolve().parent
load_dotenv(_env_dir / ".env")
load_dotenv()  # also CWD

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

_BASE_DIR = Path(__file__).resolve().parent
_DATA_DIR = _BASE_DIR / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _resolve_database_url() -> str:
    """Prefer DATABASE_URL; optional MYSQL_PASSWORD builds MySQL when URL unset."""
    explicit = os.getenv("DATABASE_URL")
    mysql_password = os.getenv("MYSQL_PASSWORD")

    if mysql_password and (not explicit or explicit.startswith("mysql")):
        user = os.getenv("MYSQL_USER", "luna")
        host = os.getenv("MYSQL_HOST", "127.0.0.1")
        port = os.getenv("MYSQL_PORT", "3306")
        db_name = os.getenv("MYSQL_DATABASE", "luna_fsq")
        if explicit and explicit.startswith("mysql://"):
            url = "mysql+pymysql://" + explicit[len("mysql://"):]
        elif explicit and explicit.startswith("mysql+pymysql://"):
            url = explicit
        else:
            url = f"mysql+pymysql://{user}:{mysql_password}@{host}:{port}/{db_name}"
        return url

    url = explicit or "sqlite:///./data/luna.db"
    # SQLAlchemy needs the PyMySQL driver prefix
    if url.startswith("mysql://"):
        url = "mysql+pymysql://" + url[len("mysql://"):]
    return url


DATABASE_URL = _resolve_database_url()

# If relative sqlite path, resolve under package dir so CWD does not matter
if DATABASE_URL.startswith("sqlite:///./"):
    rel = DATABASE_URL.replace("sqlite:///./", "", 1)
    abs_path = (_BASE_DIR / rel).resolve()
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    DATABASE_URL = f"sqlite:///{abs_path.as_posix()}"

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
