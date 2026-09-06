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

import hashlib
import json
import os
import re
import secrets
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Iterator, List, Optional

from .config import settings

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
    return str(settings.data_dir)


def _collections_root() -> str:
    return os.path.join(get_data_dir(), "collections")


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"^[a-zA-Z0-9_\-\.\s%!@#$&'()+,;=\[\]]{1,128}$")
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
    if not slug or len(slug) > 128:
        raise ValueError(f"Invalid collection slug length: {slug!r}")
    if slug.startswith("."):
        raise ValueError("Slug cannot start with a dot")
    if ".." in slug or "/" in slug or "\\" in slug:
        raise ValueError("Slug cannot contain traversal characters")
    if not _SLUG_RE.match(slug):
        raise ValueError(f"Invalid collection slug: {slug!r}")


def _validate_filename(filename: str) -> None:
    if "/" in filename or "\\" in filename or filename.startswith(".") or ".." in filename:
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
    ctag: int = 1

    def as_dict(self) -> dict:
        return {
            "slug": self.slug,
            "id": self.slug,
            "display_name": self.display_name,
            "title": self.display_name,
            "color": self.color,
            "type": self.collection_type,
            "description": self.description,
            "ctag": self.ctag,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CollectionMeta":
        return cls(
            slug=data["slug"],
            display_name=data.get("display_name", data["slug"]),
            color=data.get("color", DEFAULT_CALENDAR_COLOR),
            collection_type=data.get("type", "calendar"),
            description=data.get("description", ""),
            ctag=data.get("ctag", 1),
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

    if slug is not None:
        _validate_slug(slug)
    else:
        slug = _safe_slug(display_name)

    # Ensure uniqueness by auto-renaming
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
    with _lock:
        if not os.path.isdir(col_dir):
            return False
        shutil.rmtree(col_dir)
    return True


# ---------------------------------------------------------------------------
# Item operations
# ---------------------------------------------------------------------------

def _etag(content: str) -> str:
    return hashlib.md5(content.encode("utf-8"), usedforsecurity=False).hexdigest()


# ETag Caching helpers
def _get_cache_path(username: str, slug: str) -> str:
    return os.path.join(_collection_dir(username, slug), ".cache.json")


def _load_cache(username: str, slug: str) -> dict:
    path = _get_cache_path(username, slug)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_cache(username: str, slug: str, cache: dict) -> None:
    path = _get_cache_path(username, slug)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass


@dataclass
class ItemMeta:
    filename: str
    etag: str
    size: int


def _scan_entries(username: str, slug: str, load_content: bool = False) -> list[tuple[str, str, int, Optional[str]]]:
    """Scan collection directory, calculate/cache ETags, and optionally load file content."""
    _validate_slug(slug)
    col_dir = _collection_dir(username, slug)
    if not os.path.isdir(col_dir):
        return []
    cache = _load_cache(username, slug)
    cache_changed = False
    results: list[tuple[str, str, int, Optional[str]]] = []
    for entry in sorted(os.scandir(col_dir), key=lambda e: e.name):
        if entry.is_file() and (entry.name.endswith(".ics") or entry.name.endswith(".vcf")):
            try:
                stat = entry.stat()
                mtime = stat.st_mtime
                size = stat.st_size
                content: Optional[str] = None
                cached = cache.get(entry.name)
                if cached and cached.get("mtime") == mtime and cached.get("size") == size:
                    etag = cached["etag"]
                    if load_content:
                        with open(entry.path, "r", encoding="utf-8") as f:
                            content = f.read()
                else:
                    with open(entry.path, "r", encoding="utf-8") as f:
                        content = f.read()
                    etag = _etag(content)
                    cache[entry.name] = {
                        "etag": etag,
                        "size": size,
                        "mtime": mtime,
                    }
                    cache_changed = True
                results.append((entry.name, etag, size, content))
            except Exception:
                pass
    if cache_changed:
        _write_cache(username, slug, cache)
    return results


def list_items_meta(username: str, slug: str) -> List[ItemMeta]:
    """Return only metadata (filename, etag, size) for all items, utilizing cache."""
    entries = _scan_entries(username, slug, load_content=False)
    return [ItemMeta(filename=name, etag=etag, size=size) for name, etag, size, _ in entries]


def _validate_ics(content: str) -> None:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Empty ICS content")
    if not any(line.startswith("BEGIN:VCALENDAR") for line in lines):
        raise ValueError("Missing BEGIN:VCALENDAR")
    if not any(line.startswith("END:VCALENDAR") for line in lines):
        raise ValueError("Missing END:VCALENDAR")
    
    has_component = False
    in_event = False
    in_todo = False
    for line in lines:
        if line.startswith("BEGIN:VEVENT"):
            in_event = True
        elif line.startswith("END:VEVENT"):
            if not in_event:
                raise ValueError("END:VEVENT without BEGIN:VEVENT")
            in_event = False
            has_component = True
        elif line.startswith("BEGIN:VTODO"):
            in_todo = True
        elif line.startswith("END:VTODO"):
            if not in_todo:
                raise ValueError("END:VTODO without BEGIN:VTODO")
            in_todo = False
            has_component = True
            
    if in_event or in_todo:
        raise ValueError("Unclosed VEVENT or VTODO component")
    if not has_component:
        raise ValueError("Missing VEVENT or VTODO component")


def _validate_vcf(content: str) -> None:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Empty VCF content")
    if not any(line.startswith("BEGIN:VCARD") for line in lines):
        raise ValueError("Missing BEGIN:VCARD")
    if not any(line.startswith("END:VCARD") for line in lines):
        raise ValueError("Missing END:VCARD")
        
    in_vcard = False
    has_fn = False
    for line in lines:
        if line.startswith("BEGIN:VCARD"):
            in_vcard = True
        elif line.startswith("END:VCARD"):
            if not in_vcard:
                raise ValueError("END:VCARD without BEGIN:VCARD")
            in_vcard = False
        elif line.startswith("FN:") or line.startswith("FN;"):
            has_fn = True
            
    if in_vcard:
        raise ValueError("Unclosed VCARD")
    if not has_fn:
        raise ValueError("Missing FN (Formatted Name) property")


def list_items(username: str, slug: str) -> List[Item]:
    """Return all items in a collection, utilizing cache for ETags."""
    entries = _scan_entries(username, slug, load_content=True)
    return [Item(filename=name, content=content or "", etag=etag) for name, etag, _, content in entries]


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
    
    # Validate content
    if filename.endswith(".ics"):
        _validate_ics(content)
    elif filename.endswith(".vcf"):
        _validate_vcf(content)
        
    col_dir = _collection_dir(username, slug)
    if not os.path.isdir(col_dir):
        raise FileNotFoundError(f"Collection {slug!r} not found for user {username!r}")
    path = _item_path(username, slug, filename)
    tmp = path + ".tmp"
    with _lock:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
        
        # Increment CTag
        meta = _read_meta(username, slug)
        if meta:
            meta.ctag += 1
            _write_meta(username, meta)
            
    return Item(filename=filename, content=content, etag=_etag(content))


def delete_item(username: str, slug: str, filename: str) -> bool:
    """Delete an item. Returns True if deleted."""
    _validate_slug(slug)
    _validate_filename(filename)
    path = _item_path(username, slug, filename)
    with _lock:
        if os.path.isfile(path):
            os.remove(path)
            
            # Increment CTag
            meta = _read_meta(username, slug)
            if meta:
                meta.ctag += 1
                _write_meta(username, meta)
                
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
    user_dir = _user_dir(username)
    if os.path.isdir(user_dir):
        shutil.rmtree(user_dir)


def get_collection_ctag(username: str, slug: str) -> str:
    """Retrieve CTag directly from collection meta."""
    meta = _read_meta(username, slug)
    if meta:
        return str(meta.ctag)
    return "0"


# ---------------------------------------------------------------------------
# Shares & Export/Import
# ---------------------------------------------------------------------------

def _shares_path() -> str:
    return os.path.join(get_data_dir(), "shares.json")


def _load_shares() -> dict:
    path = _shares_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_shares(shares: dict) -> None:
    path = _shares_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(shares, f, indent=2)
    os.replace(tmp, path)


def get_collection_share(username: str, slug: str) -> Optional[dict]:
    _validate_slug(slug)
    shares = _load_shares()
    for token, info in shares.items():
        if info.get("username") == username and info.get("slug") == slug:
            return {"token": token, **info}
    return None


def create_collection_share(username: str, slug: str) -> dict:
    _validate_slug(slug)
    with _lock:
        shares = _load_shares()
        for token in list(shares.keys()):
            if shares[token].get("username") == username and shares[token].get("slug") == slug:
                del shares[token]
        token = secrets.token_urlsafe(16)
        shares[token] = {
            "username": username,
            "slug": slug,
            "created_at": time.time(),
        }
        _save_shares(shares)
    return {"token": token, "username": username, "slug": slug}


def revoke_collection_share(username: str, slug: str) -> bool:
    _validate_slug(slug)
    with _lock:
        shares = _load_shares()
        found = False
        for token in list(shares.keys()):
            if shares[token].get("username") == username and shares[token].get("slug") == slug:
                del shares[token]
                found = True
        if found:
            _save_shares(shares)
    return found


def get_share_by_token(token: str) -> Optional[dict]:
    if not token or not re.match(r"^[a-zA-Z0-9_\-]+$", token):
        return None
    shares = _load_shares()
    return shares.get(token)


def export_collection_ics(username: str, slug: str) -> str:
    """Combine all events and tasks of a collection into a single valid iCalendar text."""
    _validate_slug(slug)
    meta = get_collection(username, slug)
    display_name = meta.display_name if meta else slug
    items = list_items(username, slug)

    components: list[str] = []
    for item in items:
        if not item.filename.endswith(".ics"):
            continue
        lines = item.content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        in_comp = False
        comp_lines: list[str] = []
        for line in lines:
            if line.startswith("BEGIN:VEVENT") or line.startswith("BEGIN:VTODO"):
                in_comp = True
                comp_lines = [line]
            elif in_comp:
                comp_lines.append(line)
                if line.startswith("END:VEVENT") or line.startswith("END:VTODO"):
                    in_comp = False
                    components.append("\r\n".join(comp_lines))

    header = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Kayendar//EN",
        f"X-WR-CALNAME:{display_name}",
    ]
    footer = ["END:VCALENDAR", ""]
    return "\r\n".join(header) + "\r\n" + "\r\n".join(components) + "\r\n" + "\r\n".join(footer)


def import_collection_ics(username: str, slug: str, raw_ics: str) -> int:
    """Parse raw iCalendar text and import each VEVENT and VTODO as an individual item."""
    _validate_slug(slug)
    lines = raw_ics.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    in_comp = False
    comp_lines: list[str] = []
    imported_count = 0

    for line in lines:
        if line.startswith("BEGIN:VEVENT") or line.startswith("BEGIN:VTODO"):
            in_comp = True
            comp_lines = [line]
        elif in_comp:
            comp_lines.append(line)
            if line.startswith("END:VEVENT") or line.startswith("END:VTODO"):
                in_comp = False
                uid: Optional[str] = None
                for cline in comp_lines:
                    if cline.startswith("UID:"):
                        uid = cline[4:].strip()
                        break
                if not uid:
                    uid = str(uuid.uuid4())
                safe_uid = re.sub(r"[^a-zA-Z0-9_\-\.@]", "-", uid)[:64]
                filename = f"{safe_uid}.ics"

                item_content = (
                    "BEGIN:VCALENDAR\r\n"
                    "VERSION:2.0\r\n"
                    "PRODID:-//Kayendar//EN\r\n"
                    + "\r\n".join(comp_lines)
                    + "\r\nEND:VCALENDAR\r\n"
                )
                try:
                    put_item(username, slug, filename, item_content)
                    imported_count += 1
                except Exception:
                    pass
    return imported_count


def export_collection_vcf(username: str, slug: str) -> str:
    """Combine all contacts of an addressbook collection into a single multi-vCard text."""
    _validate_slug(slug)
    items = list_items(username, slug)
    cards: list[str] = []
    for item in items:
        if not item.filename.endswith(".vcf"):
            continue
        cleaned = item.content.strip()
        if cleaned:
            cards.append(cleaned)
    return "\r\n".join(cards) + ("\r\n" if cards else "")


def import_collection_vcf(username: str, slug: str, raw_vcf: str) -> int:
    """Parse raw vCard text and import each VCARD component as an individual item."""
    _validate_slug(slug)
    lines = raw_vcf.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    in_vcard = False
    card_lines: list[str] = []
    imported_count = 0

    for line in lines:
        if line.startswith("BEGIN:VCARD"):
            in_vcard = True
            card_lines = [line]
        elif in_vcard:
            card_lines.append(line)
            if line.startswith("END:VCARD"):
                in_vcard = False
                uid: Optional[str] = None
                for cline in card_lines:
                    if cline.startswith("UID:"):
                        uid = cline[4:].strip()
                        break
                if not uid:
                    uid = str(uuid.uuid4())
                safe_uid = re.sub(r"[^a-zA-Z0-9_\-\.@]", "-", uid)[:64]
                filename = f"{safe_uid}.vcf"
                item_content = "\r\n".join(card_lines) + "\r\n"
                try:
                    put_item(username, slug, filename, item_content)
                    imported_count += 1
                except Exception:
                    pass
    return imported_count

