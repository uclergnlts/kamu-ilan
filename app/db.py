from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def ensure_schema() -> None:
    """Apply small, backwards-compatible MVP schema additions."""
    columns = {column["name"] for column in inspect(engine).get_columns("user_filters")}
    if "subscribed" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE user_filters ADD COLUMN subscribed BOOLEAN NOT NULL DEFAULT TRUE")
            )
