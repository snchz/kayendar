"""
kayendar/dav.py

CalDAV and CardDAV protocol handler.
Mounts under /dav/ and implements the WebDAV methods required for
synchronisation with iOS, Thunderbird, DAVx⁵ and other clients.

Supported methods:
  OPTIONS, PROPFIND, REPORT, GET, PUT, DELETE, MKCOL / MKCALENDAR
"""

from __future__ import annotations

import base64
import textwrap
import xml.etree.ElementTree as ET
from typing import Optional, Tuple
from urllib.parse import unquote

from fastapi import APIRouter, Request, Response
from fastapi.responses import PlainTextResponse

from . import auth, storage

# ---------------------------------------------------------------------------
# Namespace map
# ---------------------------------------------------------------------------

NS = {
    "D": "DAV:",
    "C": "urn:ietf:params:xml:ns:caldav",
    "CR": "urn:ietf:params:xml:ns:carddav",
    "CS": "http://calendarserver.org/ns/",
    "ICAL": "http://apple.com/ns/ical/",
}

for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)


def _ns(prefix: str, tag: str) -> str:
    return f"{{{NS[prefix]}}}{tag}"


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter()

DAV_HEADER = "1, 2, 3, addressbook, calendar-access"
ALLOW_HEADER = "OPTIONS, PROPFIND, REPORT, GET, HEAD, PUT, DELETE, MKCOL, MKCALENDAR"


# ---------------------------------------------------------------------------
# Authentication helper
# ---------------------------------------------------------------------------

def _authenticate(request: Request) -> Optional[str]:
    """Return username if Basic Auth credentials are valid, else None."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.lower().startswith("basic "):
        return None
    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        username, _, password = decoded.partition(":")
        if auth.verify_user(username, password):
            return username
    except Exception:
        pass
    return None


def _require_auth(request: Request) -> Tuple[Optional[str], Optional[Response]]:
    username = _authenticate(request)
    if username is None:
        return None, Response(
            status_code=401,
            headers={
                "WWW-Authenticate": 'Basic realm="Kayendar"',
                "DAV": DAV_HEADER,
            },
        )
    return username, None


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def _xml_response(body: str, status: int = 207) -> Response:
    return Response(
        content=body,
        status_code=status,
        media_type="application/xml; charset=utf-8",
        headers={"DAV": DAV_HEADER},
    )


def _multistatus(*responses: ET.Element) -> str:
    ms = ET.Element(_ns("D", "multistatus"))
    for r in responses:
        ms.append(r)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(ms, encoding="unicode")


def _propfind_response(href: str, props: dict, missing: list | None = None) -> ET.Element:
    """Build a <D:response> element for a single resource."""
    resp = ET.Element(_ns("D", "response"))
    ET.SubElement(resp, _ns("D", "href")).text = href

    if props:
        propstat_ok = ET.SubElement(resp, _ns("D", "propstat"))
        prop_el = ET.SubElement(propstat_ok, _ns("D", "prop"))
        for tag, value in props.items():
            el = ET.SubElement(prop_el, tag)
            if isinstance(value, str):
                el.text = value
            elif isinstance(value, list):
                for child in value:
                    if isinstance(child, ET.Element):
                        el.append(child)
                    else:
                        ET.SubElement(el, child)
            elif isinstance(value, ET.Element):
                el.append(value)
        ET.SubElement(propstat_ok, _ns("D", "status")).text = "HTTP/1.1 200 OK"

    if missing:
        propstat_404 = ET.SubElement(resp, _ns("D", "propstat"))
        prop_el = ET.SubElement(propstat_404, _ns("D", "prop"))
        for tag in missing:
            ET.SubElement(prop_el, tag)
        ET.SubElement(propstat_404, _ns("D", "status")).text = "HTTP/1.1 404 Not Found"

    return resp


# ---------------------------------------------------------------------------
# Resource type helpers
# ---------------------------------------------------------------------------

def _collection_resourcetype(col_type: str) -> ET.Element:
    rt = ET.Element(_ns("D", "resourcetype"))
    ET.SubElement(rt, _ns("D", "collection"))
    if col_type == "calendar":
        ET.SubElement(rt, _ns("C", "calendar"))
    else:
        ET.SubElement(rt, _ns("CR", "addressbook"))
    return rt


def _principal_resourcetype() -> ET.Element:
    rt = ET.Element(_ns("D", "resourcetype"))
    ET.SubElement(rt, _ns("D", "collection"))
    ET.SubElement(rt, _ns("D", "principal"))
    return rt


def _parse_depth(request: Request) -> str:
    return request.headers.get("Depth", "1")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

# OPTIONS — discovery
@router.options("/{path:path}")
async def dav_options(path: str, request: Request) -> Response:
    return Response(
        status_code=200,
        headers={
            "DAV": DAV_HEADER,
            "Allow": ALLOW_HEADER,
            "Content-Length": "0",
        },
    )


# PROPFIND — property discovery
@router.api_route("/{path:path}", methods=["PROPFIND"])
async def dav_propfind(path: str, request: Request) -> Response:
    username, err = _require_auth(request)
    if err:
        return err

    depth = _parse_depth(request)
    parts = [p for p in path.strip("/").split("/") if p]
    # parts: [] = root, [username] = principal, [username, slug] = collection,
    #              [username, slug, filename] = item

    # --- root ---
    if not parts:
        user_principal = f"/dav/{username}/"
        responses = [_propfind_response(
            "/dav/",
            {_ns("D", "resourcetype"): _principal_resourcetype(),
             _ns("D", "displayname"): "Kayendar",
             _ns("D", "current-user-principal"): user_principal},
        )]
        if depth != "0":
            cal_home = ET.Element(_ns("D", "href"))
            cal_home.text = user_principal
            card_home = ET.Element(_ns("D", "href"))
            card_home.text = user_principal
            responses.append(_propfind_response(
                user_principal,
                {_ns("D", "resourcetype"): _principal_resourcetype(),
                 _ns("D", "displayname"): username,
                 _ns("D", "current-user-principal"): user_principal,
                 _ns("C", "calendar-home-set"): cal_home,
                 _ns("CR", "addressbook-home-set"): card_home},
            ))
        return _xml_response(_multistatus(*responses))

    # --- principal (username) ---
    if len(parts) == 1:
        uname = parts[0]
        if uname != username:
            return Response(status_code=403, headers={"DAV": DAV_HEADER})
        
        cal_home = ET.Element(_ns("D", "href"))
        cal_home.text = f"/dav/{uname}/"
        
        card_home = ET.Element(_ns("D", "href"))
        card_home.text = f"/dav/{uname}/"
        
        responses = [_propfind_response(
            f"/dav/{uname}/",
            {_ns("D", "resourcetype"): _principal_resourcetype(),
             _ns("D", "displayname"): uname,
             _ns("D", "current-user-principal"): f"/dav/{uname}/",
             _ns("C", "calendar-home-set"): cal_home,
             _ns("CR", "addressbook-home-set"): card_home},
        )]
        if depth != "0":
            for col in storage.list_collections(uname):
                responses.append(_collection_propfind_response(uname, col))
        return _xml_response(_multistatus(*responses))

    # --- collection ---
    if len(parts) == 2:
        uname, slug = parts
        if uname != username:
            return Response(status_code=403, headers={"DAV": DAV_HEADER})
        col = storage.get_collection(uname, slug)
        if col is None:
            return Response(status_code=404, headers={"DAV": DAV_HEADER})
        responses = [_collection_propfind_response(uname, col)]
        if depth != "0":
            for item in storage.list_items(uname, slug):
                responses.append(_item_propfind_response(uname, slug, item))
        return _xml_response(_multistatus(*responses))

    # --- item ---
    if len(parts) == 3:
        uname, slug, filename = parts
        if uname != username:
            return Response(status_code=403, headers={"DAV": DAV_HEADER})
        item = storage.get_item(uname, slug, filename)
        if item is None:
            return Response(status_code=404, headers={"DAV": DAV_HEADER})
        return _xml_response(_multistatus(_item_propfind_response(uname, slug, item)))

    return Response(status_code=404, headers={"DAV": DAV_HEADER})


def _collection_propfind_response(username: str, col: storage.CollectionMeta) -> ET.Element:
    rt = _collection_resourcetype(col.collection_type)
    props = {
        _ns("D", "resourcetype"): rt,
        _ns("D", "displayname"): col.display_name,
        _ns("D", "getetag"): col.slug,
    }
    if col.collection_type == "calendar":
        props[_ns("C", "calendar-color")] = col.color
        props[_ns("ICAL", "calendar-color")] = col.color
        props[_ns("C", "supported-calendar-component-set")] = [
            ET.Element(_ns("C", "comp"), attrib={"name": "VEVENT"}),
            ET.Element(_ns("C", "comp"), attrib={"name": "VTODO"}),
        ]
    else:
        props[_ns("CR", "addressbook-description")] = col.description
    return _propfind_response(f"/dav/{username}/{col.slug}/", props)


def _item_propfind_response(username: str, slug: str, item: storage.Item) -> ET.Element:
    props = {
        _ns("D", "getetag"): f'"{item.etag}"',
        _ns("D", "getcontenttype"): (
            "text/calendar; charset=utf-8" if item.filename.endswith(".ics")
            else "text/vcard; charset=utf-8"
        ),
    }
    return _propfind_response(f"/dav/{username}/{slug}/{item.filename}", props)


# GET / HEAD — retrieve item
@router.api_route("/{path:path}", methods=["GET", "HEAD"])
async def dav_get(path: str, request: Request) -> Response:
    username, err = _require_auth(request)
    if err:
        return err

    parts = [p for p in path.strip("/").split("/") if p]
    if len(parts) != 3:
        return Response(status_code=404, headers={"DAV": DAV_HEADER})

    uname, slug, filename = parts
    if uname != username:
        return Response(status_code=403, headers={"DAV": DAV_HEADER})

    item = storage.get_item(uname, slug, filename)
    if item is None:
        return Response(status_code=404, headers={"DAV": DAV_HEADER})

    content_type = (
        "text/calendar; charset=utf-8"
        if filename.endswith(".ics")
        else "text/vcard; charset=utf-8"
    )
    return Response(
        content=item.content if request.method == "GET" else "",
        status_code=200,
        media_type=content_type,
        headers={
            "ETag": f'"{item.etag}"',
            "DAV": DAV_HEADER,
        },
    )


# PUT — create/update item
@router.put("/{path:path}")
async def dav_put(path: str, request: Request) -> Response:
    username, err = _require_auth(request)
    if err:
        return err

    parts = [p for p in path.strip("/").split("/") if p]
    if len(parts) != 3:
        return Response(status_code=400, headers={"DAV": DAV_HEADER})

    uname, slug, filename = parts
    if uname != username:
        return Response(status_code=403, headers={"DAV": DAV_HEADER})

    try:
        content = (await request.body()).decode("utf-8")
    except Exception:
        return Response(status_code=400, headers={"DAV": DAV_HEADER})

    try:
        item = storage.put_item(uname, slug, filename, content)
    except (FileNotFoundError, ValueError) as exc:
        return Response(status_code=409, content=str(exc), headers={"DAV": DAV_HEADER})

    return Response(
        status_code=201,
        headers={"ETag": f'"{item.etag}"', "DAV": DAV_HEADER},
    )


# DELETE — remove item or collection
@router.delete("/{path:path}")
async def dav_delete(path: str, request: Request) -> Response:
    username, err = _require_auth(request)
    if err:
        return err

    parts = [p for p in path.strip("/").split("/") if p]

    if len(parts) == 2:
        uname, slug = parts
        if uname != username:
            return Response(status_code=403, headers={"DAV": DAV_HEADER})
        deleted = storage.delete_collection(uname, slug)
        return Response(status_code=204 if deleted else 404, headers={"DAV": DAV_HEADER})

    if len(parts) == 3:
        uname, slug, filename = parts
        if uname != username:
            return Response(status_code=403, headers={"DAV": DAV_HEADER})
        deleted = storage.delete_item(uname, slug, filename)
        return Response(status_code=204 if deleted else 404, headers={"DAV": DAV_HEADER})

    return Response(status_code=400, headers={"DAV": DAV_HEADER})


# MKCOL / MKCALENDAR — create collection
@router.api_route("/{path:path}", methods=["MKCOL", "MKCALENDAR"])
async def dav_mkcol(path: str, request: Request) -> Response:
    username, err = _require_auth(request)
    if err:
        return err

    parts = [p for p in path.strip("/").split("/") if p]
    if len(parts) != 2:
        return Response(status_code=409, headers={"DAV": DAV_HEADER})

    uname, slug = parts
    if uname != username:
        return Response(status_code=403, headers={"DAV": DAV_HEADER})

    col_type = "calendar" if request.method == "MKCALENDAR" else "addressbook"
    display_name = slug

    # Try to parse MKCALENDAR XML for display name / color
    try:
        body = await request.body()
        if body:
            root = ET.fromstring(body)
            dn_el = root.find(".//" + _ns("D", "displayname"))
            if dn_el is not None and dn_el.text:
                display_name = dn_el.text
    except Exception:
        pass

    try:
        col = storage.create_collection(
            username=uname,
            display_name=display_name,
            collection_type=col_type,
            slug=slug,
        )
    except Exception as exc:
        return Response(status_code=409, content=str(exc), headers={"DAV": DAV_HEADER})

    return Response(status_code=201, headers={"DAV": DAV_HEADER})


# REPORT — calendar/addressbook queries
@router.api_route("/{path:path}", methods=["REPORT"])
async def dav_report(path: str, request: Request) -> Response:
    username, err = _require_auth(request)
    if err:
        return err

    parts = [p for p in path.strip("/").split("/") if p]
    if len(parts) != 2:
        return Response(status_code=400, headers={"DAV": DAV_HEADER})

    uname, slug = parts
    if uname != username:
        return Response(status_code=403, headers={"DAV": DAV_HEADER})

    col = storage.get_collection(uname, slug)
    if col is None:
        return Response(status_code=404, headers={"DAV": DAV_HEADER})

    try:
        body = await request.body()
        root = ET.fromstring(body)
    except Exception:
        return Response(status_code=400, headers={"DAV": DAV_HEADER})

    # calendar-multiget / addressbook-multiget: return specific hrefs
    tag = root.tag
    if tag in (
        _ns("C", "calendar-multiget"),
        _ns("CR", "addressbook-multiget"),
    ):
        href_els = root.findall(_ns("D", "href"))
        hrefs = {el.text for el in href_els if el.text}
        responses = []
        for item in storage.list_items(uname, slug):
            href = f"/dav/{uname}/{slug}/{item.filename}"
            if href in hrefs or not hrefs:
                content_type = (
                    "text/calendar; charset=utf-8"
                    if item.filename.endswith(".ics")
                    else "text/vcard; charset=utf-8"
                )
                props = {
                    _ns("D", "getetag"): f'"{item.etag}"',
                    _ns("D", "getcontenttype"): content_type,
                }
                if col.collection_type == "calendar":
                    props[_ns("C", "calendar-data")] = item.content
                else:
                    props[_ns("CR", "address-data")] = item.content
                responses.append(_propfind_response(href, props))
        return _xml_response(_multistatus(*responses))

    # calendar-query: return all items (simplified — no filter evaluation)
    if tag == _ns("C", "calendar-query"):
        responses = []
        for item in storage.list_items(uname, slug):
            href = f"/dav/{uname}/{slug}/{item.filename}"
            responses.append(_propfind_response(href, {
                _ns("D", "getetag"): f'"{item.etag}"',
                _ns("C", "calendar-data"): item.content,
            }))
        return _xml_response(_multistatus(*responses))

    return Response(status_code=422, headers={"DAV": DAV_HEADER})
