def test_list_personas_requires_tenant_header(client) -> None:
    response = client.get("/api/personas")
    assert response.status_code == 400


def test_persona_crud(client) -> None:
    headers = {"X-Tenant-Id": "tenant-a"}
    payload = {
        "name": "Skeptical Architect",
        "description": "Finds ambiguity and missing constraints",
        "system_prompt": "You are a skeptical architect.",
        "focus_areas": ["requirements", "risks"],
        "tone": "direct",
        "is_active": True,
        "group_id": None,
    }
    response = client.post("/api/personas", json=payload, headers=headers)
    assert response.status_code == 201
    persona = response.json()
    assert persona["name"] == "Skeptical Architect"
    assert "output_requirements" in persona
    assert "reference_notes" in persona
    assert "examples" in persona

    list_response = client.get("/api/personas", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    persona_id = persona["id"]
    get_response = client.get(f"/api/personas/{persona_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == persona_id

    patch_response = client.patch(
        f"/api/personas/{persona_id}",
        json={"tone": "precise"},
        headers=headers,
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["tone"] == "precise"

    delete_response = client.delete(f"/api/personas/{persona_id}", headers=headers)
    assert delete_response.status_code == 204

    get_missing = client.get(f"/api/personas/{persona_id}", headers=headers)
    assert get_missing.status_code == 404


def test_reset_default_personas(client) -> None:
    headers = {"X-Tenant-Id": "tenant-defaults"}
    resp = client.post("/api/personas/reset-defaults", headers=headers)
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload) >= 3
    assert any(item.get("is_default") is True for item in payload)


def test_revert_single_default_persona(client) -> None:
    headers = {"X-Tenant-Id": "tenant-default-single"}
    seeded = client.post("/api/personas/reset-defaults", headers=headers)
    assert seeded.status_code == 200
    default_persona = seeded.json()[0]

    updated = client.patch(
        f"/api/personas/{default_persona['id']}",
        json={"name": "Changed default", "tone": "custom"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Changed default"

    reverted = client.post(
        f"/api/personas/{default_persona['id']}/reset-default",
        headers=headers,
    )
    assert reverted.status_code == 200
    assert reverted.json()["name"] != "Changed default"
    assert reverted.json()["is_default"] is True
    assert reverted.json()["is_system_locked"] is True


def test_revert_default_rejects_custom_persona(client) -> None:
    headers = {"X-Tenant-Id": "tenant-default-reject"}
    created = client.post(
        "/api/personas",
        json={
            "name": "Custom",
            "description": "custom",
            "system_prompt": "custom",
            "focus_areas": [],
            "tone": "direct",
            "is_active": True,
            "group_id": None,
        },
        headers=headers,
    )
    assert created.status_code == 201
    persona_id = created.json()["id"]

    rejected = client.post(f"/api/personas/{persona_id}/reset-default", headers=headers)
    assert rejected.status_code == 400


def test_default_personas_persist_without_duplicates_on_relist(client) -> None:
    headers = {"X-Tenant-Id": "tenant-default-persist"}

    seeded = client.post("/api/personas/reset-defaults", headers=headers)
    assert seeded.status_code == 200

    first = client.get("/api/personas", headers=headers)
    assert first.status_code == 200
    first_payload = first.json()
    first_default_ids = {
        persona["id"]
        for persona in first_payload
        if persona.get("is_default") and persona.get("is_system_locked")
    }
    assert len(first_default_ids) >= 1

    second = client.get("/api/personas", headers=headers)
    assert second.status_code == 200
    second_payload = second.json()
    second_default_ids = {
        persona["id"]
        for persona in second_payload
        if persona.get("is_default") and persona.get("is_system_locked")
    }

    assert len(second_payload) == len(first_payload)
    assert second_default_ids == first_default_ids
