# Project: Kayendar (CalDAV/CardDAV Server & Modern SPA Client)

## Architecture
Kayendar is a lightweight, self-contained CalDAV and CardDAV synchronization server with an integrated web SPA client.
- **Backend (Python / Starlette / Uvicorn)**:
    - High-performance asynchronous ASGI application handling WebDAV/CalDAV/CardDAV sync requests.
    - RFC 6764 CalDAV and CardDAV auto-discovery redirects (`/.well-known/caldav`, `/.well-known/carddav`) for zero-friction setup on iOS, macOS, and Android.
    - JSON-based user management with PBKDF2/argon2 password hashing stored in `data/users.json`.
    - Directory-based flat file storage for calendars and addressbooks:
      - Calendars: `data/calendars/<username>/<calendar_id>/` as individual `.ics` files.
      - Addressbooks: `data/contacts/<username>/<addressbook_id>/` as individual `.vcf` files.
    - HTTP Basic Authentication for DAV clients (iOS, Android, Thunderbird, etc.).
    - Cryptographically signed session cookie authentication for the SPA web client.
- **Frontend (HTML5 / Vanilla JS / CSS Glassmorphism SPA)**:
    - Zero-external-dependency Single Page Application with executive glassmorphic UI.
    - Ergonomic calendar navigation cluster (`[ Hoy ]` `[ ‹ ]` `[ › ]` `[ Mes/Año ]`), real-time live timeline indicator (`.now-indicator`) with pulsing beacon in Week View.
    - Consolidated Settings & Preferences modal and sleek Sidebar User Card (`🟢 En línea`, avatar, quick settings, logout).
    - Advanced contact management with multi-phone support (Mobile, Work, Home, Other), physical address with map links (`ADR`), company/organization (`ORG`), job title (`TITLE`), notes (`NOTE`), birthdays (`BDAY`), and click-to-call/email.
    - Contextual sidebar: displays calendars only in Calendar view and address books only in Contacts view, with click-to-filter address book collections.
    - Natural language "Quick Add" event parser in Spanish and English (Shortcut `Q`).
    - Inline calendar creation directly inside event creation dialogs.
    - VTODO tasks side drawer with drag-and-drop scheduling onto the calendar.
    - Public iCal token subscriptions, 1-click `.ics` calendar & `.vcf` address book export/import, and configurable week start (Monday / Sunday).
    - Bilingual live toggle (ES / EN).

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | E2E Test Suite Design | Establish test framework, design 4 tiers of E2E tests, write TEST_INFRA.md and TEST_READY.md. | None | DONE |
| M2 | Core Auth & File Storage | Implement users.json authentication, hash password storage, ICS/VCF directory layouts. | None | DONE |
| M3 | CalDAV/CardDAV Server | Implement OPTIONS, PROPFIND, REPORT, PUT, DELETE, MKCOL/MKCALENDAR, and RFC 6764 auto-discovery. | M2 | DONE |
| M4 | Web Client & Frontend SPA | Develop the modern Glassmorphism frontend UI with session auth and calendar/contact views. | M3 | DONE |
| M5 | Containerization & Integration | Dockerfile, docker-compose, and homelab stack deployment. | M4 | DONE |
| M6 | E2E & Adversarial Hardening | Pass 100% of E2E tests (107 passed), security auditor verification. | M1, M5 | DONE |
| M7 | Advanced Homelab UX & Features | NLP quick add, multi-phone vCard contacts, in-modal calendar creation, VTODO task scheduling, iCal sharing, Settings & Preferences modal, visible version/GitHub link, and strict CSS Grid column boundary handling. | M4, M6 | DONE |
| M8 | Public-Ready & Standards Polish | Executive design overhaul, full `.vcf` address book export/import, RFC 6764 auto-discovery, Omnisearch command palette (Ctrl+K), contact deduplication & fusion tool, RRULE event recurrence (🔁), and LocalStorage offline cache. | M7 | DONE |

## Interface Contracts
### Client ↔ Server DAV
- **Authentication**: HTTP Basic Auth with credentials matching `data/users.json`.
- **Endpoint `/dav/`**:
  - `OPTIONS /dav/`: Responds with headers `DAV: 1, 2, 3, addressbook, calendar-access`.
  - `PROPFIND /dav/`: Queries collections/items and DAV properties.
  - `REPORT /dav/...`: Calendar queries (`calendar-query`, `multiget`).
  - `PUT /dav/...`: Uploads or updates an event (`.ics`) or contact (`.vcf`).
  - `DELETE /dav/...`: Deletes an event or contact.
  - `MKCOL` / `MKCALENDAR /dav/...`: Creates standard addressbooks or calendar collections.

### Client ↔ Server Web API (for SPA)
- `POST /api/login`: Session cookie authentication.
- `POST /api/logout`: Discard session cookie.
- `GET /api/me`: Get current authenticated user info.
- `GET /api/collections`: List user calendars and addressbooks.
- `POST /api/collections`: Create new collection.
- `PATCH /api/collections/{slug}`: Update collection name or color.
- `DELETE /api/collections/{slug}`: Delete collection.
- `GET /api/collections/{slug}/items`: List all items with raw contents.
- `PUT /api/collections/{slug}/items/{filename}`: Save `.ics` or `.vcf`.
- `DELETE /api/collections/{slug}/items/{filename}`: Delete item.
- `GET /api/collections/{slug}/export`: Download `.ics` file.
- `POST /api/collections/{slug}/import`: Upload `.ics` file.
- `GET /api/collections/{slug}/share`: Get or generate public iCal subscription URL.
- `DELETE /api/collections/{slug}/share`: Revoke public share link.
- `GET /api/share/{token}`: Public read-only iCal calendar feed.

## Code Layout
- `server/`: Main application package.
  - `__main__.py`: CLI and Uvicorn server entry point.
  - `app.py`: ASGI application factory with routing and middleware.
  - `auth.py`: Basic Auth and session verification.
  - `dav.py`: CalDAV and CardDAV engine.
  - `storage.py`: Flat-file filesystem manager.
  - `web.py`: SPA REST API and public feeds.
  - `static/`: HTML5, CSS3, ES6 JavaScript SPA assets.
- `Dockerfile`: Production multi-stage lightweight image.
- `manage.py`: Administrative CLI for user provisioning.
- `tests/`: 105 automated unit and E2E tests (Tiers 1–4).
- `data/`: Storage directory (ignored by git, mounted as volume in Docker).
