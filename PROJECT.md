# Project: Kayendar (CalDAV/CardDAV Server & Modern SPA client)

## Architecture
Kayendar is a lightweight, self-contained CalDAV and CardDAV synchronization server with an integrated web SPA client..
- **Backend (Python)**:
  - Custom WSGI/ASGI or Flask-based application handling WebDAV/CalDAV/CardDAV sync requests.
  - JSON-based user management stored in `data/users.json`.
  - Directory-based storage for calendars and addressbooks:
    - Calendars are stored under `data/calendars/<username>/<calendar_id>/` as individual `.ics` files.
    - Addressbooks are stored under `data/contacts/<username>/<addressbook_id>/` as individual `.vcf` files.
  - Basic Authentication for DAV clients.
  - Session cookie authentication for the SPA frontend client.
- **Frontend (HTML/JS/CSS SPA)**:
  - Modern Single Page Application with premium glassmorphic UI.
  - Supports light/dark theme, transitions, monthly/weekly grid for calendar, and contacts view/form.
  - Communicates with the backend using standard web client logic or DAV endpoints.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | E2E Test Suite Design | Establish test framework, design 4 tiers of E2E tests, write TEST_INFRA.md and TEST_READY.md. | None | DONE |
| M2 | Core Auth & File Storage | Implement users.json authentication, hash password storage, ICS/VCF directory layouts. | None | IN_PROGRESS |
| M3 | CalDAV/CardDAV Server | Implement OPTIONS, PROPFIND, REPORT, PUT, DELETE, MKCOL/MKCALENDAR. | M2 | PLANNED |
| M4 | Web Client & Frontend SPA | Develop the modern Glassmorphism frontend UI with session auth and calendar/contact views. | M3 | PLANNED |
| M5 | Containerization & Integration | Dockerfile, docker-compose, and basic integration testing. | M4 | PLANNED |
| M6 | E2E & Adversarial Hardening | Pass 100% of E2E tests (M1), perform adversarial coverage verification (Tier 5). | M1, M5 | PLANNED |

## Interface Contracts
### Client ↔ Server DAV
- **Authentication**: HTTP Basic Auth with credentials matching `data/users.json`.
- **Endpoint `/dav/`**:
  - `OPTIONS /dav/`: Responds with headers `DAV: 1, 2, 3, addressbook, calendar-access`.
  - `PROPFIND /dav/`: Queries collections/items.
  - `REPORT /dav/...`: Calendar queries.
  - `PUT /dav/...`: Uploads or updates an event (`.ics`) or contact (`.vcf`).
  - `DELETE /dav/...`: Deletes an event or contact.
  - `MKCOL` / `MKCALENDAR /dav/...`: Creates standard or specialized collections.

### Client ↔ Server Web API (for SPA)
- `POST /api/auth/login`: Session cookie authentication.
- `POST /api/auth/logout`: Discard session cookie.
- `GET /api/user/me`: Get current user info.
- Web client may also use the standard `/dav/` paths using HTTP verbs to manage resources directly.

## Code Layout
- `kayendar/`: Main Python application package.
  - `__init__.py`: Package initialization.
  - `__main__.py`: Entry point for starting the server.
  - `auth.py`: Basic Auth and session authentication logic.
  - `storage.py`: Local file system interactions (`.ics` / `.vcf` reader/writer).
  - `dav.py`: CalDAV and CardDAV protocol implementation handler.
  - `web.py`: SPA endpoints, routing, and serving static assets.
  - `static/`: Contains HTML, CSS, JS files for the SPA client.
- `data/`: Storage directory (ignored by git).
- `tests/`: Test suites.
  - `e2e/`: E2E test scripts.
  - `unit/`: Unit tests.
- `Dockerfile`: Production image.
- `docker-compose.yml`: Homelab deployment compose file.
- `.gitignore`: Configured to ignore data and python cache files.
