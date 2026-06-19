import pytest
import requests

@pytest.mark.tier2
def test_spa_login_empty_payload(server_url):
    """POST to /api/login with empty username/password in JSON, asserting 400 Bad Request."""
    payloads = [
        {},
        {"username": ""},
        {"password": ""},
        {"username": "", "password": ""},
        {"username": "   ", "password": "   "},
    ]
    
    for payload in payloads:
        response = requests.post(f"{server_url}/api/login", json=payload)
        # Server should return 400 Bad Request or 401 Unauthorized for empty/missing credentials
        assert response.status_code in (400, 401)


@pytest.mark.tier2
def test_spa_static_traversal(server_url):
    """GET static assets using traversal paths (e.g. /static/../../conftest.py), asserting 400/403/404."""
    traversal_paths = [
        f"{server_url}/static/../../conftest.py",
        f"{server_url}/static/../auth.py",
        f"{server_url}/static/..%2f..%2fconftest.py",
        f"{server_url}/static/%2e%2e/%2e%2e/conftest.py",
    ]
    
    for path in traversal_paths:
        response = requests.get(path)
        assert response.status_code in (400, 403, 404)


@pytest.mark.tier2
def test_spa_me_malformed_cookie(server_url):
    """GET /api/me with malformed cookie header, asserting 401."""
    malformed_cookies = [
        "session=malformed_session_cookie_123",
        "session=",
        "session=..%2F..%2Fetc",
        "session=None",
    ]
    
    for cookie in malformed_cookies:
        headers = {"Cookie": cookie}
        response = requests.get(f"{server_url}/api/me", headers=headers)
        assert response.status_code == 401


@pytest.mark.tier2
def test_spa_collection_crud_invalid(server_url, spa_session):
    """POST/PUT to SPA collection endpoint with missing name/title or invalid color formats, asserting 400 Bad Request."""
    # 1. POST with missing fields
    invalid_create_payloads = [
        # Missing id
        {"type": "calendar", "title": "No ID", "color": "#ff0000"},
        # Missing type
        {"id": "col_no_type", "title": "No Type", "color": "#ff0000"},
        # Missing title
        {"id": "col_no_title", "type": "calendar", "color": "#ff0000"},
        # Invalid color format (not a hex code starting with #)
        {"id": "col_bad_color", "type": "calendar", "title": "Bad Color", "color": "red"},
        {"id": "col_bad_color2", "type": "calendar", "title": "Bad Color 2", "color": "123456"},
    ]
    
    for payload in invalid_create_payloads:
        response = spa_session.post(f"{server_url}/api/collections", json=payload)
        assert response.status_code == 400

    # 2. Create a valid collection to test PUT with invalid parameters
    valid_id = "valid_spa_col"
    spa_session.post(f"{server_url}/api/collections", json={
        "id": valid_id,
        "type": "calendar",
        "title": "Valid Init",
        "color": "#ffffff"
    })
    
    # 3. PUT with invalid fields
    invalid_update_payloads = [
        # Invalid color format
        {"title": "Updated Title", "color": "invalid_color"},
        {"title": "Updated Title", "color": "#12"},
        # Empty title
        {"title": "", "color": "#000000"},
    ]
    
    for payload in invalid_update_payloads:
        response = spa_session.put(f"{server_url}/api/collections/{valid_id}", json=payload)
        assert response.status_code == 400
        
    # Clean up
    spa_session.delete(f"{server_url}/api/collections/{valid_id}")


@pytest.mark.tier2
def test_spa_crud_nonexistent_collection(server_url, spa_session):
    """PUT/DELETE to non-existent collection IDs via UI API, asserting 404 Not Found."""
    non_existent_id = "nonexistent_col_999"
    
    # Try PUT
    update_payload = {"title": "Should Fail", "color": "#000000"}
    put_response = spa_session.put(f"{server_url}/api/collections/{non_existent_id}", json=update_payload)
    assert put_response.status_code == 404
    
    # Try DELETE
    delete_response = spa_session.delete(f"{server_url}/api/collections/{non_existent_id}")
    assert delete_response.status_code == 404
