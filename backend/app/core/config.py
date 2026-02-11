from pathlib import Path
import os
import tomllib
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


def load_config_file() -> dict:
    config_path = get_config_path()
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "rb") as handle:
            return tomllib.load(handle)
    except Exception:
        return {}


def get_config_path() -> str:
    config_path = os.getenv("ODR_CONFIG_PATH")
    if config_path:
        return config_path
    return str(Path(__file__).resolve().parents[2] / "config.toml")


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return '""'
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def save_config_values(values: dict[str, Any]) -> None:
    existing = load_config_file()
    for key, value in values.items():
        existing[key] = value
    path = Path(get_config_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key} = {_toml_value(existing[key])}" for key in sorted(existing.keys())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_csv(value: str | list[str] | None, default: list[str]) -> list[str]:
    if value is None:
        return default
    if isinstance(value, list):
        return [item for item in (item.strip() for item in value) if item]
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
    LLM_PROVIDER: str = "openai"
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 700
    OPENAI_MAX_INPUT_CHARS: int = 12000
    OPENAI_TEMPERATURE: float = 0.2
    OPENAI_TIMEOUT_SECONDS: int = 30
    BEDROCK_MODEL_ID: str = "anthropic.claude-3-5-haiku-20241022-v1:0"
    BEDROCK_REGION: str = "us-east-1"
    BEDROCK_AWS_ACCESS_KEY_ID: str | None = None
    BEDROCK_AWS_SECRET_ACCESS_KEY: str | None = None
    BEDROCK_AWS_SESSION_TOKEN: str | None = None
    REVIEW_INLINE: bool = False
    DOC_REPO_ROOT: str = ".run/doc-repos"
    DOC_REPO_ENABLED: bool = True
    CORS_ALLOW_ORIGINS: str = (
        "http://localhost:3000,http://127.0.0.1:3000,https://opinion.zlyxy.me"
    )
    CORS_ALLOW_ORIGIN_REGEX: str | None = None
    CORS_ALLOW_CREDENTIALS: bool = False
    CORS_ALLOW_METHODS: str = "*"
    CORS_ALLOW_HEADERS: str = "*"
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
        # Precedence: runtime args > exported env vars > .env files > config.toml > file secrets.
        # This keeps shell/env overrides reliable while still allowing persisted defaults in config.toml.
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            load_config_file,
            file_secret_settings,
        )

    @property
    def cors_allow_origins_list(self) -> list[str]:
        return parse_csv(
            self.CORS_ALLOW_ORIGINS,
            [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "https://opinion.zlyxy.me",
            ],
        )

    @property
    def cors_allow_methods_list(self) -> list[str]:
        return parse_csv(self.CORS_ALLOW_METHODS, ["*"])

    @property
    def cors_allow_headers_list(self) -> list[str]:
        return parse_csv(self.CORS_ALLOW_HEADERS, ["*"])


settings = Settings()
