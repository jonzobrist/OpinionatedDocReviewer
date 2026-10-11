"""Smoke-test Boto3/Botocore/urllib3 against a local HTTP endpoint, never AWS."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.reviews import llm_provider


def test_bedrock_converse_uses_real_sdk_and_http_transport(monkeypatch) -> None:
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append(
                {
                    "path": self.path,
                    "authorization": self.headers.get("Authorization", ""),
                    "body": json.loads(self.rfile.read(int(self.headers["Content-Length"]))),
                }
            )
            response = json.dumps(
                {
                    "output": {"message": {"role": "assistant", "content": [{"text": "review ok"}]}},
                    "stopReason": "end_turn",
                    "usage": {"inputTokens": 2, "outputTokens": 2, "totalTokens": 4},
                    "metrics": {"latencyMs": 1},
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # Explicit fake credentials ensure no profile or metadata credentials are
    # consulted. The service-specific SDK endpoint points only to this server.
    monkeypatch.setenv("AWS_ENDPOINT_URL_BEDROCK_RUNTIME", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    monkeypatch.setattr(llm_provider.settings, "LLM_PROVIDER", "bedrock")
    monkeypatch.setattr(llm_provider.settings, "BEDROCK_REGION", "us-east-1")
    monkeypatch.setattr(llm_provider.settings, "BEDROCK_MODEL_ID", "test-model")
    monkeypatch.setattr(llm_provider.settings, "BEDROCK_AWS_ACCESS_KEY_ID", "test-bedrock")
    monkeypatch.setattr(llm_provider.settings, "BEDROCK_AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setattr(llm_provider.settings, "BEDROCK_AWS_SESSION_TOKEN", None)
    try:
        assert llm_provider.provider_health()["ok"] is True
        assert llm_provider.generate_completion("Review this document") == "review ok"
        assert len(requests) == 1
        request = requests[0]
        assert request["path"] == "/model/test-model/converse"
        assert request["authorization"].startswith("AWS4-HMAC-SHA256 Credential=test-bedrock/")
        assert request["body"]["messages"] == [
            {"role": "user", "content": [{"text": "Review this document"}]}
        ]
        assert request["body"]["inferenceConfig"] == {
            "maxTokens": llm_provider.settings.OPENAI_MAX_TOKENS,
            "temperature": llm_provider.settings.OPENAI_TEMPERATURE,
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
