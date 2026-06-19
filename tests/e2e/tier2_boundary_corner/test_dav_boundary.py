import pytest
import requests

# ----------------- CalDAV Boundary Tests -----------------

@pytest.mark.tier2
def test_caldav_put_malformed_ics(server_url, dav_session, test_user):
    """PUT to a calendar collection with a malformed/empty/invalid VEVENT ICS payload, asserting 400 Bad Request."""
    username = test_user["username"]
    
    # Create the calendar collection first
    dav_session.request("MKCALENDAR", f"{server_url}/dav/{username}/personal_cal/")
    
    malformed_payloads = [
        "",
        "NOT_ICS_CONTENT",
        "BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR",  # Missing VEVENT
        "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:123\nSUMMARY:No end tag",  # Unclosed VEVENT
    ]
    
    headers = {"Content-Type": "text/calendar; charset=utf-8"}
    for payload in malformed_payloads:
        response = dav_session.put(
            f"{server_url}/dav/{username}/personal_cal/bad_event.ics",
            headers=headers,
            data=payload
        )
        assert response.status_code == 400


@pytest.mark.tier2
def test_caldav_put_traversal(server_url, dav_session, test_user):
    """PUT to a calendar event path containing directory traversal attempts, asserting 400/403/404."""
    username = test_user["username"]
    
    # Create the calendar collection first
    dav_session.request("MKCALENDAR", f"{server_url}/dav/{username}/personal_cal/")
    
    traversal_paths = [
        f"{server_url}/dav/{username}/../../event.ics",
        f"{server_url}/dav/{username}/personal_cal/../../event.ics",
        f"{server_url}/dav/../../event.ics",
        f"{server_url}/dav/{username}/personal_cal/..%2f..%2fevent.ics",
    ]
    
    ics_payload = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:uid_traversal@example.com
SUMMARY:Traversal Event
END:VEVENT
END:VCALENDAR"""
    
    headers = {"Content-Type": "text/calendar; charset=utf-8"}
    for path in traversal_paths:
        response = dav_session.put(path, headers=headers, data=ics_payload)
        assert response.status_code in (400, 403, 404)


@pytest.mark.tier2
def test_caldav_propfind_malformed_xml(server_url, dav_session, test_user):
    """Send PROPFIND request with malformed XML payload or missing Depth header, asserting graceful response (400 or valid parser recovery)."""
    username = test_user["username"]
    
    # 1. Malformed XML payload
    malformed_xml = """<?xml version="1.0" encoding="utf-8" ?>
    <d:propfind xmlns:d="DAV:">
      <d:prop>
        <d:resourcetype>
    """  # Missing closing tags
    
    headers = {"Depth": "1", "Content-Type": "application/xml; charset=utf-8"}
    response_malformed = dav_session.request(
        "PROPFIND",
        f"{server_url}/dav/{username}/",
        headers=headers,
        data=malformed_xml
    )
    # The server should handle malformed XML gracefully without crashing.
    # It either returns 400 Bad Request or recovers and returns 207 Multi-Status.
    assert response_malformed.status_code in (400, 207)

    # 2. Missing Depth header
    headers_no_depth = {"Content-Type": "application/xml; charset=utf-8"}
    valid_xml = """<?xml version="1.0" encoding="utf-8" ?>
    <d:propfind xmlns:d="DAV:">
      <d:prop>
        <d:resourcetype/>
      </d:prop>
    </d:propfind>"""
    
    response_no_depth = dav_session.request(
        "PROPFIND",
        f"{server_url}/dav/{username}/",
        headers=headers_no_depth,
        data=valid_xml
    )
    # Should handle missing Depth header gracefully (defaulting to 0, 1, infinity or returning 400 Bad Request)
    assert response_no_depth.status_code in (200, 207, 400)


@pytest.mark.tier2
def test_caldav_delete_nonexistent_event(server_url, dav_session, test_user):
    """Send DELETE to a non-existent event file, asserting 404 Not Found."""
    username = test_user["username"]
    
    # Ensure collection exists
    dav_session.request("MKCALENDAR", f"{server_url}/dav/{username}/personal_cal/")
    
    response = dav_session.delete(
        f"{server_url}/dav/{username}/personal_cal/nonexistent_event_999.ics"
    )
    assert response.status_code == 404


@pytest.mark.tier2
def test_caldav_mkcalendar_conflict(server_url, dav_session, test_user):
    """Send MKCALENDAR to an already existing calendar collection path, asserting 405 Method Not Allowed or 409 Conflict."""
    username = test_user["username"]
    path = f"{server_url}/dav/{username}/duplicate_cal/"
    
    # Create the calendar collection first
    response1 = dav_session.request("MKCALENDAR", path)
    assert response1.status_code == 201
    
    # Attempt to create again
    response2 = dav_session.request("MKCALENDAR", path)
    assert response2.status_code in (405, 409)


# ----------------- CardDAV Boundary Tests -----------------

@pytest.mark.tier2
def test_carddav_put_malformed_vcf(server_url, dav_session, test_user):
    """PUT to an addressbook collection with a malformed/empty/invalid VCARD VCF payload, asserting 400 Bad Request."""
    username = test_user["username"]
    
    # Create the addressbook collection first
    dav_session.request("MKCOL", f"{server_url}/dav/{username}/friends/")
    
    malformed_payloads = [
        "",
        "NOT_VCARD_CONTENT",
        "BEGIN:VCARD\nVERSION:3.0\nEND:VCARD",  # Missing FN (Formatted Name)
        "BEGIN:VCARD\nFN:John Doe\n",  # Unclosed VCARD
    ]
    
    headers = {"Content-Type": "text/vcard; charset=utf-8"}
    for payload in malformed_payloads:
        response = dav_session.put(
            f"{server_url}/dav/{username}/friends/bad_contact.vcf",
            headers=headers,
            data=payload
        )
        assert response.status_code == 400


@pytest.mark.tier2
def test_carddav_put_traversal(server_url, dav_session, test_user):
    """PUT to a contact card path containing directory traversal attempts, asserting 400/403/404."""
    username = test_user["username"]
    
    # Create the addressbook collection first
    dav_session.request("MKCOL", f"{server_url}/dav/{username}/friends/")
    
    traversal_paths = [
        f"{server_url}/dav/{username}/../../contact.vcf",
        f"{server_url}/dav/{username}/friends/../../contact.vcf",
        f"{server_url}/dav/../../contact.vcf",
        f"{server_url}/dav/{username}/friends/..%2f..%2fcontact.vcf",
    ]
    
    vcf_payload = """BEGIN:VCARD
VERSION:3.0
FN:Traversal Contact
N:Contact;Traversal;;;
END:VCARD"""
    
    headers = {"Content-Type": "text/vcard; charset=utf-8"}
    for path in traversal_paths:
        response = dav_session.put(path, headers=headers, data=vcf_payload)
        assert response.status_code in (400, 403, 404)


@pytest.mark.tier2
def test_carddav_propfind_nonexistent_collection(server_url, dav_session, test_user):
    """Send PROPFIND request to a non-existent contacts folder, asserting 404 Not Found."""
    username = test_user["username"]
    
    headers = {"Depth": "1", "Content-Type": "application/xml; charset=utf-8"}
    body = """<?xml version="1.0" encoding="utf-8" ?>
    <d:propfind xmlns:d="DAV:">
      <d:prop>
        <d:resourcetype/>
      </d:prop>
    </d:propfind>"""
    
    response = dav_session.request(
        "PROPFIND",
        f"{server_url}/dav/{username}/nonexistent_folder_xyz/",
        headers=headers,
        data=body
    )
    assert response.status_code == 404


@pytest.mark.tier2
def test_carddav_delete_nonexistent_contact(server_url, dav_session, test_user):
    """Send DELETE to a non-existent contact card, asserting 404 Not Found."""
    username = test_user["username"]
    
    # Ensure collection exists
    dav_session.request("MKCOL", f"{server_url}/dav/{username}/friends/")
    
    response = dav_session.delete(
        f"{server_url}/dav/{username}/friends/nonexistent_contact_999.vcf"
    )
    assert response.status_code == 404


@pytest.mark.tier2
def test_carddav_mkcol_addressbook_conflict(server_url, dav_session, test_user):
    """Create addressbook on a non-existent parent collection path or invalid user path, asserting 403 or 409 Conflict."""
    username = test_user["username"]
    
    # 1. Create collection with non-existent parent path
    headers = {"Content-Type": "application/xml; charset=utf-8"}
    body = """<?xml version="1.0" encoding="utf-8" ?>
    <d:mkcol xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:carddav">
      <d:set>
        <d:prop>
          <d:resourcetype>
            <d:collection/>
            <c:addressbook/>
          </d:resourcetype>
          <d:displayname>Deep Address Book</d:displayname>
        </d:prop>
      </d:set>
    </d:mkcol>"""
    
    response_deep = dav_session.request(
        "MKCOL",
        f"{server_url}/dav/{username}/nonexistent_parent/mybook/",
        headers=headers,
        data=body
    )
    # The parent does not exist, so MKCOL should return 409 Conflict (or 403 Forbidden)
    assert response_deep.status_code in (403, 409)

    # 2. Create addressbook for another invalid user path
    response_invalid_user = dav_session.request(
        "MKCOL",
        f"{server_url}/dav/nonexistent_user_abc/mybook/",
        headers=headers,
        data=body
    )
    assert response_invalid_user.status_code in (403, 409)
