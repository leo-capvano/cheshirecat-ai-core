from cat.auth import get_all_permissions


def test_get_available_permissions(client, admin_headers):

    # After routes are imported, all permission strings should be registered
    all_perms = get_all_permissions()

    assert isinstance(all_perms, set)
    # Core permissions should be registered
    assert "chat:edit" in all_perms
    assert "chat:read" in all_perms
    assert "plugins:list" in all_perms
    assert "uploads:write" in all_perms
    assert "settings:read" in all_perms
