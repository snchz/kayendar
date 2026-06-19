import os
import json
import pytest
from pathlib import Path

def get_data_dir() -> Path:
    data_dir_env = os.environ.get("KAYENDAR_DATA_DIR")
    if data_dir_env:
        return Path(data_dir_env)
    return Path(__file__).resolve().parent.parent.parent.parent / "data"


@pytest.mark.tier1
def test_user_json_hashing(test_user):
    """Verify that the generated user entry in users.json uses pbkdf2_sha256 hashing."""
    data_dir = get_data_dir()
    users_file = data_dir / "users.json"
    assert users_file.exists()
    
    with open(users_file, "r", encoding="utf-8") as f:
        users = json.load(f)
        
    username = test_user["username"]
    assert username in users
    user_entry = users[username]
    
    assert user_entry["algo"] == "pbkdf2_sha256"
    assert "salt" in user_entry
    assert "hash" in user_entry
    assert user_entry["iterations"] == 100000
    assert len(user_entry["salt"]) == 32  # 16 bytes hex-encoded
    assert len(user_entry["hash"]) == 64  # sha256 hex-encoded


@pytest.mark.tier1
def test_user_directories_created(server_url, test_user, dav_session):
    """Verify that calendar and contacts directories are created for a user upon first access."""
    # Perform first access to trigger directory creation if it wasn't already triggered
    response = dav_session.options(f"{server_url}/dav/")
    assert response.status_code == 200
    
    data_dir = get_data_dir()
    username = test_user["username"]
    
    calendar_dir = data_dir / "collections" / username
    contacts_dir = data_dir / "collections" / username
    
    assert calendar_dir.is_dir()
    assert contacts_dir.is_dir()


@pytest.mark.tier1
def test_file_structure_event(server_url, test_user, dav_session):
    """Verify that PUT calendar event creates a corresponding .ics file in the filesystem."""
    username = test_user["username"]
    
    # Ensure calendar collection exists
    dav_session.request("MKCALENDAR", f"{server_url}/dav/{username}/personal_cal/")
    
    ics_payload = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Kayendar//NONSGML v1.0//EN
BEGIN:VEVENT
UID:uid_event_storage@example.com
DTSTAMP:20260619T110000Z
DTSTART:20260619T120000Z
DTEND:20260619T130000Z
SUMMARY:Storage Event
END:VEVENT
END:VCALENDAR"""

    response = dav_session.put(
        f"{server_url}/dav/{username}/personal_cal/event1.ics",
        headers={"Content-Type": "text/calendar; charset=utf-8"},
        data=ics_payload
    )
    assert response.status_code in (201, 204)
    
    data_dir = get_data_dir()
    event_file = data_dir / "collections" / username / "personal_cal" / "event1.ics"
    assert event_file.is_file()
    
    with open(event_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert "BEGIN:VCALENDAR" in content
    assert "END:VCALENDAR" in content
    assert "Storage Event" in content


@pytest.mark.tier1
def test_file_structure_contact(server_url, test_user, dav_session):
    """Verify that PUT contact card creates a corresponding .vcf file on disk."""
    username = test_user["username"]
    
    # Ensure contacts collection exists
    dav_session.request("MKCOL", f"{server_url}/dav/{username}/friends/")
    
    vcf_payload = """BEGIN:VCARD
VERSION:3.0
FN:Jane Smith
N:Smith;Jane;;;
EMAIL;TYPE=INTERNET:jane.smith@example.com
END:VCARD"""

    response = dav_session.put(
        f"{server_url}/dav/{username}/friends/contact1.vcf",
        headers={"Content-Type": "text/vcard; charset=utf-8"},
        data=vcf_payload
    )
    assert response.status_code in (201, 204)
    
    data_dir = get_data_dir()
    contact_file = data_dir / "collections" / username / "friends" / "contact1.vcf"
    assert contact_file.is_file()
    
    with open(contact_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert "BEGIN:VCARD" in content
    assert "END:VCARD" in content
    assert "Jane Smith" in content


@pytest.mark.tier1
def test_data_isolation_dav(server_url, test_user, dav_session):
    """Verify that User A cannot read or access User B's calendars or contacts directories."""
    username_a = test_user["username"]
    
    # Create User B credentials manually
    username_b = f"{username_a}_userb"
    password_b = "password_userb"
    
    # Register user B
    import hashlib
    import shutil
    data_dir = get_data_dir()
    users_json_path = data_dir / "users.json"
    
    salt_bytes = os.urandom(16)
    salt_hex = salt_bytes.hex()
    hash_bytes = hashlib.pbkdf2_hmac(
        "sha256",
        password_b.encode("utf-8"),
        salt_bytes,
        100000
    )
    hash_hex = hash_bytes.hex()
    
    with open(users_json_path, "r", encoding="utf-8") as f:
        users = json.load(f)
    users[username_b] = {
        "salt": salt_hex,
        "hash": hash_hex,
        "iterations": 100000,
        "algo": "pbkdf2_sha256",
        "email": f"{username_b}@example.com"
    }
    with open(users_json_path, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4)
        
    try:
        # User B makes first access to ensure directories exist
        import requests
        session_b = requests.Session()
        session_b.auth = (username_b, password_b)
        response_b = session_b.options(f"{server_url}/dav/")
        assert response_b.status_code == 200
        
        # User B creates calendar and contacts collections
        mkcal_resp = session_b.request("MKCALENDAR", f"{server_url}/dav/{username_b}/personal_cal/")
        assert mkcal_resp.status_code == 201
        
        mkcol_resp = session_b.request("MKCOL", f"{server_url}/dav/{username_b}/friends/")
        assert mkcol_resp.status_code == 201
        
        # User A (via dav_session) tries to access User B's collections and should get 403 or 404
        cal_access_resp = dav_session.request("PROPFIND", f"{server_url}/dav/{username_b}/personal_cal/")
        assert cal_access_resp.status_code in (403, 404)
        
        contact_access_resp = dav_session.request("PROPFIND", f"{server_url}/dav/{username_b}/friends/")
        assert contact_access_resp.status_code in (403, 404)
        
    finally:
        # Cleanup User B record
        with open(users_json_path, "r", encoding="utf-8") as f:
            users = json.load(f)
        if username_b in users:
            del users[username_b]
        with open(users_json_path, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4)
            
        # Cleanup User B folders
        for folder in ["collections"]:
            user_folder = data_dir / folder / username_b
            if user_folder.exists():
                shutil.rmtree(user_folder)
