import pytest

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


def test_generate_completion_unsupported_provider_raises(monkeypatch) -> None:
    monkeypatch.setattr(llm_provider.settings, "LLM_PROVIDER", "unknown-provider")
    with pytest.raises(llm_provider.LLMProviderError) as exc:
        llm_provider.generate_completion("hello")
    assert "Unsupported LLM provider" in str(exc.value)


def test_generate_with_openai_wraps_provider_errors(monkeypatch) -> None:
    class _DummyOpenAIError(Exception):
        pass

    class _DummyClient:
        class responses:
            @staticmethod
            def create(**_kwargs):
                raise _DummyOpenAIError("provider down")

    monkeypatch.setattr(llm_provider, "OpenAIError", _DummyOpenAIError)
    monkeypatch.setattr(llm_provider, "get_openai_client", lambda: _DummyClient())

    with pytest.raises(llm_provider.LLMProviderError) as exc:
        llm_provider._generate_with_openai("prompt")
    assert "provider down" in str(exc.value)


def test_generate_with_bedrock_wraps_client_errors(monkeypatch) -> None:
    class _DummyClient:
        def converse(self, **_kwargs):
            raise RuntimeError("bedrock unavailable")

    class _DummySession:
        def client(self, *_args, **_kwargs):
            return _DummyClient()

        def get_credentials(self):
            return object()

    class _DummyBoto3:
        @staticmethod
        def Session(**_kwargs):
            return _DummySession()

    class _DummyBotoConfig:
        def __init__(self, **_kwargs):
            pass

    import builtins

    real_import = builtins.__import__

    def _fake_import(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: ANN001
        if name == "boto3":
            return _DummyBoto3
        if name == "botocore.config":
            return type("_BC", (), {"Config": _DummyBotoConfig})
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(llm_provider.settings, "BEDROCK_MODEL_ID", "model")
    monkeypatch.setattr(builtins, "__import__", _fake_import)

    with pytest.raises(llm_provider.LLMProviderError) as exc:
        llm_provider._generate_with_bedrock("prompt")
    assert "bedrock unavailable" in str(exc.value)
