import pytest

VCF_PAYLOAD = """BEGIN:VCARD
VERSION:3.0
FN:John Doe
N:Doe;John;;;
EMAIL;TYPE=INTERNET:john.doe@example.com
END:VCARD"""

@pytest.mark.tier1
def test_carddav_options(server_url, dav_session):
    """Send OPTIONS request to /dav/ and assert response header 'DAV' contains 'addressbook'."""
    response = dav_session.options(f"{server_url}/dav/")
    assert response.status_code == 200
    dav_header = response.headers.get("DAV", "")
    assert "addressbook" in dav_header


@pytest.mark.tier1
def test_carddav_propfind(server_url, dav_session, test_user):
    """Send PROPFIND to /dav/{username}/ and assert 207 Multi-Status."""
    username = test_user["username"]
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
        data=body
    )
    assert response.status_code == 207


@pytest.mark.tier1
def test_carddav_mkcol_addressbook(server_url, dav_session, test_user):
    """Send MKCOL (with addressbook body/parameters) to addressbook endpoint and assert 201 Created."""
    username = test_user["username"]
    headers = {"Content-Type": "application/xml; charset=utf-8"}
    body = """<?xml version="1.0" encoding="utf-8" ?>
    <d:mkcol xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:carddav">
      <d:set>
        <d:prop>
          <d:resourcetype>
            <d:collection/>
            <c:addressbook/>
          </d:resourcetype>
          <d:displayname>Friends Address Book</d:displayname>
        </d:prop>
      </d:set>
    </d:mkcol>"""
    
    response = dav_session.request(
        "MKCOL",
        f"{server_url}/dav/{username}/friends/",
        headers=headers,
        data=body
    )
    assert response.status_code == 201


@pytest.mark.tier1
def test_carddav_put_contact(server_url, dav_session, test_user):
    """Send PUT with a valid VCARD VCF payload to contact endpoint and assert 201 Created."""
    username = test_user["username"]
    
    # Ensure collection exists
    dav_session.request("MKCOL", f"{server_url}/dav/{username}/friends/")
    
    headers = {"Content-Type": "text/vcard; charset=utf-8"}
    response = dav_session.put(
        f"{server_url}/dav/{username}/friends/contact1.vcf",
        headers=headers,
        data=VCF_PAYLOAD
    )
    assert response.status_code in (201, 204)


@pytest.mark.tier1
def test_carddav_delete_contact(server_url, dav_session, test_user):
    """Send DELETE to contact endpoint and assert 200 OK or 204 No Content."""
    username = test_user["username"]
    
    # Ensure collection and contact exist
    dav_session.request("MKCOL", f"{server_url}/dav/{username}/friends/")
    dav_session.put(
        f"{server_url}/dav/{username}/friends/contact1.vcf",
        headers={"Content-Type": "text/vcard; charset=utf-8"},
        data=VCF_PAYLOAD
    )
    
    response = dav_session.delete(f"{server_url}/dav/{username}/friends/contact1.vcf")
    assert response.status_code in (200, 204)
