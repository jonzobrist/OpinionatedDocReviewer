from sqlalchemy import create_engine, text

from app.db.init_db import _ensure_review_job_quality_telemetry_column


def test_ensure_review_job_quality_telemetry_column_is_backward_safe() -> None:
    engine = create_engine("sqlite://")

    with engine.connect() as connection:
        connection.execute(
            text(
                "CREATE TABLE review_jobs ("
                "id INTEGER PRIMARY KEY, "
                "tenant_id TEXT, "
                "document_version_id INTEGER, "
                "status TEXT"
                ")"
            )
        )
        connection.execute(
            text(
                "INSERT INTO review_jobs (id, tenant_id, document_version_id, status) "
                "VALUES (1, 'tenant-migrate', 7, 'queued')"
            )
        )
        connection.commit()

        _ensure_review_job_quality_telemetry_column(connection)
        connection.commit()

        columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(review_jobs)")).fetchall()
        }
        assert "quality_telemetry" in columns

        first_value = connection.execute(
            text("SELECT quality_telemetry FROM review_jobs WHERE id=1")
        ).scalar()
        assert first_value == "{}"

        preserved_value = '{"total_comments": 5}'
        connection.execute(
            text("UPDATE review_jobs SET quality_telemetry=:value WHERE id=1"),
            {"value": preserved_value},
        )
        connection.commit()

        _ensure_review_job_quality_telemetry_column(connection)
        connection.commit()

        second_value = connection.execute(
            text("SELECT quality_telemetry FROM review_jobs WHERE id=1")
        ).scalar()
        assert second_value == preserved_value
