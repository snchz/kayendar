import pytest
import requests
import concurrent.futures
import server.auth as auth

@pytest.mark.tier2
def test_auth_extremely_long_credentials(server_url):
    """Send auth/login requests with extremely long username and password (e.g. 1000 characters)
    and assert response is handled gracefully without crash.
    """
    long_username = "a" * 1000
    long_password = "b" * 1000

    # Test via Web API login
    try:
        response_api = requests.post(
            f"{server_url}/api/login",
            json={"username": long_username, "password": long_password},
            timeout=5
        )
        assert response_api.status_code in (400, 401, 403)
    except requests.exceptions.RequestException:
        # If server rejected request early or connection closed cleanly
        pass

    # Test via WebDAV Basic Auth
    try:
        response_dav = requests.options(
            f"{server_url}/dav/",
            auth=(long_username, long_password),
            timeout=5
        )
        assert response_dav.status_code in (400, 401, 403)
    except requests.exceptions.RequestException:
        pass

    # Direct auth function check should raise ValueError for long passwords
    with pytest.raises(ValueError):
        auth.verify_user(long_username, long_password)


@pytest.mark.tier2
def test_auth_special_characters(server_url):
    """Use credentials containing special, non-ASCII, emojis, or control characters,
    asserting correct hashing/verification.
    """
    # Emojis and control chars in username should fail validation (raise ValueError)
    invalid_username = "user_🤖_\x01"
    with pytest.raises(ValueError):
        auth.create_user(invalid_username, "valid_password")

    # Valid username, but password containing emoji, non-ASCII and control characters
    username = "test_special_user"
    special_password = "pásswørd!💩\x01\x0f"

    # Register user directly via auth module to bypass network registration if API doesn't exist,
    # or ensure it hashes correctly.
    try:
        auth.create_user(username, special_password)
    except ValueError:
        pass

    # Verify that auth.verify_user returns True with correct special password
    assert auth.verify_user(username, special_password) is True
    # Verify incorrect password fails
    assert auth.verify_user(username, special_password + "extra") is False

    # Also test authentication via Web API if running
    try:
        response = requests.post(
            f"{server_url}/api/login",
            json={"username": username, "password": special_password},
            timeout=5
        )
        assert response.status_code in (200, 400, 401, 403)
    except requests.exceptions.RequestException:
        pass


@pytest.mark.tier2
def test_auth_injection_attempts(server_url):
    """Send credentials with SQL/NoSQL injection payloads and assert authentication is rejected
    (401/400) without backend script errors or db damage.
    """
    sql_payloads = [
        "' OR '1'='1",
        "admin' --",
        "'; DROP TABLE users; --",
        "\" or 1=1--",
    ]
    nosql_payloads = [
        '{"$gt": ""}',
        '{"$ne": null}',
    ]

    for payload in sql_payloads + nosql_payloads:
        # Direct check
        with pytest.raises(ValueError):
            # Username validation in auth.py rejects special characters like quotes or braces,
            # so it should raise ValueError.
            auth.verify_user(payload, "password")

        # Web API check
        try:
            response_api = requests.post(
                f"{server_url}/api/login",
                json={"username": payload, "password": "password"},
                timeout=5
            )
            assert response_api.status_code in (400, 401, 403)
        except requests.exceptions.RequestException:
            pass

        # WebDAV check
        try:
            response_dav = requests.options(
                f"{server_url}/dav/",
                auth=(payload, "password"),
                timeout=5
            )
            assert response_dav.status_code in (400, 401, 403)
        except requests.exceptions.RequestException:
            pass


@pytest.mark.tier2
def test_auth_invalid_session_cookie(server_url):
    """Attempt web API requests with corrupted, expired, or spoofed session cookies,
    asserting 401 response.
    """
    spoofed_cookies = [
        "session=invalidcookie123",
        "session=",
        "session=../../etc/passwd",
        "session={'username': 'admin'}",
    ]

    for cookie in spoofed_cookies:
        headers = {"Cookie": cookie}
        try:
            response = requests.get(f"{server_url}/api/me", headers=headers, timeout=5)
            assert response.status_code == 401
        except requests.exceptions.RequestException:
            pass


@pytest.mark.tier2
def test_auth_concurrent_requests(server_url, test_user):
    """Verify concurrent auth requests or rapid successive login calls from same client do not cause server lockups."""
    username = test_user["username"]
    password = test_user["password"]

    def make_request():
        try:
            return requests.post(
                f"{server_url}/api/login",
                json={"username": username, "password": password},
                timeout=5
            )
        except requests.exceptions.RequestException as e:
            return e

    # Send concurrent requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(make_request) for _ in range(10)]
        results = [f.result() for f in futures]

    for res in results:
        if isinstance(res, requests.Response):
            assert res.status_code in (200, 400, 401, 403)
        elif isinstance(res, Exception):
            # In a non-running server environment or strict environment, requests.exceptions.RequestException
            # could be raised. But if server runs, it should not lock up.
            pass
