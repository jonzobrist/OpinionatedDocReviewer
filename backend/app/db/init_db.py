from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.session import SessionLocal, engine
from app.db import models
from sqlalchemy import text

DEFAULT_TENANT = "local-dev"


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_schema()
    seed_default_personas(tenant_id=DEFAULT_TENANT)


def seed_default_personas(tenant_id: str, db: Session | None = None) -> None:
    owns_session = db is None
    if db is None:
        db = SessionLocal()
    try:
        existing = (
            db.query(models.Persona)
            .filter(models.Persona.tenant_id == tenant_id)
            .count()
        )
        if existing > 0:
            return

        group = models.PersonaGroup(
            tenant_id=tenant_id,
            name="Default Review",
            description="Baseline review personas for quick-start feedback.",
        )
        db.add(group)
        db.flush()

        personas = [
            models.Persona(
                tenant_id=tenant_id,
                name="Clarity Editor",
                description="Improves structure, flow, and readability.",
                system_prompt="Review the document for clarity, structure, and missing context. Provide concise, actionable edits.",
                focus_areas=["structure", "readability", "ambiguity"],
                tone="direct, constructive",
                group_id=group.id,
            ),
            models.Persona(
                tenant_id=tenant_id,
                name="Risk & Compliance",
                description="Flags risk, security, privacy, and policy issues.",
                system_prompt="Identify risk, compliance, privacy, and security concerns. Note missing approvals or safeguards.",
                focus_areas=["security", "privacy", "compliance", "risk"],
                tone="cautious, precise",
                group_id=group.id,
            ),
            models.Persona(
                tenant_id=tenant_id,
                name="Executive Summary",
                description="Highlights key takeaways and action items.",
                system_prompt="Summarize key points, decisions, and action items. Flag gaps in executive-level messaging.",
                focus_areas=["summary", "decision clarity", "action items"],
                tone="succinct, strategic",
                group_id=group.id,
            ),
        ]
        db.add_all(personas)
        db.commit()
    finally:
        if owns_session:
            db.close()


def _ensure_schema() -> None:
    with engine.connect() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        _ensure_column(
            connection,
            "review_jobs",
            "trigger",
            "TEXT DEFAULT 'auto'",
        )
        _ensure_column(
            connection,
            "review_jobs",
            "completed_at",
            "DATETIME",
        )
        _ensure_column(
            connection,
            "comments",
            "review_job_id",
            "INTEGER",
        )
        connection.execute(
            text("UPDATE review_jobs SET trigger='auto' WHERE trigger IS NULL")
        )
        connection.commit()


def _ensure_column(connection, table: str, column: str, ddl: str) -> None:
    rows = connection.execute(text(f"PRAGMA table_info({table})")).fetchall()
    existing = {row[1] for row in rows}
    if column in existing:
        return
    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
