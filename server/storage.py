"""
kayendar/storage.py

Filesystem-based CalDAV/CardDAV storage backend.

Structure on disk:
  data/
    users.json          (managed by auth.py)
    collections/
      <username>/
        <collection_slug>/
          .meta.json    (name, color, type: "calendar" | "addressbook")
          <uid>.ics     (calendar events)
          <uid>.vcf     (contacts)
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from dataclasses import dataclass, field
from typing import Iterator, List, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_data_dir: Optional[str] = None


def set_data_dir(path: str) -> None:
    global _data_dir
    _data_dir = path


def get_data_dir() -> str:
    if _data_dir is not None:
        return _data_dir
    return os.environ.get("KAYENDAR_DATA_DIR", "data")


def _collections_root() -> str:
    return os.path.join(get_data_dir(), "collections")


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")
_UID_RE = re.compile(r"^[a-zA-Z0-9_\-\.@]{1,128}$")

_lock = threading.Lock()


def _safe_slug(value: str) -> str:
    """Sanitize a string to a safe filesystem slug."""
    slug = re.sub(r"[^a-zA-Z0-9_\-]", "-", value)
    slug = slug.strip("-")[:64] or "default"
    return slug


def _user_dir(username: str) -> str:
    return os.path.join(_collections_root(), username)


def _collection_dir(username: str, slug: str) -> str:
    return os.path.join(_user_dir(username), slug)


def _meta_path(username: str, slug: str) -> str:
    return os.path.join(_collection_dir(username, slug), ".meta.json")


def _item_path(username: str, slug: str, filename: str) -> str:
    return os.path.join(_collection_dir(username, slug), filename)


def _validate_slug(slug: str) -> None:
    if not _SLUG_RE.match(slug):
        raise ValueError(f"Invalid collection slug: {slug!r}")
    if slug.startswith("."):
        raise ValueError("Slug cannot start with a dot")


def _validate_filename(filename: str) -> None:
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise ValueError(f"Invalid filename: {filename!r}")
    if not (filename.endswith(".ics") or filename.endswith(".vcf")):
        raise ValueError("Item filename must end in .ics or .vcf")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

COLLECTION_TYPES = {"calendar", "addressbook"}
DEFAULT_CALENDAR_COLOR = "#3B82F6"
DEFAULT_ADDRESSBOOK_COLOR = "#10B981"


@dataclass
class CollectionMeta:
    slug: str
    display_name: str
    color: str
    collection_type: str  # "calendar" | "addressbook"
    description: str = ""

    def as_dict(self) -> dict:
        return {
            "slug": self.slug,
            "display_name": self.display_name,
            "color": self.color,
            "type": self.collection_type,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CollectionMeta":
        return cls(
            slug=data["slug"],
            display_name=data.get("display_name", data["slug"]),
            color=data.get("color", DEFAULT_CALENDAR_COLOR),
            collection_type=data.get("type", "calendar"),
            description=data.get("description", ""),
        )


@dataclass
class Item:
    filename: str   # e.g. "abc123.ics"
    content: str    # raw iCal/vCard text
    etag: str       # MD5 hex of content


# ---------------------------------------------------------------------------
# Collection operations
# ---------------------------------------------------------------------------

def _read_meta(username: str, slug: str) -> Optional[CollectionMeta]:
    path = _meta_path(username, slug)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return CollectionMeta.from_dict(data)
    except Exception:
        return None


def _write_meta(username: str, meta: CollectionMeta) -> None:
    col_dir = _collection_dir(username, meta.slug)
    os.makedirs(col_dir, exist_ok=True)
    path = _meta_path(username, meta.slug)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(meta.as_dict(), f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def list_collections(username: str) -> List[CollectionMeta]:
    """Return all collections for a user."""
    user_dir = _user_dir(username)
    if not os.path.isdir(user_dir):
        return []
    results = []
    for entry in sorted(os.scandir(user_dir), key=lambda e: e.name):
        if entry.is_dir() and not entry.name.startswith("."):
            meta = _read_meta(username, entry.name)
            if meta is not None:
                results.append(meta)
    return results


def create_collection(
    username: str,
    display_name: str,
    collection_type: str,
    color: Optional[str] = None,
    description: str = "",
    slug: Optional[str] = None,
) -> CollectionMeta:
    """Create a new calendar or addressbook collection."""
    if collection_type not in COLLECTION_TYPES:
        raise ValueError(f"collection_type must be one of {COLLECTION_TYPES}")
    if color is None:
        color = DEFAULT_CALENDAR_COLOR if collection_type == "calendar" else DEFAULT_ADDRESSBOOK_COLOR

    if slug is None:
        slug = _safe_slug(display_name)

    # Ensure uniqueness
    base_slug = slug
    counter = 1
    with _lock:
        while os.path.isdir(_collection_dir(username, slug)):
            slug = f"{base_slug}-{counter}"
            counter += 1
        meta = CollectionMeta(
            slug=slug,
            display_name=display_name,
            color=color,
            collection_type=collection_type,
            description=description,
        )
        _write_meta(username, meta)

    return meta


def get_collection(username: str, slug: str) -> Optional[CollectionMeta]:
    """Retrieve metadata for a single collection."""
    _validate_slug(slug)
    return _read_meta(username, slug)


def update_collection(
    username: str,
    slug: str,
    display_name: Optional[str] = None,
    color: Optional[str] = None,
    description: Optional[str] = None,
) -> Optional[CollectionMeta]:
    """Update collection metadata. Returns None if not found."""
    _validate_slug(slug)
    with _lock:
        meta = _read_meta(username, slug)
        if meta is None:
            return None
        if display_name is not None:
            meta.display_name = display_name
        if color is not None:
            meta.color = color
        if description is not None:
            meta.description = description
        _write_meta(username, meta)
    return meta


def delete_collection(username: str, slug: str) -> bool:
    """Delete a collection and all its items. Returns True if deleted."""
    _validate_slug(slug)
    col_dir = _collection_dir(username, slug)
    if not os.path.isdir(col_dir):
        return False
    import shutil
    with _lock:
        if not os.path.isdir(col_dir):
            return False
        shutil.rmtree(col_dir)
    return True


# ---------------------------------------------------------------------------
# Item operations
# ---------------------------------------------------------------------------

import hashlib as _hashlib


def _etag(content: str) -> str:
    return _hashlib.md5(content.encode("utf-8")).hexdigest()


def list_items(username: str, slug: str) -> List[Item]:
    """Return all items in a collection."""
    _validate_slug(slug)
    col_dir = _collection_dir(username, slug)
    if not os.path.isdir(col_dir):
        return []
    items = []
    for entry in sorted(os.scandir(col_dir), key=lambda e: e.name):
        if entry.is_file() and (entry.name.endswith(".ics") or entry.name.endswith(".vcf")):
            try:
                with open(entry.path, "r", encoding="utf-8") as f:
                    content = f.read()
                items.append(Item(filename=entry.name, content=content, etag=_etag(content)))
            except Exception:
                pass
    return items


def get_item(username: str, slug: str, filename: str) -> Optional[Item]:
    """Get a single item by filename."""
    _validate_slug(slug)
    _validate_filename(filename)
    path = _item_path(username, slug, filename)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return Item(filename=filename, content=content, etag=_etag(content))


def put_item(username: str, slug: str, filename: str, content: str) -> Item:
    """Create or update an item. Collection must exist."""
    _validate_slug(slug)
    _validate_filename(filename)
    col_dir = _collection_dir(username, slug)
    if not os.path.isdir(col_dir):
        raise FileNotFoundError(f"Collection {slug!r} not found for user {username!r}")
    path = _item_path(username, slug, filename)
    tmp = path + ".tmp"
    with _lock:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    return Item(filename=filename, content=content, etag=_etag(content))


def delete_item(username: str, slug: str, filename: str) -> bool:
    """Delete an item. Returns True if deleted."""
    _validate_slug(slug)
    _validate_filename(filename)
    path = _item_path(username, slug, filename)
    with _lock:
        if os.path.isfile(path):
            os.remove(path)
            return True
    return False


# ---------------------------------------------------------------------------
# User bootstrap
# ---------------------------------------------------------------------------

def ensure_default_collections(username: str) -> None:
    """Create default calendar and addressbook for a new user if they don't exist."""
    user_dir = _user_dir(username)
    if os.path.isdir(user_dir) and os.listdir(user_dir):
        return  # already has collections

    create_collection(
        username=username,
        display_name="Personal",
        collection_type="calendar",
        color="#6366F1",
        slug="personal",
    )
    create_collection(
        username=username,
        display_name="Contacts",
        collection_type="addressbook",
        color="#10B981",
        slug="contacts",
    )


def delete_user_data(username: str) -> None:
    """Delete all collections and items for a user."""
    import shutil
    user_dir = _user_dir(username)
    if os.path.isdir(user_dir):
        shutil.rmtree(user_dir)


def get_collection_ctag(username: str, slug: str) -> str:
    """Calculate a dynamic CTag for a collection based on directory and file modification times."""
    col_dir = _collection_dir(username, slug)
    if not os.path.isdir(col_dir):
        return "0"
    try:
        mtimes = [os.path.getmtime(col_dir)]
        for entry in os.scandir(col_dir):
            if entry.is_file():
                mtimes.append(entry.stat().st_mtime)
        return str(int(sum(mtimes)))
    except Exception:
        return "1"
