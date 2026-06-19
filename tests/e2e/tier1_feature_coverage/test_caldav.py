import pytest

ICS_PAYLOAD = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Kayendar//NONSGML v1.0//EN
BEGIN:VEVENT
UID:uid1@example.com
DTSTAMP:20260619T110000Z
DTSTART:20260619T120000Z
DTEND:20260619T130000Z
SUMMARY:Test Event 1
END:VEVENT
END:VCALENDAR"""

@pytest.mark.tier1
def test_caldav_options(server_url, dav_session):
    """Send OPTIONS request to /dav/ and assert response header 'DAV' contains 'calendar-access'."""
    response = dav_session.options(f"{server_url}/dav/")
    assert response.status_code == 200
    dav_header = response.headers.get("DAV", "")
    assert "calendar-access" in dav_header


@pytest.mark.tier1
def test_caldav_propfind(server_url, dav_session, test_user):
    """Send PROPFIND request to /dav/{username}/ and assert 207 Multi-Status."""
    username = test_user["username"]
    
    # PROPFIND request with Depth header
    headers = {"Depth": "1", "Content-Type": "application/xml; charset=utf-8"}
    
    # Standard WebDAV PROPFIND XML body
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
        data=body
    )
    assert response.status_code == 207


@pytest.mark.tier1
def test_caldav_mkcalendar(server_url, dav_session, test_user):
    """Send MKCALENDAR request to create a calendar collection and assert 201 Created."""
    username = test_user["username"]
    
    # MKCALENDAR or MKCOL with calendar body
    headers = {"Content-Type": "application/xml; charset=utf-8"}
    body = """<?xml version="1.0" encoding="utf-8" ?>
    <C:mkcalendar xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
      <D:set>
        <D:prop>
          <D:displayname>Personal Calendar</D:displayname>
          <C:supported-calendar-component-set>
            <C:comp name="VEVENT"/>
          </C:supported-calendar-component-set>
        </D:prop>
      </D:set>
    </C:mkcalendar>"""
    
    response = dav_session.request(
        "MKCALENDAR",
        f"{server_url}/dav/{username}/personal_cal/",
        headers=headers,
        data=body
    )
    # CalDAV standard allows 201 Created
    assert response.status_code == 201


@pytest.mark.tier1
def test_caldav_put_event(server_url, dav_session, test_user):
    """Send PUT with a valid VEVENT ICS payload to calendar endpoint and assert 201 Created."""
    username = test_user["username"]
    
    # Ensure collection exists first (optional but good practice)
    dav_session.request("MKCALENDAR", f"{server_url}/dav/{username}/personal_cal/")
    
    headers = {"Content-Type": "text/calendar; charset=utf-8"}
    response = dav_session.put(
        f"{server_url}/dav/{username}/personal_cal/event1.ics",
        headers=headers,
        data=ICS_PAYLOAD
    )
    assert response.status_code in (201, 204)


@pytest.mark.tier1
def test_caldav_delete_event(server_url, dav_session, test_user):
    """Send DELETE to remove an event and assert 200 OK or 204 No Content."""
    username = test_user["username"]
    
    # Ensure collection and event exist
    dav_session.request("MKCALENDAR", f"{server_url}/dav/{username}/personal_cal/")
    dav_session.put(
        f"{server_url}/dav/{username}/personal_cal/event1.ics",
        headers={"Content-Type": "text/calendar; charset=utf-8"},
        data=ICS_PAYLOAD
    )
    
    response = dav_session.delete(f"{server_url}/dav/{username}/personal_cal/event1.ics")
    assert response.status_code in (200, 204)
