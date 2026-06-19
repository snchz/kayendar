import pytest
import requests

@pytest.mark.tier1
def test_spa_serve_index(server_url):
    """Send a GET request to / and assert it serves HTML content."""
    response = requests.get(f"{server_url}/")
    assert response.status_code == 200
    assert "html" in response.headers.get("Content-Type", "").lower()


@pytest.mark.tier1
def test_spa_api_me_authenticated(server_url, spa_session, test_user):
    """Query /api/me with session cookie and verify user information is returned."""
    response = spa_session.get(f"{server_url}/api/me")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == test_user["username"]


@pytest.mark.tier1
def test_spa_api_me_unauthenticated(server_url):
    """Query /api/me without session cookie and assert 401 Unauthorized."""
    response = requests.get(f"{server_url}/api/me")
    assert response.status_code == 401


@pytest.mark.tier1
def test_spa_list_collections(server_url, spa_session):
    """Use spa_session to GET user collections and assert they are listed."""
    response = spa_session.get(f"{server_url}/api/collections")
    assert response.status_code == 200
    collections = response.json()
    assert isinstance(collections, list)


@pytest.mark.tier1
def test_spa_crud_collection(server_url, spa_session):
    """Use spa_session to create, update, and delete a user collection."""
    create_payload = {
        "display_name": "SPA Calendar",
        "type": "calendar",
        "color": "#0000ff",
    }
    create_response = spa_session.post(f"{server_url}/api/collections", json=create_payload)
    assert create_response.status_code == 201
    created = create_response.json()
    slug = created["slug"]

    update_response = spa_session.patch(
        f"{server_url}/api/collections/{slug}",
        json={"display_name": "Updated SPA Calendar", "color": "#ff00ff"},
    )
    assert update_response.status_code == 200
    updated_data = update_response.json()
    assert updated_data["display_name"] == "Updated SPA Calendar"
    assert updated_data["color"] == "#ff00ff"

    delete_response = spa_session.delete(f"{server_url}/api/collections/{slug}")
    assert delete_response.status_code == 200
