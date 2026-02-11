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
        settings.OPENAI_API_KEY = original["OPENAI_API_KEY"]
