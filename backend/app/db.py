"""
SQLAlchemy engine/session setup. SQLite today (checklist: "SQLite as the
Postgres stand-in for now"), but every access goes through this module's
`engine`/`SessionLocal`, so pointing DATABASE_URL at Postgres later is a
one-line env change, not a rewrite.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args)
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
    # Import models here so they're registered on Base.metadata before create_all.
    from . import models_db  # noqa: F401

    Base.metadata.create_all(bind=engine)
