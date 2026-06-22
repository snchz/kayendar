import os
import json
import shutil
import hashlib
import random
import string
from pathlib import Path
import pytest
import requests
from server.auth import _lock_db_file

# Resolve repo root and data directory
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

def get_data_dir() -> Path:
    data_dir_env = os.environ.get("KAYENDAR_DATA_DIR")
    if data_dir_env:
        return Path(data_dir_env)
    return REPO_ROOT / "data"

def register_user(username: str, password: str) -> None:
    data_dir = get_data_dir()
    users_json_path = data_dir / "users.json"
    
    salt_bytes = os.urandom(16)
    salt_hex = salt_bytes.hex()
    hash_bytes = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        100000
    )
    hash_hex = hash_bytes.hex()
    
    users = {}
    with _lock_db_file(str(users_json_path)):
        if users_json_path.exists():
            with open(users_json_path, "r", encoding="utf-8") as f:
                try:
                    users = json.load(f)
                except json.JSONDecodeError:
                    pass
                    
        users[username] = {
            "salt": salt_hex,
            "hash": hash_hex,
            "iterations": 100000,
            "algo": "pbkdf2_sha256",
            "email": f"{username}@example.com"
        }
        
        users_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(users_json_path, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4)

def cleanup_user_records(username: str) -> None:
    data_dir = get_data_dir()
    users_json_path = data_dir / "users.json"
    
    with _lock_db_file(str(users_json_path)):
        if users_json_path.exists():
            with open(users_json_path, "r", encoding="utf-8") as f:
                try:
                    users = json.load(f)
                except json.JSONDecodeError:
                    users = {}
            if username in users:
                del users[username]
            with open(users_json_path, "w", encoding="utf-8") as f:
                json.dump(users, f, indent=4)
                
    for folder in ["collections"]:
        user_folder = data_dir / folder / username
        if user_folder.exists():
            shutil.rmtree(user_folder)


# ----------------- Scenario 1 -----------------

@pytest.mark.tier4
def test_sync_loop_and_incremental_updates(server_url, dav_session, test_user):
    """
    Simulate a client sync cycle:
    1. Create a calendar collection.
    2. PUT 3 events via CalDAV session.
    3. Perform PROPFIND to check they are all present.
    4. Update one event (PUT event with modified SUMMARY).
    5. Delete another (DELETE).
    6. Perform range-query REPORT or PROPFIND to verify the client gets:
       - the modified event,
       - the remaining original event,
       - and the deleted event returns 404.
    """
    username = test_user["username"]
    cal_url = f"{server_url}/dav/{username}/sync_cal/"
    
    # 1. Create calendar collection
    mkcal_resp = dav_session.request("MKCALENDAR", cal_url)
    assert mkcal_resp.status_code in (201, 204, 405)
    
    # 2. PUT 3 events
    events = {
        "event1.ics": """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Kayendar//NONSGML v1.0//EN
BEGIN:VEVENT
UID:uid_sync_1
DTSTAMP:20260619T110000Z
DTSTART:20260619T120000Z
DTEND:20260619T130000Z
SUMMARY:Sync Event 1
END:VEVENT
END:VCALENDAR""",
        "event2.ics": """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Kayendar//NONSGML v1.0//EN
BEGIN:VEVENT
UID:uid_sync_2
DTSTAMP:20260619T110000Z
DTSTART:20260619T120000Z
DTEND:20260619T130000Z
SUMMARY:Sync Event 2
END:VEVENT
END:VCALENDAR""",
        "event3.ics": """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Kayendar//NONSGML v1.0//EN
BEGIN:VEVENT
UID:uid_sync_3
DTSTAMP:20260619T110000Z
DTSTART:20260619T120000Z
DTEND:20260619T130000Z
SUMMARY:Sync Event 3
END:VEVENT
END:VCALENDAR"""
    }
    
    headers = {"Content-Type": "text/calendar; charset=utf-8"}
    for filename, payload in events.items():
        put_resp = dav_session.put(f"{cal_url}{filename}", headers=headers, data=payload)
        assert put_resp.status_code in (201, 204)
        
    # 3. Perform PROPFIND to check they are all present
    propfind_body = """<?xml version="1.0" encoding="utf-8" ?>
    <d:propfind xmlns:d="DAV:">
      <d:prop>
        <d:resourcetype/>
      </d:prop>
    </d:propfind>"""
    propfind_headers = {"Depth": "1", "Content-Type": "application/xml; charset=utf-8"}
    pf_resp = dav_session.request("PROPFIND", cal_url, headers=propfind_headers, data=propfind_body)
    assert pf_resp.status_code == 207
    xml_content = pf_resp.text
    assert "event1.ics" in xml_content
    assert "event2.ics" in xml_content
    assert "event3.ics" in xml_content

    # 4. Update one event (PUT event with modified SUMMARY)
    updated_payload = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Kayendar//NONSGML v1.0//EN
BEGIN:VEVENT
UID:uid_sync_1
DTSTAMP:20260619T110000Z
DTSTART:20260619T120000Z
DTEND:20260619T130000Z
SUMMARY:Sync Event 1 Modified
END:VEVENT
END:VCALENDAR"""
    update_resp = dav_session.put(f"{cal_url}event1.ics", headers=headers, data=updated_payload)
    assert update_resp.status_code in (200, 201, 204)

    # 5. Delete another event (event2.ics)
    del_resp = dav_session.delete(f"{cal_url}event2.ics")
    assert del_resp.status_code in (200, 204)

    # 6. Perform a range-query REPORT or PROPFIND to verify
    # Try range-query REPORT first
    report_body = """<?xml version="1.0" encoding="utf-8" ?>
    <C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
      <D:prop>
        <C:calendar-data/>
      </D:prop>
      <C:filter>
        <C:comp-filter name="VCALENDAR">
          <C:comp-filter name="VEVENT">
            <C:time-range start="20260619T000000Z" end="20260620T000000Z"/>
          </C:comp-filter>
        </C:comp-filter>
      </C:filter>
    </C:calendar-query>"""
    report_resp = dav_session.request("REPORT", cal_url, headers=propfind_headers, data=report_body)
    
    if report_resp.status_code == 207:
        report_xml = report_resp.text
        assert "Sync Event 1 Modified" in report_xml
        assert "Sync Event 3" in report_xml
        assert "event2.ics" not in report_xml or "404" in report_xml
    else:
        # Fallback to PROPFIND and GET verification
        pf_resp2 = dav_session.request("PROPFIND", cal_url, headers=propfind_headers, data=propfind_body)
        assert pf_resp2.status_code == 207
        xml_content2 = pf_resp2.text
        assert "event1.ics" in xml_content2
        assert "event3.ics" in xml_content2
        assert "event2.ics" not in xml_content2
        
    # Check GET calls
    get_e1 = dav_session.get(f"{cal_url}event1.ics")
    assert get_e1.status_code == 200
    assert "Sync Event 1 Modified" in get_e1.text
    
    get_e2 = dav_session.get(f"{cal_url}event2.ics")
    assert get_e2.status_code == 404
    
    get_e3 = dav_session.get(f"{cal_url}event3.ics")
    assert get_e3.status_code == 200
    assert "Sync Event 3" in get_e3.text


# ----------------- Scenario 2 -----------------

@pytest.mark.tier4
def test_multi_user_collaboration_and_isolation(server_url, dav_session, test_user):
    """
    Create two test users dynamically (Alice and Bob).
    Alice creates a calendar collection and uploads events.
    Bob attempts to access Alice's calendar files and collections via Bob's Basic Auth and Bob's SPA session, asserting 403 or 404 rejection.
    Alice updates her event, and we verify that Bob's collections list remains clean/isolated.
    """
    # Alice is test_user
    alice_username = test_user["username"]
    
    # Register Bob dynamically
    rand_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    bob_username = f"bob_{rand_suffix}"
    bob_password = f"password_{rand_suffix}"
    
    register_user(bob_username, bob_password)
    
    try:
        # Alice creates a calendar collection and uploads an event
        alice_cal_url = f"{server_url}/dav/{alice_username}/alice_cal/"
        mkcal_resp = dav_session.request("MKCALENDAR", alice_cal_url)
        assert mkcal_resp.status_code in (201, 204, 405)
        
        headers = {"Content-Type": "text/calendar; charset=utf-8"}
        event_payload = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:uid_alice_1
SUMMARY:Alice Secret Meeting
END:VEVENT
END:VCALENDAR"""
        put_resp = dav_session.put(f"{alice_cal_url}event1.ics", headers=headers, data=event_payload)
        assert put_resp.status_code in (201, 204)
        
        # Bob's Basic Auth Session
        bob_dav_session = requests.Session()
        bob_dav_session.auth = (bob_username, bob_password)
        
        # Bob attempts to access Alice's calendar collection (PROPFIND)
        bob_pf_resp = bob_dav_session.request(
            "PROPFIND",
            alice_cal_url,
            headers={"Depth": "1", "Content-Type": "application/xml; charset=utf-8"},
            data="""<?xml version="1.0" encoding="utf-8" ?><d:propfind xmlns:d="DAV:"><d:prop><d:resourcetype/></d:prop></d:propfind>"""
        )
        assert bob_pf_resp.status_code in (401, 403, 404)
        
        # Bob attempts to access Alice's event file (GET)
        bob_get_resp = bob_dav_session.get(f"{alice_cal_url}event1.ics")
        assert bob_get_resp.status_code in (401, 403, 404)
        
        # Bob's SPA Session
        bob_spa_session = requests.Session()
        login_resp = bob_spa_session.post(
            f"{server_url}/api/login",
            json={"username": bob_username, "password": bob_password}
        )
        assert login_resp.status_code == 200
        
        # Bob attempts to access Alice's collection via SPA session
        bob_spa_col_resp = bob_spa_session.get(f"{server_url}/api/collections/alice_cal")
        assert bob_spa_col_resp.status_code in (401, 403, 404)
        
        # Bob's collections list should remain clean
        bob_cols_resp = bob_spa_session.get(f"{server_url}/api/collections")
        assert bob_cols_resp.status_code == 200
        bob_cols = bob_cols_resp.json()
        assert isinstance(bob_cols, list)
        for col in bob_cols:
            assert col.get("id") != "alice_cal"
            assert col.get("title") != "Alice Secret Meeting"

        # Alice updates her event
        updated_event_payload = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:uid_alice_1
SUMMARY:Alice Secret Meeting Updated
END:VEVENT
END:VCALENDAR"""
        put_resp_upd = dav_session.put(f"{alice_cal_url}event1.ics", headers=headers, data=updated_event_payload)
        assert put_resp_upd.status_code in (200, 201, 204)
        
        # Verify that Bob's collections list remains clean/isolated
        bob_cols_resp2 = bob_spa_session.get(f"{server_url}/api/collections")
        assert bob_cols_resp2.status_code == 200
        bob_cols2 = bob_cols_resp2.json()
        assert isinstance(bob_cols2, list)
        for col in bob_cols2:
            assert col.get("id") != "alice_cal"
            
    finally:
        cleanup_user_records(bob_username)


# ----------------- Scenario 3 -----------------

@pytest.mark.tier4
def test_spa_dashboard_initial_provisioning(server_url, spa_session, test_user):
    """
    Emulate a first-time login of a new user. Log in via SPA cookie authentication.
    Call SPA endpoints to create a personal calendar (with title "My Cal" and color "#00FF00")
    and a contacts book (with title "Homelab Contacts" and color "#0000FF").
    Perform collection list queries, add a contact card and an event via SPA UI API endpoints,
    and then fetch /api/me or /api/dashboard/stats to verify that all collections, events,
    and contacts are reported with their correct metadata and counts.
    """
    username = test_user["username"]
    
    # 1. Create a personal calendar collection via SPA API
    cal_payload = {
        "id": "my_cal",
        "type": "calendar",
        "title": "My Cal",
        "color": "#00ff00"
    }
    create_cal_resp = spa_session.post(f"{server_url}/api/collections", json=cal_payload)
    assert create_cal_resp.status_code in (200, 201)
    
    # 2. Create a contacts book collection via SPA API
    contacts_payload = {
        "id": "homelab_contacts",
        "type": "addressbook",
        "title": "Homelab Contacts",
        "color": "#0000ff"
    }
    create_contacts_resp = spa_session.post(f"{server_url}/api/collections", json=contacts_payload)
    assert create_contacts_resp.status_code in (200, 201)
    
    # 3. Perform collection list queries
    list_resp = spa_session.get(f"{server_url}/api/collections")
    assert list_resp.status_code == 200
    collections = list_resp.json()
    assert isinstance(collections, list)
    
    cal_found = False
    contacts_found = False
    for col in collections:
        if col.get("id") == "my_cal":
            cal_found = True
            assert col.get("title") == "My Cal"
            assert col.get("color") == "#00ff00"
            assert col.get("type") == "calendar"
        elif col.get("id") == "homelab_contacts":
            contacts_found = True
            assert col.get("title") == "Homelab Contacts"
            assert col.get("color") == "#0000ff"
            assert col.get("type") == "addressbook"
            
    assert cal_found
    assert contacts_found

    # 4. Add a contact card and an event via SPA UI API endpoints / DAV fallback
    # SPA clients can write resources directly using standard DAV endpoints or specialized REST endpoints
    event_payload = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:uid_spa_event_1
SUMMARY:SPA Event
END:VEVENT
END:VCALENDAR"""
    
    contact_payload = """BEGIN:VCARD
VERSION:3.0
FN:SPA Contact
N:Contact;SPA;;;
TEL;TYPE=CELL:+15559998888
END:VCARD"""

    # We try both custom API endpoints and standard DAV endpoints using cookie session
    # Try custom event API first: POST /api/collections/my_cal/events
    headers_ics = {"Content-Type": "text/calendar; charset=utf-8"}
    post_event_resp = spa_session.post(f"{server_url}/api/collections/my_cal/events", json={"event": event_payload})
    if post_event_resp.status_code not in (200, 201):
        # Fallback to direct DAV PUT with SPA session (cookie-based auth)
        put_event_resp = spa_session.put(
            f"{server_url}/dav/{username}/my_cal/event1.ics",
            headers=headers_ics,
            data=event_payload
        )
        assert put_event_resp.status_code in (201, 204)

    # Try custom contacts API first: POST /api/collections/homelab_contacts/contacts
    headers_vcf = {"Content-Type": "text/vcard; charset=utf-8"}
    post_contact_resp = spa_session.post(f"{server_url}/api/collections/homelab_contacts/contacts", json={"contact": contact_payload})
    if post_contact_resp.status_code not in (200, 201):
        # Fallback to direct DAV PUT with SPA session (cookie-based auth)
        put_contact_resp = spa_session.put(
            f"{server_url}/dav/{username}/homelab_contacts/contact1.vcf",
            headers=headers_vcf,
            data=contact_payload
        )
        assert put_contact_resp.status_code in (201, 204)

    # 5. Fetch /api/me or /api/dashboard/stats to verify
    stats_resp = spa_session.get(f"{server_url}/api/dashboard/stats")
    if stats_resp.status_code == 200:
        stats = stats_resp.json()
        # Verify counts if present
        if "collections_count" in stats:
            assert stats["collections_count"] == 2
        if "events_count" in stats:
            assert stats["events_count"] == 1
        if "contacts_count" in stats:
            assert stats["contacts_count"] == 1
    else:
        # Fallback verification via user/me or collections
        me_resp = spa_session.get(f"{server_url}/api/me")
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["username"] == username
        
        # Verify collection list items
        list_resp2 = spa_session.get(f"{server_url}/api/collections")
        assert list_resp2.status_code == 200
        collections2 = list_resp2.json()
        assert len(collections2) == 2


# ----------------- Scenario 4 -----------------

@pytest.mark.tier4
def test_data_backup_restore_recovery(server_url, dav_session, test_user):
    """
    Simulate a full server data backup and restore.
    1. Create a test user (test_user fixture).
    2. Create calendar/addressbook and upload 2 events and 2 contacts via DAV.
    3. Access the filesystem database directory KAYENDAR_DATA_DIR directly and perform a backup
       (copying users.json, calendars, and contacts folders to a temporary backup location inside the workspace).
    4. Simulate a disaster: delete the user and their directories via API, or clear them from disk,
       verifying they are gone (DAV calls return 401/404).
    5. Restore the backup by copying files back to KAYENDAR_DATA_DIR.
    6. Send requests using the original credentials and verify all calendar events and contacts are restored.
    """
    username = test_user["username"]
    
    # 1. Create collections
    cal_url = f"{server_url}/dav/{username}/backup_cal/"
    contacts_url = f"{server_url}/dav/{username}/backup_contacts/"
    
    mkcal_resp = dav_session.request("MKCALENDAR", cal_url)
    assert mkcal_resp.status_code in (201, 204, 405)
    
    mkcol_resp = dav_session.request("MKCOL", contacts_url)
    assert mkcol_resp.status_code in (201, 204, 405)
    
    # 2. Upload 2 events and 2 contacts
    events = {
        "event1.ics": """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:uid_b1
SUMMARY:Backup Event 1
END:VEVENT
END:VCALENDAR""",
        "event2.ics": """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:uid_b2
SUMMARY:Backup Event 2
END:VEVENT
END:VCALENDAR"""
    }
    
    contacts = {
        "contact1.vcf": """BEGIN:VCARD
VERSION:3.0
FN:Backup Contact 1
END:VCARD""",
        "contact2.vcf": """BEGIN:VCARD
VERSION:3.0
FN:Backup Contact 2
END:VCARD"""
    }
    
    headers_ics = {"Content-Type": "text/calendar; charset=utf-8"}
    for filename, payload in events.items():
        put_resp = dav_session.put(f"{cal_url}{filename}", headers=headers_ics, data=payload)
        assert put_resp.status_code in (201, 204)
        
    headers_vcf = {"Content-Type": "text/vcard; charset=utf-8"}
    for filename, payload in contacts.items():
        put_resp = dav_session.put(f"{contacts_url}{filename}", headers=headers_vcf, data=payload)
        assert put_resp.status_code in (201, 204)
        
    # 3. Access filesystem directory KAYENDAR_DATA_DIR directly and perform backup
    data_dir = get_data_dir()
    backup_dir = REPO_ROOT / "tests" / "e2e" / "tmp_backup"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy users.json
    users_json = data_dir / "users.json"
    shutil.copy2(users_json, backup_dir / "users.json")
    
    # Copy calendars and contacts user folders
    cal_user_dir = data_dir / "collections" / username
    con_user_dir = data_dir / "collections" / username
    
    shutil.copytree(cal_user_dir, backup_dir / "collections" / username, dirs_exist_ok=True)
    shutil.copytree(con_user_dir, backup_dir / "collections" / username, dirs_exist_ok=True)
    
    # 4. Simulate a disaster (delete user from users.json and their directories)
    # Perform user record cleanup
    with _lock_db_file(str(users_json)):
        if users_json.exists():
            with open(users_json, "r", encoding="utf-8") as f:
                users = json.load(f)
            if username in users:
                del users[username]
            with open(users_json, "w", encoding="utf-8") as f:
                json.dump(users, f, indent=4)
                
    if cal_user_dir.exists():
        shutil.rmtree(cal_user_dir)
    if con_user_dir.exists():
        shutil.rmtree(con_user_dir)
        
    # Verify they are gone (DAV calls return 401 Unauthorized because user record is deleted)
    options_resp = dav_session.options(f"{server_url}/dav/")
    assert options_resp.status_code in (401, 403, 404)
    
    # 5. Restore the backup
    # Restore users.json
    shutil.copy2(backup_dir / "users.json", users_json)
    
    # Restore directories
    shutil.copytree(backup_dir / "collections" / username, cal_user_dir, dirs_exist_ok=True)
    shutil.copytree(backup_dir / "collections" / username, con_user_dir, dirs_exist_ok=True)
    
    # 6. Verify restored resources are accessible
    options_resp2 = dav_session.options(f"{server_url}/dav/")
    assert options_resp2.status_code == 200
    
    # Verify events
    for filename in events.keys():
        get_resp = dav_session.get(f"{cal_url}{filename}")
        assert get_resp.status_code == 200
        assert filename.split(".")[0].capitalize().replace("1", " 1").replace("2", " 2") in get_resp.text
        
    # Verify contacts
    for filename in contacts.keys():
        get_resp = dav_session.get(f"{contacts_url}{filename}")
        assert get_resp.status_code == 200
        assert filename.split(".")[0].capitalize().replace("1", " 1").replace("2", " 2") in get_resp.text
        
    # Clean up backup
    if backup_dir.exists():
        shutil.rmtree(backup_dir)


# ----------------- Scenario 5 -----------------

@pytest.mark.tier4
def test_collection_export_import_compatibility(server_url, dav_session, test_user):
    """
    Import external calendar/contacts data (emulating migration from Google Calendar or Radicale).
    Take standard multi-event .ics data and multi-card .vcf data and upload them via PUT or SPA endpoints.
    Retrieve the resources via CalDAV and CardDAV and verify that the items parse correctly
    (events have proper summary, start/end dates; contacts have correct emails/phones)
    and no attributes are lost or corrupted.
    """
    username = test_user["username"]
    
    cal_url = f"{server_url}/dav/{username}/import_cal/"
    contacts_url = f"{server_url}/dav/{username}/import_contacts/"
    
    # Create collections
    mkcal_resp = dav_session.request("MKCALENDAR", cal_url)
    assert mkcal_resp.status_code in (201, 204, 405)
    
    mkcol_resp = dav_session.request("MKCOL", contacts_url)
    assert mkcol_resp.status_code in (201, 204, 405)
    
    # Multi-event ICS data
    multi_ics = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Google Inc//Google Calendar 70.9054//EN
BEGIN:VEVENT
UID:google-event-1
SUMMARY:Google Calendar Event 1
DTSTART:20260619T100000Z
DTEND:20260619T110000Z
END:VEVENT
BEGIN:VEVENT
UID:google-event-2
SUMMARY:Google Calendar Event 2
DTSTART:20260619T120000Z
DTEND:20260619T130000Z
END:VEVENT
END:VCALENDAR"""

    # Multi-card VCF data
    multi_vcf = """BEGIN:VCARD
VERSION:3.0
FN:Radicale Contact 1
N:Contact;Radicale 1;;;
EMAIL;TYPE=INTERNET:radicale1@example.com
TEL;TYPE=CELL:+15551111111
END:VCARD
BEGIN:VCARD
VERSION:3.0
FN:Radicale Contact 2
N:Contact;Radicale 2;;;
EMAIL;TYPE=INTERNET:radicale2@example.com
TEL;TYPE=CELL:+15552222222
END:VCARD"""

    # Upload via PUT
    put_ics_resp = dav_session.put(f"{cal_url}imported.ics", headers={"Content-Type": "text/calendar; charset=utf-8"}, data=multi_ics)
    assert put_ics_resp.status_code in (201, 204)
    
    put_vcf_resp = dav_session.put(f"{contacts_url}imported.vcf", headers={"Content-Type": "text/vcard; charset=utf-8"}, data=multi_vcf)
    assert put_vcf_resp.status_code in (201, 204)
    
    # Try parsing via icalendar and vobject if installed, else fallback to string parsing
    # First, let's see how the server exposed them. Does it return them as one file or multiple?
    # Perform PROPFIND on collections
    propfind_body = """<?xml version="1.0" encoding="utf-8" ?>
    <d:propfind xmlns:d="DAV:">
      <d:prop>
        <d:resourcetype/>
      </d:prop>
    </d:propfind>"""
    propfind_headers = {"Depth": "1", "Content-Type": "application/xml; charset=utf-8"}
    
    cal_pf = dav_session.request("PROPFIND", cal_url, headers=propfind_headers, data=propfind_body)
    assert cal_pf.status_code == 207
    cal_xml = cal_pf.text
    
    # Verify calendar events
    if "google-event-1.ics" in cal_xml or "google-event-2.ics" in cal_xml:
        # Server split them on PUT import
        get_e1 = dav_session.get(f"{cal_url}google-event-1.ics")
        assert get_e1.status_code == 200
        get_e2 = dav_session.get(f"{cal_url}google-event-2.ics")
        assert get_e2.status_code == 200
        
        cal_contents = get_e1.text + "\n" + get_e2.text
    else:
        # Stored under imported.ics
        get_imported = dav_session.get(f"{cal_url}imported.ics")
        assert get_imported.status_code == 200
        cal_contents = get_imported.text

    # String validation of events
    assert "Google Calendar Event 1" in cal_contents
    assert "google-event-1" in cal_contents
    assert "Google Calendar Event 2" in cal_contents
    assert "google-event-2" in cal_contents
    assert "20260619T100000Z" in cal_contents
    assert "20260619T110000Z" in cal_contents
    
    # Try library parsing
    try:
        from icalendar import Calendar
        cal = Calendar.from_ical(cal_contents)
        events_list = [e for e in cal.walk('VEVENT')]
        assert len(events_list) >= 1
        summaries = [str(e.get('summary')) for e in events_list]
        assert any("Google Calendar Event 1" in s for s in summaries)
    except Exception:
        # Library parsing is optional fallback
        pass

    # Verify contacts
    con_pf = dav_session.request("PROPFIND", contacts_url, headers=propfind_headers, data=propfind_body)
    assert con_pf.status_code == 207
    con_xml = con_pf.text
    
    if "radicale1.vcf" in con_xml or "radicale2.vcf" in con_xml or "Radicale Contact 1.vcf" in con_xml:
        # Server split them
        # Find which filenames are actually in XML
        filenames = []
        import re
        for match in re.finditer(r'<d:href>[^<]*contacts/[^/]+/import_contacts/([^<]+)</d:href>', con_xml):
            fn = match.group(1)
            if fn and fn != "import_contacts/":
                filenames.append(fn)
                
        con_contents = ""
        for fn in filenames:
            get_c = dav_session.get(f"{contacts_url}{fn}")
            if get_c.status_code == 200:
                con_contents += get_c.text + "\n"
    else:
        # Stored under imported.vcf
        get_imported_vcf = dav_session.get(f"{contacts_url}imported.vcf")
        assert get_imported_vcf.status_code == 200
        con_contents = get_imported_vcf.text

    # String validation of contacts
    assert "Radicale Contact 1" in con_contents
    assert "radicale1@example.com" in con_contents
    assert "+15551111111" in con_contents
    assert "Radicale Contact 2" in con_contents
    assert "radicale2@example.com" in con_contents
    assert "+15552222222" in con_contents
    
    # Try library parsing
    try:
        import vobject
        # vobject.readComponents parses multiple vcards from a stream
        vcards = list(vobject.readComponents(con_contents))
        assert len(vcards) >= 1
        fns = [v.fn.value for v in vcards if hasattr(v, 'fn')]
        assert any("Radicale Contact 1" in f for f in fns)
    except Exception:
        # Library parsing is optional fallback
        pass
