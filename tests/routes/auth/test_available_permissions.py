
from cat.auth import get_full_permissions

def test_get_available_permissions(client, admin_headers):

    response = client.get(
        "/auth/available-permissions",
        headers=admin_headers
    )
    assert response.status_code == 200
    data = response.json()
    
    assert isinstance(data, dict)
    assert data == get_full_permissions()