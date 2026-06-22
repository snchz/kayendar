"""
kayendar/web.py

REST API for the web SPA (JSON over HTTP).
Handles session-based authentication (cookie) and CRUD for calendars,
addressbooks, events, and contacts.
"""

from __future__ import annotations

import json
import os
import uuid
import re
from typing import Optional

from fastapi import APIRouter, Cookie, Form, Request, Response
from fastapi.responses import JSONResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from . import auth, storage

router = APIRouter(prefix="/api")

def _validate_color(color: str) -> bool:
    if not isinstance(color, str):
        return False
    return bool(re.match(r"^#[0-9a-fA-F]{3}$|^#[0-9a-fA-F]{6}$", color))

# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

_SECRET_KEY: str = os.environ.get("KAYENDAR_SECRET_KEY", "change-me-in-production")
_SECURE_COOKIES: bool = os.environ.get("KAYENDAR_SECURE_COOKIES", "").lower() in (
    "1", "true", "yes",
)
_SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days
_SESSION_COOKIE = "kayendar_session"

_serializer: Optional[URLSafeTimedSerializer] = None


def _get_serializer() -> URLSafeTimedSerializer:
    global _serializer
    if _serializer is None:
        _serializer = URLSafeTimedSerializer(_SECRET_KEY)
    return _serializer


def _make_session_cookie(username: str) -> str:
    return _get_serializer().dumps({"user": username})


def _read_session_cookie(token: str) -> Optional[str]:
    try:
        data = _get_serializer().loads(token, max_age=_SESSION_MAX_AGE)
        return data.get("user")
    except (BadSignature, SignatureExpired, Exception):
        return None


def _get_current_user(request: Request) -> Optional[str]:
    token = request.cookies.get(_SESSION_COOKIE)
    if not token:
        return None
    return _read_session_cookie(token)


def _json_error(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": message})


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@router.post("/login")
async def login(request: Request) -> JSONResponse:
    try:
        body = await request.json()
        username = body.get("username", "")
        password = body.get("password", "")
    except Exception:
        return _json_error(400, "Invalid JSON")

    try:
        valid = auth.verify_user(username, password)
    except ValueError as e:
        return _json_error(400, str(e))

    if not valid:
        return _json_error(401, "Invalid credentials")

    # Ensure default collections exist
    storage.ensure_default_collections(username)

    token = _make_session_cookie(username)
    response = JSONResponse(content={"ok": True, "username": username})
    response.set_cookie(
        key=_SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=_SESSION_MAX_AGE,
        secure=_SECURE_COOKIES,
    )
    return response


@router.post("/logout")
async def logout() -> JSONResponse:
    response = JSONResponse(content={"ok": True})
    response.delete_cookie(_SESSION_COOKIE)
    return response


@router.get("/me")
async def me(request: Request) -> JSONResponse:
    user = _get_current_user(request)
    if not user:
        return _json_error(401, "Not authenticated")
    return JSONResponse({"username": user})


# ---------------------------------------------------------------------------
# Collection endpoints
# ---------------------------------------------------------------------------

@router.get("/collections")
async def get_collections(request: Request) -> JSONResponse:
    user = _get_current_user(request)
    if not user:
        return _json_error(401, "Not authenticated")
    cols = storage.list_collections(user)
    return JSONResponse([c.as_dict() for c in cols])


@router.post("/collections")
async def create_collection(request: Request) -> JSONResponse:
    user = _get_current_user(request)
    if not user:
        return _json_error(401, "Not authenticated")
    try:
        body = await request.json()
    except Exception:
        return _json_error(400, "Invalid JSON")

    body_display_name = body.get("display_name")
    if body_display_name is not None:
        display_name = body_display_name.strip()
        slug = body.get("slug")
    else:
        title = body.get("title")
        val_id = body.get("id")
        if title is None or val_id is None:
            return _json_error(400, "title and id/slug are required")
        display_name = str(title).strip()
        slug = str(val_id).strip()

    col_type = body.get("type")
    if not col_type:
        return _json_error(400, "type is required")
    if col_type not in storage.COLLECTION_TYPES:
        return _json_error(400, f"type must be one of {list(storage.COLLECTION_TYPES)}")

    color = body.get("color")
    if color is not None and not _validate_color(color):
        return _json_error(400, "Invalid color format")
    description = body.get("description", "")

    try:
        col = storage.create_collection(user, display_name, col_type, color, description, slug=slug)
    except ValueError as e:
        return _json_error(400, str(e))
    return JSONResponse(col.as_dict(), status_code=201)


@router.get("/collections/{slug}")
async def get_collection(slug: str, request: Request) -> JSONResponse:
    user = _get_current_user(request)
    if not user:
        return _json_error(401, "Not authenticated")
    col = storage.get_collection(user, slug)
    if col is None:
        return _json_error(404, "Collection not found")
    return JSONResponse(col.as_dict())


@router.patch("/collections/{slug}")
@router.put("/collections/{slug}")
async def update_collection(slug: str, request: Request) -> JSONResponse:
    user = _get_current_user(request)
    if not user:
        return _json_error(401, "Not authenticated")
    try:
        body = await request.json()
    except Exception:
        return _json_error(400, "Invalid JSON")

    display_name = body.get("display_name") or body.get("title")
    if display_name is not None:
        display_name = display_name.strip()
        if not display_name:
            return _json_error(400, "title/display_name cannot be empty")

    color = body.get("color")
    if color is not None and not _validate_color(color):
        return _json_error(400, "Invalid color format")

    col = storage.update_collection(
        user,
        slug,
        display_name=display_name,
        color=color,
        description=body.get("description"),
    )
    if col is None:
        return _json_error(404, "Collection not found")
    return JSONResponse(col.as_dict())


@router.delete("/collections/{slug}")
async def delete_collection(slug: str, request: Request) -> JSONResponse:
    user = _get_current_user(request)
    if not user:
        return _json_error(401, "Not authenticated")
    deleted = storage.delete_collection(user, slug)
    if not deleted:
        return _json_error(404, "Collection not found")
    return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# Item endpoints (events & contacts)
# ---------------------------------------------------------------------------

@router.get("/collections/{slug}/items")
async def list_items(slug: str, request: Request) -> JSONResponse:
    user = _get_current_user(request)
    if not user:
        return _json_error(401, "Not authenticated")
    col = storage.get_collection(user, slug)
    if col is None:
        return _json_error(404, "Collection not found")
    items = storage.list_items(user, slug)
    return JSONResponse([
        {"filename": i.filename, "etag": i.etag, "content": i.content}
        for i in items
    ])


@router.get("/collections/{slug}/items/{filename}")
async def get_item(slug: str, filename: str, request: Request) -> JSONResponse:
    user = _get_current_user(request)
    if not user:
        return _json_error(401, "Not authenticated")
    item = storage.get_item(user, slug, filename)
    if item is None:
        return _json_error(404, "Item not found")
    return JSONResponse({"filename": item.filename, "etag": item.etag, "content": item.content})


@router.put("/collections/{slug}/items/{filename}")
async def put_item(slug: str, filename: str, request: Request) -> JSONResponse:
    user = _get_current_user(request)
    if not user:
        return _json_error(401, "Not authenticated")
    try:
        body = await request.json()
        content = body.get("content", "")
    except Exception:
        return _json_error(400, "Invalid JSON")

    try:
        item = storage.put_item(user, slug, filename, content)
    except FileNotFoundError as e:
        return _json_error(409, str(e))
    except ValueError as e:
        return _json_error(400, str(e))

    return JSONResponse({"filename": item.filename, "etag": item.etag}, status_code=201)


@router.delete("/collections/{slug}/items/{filename}")
async def delete_item(slug: str, filename: str, request: Request) -> JSONResponse:
    user = _get_current_user(request)
    if not user:
        return _json_error(401, "Not authenticated")
    deleted = storage.delete_item(user, slug, filename)
    if not deleted:
        return _json_error(404, "Item not found")
    return JSONResponse({"ok": True})


@router.get("/dashboard/stats")
async def get_dashboard_stats(request: Request) -> JSONResponse:
    user = _get_current_user(request)
    if not user:
        return _json_error(401, "Not authenticated")
    
    cols = storage.list_collections(user)
    
    events_count = 0
    contacts_count = 0
    collections_count = 0
    
    for col in cols:
        items = storage.list_items(user, col.slug)
        items_count = len(items)
        if col.collection_type == "calendar":
            events_count += items_count
        elif col.collection_type == "addressbook":
            contacts_count += items_count
            
        # Count the collection in stats if it's not one of the default empty collections
        if col.slug not in ("personal", "contacts") or items_count > 0:
            collections_count += 1
            
    return JSONResponse({
        "collections_count": collections_count,
        "events_count": events_count,
        "contacts_count": contacts_count
    })

