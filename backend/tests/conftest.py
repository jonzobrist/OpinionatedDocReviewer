import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.config import settings
from app.db.models import Base
from app.main import create_app

SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_MODE", "header")
    # Default tests off the LLM verdict pass so the existing route
    # integration tests do not reach out to a real OpenAI API. Tests
    # that exercise the LLM verdict explicitly opt in and patch
    # generate_completion themselves.
    monkeypatch.setattr(settings, "META_VERDICT_USE_LLM", False)
    monkeypatch.setattr(
        "app.api.review_jobs.enqueue_review_job",
        lambda job_id, tenant_id: None,
    )
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app(init_db_on_startup=False)
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)

    Base.metadata.drop_all(bind=engine)
