# TEST_INFRA.md — Kayendar E2E Testing Infrastructure

This document defines the architecture, design, and execution guidelines for the End-to-End (E2E) testing suite of Kayendar.

---

## 1. Test Architecture & Design

The E2E test suite is designed as an independent, opaque-box testing system. It communicates with the Kayendar server solely via its external HTTP, CalDAV, CardDAV, and Web API interfaces.

### Target Server URL
- **Local Dev / Test Run**: `http://localhost:8000` (or dynamically allocated port by the test runner)
- **Container / Production Verification**: Configurable via the `KAYENDAR_TEST_URL` environment variable.

### Directory Layout
The test suite is located in `tests/e2e/`:

```
tests/e2e/
├── conftest.py                   # Pytest shared fixtures (server startup, client setup, user lifecycle)
├── pytest.ini                    # Pytest configuration, custom markers, and options
├── requirements.txt              # Test suite dependencies
├── helpers/                      # Reusable utilities and client wrappers
│   ├── __init__.py
│   ├── dav_client.py             # Custom client wrapping WebDAV protocol (PROPFIND, PUT, DELETE, etc.)
│   ├── user_manager.py           # Handles test user database writes & backups
│   └── test_data.py              # ICS and VCF file templates/generators
├── tier1_feature_coverage/       # Happy-path verification (>=5 tests per feature)
│   ├── __init__.py
│   ├── test_auth.py
│   ├── test_caldav.py
│   ├── test_carddav.py
│   ├── test_storage.py
│   └── test_spa.py
├── tier2_boundary_corner/        # Edge cases, large payloads, malformed inputs
│   ├── __init__.py
│   ├── test_auth_boundary.py
│   ├── test_dav_boundary.py
│   ├── test_storage_boundary.py
│   └── test_spa_boundary.py
├── tier3_cross_feature/          # Multi-client/interface interactions (pairwise)
│   ├── __init__.py
│   └── test_cross_feature.py
└── tier4_homelab_scenarios/      # Complex multi-user journeys & deployment state tests
    ├── __init__.py
    └── test_homelab_scenarios.py
```

---

## 2. Test Execution Tiers

Tests are tagged with custom Pytest markers representing their verification depth:

| Tier | Name | Target Coverage | Execution Commands |
|---|---|---|---|
| **Tier 1** | Feature Coverage | Happy-path validation of all core functional components (>=5 per feature). | `pytest -m tier1` |
| **Tier 2** | Boundary & Corners | Edge cases, path traversal attempts, large payloads, and input validation. | `pytest -m tier2` |
| **Tier 3** | Cross-Feature | Pairwise interactions (e.g. WebDAV writes -> SPA reads; SPA edits -> WebDAV syncs). | `pytest -m tier3` |
| **Tier 4** | Homelab Scenarios | High-fidelity simulations: client sync loops, concurrency, backups, containerized runs. | `pytest -m tier4` |

---

## 3. Test Framework & Runner Configurations

### Dependencies (`tests/e2e/requirements.txt`)
```text
pytest>=8.0.0
pytest-playwright>=0.5.0
requests>=2.31.0
caldav>=1.3.0
vobject>=0.9.6.1
icalendar>=5.0.11
```

### Pytest Configuration (`tests/e2e/pytest.ini`)
```ini
[pytest]
testpaths = tests/e2e
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = --strict-markers -v
markers =
    tier1: Happy path feature coverage tests
    tier2: Boundary and corner case tests
    tier3: Cross-feature interaction tests
    tier4: Real-world homelab scenario tests
```

---

## 4. Server Management & Lifecycle

To ensure testing is completely self-contained and reproducible, the suite automates the target server lifecycle.

### Server Lifecycle Fixture (`tests/e2e/conftest.py`)
If `KAYENDAR_TEST_URL` is not provided, the test suite automatically provisions a local server instance:
1. Locates a free TCP port.
2. Spawns `python -m kayendar` as a subprocess, passing a temporary configuration file pointing to a sandboxed data folder.
3. Polls the TCP port until the server responds, confirming it is ready.
4. Shuts down the process gracefully during teardown.

### User Provisioning & Mocking
Since the application uses local JSON storage (`data/users.json`), the tests manage users as follows:
- **Backup & Restore**: Before test execution, the existing `data/users.json` is backed up. On completion, it is restored.
- **Fixture `test_user`**: Generates a temporary user (e.g. `test_user_abc123`), hashes the password using Kayendar's authentication hashing format, writes it into the temporary `users.json`, and cleans up user files on test completion.

### Auth Handling
- **Basic Auth**: Embedded directly in requests via headers: `Authorization: Basic <base64(username:password)>`.
- **Session Auth (SPA)**: The test suite calls `POST /api/auth/login` to obtain the cookie, which is then added to the Playwright browser context or standard `requests` session.

---

## 5. Mocking / Emulating WebDAV & Web API Clients

The E2E suite employs specialized helpers to simulate real clients:
1. **CalDAV Client Emulator**: Uses the `caldav` python library to simulate Thunderbird or iOS sync routines.
2. **Raw WebDAV Session**: Uses Python `requests` for lower-level control of custom headers (e.g., `Depth`, custom properties), allowing exact protocol verification.
3. **Playwright Browser Page**: Emulates the client SPA inside a real web page context to click elements, interact with glassmorphism forms, and check session cookie persistence.
