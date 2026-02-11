from app.reviews import llm_provider


def test_provider_health_openai_missing_key(monkeypatch) -> None:
    monkeypatch.setattr(llm_provider.settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(llm_provider.settings, "OPENAI_API_KEY", None)
    health = llm_provider.provider_health()
    assert health["provider"] == "openai"
    assert health["ok"] is False


def test_provider_health_openai_with_key(monkeypatch) -> None:
    monkeypatch.setattr(llm_provider.settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(llm_provider.settings, "OPENAI_API_KEY", "x-test")
    health = llm_provider.provider_health()
    assert health["provider"] == "openai"
    assert health["ok"] is True


def test_generate_completion_bedrock_dispatch(monkeypatch) -> None:
    monkeypatch.setattr(llm_provider.settings, "LLM_PROVIDER", "bedrock")
    monkeypatch.setattr(llm_provider, "_generate_with_bedrock", lambda prompt: f"ok:{prompt}")
    assert llm_provider.generate_completion("hello") == "ok:hello"
