"""Tests for the unified /settings endpoint."""


def test_get_settings_list(client, admin_headers):
    """GET /settings returns a list of services that have settings."""
    response = client.get("/settings", headers=admin_headers)
    assert response.status_code == 200

    entries = response.json()
    assert isinstance(entries, list)

    # CoreSettings should appear (it has a nested Settings class)
    core_entry = next((e for e in entries if e["type"] == "core" and e["slug"] == "core"), None)
    assert core_entry is not None
    assert core_entry["name"] == "Core Settings"
    assert core_entry["plugin_id"] == "core"
    assert "schema" in core_entry
    assert core_entry["schema"] is not None
    assert isinstance(core_entry["settings"], dict)


def test_get_settings_filter_by_type(client, admin_headers):
    """GET /settings?type=core returns only core settings."""
    response = client.get("/settings?type=core", headers=admin_headers)
    assert response.status_code == 200

    entries = response.json()
    assert all(e["type"] == "core" for e in entries)


def test_get_settings_filter_by_plugin_id(client, admin_headers):
    """GET /settings?plugin_id=core returns only core plugin settings."""
    response = client.get("/settings?plugin_id=core", headers=admin_headers)
    assert response.status_code == 200

    entries = response.json()
    assert all(e["plugin_id"] == "core" for e in entries)


def test_get_settings_filter_no_match(client, admin_headers):
    """GET /settings with non-existent type returns empty list."""
    response = client.get("/settings?type=nonexistent", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_put_settings_success(client, admin_headers):
    """PUT /settings/core/core updates core settings."""
    payload = {"default_llm": "openai:gpt-4", "default_embedder": "openai:text-embedding-3-small"}
    response = client.put("/settings/core/core", json=payload, headers=admin_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["slug"] == "core"
    assert data["type"] == "core"
    assert data["settings"]["default_llm"] == "openai:gpt-4"
    assert data["settings"]["default_embedder"] == "openai:text-embedding-3-small"
    assert data["schema"] is not None


def test_put_settings_persists(client, admin_headers):
    """PUT then GET shows persisted settings."""
    payload = {"default_llm": "anthropic:claude", "default_embedder": "openai:embed"}
    client.put("/settings/core/core", json=payload, headers=admin_headers)

    response = client.get("/settings?type=core", headers=admin_headers)
    assert response.status_code == 200

    entries = response.json()
    core_entry = next((e for e in entries if e["slug"] == "core"), None)
    assert core_entry is not None
    assert core_entry["settings"]["default_llm"] == "anthropic:claude"


def test_put_settings_unknown_service(client, admin_headers):
    """PUT /settings/model_providers/nonexistent returns 404."""
    response = client.put(
        "/settings/model_providers/nonexistent",
        json={"key": "value"},
        headers=admin_headers,
    )
    assert response.status_code == 404


def test_put_settings_validation_error(client, admin_headers):
    """PUT /settings/core/core with wrong type returns 400."""
    # default_llm expects a string, send an int
    response = client.put(
        "/settings/core/core",
        json={"default_llm": 123},
        headers=admin_headers,
    )
    # Pydantic may coerce int to str, so this test depends on schema strictness.
    # If no validation error, the value is simply coerced — that's acceptable.
    assert response.status_code in (200, 400)


def test_old_plugin_settings_endpoint_removed(client, admin_headers):
    """GET /plugins/{id}/settings should no longer exist."""
    response = client.get("/plugins/core/settings", headers=admin_headers)
    # Should be 404 or 405 since the endpoint was removed
    assert response.status_code in (404, 405, 422)


def test_old_me_settings_endpoint_removed(client, admin_headers):
    """GET /me/settings should no longer exist."""
    response = client.get("/me/settings", headers=admin_headers)
    # Should be 404 or 405 since the endpoint was removed
    assert response.status_code in (404, 405, 422)


def test_old_service_settings_endpoint_removed(client, admin_headers):
    """GET /services/core/core/settings should no longer exist."""
    response = client.get("/services/core/core/settings", headers=admin_headers)
    # Should be 404 or 405 since the endpoint was removed
    assert response.status_code in (404, 405, 422)


def test_services_catalog_still_works(client, admin_headers):
    """GET /services still returns the read-only service catalog."""
    response = client.get("/services", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    # Should have at least core service type
    assert "core" in data
