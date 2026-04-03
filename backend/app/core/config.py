import os
from pathlib import Path
import tomllib
from typing import Any
from urllib.parse import urlsplit

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


def normalize_origin(value: str) -> str:
    origin = (value or "").strip()
    if not origin or origin == "*":
        return origin
    origin = origin.rstrip("/")
    parsed = urlsplit(origin)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"

    # Accept hostname[:port] entries and default to https in non-local deployments.
    if origin.startswith(("localhost", "127.", "[::1]")):
        return f"http://{origin}"
    return f"https://{origin}"


class Settings(BaseSettings):
    APP_NAME: str = "OpinionatedDocReviewer API"
    APP_VERSION: str = "0.1.0"
    API_PREFIX: str = "/api"
    DATABASE_URL: str = f"sqlite:///{(Path(__file__).resolve().parents[3] / '.run' / 'app.db')}"
    PORT: int = 8006
    REDIS_URL: str = "redis://localhost:6379/0"
    REVIEW_QUEUE_NAME: str = "review-jobs"
    LLM_PROVIDER: str = "openai"
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 700
    OPENAI_MAX_INPUT_CHARS: int = 12000
    DOC_MAX_CHARS: int = 500000
    COMMENT_MAX_CHARS: int = 4000
    OPENAI_TEMPERATURE: float = 0.2
    OPENAI_TIMEOUT_SECONDS: int = 30
    REVIEW_JOB_TIMEOUT_SECONDS: int = 1800  # wall-clock RQ job timeout (default 30min for slow local LLMs)
    LLAMACPP_BASE_URL: str = "http://100.89.116.109:8080/v1"
    LLAMACPP_MODEL: str = "ggml-org/gemma-4-26B-A4B-it-GGUF:Q4_K_M"
    LLAMACPP_API_KEY: str = "no-key"
    LLAMACPP_MAX_TOKENS: int = 2048  # thinking models need headroom for reasoning trace
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
    CORS_ALLOW_METHODS: str = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    CORS_ALLOW_HEADERS: str = "Authorization,Content-Type,X-Tenant-Id,X-User-Email,X-User-Id"
    CORS_MAX_AGE: int = 600
    CSRF_ENFORCE_ORIGIN: bool = True
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_MAX_REQUESTS: int = 180
    AUTH_MODE: str = "oidc"
    DEFAULT_TENANT_ID: str = "local-dev"
    OIDC_ISSUER_URL: str | None = None
    OIDC_JWKS_URL: str | None = None
    OIDC_AUDIENCE: str | None = None
    OIDC_ALGORITHMS: str = "RS256"
    OIDC_TENANT_CLAIM: str = "tid"
    OIDC_EMAIL_CLAIM: str = "email"
    OIDC_NAME_CLAIM: str = "name"
    OIDC_ROLES_CLAIM: str = "roles"
    OIDC_ADMIN_ROLE: str = "admin"
    OIDC_ALLOW_LOCAL_HEADER_FALLBACK: bool = True
    LOCAL_AUTH_JWT_SECRET: str = "change-me-local-auth-secret"
    LOCAL_AUTH_JWT_ALGORITHM: str = "HS256"
    LOCAL_AUTH_ACCESS_TOKEN_TTL_MINUTES: int = 720
    AUTH_EMAIL_TOKEN_TTL_MINUTES: int = 30
    AUTH_PASSWORD_RESET_TTL_MINUTES: int = 30
    AUTH_MFA_CODE_TTL_MINUTES: int = 10
    AUTH_MFA_MAX_ATTEMPTS: int = 5
    AUTH_DEV_ECHO_CODES: bool = False
    ALLOWED_HOSTS: str = "*"
    TRUST_PROXY_HEADERS: bool = False
    PROXY_TRUSTED_IPS: str = "127.0.0.1"
    META_AUTO_SYNTHESIS_ENABLED: bool = True
    META_AGENT_NAME: str = "Meta Reviewer"
    META_AGENT_DESCRIPTION: str = "Synthesizes reviewer comments into ranked directives."
    META_AGENT_SYSTEM_PROMPT: str = (
        "Synthesize reviewer comments into concise, actionable directives for document improvement."
    )
    META_AGENT_FOCUS_AREAS: str = (
        "deduplication,conflict resolution,actionability,prioritization,risk surfacing"
    )
    META_AGENT_TONE: str = "decisive, practical"
    META_AGENT_REFERENCE_NOTES: str | None = None
    META_AGENT_OUTPUT_FORMAT: str = "bullet_list"
    META_AGENT_OUTPUT_MAX_BULLETS: int = 5
    META_AGENT_OUTPUT_REQUIRE_QUOTE_EXCERPT: bool = False
    META_AGENT_OUTPUT_REQUIRE_ACTIONABLE: bool = True
    META_AGENT_OUTPUT_INCLUDE_SEVERITY: bool = True
    META_AGENT_EXAMPLES: str = ""
    META_MAX_DIRECTIVES_PER_GROUP: int = 5
    META_GLOBAL_DEDUPE_THRESHOLD: float = 0.72

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
        return [
            normalize_origin(item)
            for item in parse_csv(
                self.CORS_ALLOW_ORIGINS,
                [
                    "http://localhost:3000",
                    "http://127.0.0.1:3000",
                    "https://opinion.zlyxy.me",
                ],
            )
        ]

    @property
    def cors_allow_methods_list(self) -> list[str]:
        return parse_csv(self.CORS_ALLOW_METHODS, ["*"])

    @property
    def cors_allow_headers_list(self) -> list[str]:
        return parse_csv(self.CORS_ALLOW_HEADERS, ["*"])

    @property
    def allowed_hosts_list(self) -> list[str]:
        return parse_csv(self.ALLOWED_HOSTS, ["*"])

    @property
    def proxy_trusted_ips_list(self) -> list[str]:
        return parse_csv(self.PROXY_TRUSTED_IPS, ["127.0.0.1"])

    @property
    def meta_agent_focus_areas_list(self) -> list[str]:
        return parse_csv(
            self.META_AGENT_FOCUS_AREAS,
            ["deduplication", "conflict resolution", "actionability", "prioritization"],
        )

    @property
    def meta_agent_examples_list(self) -> list[str]:
        return parse_csv(self.META_AGENT_EXAMPLES, [])


settings = Settings()
