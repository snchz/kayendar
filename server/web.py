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
from typing import Optional

from fastapi import APIRouter, Cookie, Form, Request, Response
from fastapi.responses import JSONResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from . import auth, storage

router = APIRouter(prefix="/api")

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

    display_name = body.get("display_name", "").strip()
    col_type = body.get("type", "calendar")
    color = body.get("color")
    description = body.get("description", "")

    if not display_name:
        return _json_error(400, "display_name is required")
    if col_type not in storage.COLLECTION_TYPES:
        return _json_error(400, f"type must be one of {list(storage.COLLECTION_TYPES)}")

    try:
        col = storage.create_collection(user, display_name, col_type, color, description)
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
async def update_collection(slug: str, request: Request) -> JSONResponse:
    user = _get_current_user(request)
    if not user:
        return _json_error(401, "Not authenticated")
    try:
        body = await request.json()
    except Exception:
        return _json_error(400, "Invalid JSON")

    col = storage.update_collection(
        user,
        slug,
        display_name=body.get("display_name"),
        color=body.get("color"),
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
    except (FileNotFoundError, ValueError) as e:
        return _json_error(409, str(e))

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
