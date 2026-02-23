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
        "META_AGENT_NAME": settings.META_AGENT_NAME,
        "META_AGENT_DESCRIPTION": settings.META_AGENT_DESCRIPTION,
        "META_AGENT_SYSTEM_PROMPT": settings.META_AGENT_SYSTEM_PROMPT,
        "META_AGENT_FOCUS_AREAS": settings.META_AGENT_FOCUS_AREAS,
        "META_AGENT_TONE": settings.META_AGENT_TONE,
        "META_AGENT_REFERENCE_NOTES": settings.META_AGENT_REFERENCE_NOTES,
        "META_AGENT_OUTPUT_FORMAT": settings.META_AGENT_OUTPUT_FORMAT,
        "META_AGENT_OUTPUT_MAX_BULLETS": settings.META_AGENT_OUTPUT_MAX_BULLETS,
        "META_AGENT_OUTPUT_REQUIRE_QUOTE_EXCERPT": settings.META_AGENT_OUTPUT_REQUIRE_QUOTE_EXCERPT,
        "META_AGENT_OUTPUT_REQUIRE_ACTIONABLE": settings.META_AGENT_OUTPUT_REQUIRE_ACTIONABLE,
        "META_AGENT_OUTPUT_INCLUDE_SEVERITY": settings.META_AGENT_OUTPUT_INCLUDE_SEVERITY,
        "META_AGENT_EXAMPLES": settings.META_AGENT_EXAMPLES,
        "META_MAX_DIRECTIVES_PER_GROUP": settings.META_MAX_DIRECTIVES_PER_GROUP,
        "META_GLOBAL_DEDUPE_THRESHOLD": settings.META_GLOBAL_DEDUPE_THRESHOLD,
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
            "meta_agent_name": "Meta Reviewer",
            "meta_agent_description": "Consolidates reviewer comments.",
            "meta_agent_system_prompt": "Synthesize reviewer comments into direct actions.",
            "meta_agent_focus_areas": "dedupe,prioritization",
            "meta_agent_tone": "direct",
            "meta_agent_reference_notes": "Prefer concrete edits.",
            "meta_agent_output_format": "bullet_list",
            "meta_agent_output_max_bullets": 4,
            "meta_agent_output_require_quote_excerpt": False,
            "meta_agent_output_require_actionable": True,
            "meta_agent_output_include_severity": True,
            "meta_agent_examples": "Use active voice,Include owner",
            "meta_max_directives_per_group": 4,
            "meta_global_dedupe_threshold": 0.75,
            "openai_api_key": "sk-test",
        }
        put_resp = client.put("/api/settings", json=payload, headers=headers)
        assert put_resp.status_code == 200
        body = put_resp.json()
        assert body["llm_provider"] == "bedrock"
        assert body["openai_api_key_set"] is True
        assert body["meta_agent_name"] == "Meta Reviewer"
        assert body["meta_global_dedupe_threshold"] == 0.75
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
        settings.META_AGENT_NAME = original["META_AGENT_NAME"]
        settings.META_AGENT_DESCRIPTION = original["META_AGENT_DESCRIPTION"]
        settings.META_AGENT_SYSTEM_PROMPT = original["META_AGENT_SYSTEM_PROMPT"]
        settings.META_AGENT_FOCUS_AREAS = original["META_AGENT_FOCUS_AREAS"]
        settings.META_AGENT_TONE = original["META_AGENT_TONE"]
        settings.META_AGENT_REFERENCE_NOTES = original["META_AGENT_REFERENCE_NOTES"]
        settings.META_AGENT_OUTPUT_FORMAT = original["META_AGENT_OUTPUT_FORMAT"]
        settings.META_AGENT_OUTPUT_MAX_BULLETS = original["META_AGENT_OUTPUT_MAX_BULLETS"]
        settings.META_AGENT_OUTPUT_REQUIRE_QUOTE_EXCERPT = original[
            "META_AGENT_OUTPUT_REQUIRE_QUOTE_EXCERPT"
        ]
        settings.META_AGENT_OUTPUT_REQUIRE_ACTIONABLE = original[
            "META_AGENT_OUTPUT_REQUIRE_ACTIONABLE"
        ]
        settings.META_AGENT_OUTPUT_INCLUDE_SEVERITY = original[
            "META_AGENT_OUTPUT_INCLUDE_SEVERITY"
        ]
        settings.META_AGENT_EXAMPLES = original["META_AGENT_EXAMPLES"]
        settings.META_MAX_DIRECTIVES_PER_GROUP = original["META_MAX_DIRECTIVES_PER_GROUP"]
        settings.META_GLOBAL_DEDUPE_THRESHOLD = original["META_GLOBAL_DEDUPE_THRESHOLD"]
        settings.OPENAI_API_KEY = original["OPENAI_API_KEY"]
