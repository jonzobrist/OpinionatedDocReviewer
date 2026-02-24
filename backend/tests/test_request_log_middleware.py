def test_request_log_includes_forwarded_headers(client, caplog) -> None:
    headers = {
        "X-Tenant-Id": "tenant-log",
        "X-Forwarded-For": "203.0.113.10, 10.0.0.1",
        "X-Real-IP": "203.0.113.10",
    }
    caplog.set_level("INFO", logger="app.request")

    response = client.get("/api/status", headers=headers)
    assert response.status_code == 200

    messages = [record.getMessage() for record in caplog.records if record.name == "app.request"]
    assert any('xff="203.0.113.10, 10.0.0.1"' in message for message in messages)
    assert any('xri="203.0.113.10"' in message for message in messages)
