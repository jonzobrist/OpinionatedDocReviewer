from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.session import SessionLocal, engine
from app.db import models
from sqlalchemy import text

DEFAULT_TENANT = "local-dev"
DEFAULT_GROUP_NAME = "Default Review"


def default_persona_definitions() -> list[dict]:
    return [
        {
            "name": "Clarity Editor",
            "description": "Improves structure, flow, and readability.",
            "system_prompt": "Review the document for clarity, structure, and missing context. Provide concise, actionable edits.",
            "focus_areas": ["structure", "readability", "ambiguity"],
            "tone": "direct, constructive",
            "reference_notes": "Prioritize clarity gaps and confusing transitions before style preferences.",
            "output_requirements": {
                "format": "bullet_list",
                "max_bullets": 4,
                "require_quote_excerpt": True,
                "require_actionable": True,
                "include_severity": False,
            },
            "examples": [],
            "sort_order": 10,
            "color_theme": "#1d8a7a",
        },
        {
            "name": "Risk & Compliance",
            "description": "Flags risk, security, privacy, and policy issues.",
            "system_prompt": "Identify risk, compliance, privacy, and security concerns. Note missing approvals or safeguards.",
            "focus_areas": ["security", "privacy", "compliance", "risk"],
            "tone": "cautious, precise",
            "reference_notes": "Call out control gaps and legal/compliance ambiguity with concrete mitigation steps.",
            "output_requirements": {
                "format": "bullet_list",
                "max_bullets": 4,
                "require_quote_excerpt": True,
                "require_actionable": True,
                "include_severity": True,
            },
            "examples": [],
            "sort_order": 20,
            "color_theme": "#b7482f",
        },
        {
            "name": "Executive Summary",
            "description": "Highlights key takeaways and action items.",
            "system_prompt": "Summarize key points, decisions, and action items. Flag gaps in executive-level messaging.",
            "focus_areas": ["summary", "decision clarity", "action items"],
            "tone": "succinct, strategic",
            "reference_notes": "Optimize for fast executive consumption and explicit ownership of next actions.",
            "output_requirements": {
                "format": "bullet_list",
                "max_bullets": 4,
                "require_quote_excerpt": True,
                "require_actionable": True,
                "include_severity": False,
            },
            "examples": [],
            "sort_order": 30,
            "color_theme": "#2d6eea",
        },
    ]


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_schema()
    seed_default_personas(tenant_id=DEFAULT_TENANT)
    seed_default_admin_user(tenant_id=DEFAULT_TENANT)


def seed_default_personas(tenant_id: str, db: Session | None = None) -> None:
    owns_session = db is None
    if db is None:
        db = SessionLocal()
    try:
        existing = (
            db.query(models.Persona)
            .filter(
                models.Persona.tenant_id == tenant_id,
                models.Persona.is_default.is_(True),
            )
            .count()
        )
        if existing > 0:
            return
        upsert_default_personas(tenant_id=tenant_id, db=db)
        db.commit()
    finally:
        if owns_session:
            db.close()


def seed_default_admin_user(tenant_id: str, db: Session | None = None) -> None:
    owns_session = db is None
    if db is None:
        db = SessionLocal()
    try:
        existing = (
            db.query(models.User)
            .filter(
                models.User.tenant_id == tenant_id,
                models.User.role == "admin",
            )
            .first()
        )
        if existing:
            return
        db.add(
            models.User(
                tenant_id=tenant_id,
                name="Local Admin",
                email=f"admin+{tenant_id}@local",
                role="admin",
                is_active=True,
            )
        )
        db.commit()
    finally:
        if owns_session:
            db.close()


def upsert_default_personas(tenant_id: str, db: Session) -> None:
    group = _ensure_default_group(tenant_id, db)
    for payload in default_persona_definitions():
        existing = (
            db.query(models.Persona)
            .filter(
                models.Persona.tenant_id == tenant_id,
                models.Persona.name == payload["name"],
                models.Persona.is_default.is_(True),
            )
            .first()
        )
        if existing:
            existing.description = payload["description"]
            existing.system_prompt = payload["system_prompt"]
            existing.focus_areas = payload["focus_areas"]
            existing.tone = payload["tone"]
            existing.reference_notes = payload["reference_notes"]
            existing.output_requirements = payload["output_requirements"]
            existing.examples = payload["examples"]
            existing.sort_order = payload["sort_order"]
            existing.color_theme = payload["color_theme"]
            existing.group_id = group.id
            existing.is_system_locked = True
            existing.is_default = True
            continue
        db.add(
            models.Persona(
                tenant_id=tenant_id,
                name=payload["name"],
                description=payload["description"],
                system_prompt=payload["system_prompt"],
                focus_areas=payload["focus_areas"],
                tone=payload["tone"],
                reference_notes=payload["reference_notes"],
                output_requirements=payload["output_requirements"],
                examples=payload["examples"],
                sort_order=payload["sort_order"],
                color_theme=payload["color_theme"],
                group_id=group.id,
                is_default=True,
                is_system_locked=True,
                is_active=True,
            )
        )


def reset_default_persona(tenant_id: str, persona: models.Persona, db: Session) -> models.Persona:
    payload = _match_default_persona_definition(persona)
    if payload is None:
        return persona
    group = _ensure_default_group(tenant_id, db)
    persona.name = payload["name"]
    persona.description = payload["description"]
    persona.system_prompt = payload["system_prompt"]
    persona.focus_areas = payload["focus_areas"]
    persona.tone = payload["tone"]
    persona.reference_notes = payload["reference_notes"]
    persona.output_requirements = payload["output_requirements"]
    persona.examples = payload["examples"]
    persona.sort_order = payload["sort_order"]
    persona.color_theme = payload["color_theme"]
    persona.group_id = group.id
    persona.is_default = True
    persona.is_system_locked = True
    persona.is_active = True
    db.commit()
    db.refresh(persona)
    return persona


def _ensure_default_group(tenant_id: str, db: Session) -> models.PersonaGroup:
    group = (
        db.query(models.PersonaGroup)
        .filter(
            models.PersonaGroup.tenant_id == tenant_id,
            models.PersonaGroup.name == DEFAULT_GROUP_NAME,
        )
        .first()
    )
    if group:
        return group
    group = models.PersonaGroup(
        tenant_id=tenant_id,
        name=DEFAULT_GROUP_NAME,
        description="Baseline review personas for quick-start feedback.",
    )
    db.add(group)
    db.flush()
    return group


def _match_default_persona_definition(persona: models.Persona) -> dict | None:
    definitions = default_persona_definitions()
    if not definitions:
        return None
    for payload in definitions:
        if payload["name"] == persona.name:
            return payload
    for payload in definitions:
        if payload["sort_order"] == persona.sort_order:
            return payload
    sorted_defs = sorted(
        definitions,
        key=lambda item: abs(int(item.get("sort_order", 0)) - int(persona.sort_order or 0)),
    )
    return sorted_defs[0]


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
            "provider",
            "TEXT DEFAULT 'openai'",
        )
        _ensure_column(
            connection,
            "review_jobs",
            "model",
            "TEXT DEFAULT 'gpt-4o-mini'",
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
        _ensure_column(
            connection,
            "comments",
            "output_metadata",
            "JSON",
        )
        _ensure_column(
            connection,
            "documents",
            "is_archived",
            "BOOLEAN DEFAULT 0",
        )
        _ensure_column(
            connection,
            "documents",
            "archived_at",
            "DATETIME",
        )
        _ensure_column(connection, "personas", "reference_notes", "TEXT")
        _ensure_column(connection, "personas", "output_requirements", "JSON")
        _ensure_column(connection, "personas", "examples", "JSON")
        _ensure_column(connection, "personas", "is_default", "BOOLEAN DEFAULT 0")
        _ensure_column(connection, "personas", "is_system_locked", "BOOLEAN DEFAULT 0")
        _ensure_column(connection, "personas", "sort_order", "INTEGER DEFAULT 100")
        _ensure_column(connection, "personas", "color_theme", "TEXT")
        _ensure_column(connection, "users", "account_state", "TEXT DEFAULT 'active'")
        _ensure_column(connection, "users", "email_verified_at", "DATETIME")
        _ensure_column(connection, "users", "last_login_at", "DATETIME")
        _ensure_column(connection, "meta_comments", "impact", "TEXT DEFAULT 'medium'")
        _ensure_column(connection, "meta_comments", "effort", "TEXT DEFAULT 'medium'")
        _ensure_column(connection, "meta_comments", "confidence", "REAL DEFAULT 0.5")
        _ensure_column(connection, "meta_comments", "why_now", "TEXT")
        _ensure_column(connection, "meta_comments", "recommended_change", "TEXT")
        _ensure_column(connection, "meta_comments", "verification_step", "TEXT")
        _ensure_column(connection, "meta_comments", "status", "TEXT DEFAULT 'open'")
        _ensure_column(connection, "meta_comments", "assignee", "TEXT")
        _ensure_column(connection, "meta_comments", "due_at", "TEXT")
        _ensure_column(connection, "meta_comments", "rank_score", "REAL DEFAULT 0")
        connection.execute(
            text("UPDATE review_jobs SET trigger='auto' WHERE trigger IS NULL")
        )
        connection.execute(
            text("UPDATE review_jobs SET provider='openai' WHERE provider IS NULL OR provider=''")
        )
        connection.execute(
            text("UPDATE review_jobs SET model='gpt-4o-mini' WHERE model IS NULL OR model=''")
        )
        connection.execute(
            text("UPDATE documents SET is_archived=0 WHERE is_archived IS NULL")
        )
        connection.execute(
            text("UPDATE comments SET output_metadata='{}' WHERE output_metadata IS NULL OR output_metadata=''")
        )
        connection.execute(
            text("UPDATE personas SET output_requirements='{}' WHERE output_requirements IS NULL OR output_requirements=''")
        )
        connection.execute(
            text("UPDATE personas SET examples='[]' WHERE examples IS NULL OR examples=''")
        )
        connection.execute(
            text("UPDATE personas SET is_default=0 WHERE is_default IS NULL")
        )
        connection.execute(
            text("UPDATE personas SET is_system_locked=0 WHERE is_system_locked IS NULL")
        )
        connection.execute(
            text("UPDATE personas SET sort_order=100 WHERE sort_order IS NULL")
        )
        connection.execute(
            text("UPDATE users SET account_state='active' WHERE account_state IS NULL OR account_state=''")
        )
        connection.execute(
            text("UPDATE meta_comments SET impact='medium' WHERE impact IS NULL OR impact=''")
        )
        connection.execute(
            text("UPDATE meta_comments SET effort='medium' WHERE effort IS NULL OR effort=''")
        )
        connection.execute(
            text("UPDATE meta_comments SET confidence=0.5 WHERE confidence IS NULL")
        )
        connection.execute(
            text("UPDATE meta_comments SET status='open' WHERE status IS NULL OR status=''")
        )
        connection.execute(
            text("UPDATE meta_comments SET rank_score=0 WHERE rank_score IS NULL")
        )
        connection.commit()


def _ensure_column(connection, table: str, column: str, ddl: str) -> None:
    rows = connection.execute(text(f"PRAGMA table_info({table})")).fetchall()
    existing = {row[1] for row in rows}
    if column in existing:
        return
    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
