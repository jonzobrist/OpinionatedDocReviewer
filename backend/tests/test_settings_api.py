from app.core.config import settings


def test_settings_get_and_update(client, monkeypatch) -> None:
    headers = {"X-Tenant-Id": "tenant-a"}
    monkeypatch.setattr("app.api.settings.save_config_values", lambda _: None)
    original = {
        "LLM_PROVIDER": settings.LLM_PROVIDER,
        "OPENAI_MODEL": settings.OPENAI_MODEL,
        "OPENAI_MAX_TOKENS": settings.OPENAI_MAX_TOKENS,
        "OPENAI_TEMPERATURE": settings.OPENAI_TEMPERATURE,
        "OPENAI_TIMEOUT_SECONDS": settings.OPENAI_TIMEOUT_SECONDS,
        "BEDROCK_MODEL_ID": settings.BEDROCK_MODEL_ID,
        "BEDROCK_REGION": settings.BEDROCK_REGION,
        "REVIEW_INLINE": settings.REVIEW_INLINE,
        "REDIS_URL": settings.REDIS_URL,
        "REVIEW_QUEUE_NAME": settings.REVIEW_QUEUE_NAME,
        "DOC_REPO_ENABLED": settings.DOC_REPO_ENABLED,
        "DOC_REPO_ROOT": settings.DOC_REPO_ROOT,
        "CORS_ALLOW_ORIGINS": settings.CORS_ALLOW_ORIGINS,
        "CORS_ALLOW_ORIGIN_REGEX": settings.CORS_ALLOW_ORIGIN_REGEX,
        "CORS_ALLOW_CREDENTIALS": settings.CORS_ALLOW_CREDENTIALS,
        "CORS_ALLOW_METHODS": settings.CORS_ALLOW_METHODS,
        "CORS_ALLOW_HEADERS": settings.CORS_ALLOW_HEADERS,
        "CORS_MAX_AGE": settings.CORS_MAX_AGE,
        "OPENAI_API_KEY": settings.OPENAI_API_KEY,
    }
    try:
        get_resp = client.get("/api/settings", headers=headers)
        assert get_resp.status_code == 200
        assert "llm_provider" in get_resp.json()

        payload = {
            "llm_provider": "bedrock",
            "openai_model": "gpt-4o-mini",
            "openai_max_tokens": 512,
            "openai_temperature": 0.1,
            "openai_timeout_seconds": 20,
            "bedrock_model_id": "anthropic.claude-3-5-haiku-20241022-v1:0",
            "bedrock_region": "us-east-1",
            "review_inline": False,
            "redis_url": "redis://localhost:6379/0",
            "review_queue_name": "review-jobs",
            "doc_repo_enabled": True,
            "doc_repo_root": ".run/doc-repos",
            "cors_allow_origins": "http://localhost:3000,https://opinion.zlyxy.me",
            "cors_allow_origin_regex": "",
            "cors_allow_credentials": False,
            "cors_allow_methods": "*",
            "cors_allow_headers": "*",
            "cors_max_age": 600,
            "openai_api_key": "sk-test",
        }
        put_resp = client.put("/api/settings", json=payload, headers=headers)
        assert put_resp.status_code == 200
        body = put_resp.json()
        assert body["llm_provider"] == "bedrock"
        assert body["openai_api_key_set"] is True
    finally:
        settings.LLM_PROVIDER = original["LLM_PROVIDER"]
        settings.OPENAI_MODEL = original["OPENAI_MODEL"]
        settings.OPENAI_MAX_TOKENS = original["OPENAI_MAX_TOKENS"]
        settings.OPENAI_TEMPERATURE = original["OPENAI_TEMPERATURE"]
        settings.OPENAI_TIMEOUT_SECONDS = original["OPENAI_TIMEOUT_SECONDS"]
        settings.BEDROCK_MODEL_ID = original["BEDROCK_MODEL_ID"]
        settings.BEDROCK_REGION = original["BEDROCK_REGION"]
        settings.REVIEW_INLINE = original["REVIEW_INLINE"]
        settings.REDIS_URL = original["REDIS_URL"]
        settings.REVIEW_QUEUE_NAME = original["REVIEW_QUEUE_NAME"]
        settings.DOC_REPO_ENABLED = original["DOC_REPO_ENABLED"]
        settings.DOC_REPO_ROOT = original["DOC_REPO_ROOT"]
        settings.CORS_ALLOW_ORIGINS = original["CORS_ALLOW_ORIGINS"]
        settings.CORS_ALLOW_ORIGIN_REGEX = original["CORS_ALLOW_ORIGIN_REGEX"]
        settings.CORS_ALLOW_CREDENTIALS = original["CORS_ALLOW_CREDENTIALS"]
        settings.CORS_ALLOW_METHODS = original["CORS_ALLOW_METHODS"]
        settings.CORS_ALLOW_HEADERS = original["CORS_ALLOW_HEADERS"]
        settings.CORS_MAX_AGE = original["CORS_MAX_AGE"]
        settings.OPENAI_API_KEY = original["OPENAI_API_KEY"]
