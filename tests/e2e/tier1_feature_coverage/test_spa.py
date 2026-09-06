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


@pytest.mark.tier1
def test_spa_export_import_collection(server_url, spa_session):
    """Test 1-click export and import of .ics collections."""
    # Create a test calendar
    c_res = spa_session.post(f"{server_url}/api/collections", json={"display_name": "Export Test", "type": "calendar"})
    assert c_res.status_code == 201
    slug = c_res.json()["slug"]

    # Put an event
    ev_ics = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:export-ev-1\r\nSUMMARY:Test Export\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    put_res = spa_session.put(f"{server_url}/api/collections/{slug}/items/export-ev-1.ics", json={"content": ev_ics})
    assert put_res.status_code in (200, 201)

    # Export
    exp_res = spa_session.get(f"{server_url}/api/collections/{slug}/export")
    assert exp_res.status_code == 200
    assert "text/calendar" in exp_res.headers.get("Content-Type", "")
    assert "Test Export" in exp_res.text

    # Create target calendar to import into
    c2_res = spa_session.post(f"{server_url}/api/collections", json={"display_name": "Import Test", "type": "calendar"})
    assert c2_res.status_code == 201
    slug2 = c2_res.json()["slug"]

    # Import
    imp_res = spa_session.post(
        f"{server_url}/api/collections/{slug2}/import",
        data=exp_res.text.encode("utf-8"),
        headers={"Content-Type": "text/calendar; charset=utf-8"},
    )
    assert imp_res.status_code == 200
    assert imp_res.json()["imported"] >= 1

    # Verify items in target calendar
    items_res = spa_session.get(f"{server_url}/api/collections/{slug2}/items")
    assert items_res.status_code == 200
    assert any(i["filename"] == "export-ev-1.ics" for i in items_res.json())

    # Cleanup
    spa_session.delete(f"{server_url}/api/collections/{slug}")
    spa_session.delete(f"{server_url}/api/collections/{slug2}")


@pytest.mark.tier1
def test_spa_collection_sharing_public_feed(server_url, spa_session):
    """Test public read-only share link generation and anonymous feed fetching."""
    # Create calendar
    c_res = spa_session.post(f"{server_url}/api/collections", json={"display_name": "Share Test", "type": "calendar"})
    assert c_res.status_code == 201
    slug = c_res.json()["slug"]

    # Put an event
    ev_ics = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:share-ev-1\r\nSUMMARY:Public Shared Event\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    spa_session.put(f"{server_url}/api/collections/{slug}/items/share-ev-1.ics", json={"content": ev_ics})

    # Create share link
    share_res = spa_session.post(f"{server_url}/api/collections/{slug}/share", json={})
    assert share_res.status_code == 200
    share_data = share_res.json()
    assert share_data["shared"] is True
    token = share_data["token"]
    feed_url = share_data["url"]

    # Fetch feed anonymously without cookies/auth
    anon_res = requests.get(f"{server_url}{feed_url}")
    assert anon_res.status_code == 200
    assert "text/calendar" in anon_res.headers.get("Content-Type", "")
    assert "Public Shared Event" in anon_res.text

    # Revoke share
    del_res = spa_session.delete(f"{server_url}/api/collections/{slug}/share")
    assert del_res.status_code == 200

    # Feed should now return 404
    anon_after = requests.get(f"{server_url}{feed_url}")
    assert anon_after.status_code == 404

    # Cleanup
    spa_session.delete(f"{server_url}/api/collections/{slug}")


@pytest.mark.tier1
def test_spa_export_import_addressbook_vcf(server_url, spa_session):
    """Test 1-click export and import of .vcf address books."""
    c_res = spa_session.post(
        f"{server_url}/api/collections",
        json={"display_name": "Contact Export Test", "type": "addressbook"},
    )
    assert c_res.status_code == 201
    slug = c_res.json()["slug"]

    # Put a contact
    vcf = (
        "BEGIN:VCARD\r\n"
        "VERSION:3.0\r\n"
        "UID:card-export-1\r\n"
        "FN:Ada Lovelace\r\n"
        "EMAIL:ada@example.com\r\n"
        "TEL:+34 600 000 000\r\n"
        "END:VCARD\r\n"
    )
    put_res = spa_session.put(
        f"{server_url}/api/collections/{slug}/items/card-export-1.vcf",
        json={"content": vcf},
    )
    assert put_res.status_code in (200, 201)

    # Export .vcf
    exp_res = spa_session.get(f"{server_url}/api/collections/{slug}/export")
    assert exp_res.status_code == 200
    assert "text/vcard" in exp_res.headers.get("Content-Type", "")
    assert "Ada Lovelace" in exp_res.text

    # Create target address book to import into
    c2_res = spa_session.post(
        f"{server_url}/api/collections",
        json={"display_name": "Contact Import Test", "type": "addressbook"},
    )
    assert c2_res.status_code == 201
    slug2 = c2_res.json()["slug"]

    # Import raw vCard text
    imp_res = spa_session.post(
        f"{server_url}/api/collections/{slug2}/import",
        data=exp_res.text.encode("utf-8"),
        headers={"Content-Type": "text/vcard; charset=utf-8"},
    )
    assert imp_res.status_code == 200
    assert imp_res.json()["imported"] >= 1

    # Cleanup
    spa_session.delete(f"{server_url}/api/collections/{slug}")
    spa_session.delete(f"{server_url}/api/collections/{slug2}")


@pytest.mark.tier1
def test_well_known_dav_discovery(server_url):
    """Test RFC 6764 auto-discovery redirects for CalDAV and CardDAV."""
    for path in ["/.well-known/caldav", "/.well-known/carddav"]:
        res = requests.get(f"{server_url}{path}", allow_redirects=False)
        assert res.status_code == 308
        assert res.headers.get("Location") == "/dav/"

