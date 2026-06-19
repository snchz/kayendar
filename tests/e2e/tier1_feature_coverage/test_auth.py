import pytest
import requests

@pytest.mark.tier1
def test_basic_auth_valid(server_url, test_user):
    """Send a request (OPTIONS) to /dav/ with valid HTTP Basic credentials and assert 200 OK."""
    response = requests.options(
        f"{server_url}/dav/",
        auth=(test_user["username"], test_user["password"])
    )
    assert response.status_code == 200


@pytest.mark.tier1
def test_basic_auth_invalid(server_url):
    """Send a request to /dav/ with invalid credentials and assert 401 Unauthorized."""
    response = requests.options(
        f"{server_url}/dav/",
        auth=("non_existent_user_abc123", "wrong_password_xyz")
    )
    assert response.status_code == 401


@pytest.mark.tier1
def test_web_auth_login_valid(server_url, test_user):
    """Send a POST request to /api/login with valid JSON and assert 200 OK and session cookie."""
    session = requests.Session()
    response = session.post(
        f"{server_url}/api/login",
        json={"username": test_user["username"], "password": test_user["password"]}
    )
    assert response.status_code == 200
    
    # Assert session cookie is returned. Typically a cookie name like 'session' or similar.
    # We check that the session has at least one cookie set.
    assert len(session.cookies) > 0


@pytest.mark.tier1
def test_web_auth_login_invalid(server_url):
    """Send a POST request to /api/login with invalid credentials and assert 400 or 401."""
    response = requests.post(
        f"{server_url}/api/login",
        json={"username": "bad_user", "password": "bad_password"}
    )
    assert response.status_code in (400, 401)


@pytest.mark.tier1
def test_web_auth_logout(server_url, test_user):
    """Send a POST request to /api/logout using the session cookie, and assert 200 OK."""
    session = requests.Session()
    login_response = session.post(
        f"{server_url}/api/login",
        json={"username": test_user["username"], "password": test_user["password"]}
    )
    assert login_response.status_code == 200
    assert len(session.cookies) > 0
    
    logout_response = session.post(f"{server_url}/api/logout")
    assert logout_response.status_code == 200
    
    # Assert cookie is invalidated or cleared, or that subsequent auth'd requests fail.
    # Some servers clear the cookie immediately, others expire it.
    # We can check if trying to access me endpoint fails, or if cookies list is cleared/expired.
    me_response = session.get(f"{server_url}/api/me")
    assert me_response.status_code == 401
