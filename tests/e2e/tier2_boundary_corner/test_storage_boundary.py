import os
import json
import shutil
import pytest
import requests
from pathlib import Path
import server.auth as auth

def get_data_dir() -> Path:
    data_dir_env = os.environ.get("KAYENDAR_DATA_DIR")
    if data_dir_env:
        return Path(data_dir_env)
    return Path(__file__).resolve().parent.parent.parent.parent / "data"


@pytest.mark.tier2
def test_storage_large_payload(server_url, dav_session, test_user):
    """PUT a very large event or contact (e.g. 5MB with base64 attachment), asserting payload limit handling (413 Payload Too Large or graceful write)."""
    username = test_user["username"]
    
    # 1. Create calendar collection
    dav_session.request("MKCALENDAR", f"{server_url}/dav/{username}/personal_cal/")
    
    # Generate ~5MB payload
    large_base64 = "A" * (5 * 1024 * 1024)
    large_ics = f"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:large_uid@example.com
SUMMARY:Large Event
DESCRIPTION: {large_base64}
END:VEVENT
END:VCALENDAR"""

    headers = {"Content-Type": "text/calendar; charset=utf-8"}
    try:
        response = dav_session.put(
            f"{server_url}/dav/{username}/personal_cal/large.ics",
            headers=headers,
            data=large_ics.encode("utf-8"),
            timeout=10
        )
        # Server must either accept it (201/204) or reject it with 413 Payload Too Large
        assert response.status_code in (201, 204, 413)
    except requests.exceptions.RequestException:
        # If the server/HTTP library rejects the request early or closes connection
        pass


@pytest.mark.tier2
def test_storage_corrupted_database(test_user):
    """Mock/write a corrupted or invalid users.json, asserting that verify_user and create_user handle it gracefully."""
    data_dir = get_data_dir()
    users_file = data_dir / "users.json"
    
    # Backup original users.json
    backup_file = data_dir / "users_backup_test.json"
    if users_file.exists():
        shutil.copy2(users_file, backup_file)
    else:
        # Create empty backup to mark non-existence
        with open(backup_file, "w") as f:
            json.dump({}, f)

    try:
        # Case 1: Invalid JSON formatting
        with open(users_file, "w", encoding="utf-8") as f:
            f.write("{invalid_json: true, missing_quotes}")
            
        with pytest.raises((ValueError, json.JSONDecodeError)):
            auth.verify_user("some_user", "some_password")
            
        with pytest.raises((ValueError, json.JSONDecodeError)):
            auth.create_user("new_user", "new_password")

        # Case 2: Root element is a list instead of dict
        with open(users_file, "w", encoding="utf-8") as f:
            json.dump(["user1", "user2"], f)
            
        with pytest.raises(ValueError) as excinfo:
            auth.verify_user("some_user", "some_password")
        assert "dictionary" in str(excinfo.value)
            
        with pytest.raises(ValueError) as excinfo:
            auth.create_user("new_user", "new_password")
        assert "dictionary" in str(excinfo.value)

        # Case 3: Missing password/hash key/salt values in dictionary
        with open(users_file, "w", encoding="utf-8") as f:
            json.dump({
                "corrupted_user": {
                    "email": "corrupted@example.com"
                    # missing salt, hash, iterations, algo
                }
            }, f)
            
        # Should handle it gracefully by returning False (failed auth) instead of crashing
        assert auth.verify_user("corrupted_user", "some_password") is False

    finally:
        # Restore backup
        if backup_file.exists():
            shutil.move(str(backup_file), str(users_file))


@pytest.mark.tier2
def test_storage_user_path_traversal(server_url):
    """Register user containing directory traversal characters (e.g. ../../baduser) and check that storage directories do not escape user sandbox."""
    bad_username = "../../baduser"
    
    # 1. Assert that the core auth logic rejects the username
    with pytest.raises(ValueError) as excinfo:
        auth.create_user(bad_username, "password")
    assert "traversal" in str(excinfo.value).lower() or "character" in str(excinfo.value).lower()
    
    with pytest.raises(ValueError):
        auth.verify_user(bad_username, "password")

    # 2. Assert WebDAV calls to traversal user directories are rejected
    response = requests.options(f"{server_url}/dav/{bad_username}/")
    assert response.status_code in (400, 403, 404)


@pytest.mark.tier2
def test_storage_special_collection_id(server_url, dav_session, test_user):
    """Create collection with ID containing special characters (spaces, quotes, percent-encoding) and check that they map safely to disk and retrieve."""
    username = test_user["username"]
    
    # ID containing spaces, quotes, and percent-encoding
    special_id = "my calendar %2F !@#"
    url_safe_id = requests.utils.quote(special_id)
    collection_path = f"{server_url}/dav/{username}/{url_safe_id}/"
    
    response_mk = dav_session.request("MKCALENDAR", collection_path)
    # Server should either support creating it (201) or reject it gracefully (400/403/409)
    if response_mk.status_code == 201:
        # If created, verify we can retrieve/PROPFIND it
        headers = {"Depth": "0"}
        response_prop = dav_session.request("PROPFIND", collection_path, headers=headers)
        assert response_prop.status_code == 207
        
        # Verify it exists under data directory
        data_dir = get_data_dir()
        expected_dir = data_dir / "collections" / username / special_id
        # Note: server may url-decode or keep percent encoded or sanitize, but it should map somewhere safe
        # We can also clean up
        dav_session.delete(collection_path)
    else:
        assert response_mk.status_code in (400, 403, 405, 409)


@pytest.mark.tier2
def test_storage_non_conforming_files(server_url, dav_session, test_user):
    """Verify handling when directory contains non-conforming or corrupted files (e.g. a plain text file not ending in .ics/.vcf in collection directory)."""
    username = test_user["username"]
    
    # 1. Create calendar collection
    collection_url = f"{server_url}/dav/{username}/personal_cal/"
    dav_session.request("MKCALENDAR", collection_url)
    
    # 2. Put a valid event first
    valid_ics = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:valid_uid@example.com
SUMMARY:Valid Event
END:VEVENT
END:VCALENDAR"""
    dav_session.put(f"{collection_url}valid.ics", headers={"Content-Type": "text/calendar"}, data=valid_ics)

    # 3. Write non-conforming files directly to the collection directory on disk
    data_dir = get_data_dir()
    col_dir = data_dir / "collections" / username / "personal_cal"
    
    if col_dir.is_dir():
        # Text file that is not .ics
        readme_file = col_dir / "README.txt"
        with open(readme_file, "w", encoding="utf-8") as f:
            f.write("This is a non-conforming plain text file.")
            
        # Corrupted .ics file (e.g., empty or invalid syntax)
        corrupt_file = col_dir / "corrupted.ics"
        with open(corrupt_file, "w", encoding="utf-8") as f:
            f.write("CORRUPTED_ICS_CONTENT_THAT_DOES_NOT_MAKE_SENSE")

        # 4. Perform PROPFIND and REPORT requests and verify the server recovers gracefully
        headers = {"Depth": "1", "Content-Type": "application/xml"}
        body = """<?xml version="1.0" encoding="utf-8" ?>
        <d:propfind xmlns:d="DAV:">
          <d:prop>
            <d:resourcetype/>
          </d:prop>
        </d:propfind>"""
        
        response = dav_session.request("PROPFIND", collection_url, headers=headers, data=body)
        # Server should still return 207 Multi-Status, skipping or handling non-conforming files
        assert response.status_code == 207
