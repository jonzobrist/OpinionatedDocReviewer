from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return
    sqlite_path = database_url.replace("sqlite:///", "", 1)
    if not sqlite_path or sqlite_path == ":memory:":
        return
    Path(sqlite_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_parent_dir(settings.DATABASE_URL)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
