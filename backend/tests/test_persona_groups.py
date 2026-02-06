def test_group_crud(client) -> None:
    headers = {"X-Tenant-Id": "tenant-a"}
    payload = {"name": "Security Reviewers", "description": "Security-focused"}

    response = client.post("/api/persona-groups", json=payload, headers=headers)
    assert response.status_code == 201
    group = response.json()
    assert group["name"] == "Security Reviewers"

    list_response = client.get("/api/persona-groups", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    group_id = group["id"]
    get_response = client.get(f"/api/persona-groups/{group_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == group_id

    patch_response = client.patch(
        f"/api/persona-groups/{group_id}",
        json={"description": "Security & compliance"},
        headers=headers,
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["description"] == "Security & compliance"

    delete_response = client.delete(f"/api/persona-groups/{group_id}", headers=headers)
    assert delete_response.status_code == 204

    get_missing = client.get(f"/api/persona-groups/{group_id}", headers=headers)
    assert get_missing.status_code == 404
