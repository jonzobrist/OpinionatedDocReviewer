def test_persona_export_and_import_roundtrip(client) -> None:
    headers = {"X-Tenant-Id": "tenant-portable"}
    create_resp = client.post(
        "/api/personas",
        json={
            "name": "Portable Agent",
            "description": "portable",
            "system_prompt": "portable prompt",
            "focus_areas": ["clarity"],
            "tone": "direct",
            "is_active": True,
            "group_id": None,
        },
        headers=headers,
    )
    assert create_resp.status_code == 201

    export_resp = client.get("/api/personas/bundle/export", headers=headers)
    assert export_resp.status_code == 200
    bundle = export_resp.json()
    assert bundle["schema_version"] == "v1"
    assert len(bundle["personas"]) >= 1

    import_resp = client.post(
        "/api/personas/bundle/import",
        json={
            "schema_version": "v1",
            "conflict_policy": "rename",
            "dry_run": False,
            "personas": bundle["personas"],
        },
        headers=headers,
    )
    assert import_resp.status_code == 200
    body = import_resp.json()
    assert body["renamed"] >= 1


def test_persona_import_dry_run(client) -> None:
    headers = {"X-Tenant-Id": "tenant-portable-dryrun"}
    payload = {
        "schema_version": "v1",
        "conflict_policy": "skip",
        "dry_run": True,
        "personas": [
            {
                "name": "Dry Run Agent",
                "description": None,
                "system_prompt": "prompt",
                "focus_areas": [],
                "tone": None,
                "reference_notes": None,
                "output_requirements": {
                    "format": "bullet_list",
                    "max_bullets": 4,
                    "require_quote_excerpt": True,
                    "require_actionable": True,
                    "include_severity": False,
                },
                "examples": [],
                "sort_order": 100,
                "color_theme": None,
                "is_active": True,
                "group_name": None,
            }
        ],
    }
    dry = client.post("/api/personas/bundle/import", json=payload, headers=headers)
    assert dry.status_code == 200
    assert dry.json()["created"] == 1
    all_resp = client.get("/api/personas", headers=headers)
    assert all_resp.status_code == 200
    assert len(all_resp.json()) == 0
