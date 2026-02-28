from sqlalchemy import create_engine, text

from app.db import init_db, models


def test_persona_schema_backfills_defaults(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(init_db, "engine", engine)

    with engine.begin() as connection:
        connection.execute(text("DROP TABLE personas"))
        connection.execute(
            text(
                """
                CREATE TABLE personas (
                  id INTEGER PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  name TEXT NOT NULL,
                  description TEXT,
                  system_prompt TEXT NOT NULL,
                  focus_areas JSON,
                  tone TEXT,
                  is_active BOOLEAN DEFAULT 1,
                  group_id INTEGER,
                  created_at DATETIME
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO personas (
                  id, tenant_id, name, description, system_prompt, focus_areas,
                  tone, is_active, group_id, created_at
                ) VALUES (1, 'local-dev', 'Legacy Persona', 'desc', 'prompt', '[]', NULL, 1, NULL, CURRENT_TIMESTAMP)
                """
            )
        )

    init_db._ensure_schema()

    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT output_requirements, examples, is_default, is_system_locked, sort_order
                FROM personas
                WHERE name = 'Legacy Persona'
                """
            )
        ).first()

    assert row is not None
    assert row.output_requirements in ("{}", {})
    assert row.examples in ("[]", [])
    assert row.is_default == 0
    assert row.is_system_locked == 0
    assert row.sort_order == 100
