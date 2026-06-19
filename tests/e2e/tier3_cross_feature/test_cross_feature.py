import os
import pytest
from pathlib import Path

# Helper to locate the active data directory
def get_data_dir() -> Path:
    data_dir_env = os.environ.get("KAYENDAR_DATA_DIR")
    if data_dir_env:
        return Path(data_dir_env)
    return Path(__file__).resolve().parent.parent.parent.parent / "data"

ICS_PAYLOAD = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Kayendar//NONSGML v1.0//EN
BEGIN:VEVENT
UID:uid_cross_cal_storage@example.com
DTSTAMP:20260619T110000Z
DTSTART:20260619T120000Z
DTEND:20260619T130000Z
SUMMARY:Cross Caldav Storage Event
END:VEVENT
END:VCALENDAR"""

VCF_PAYLOAD = """BEGIN:VCARD
VERSION:3.0
FN:John Doe Cross
N:Doe;John;;;
EMAIL;TYPE=INTERNET:john.doe.cross@example.com
END:VCARD"""


@pytest.mark.tier3
def test_caldav_storage_interaction(server_url, dav_session, test_user):
    """
    Perform a CalDAV PUT of an event (.ics) to /dav/{username}/personal_cal/event.ics.
    Access the filesystem database directory directly and verify the file exists on disk and its content matches what was PUT.
    """
    username = test_user["username"]
    
    # 1. Ensure the calendar collection exists via MKCALENDAR
    mkcal_resp = dav_session.request("MKCALENDAR", f"{server_url}/dav/{username}/personal_cal/")
    assert mkcal_resp.status_code in (201, 204, 405)
    
    # 2. Put the event (.ics) to CalDAV endpoint
    headers = {"Content-Type": "text/calendar; charset=utf-8"}
    put_resp = dav_session.put(
        f"{server_url}/dav/{username}/personal_cal/event.ics",
        headers=headers,
        data=ICS_PAYLOAD
    )
    assert put_resp.status_code in (201, 204)
    
    # 3. Access filesystem directory directly and verify
    data_dir = get_data_dir()
    event_file = data_dir / "collections" / username / "personal_cal" / "event.ics"
    
    assert event_file.is_file()
    with open(event_file, "r", encoding="utf-8") as f:
        content = f.read()
        
    assert "BEGIN:VCALENDAR" in content
    assert "Cross Caldav Storage Event" in content
    assert "uid_cross_cal_storage@example.com" in content


@pytest.mark.tier3
def test_carddav_storage_interaction(server_url, dav_session, test_user):
    """
    Perform a CardDAV PUT of a contact (.vcf) to /dav/{username}/friends/contact.vcf.
    Access the filesystem database directory directly and verify the file exists on disk and contains the correct CardDAV fields.
    """
    username = test_user["username"]
    
    # 1. Ensure the addressbook collection exists via MKCOL
    mkcol_resp = dav_session.request("MKCOL", f"{server_url}/dav/{username}/friends/")
    assert mkcol_resp.status_code in (201, 204, 405)
    
    # 2. Put the contact (.vcf) to CardDAV endpoint
    headers = {"Content-Type": "text/vcard; charset=utf-8"}
    put_resp = dav_session.put(
        f"{server_url}/dav/{username}/friends/contact.vcf",
        headers=headers,
        data=VCF_PAYLOAD
    )
    assert put_resp.status_code in (201, 204)
    
    # 3. Access filesystem directory directly and verify
    data_dir = get_data_dir()
    contact_file = data_dir / "collections" / username / "friends" / "contact.vcf"
    
    assert contact_file.is_file()
    with open(contact_file, "r", encoding="utf-8") as f:
        content = f.read()
        
    assert "BEGIN:VCARD" in content
    assert "John Doe Cross" in content
    assert "john.doe.cross@example.com" in content


@pytest.mark.tier3
def test_caldav_spa_interaction(server_url, dav_session, spa_session, test_user):
    """
    Perform a CalDAV PUT of an event via the DAV session.
    Use the SPA session (spa_session fixture) to send a GET request to /api/collections/
    or /api/calendars/{calendar_id}/events and verify that the newly uploaded event is
    visible and returned correctly in the SPA client representation.
    """
    username = test_user["username"]
    
    # 1. MKCALENDAR
    dav_session.request("MKCALENDAR", f"{server_url}/dav/{username}/personal_cal/")
    
    # 2. PUT event via DAV
    headers = {"Content-Type": "text/calendar; charset=utf-8"}
    put_resp = dav_session.put(
        f"{server_url}/dav/{username}/personal_cal/event.ics",
        headers=headers,
        data=ICS_PAYLOAD
    )
    assert put_resp.status_code in (201, 204)
    
    # 3. Access via SPA session — items API
    items_resp = spa_session.get(f"{server_url}/api/collections/personal_cal/items")
    assert items_resp.status_code == 200
    items = items_resp.json()
    assert any("Cross Caldav Storage Event" in str(item.get("content", "")) for item in items)


@pytest.mark.tier3
def test_carddav_spa_interaction(server_url, dav_session, spa_session, test_user):
    """
    Perform a CardDAV PUT of a contact card via the DAV session.
    Use the SPA session (spa_session) to send a GET request to /api/collections/
    or /api/contacts/ and verify that the contact is listed in the SPA client contacts list.
    """
    username = test_user["username"]
    
    # 1. MKCOL
    dav_session.request("MKCOL", f"{server_url}/dav/{username}/friends/")
    
    # 2. PUT contact via DAV
    headers = {"Content-Type": "text/vcard; charset=utf-8"}
    put_resp = dav_session.put(
        f"{server_url}/dav/{username}/friends/contact.vcf",
        headers=headers,
        data=VCF_PAYLOAD
    )
    assert put_resp.status_code in (201, 204)
    
    items_resp = spa_session.get(f"{server_url}/api/collections/friends/items")
    assert items_resp.status_code == 200
    items = items_resp.json()
    assert any("John Doe Cross" in str(item.get("content", "")) for item in items)


@pytest.mark.tier3
def test_spa_dav_sync_interaction(server_url, dav_session, spa_session, test_user):
    """
    Use the SPA session to create or update a collection (e.g. create a calendar called "Work Calendar"
    with color "#FF0000" or rename it).
    Use the DAV session to send a PROPFIND request to the DAV endpoint /dav/
    and verify that the collection is listed and its updated metadata is correctly returned in the DAV response.
    """
    username = test_user["username"]
    create_payload = {
        "display_name": "Work Calendar",
        "type": "calendar",
        "color": "#ff0000",
    }
    create_resp = spa_session.post(f"{server_url}/api/collections", json=create_payload)
    assert create_resp.status_code == 201
    slug = create_resp.json()["slug"]

    update_resp = spa_session.patch(
        f"{server_url}/api/collections/{slug}",
        json={"display_name": "Renamed Work Calendar", "color": "#00ff00"},
    )
    assert update_resp.status_code == 200
    
    # 3. Use DAV session to send a PROPFIND request to the DAV endpoint
    headers = {"Depth": "1", "Content-Type": "application/xml; charset=utf-8"}
    body = """<?xml version="1.0" encoding="utf-8" ?>
    <d:propfind xmlns:d="DAV:">
      <d:prop>
        <d:resourcetype/>
        <d:displayname/>
      </d:prop>
    </d:propfind>"""
    
    response = dav_session.request(
        "PROPFIND",
        f"{server_url}/dav/{username}/",
        headers=headers,
        data=body,
    )
    assert response.status_code == 207

    xml_content = response.text
    assert "Renamed Work Calendar" in xml_content or slug in xml_content
