from pathlib import Path
import os
import tomllib

from pydantic_settings import BaseSettings, SettingsConfigDict


def load_config_file() -> dict:
    config_path = os.getenv("ODR_CONFIG_PATH")
    if not config_path:
        config_path = str(Path(__file__).resolve().parents[2] / "config.toml")
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "rb") as handle:
            return tomllib.load(handle)
    except Exception:
        return {}


def parse_csv(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default
    items = [item.strip() for item in value.split(",")]
    return [item for item in items if item]


class Settings(BaseSettings):
    APP_NAME: str = "OpinionatedDocReviewer API"
    APP_VERSION: str = "0.1.0"
    API_PREFIX: str = "/api"
    DATABASE_URL: str = "sqlite:///./app.db"
    PORT: int = 8006
    REDIS_URL: str = "redis://localhost:6379/0"
    REVIEW_QUEUE_NAME: str = "review-jobs"
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 700
    OPENAI_MAX_INPUT_CHARS: int = 12000
    OPENAI_TEMPERATURE: float = 0.2
    OPENAI_TIMEOUT_SECONDS: int = 30
    REVIEW_INLINE: bool = True
    DOC_REPO_ROOT: str = ".run/doc-repos"
    DOC_REPO_ENABLED: bool = True
    CORS_ALLOW_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    CORS_ALLOW_ORIGIN_REGEX: str | None = None
    CORS_ALLOW_CREDENTIALS: bool = False
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]
    CORS_MAX_AGE: int = 600

    model_config = SettingsConfigDict(
        env_file=(
            str(Path(__file__).resolve().parents[2] / ".env"),
            str(Path(__file__).resolve().parents[3] / ".env"),
        ),
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            load_config_file,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )

    @classmethod
    def model_validate(cls, obj, **kwargs):
        if isinstance(obj, dict):
            obj = dict(obj)
            obj["CORS_ALLOW_ORIGINS"] = parse_csv(
                obj.get("CORS_ALLOW_ORIGINS"),
                obj.get("CORS_ALLOW_ORIGINS", cls().CORS_ALLOW_ORIGINS),
            )
            obj["CORS_ALLOW_METHODS"] = parse_csv(
                obj.get("CORS_ALLOW_METHODS"),
                obj.get("CORS_ALLOW_METHODS", cls().CORS_ALLOW_METHODS),
            )
            obj["CORS_ALLOW_HEADERS"] = parse_csv(
                obj.get("CORS_ALLOW_HEADERS"),
                obj.get("CORS_ALLOW_HEADERS", cls().CORS_ALLOW_HEADERS),
            )
        return super().model_validate(obj, **kwargs)


settings = Settings()
