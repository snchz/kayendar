# Kayendar

> Lightweight CalDAV/CardDAV server with a modern, glassmorphism web client for your homelab.

[![Docker Image](https://img.shields.io/badge/Docker-ghcr.io%2Fsnchz%2Fkayendar-blue)](https://ghcr.io/snchz/kayendar)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## Features

- 📅 **CalDAV server** — full calendar sync with iOS, Thunderbird, DAVx⁵
- 📇 **CardDAV server** — contact sync with standard clients  
- 🌐 **Modern SPA web client** — glassmorphism UI with month/week views
- 🔐 **Secure auth** — Basic Auth for DAV clients, session cookies for the web app
- 💾 **File-based storage** — `.ics` and `.vcf` files, no database required
- 🐳 **Docker-ready** — minimal image (~80MB), perfect for Dockge/homelab
- ⚡ **Lightweight** — < 100MB RAM at rest

---

## Quick Start

### Docker (recommended)

```yaml
# docker-compose.yml
services:
  kayendar:
    image: ghcr.io/snchz/kayendar:latest
    ports:
      - "8000:8000"
    volumes:
      - kayendar_data:/data
    environment:
      KAYENDAR_SECRET_KEY: "your-long-random-secret-key"
volumes:
  kayendar_data:
```

```bash
# Create your first user
docker exec -it kayendar python manage.py adduser alice
# Open the web interface
open http://localhost:8000
```

### Local (development)

```bash
git clone https://github.com/snchz/kayendar
cd kayendar
pip install -r requirements-dev.txt

# Create a user
python manage.py adduser alice

# Run the server
python -m server
```

---

## Client Configuration

### iOS (Calendar)
1. Settings → Calendar → Accounts → Add Account → Other → Add CalDAV Account
2. **Server**: `http://your-server:8000/dav/alice/`
3. **Username**: `alice` | **Password**: your password

### iOS (Contacts)
1. Settings → Contacts → Accounts → Add Account → Other → Add CardDAV Account
2. **Server**: `http://your-server:8000/dav/alice/`

### Thunderbird / DAVx⁵
- URL: `http://your-server:8000/dav/alice/`
- Use your username and password

---

## User Management

```bash
# Add a user
python manage.py adduser alice

# List users
python manage.py listusers

# Delete a user
python manage.py deluser alice
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `KAYENDAR_DATA_DIR` | `data` | Path where data is stored |
| `KAYENDAR_SECRET_KEY` | *(insecure default)* | Session signing key — **change this!** |
| `KAYENDAR_SECURE_COOKIES` | *(off)* | Set to `true` when served over HTTPS |
| `KAYENDAR_HOST` | `0.0.0.0` | Listen host |
| `KAYENDAR_PORT` | `8000` | Listen port |
| `KAYENDAR_DEV` | *(off)* | Set to `true` to enable auto-reload |

---

## Project Structure

```
kayendar/
├── server/               # Python backend (CalDAV/CardDAV + REST API)
│   ├── app.py            # FastAPI application factory
│   ├── auth.py           # Authentication (PBKDF2 hashed passwords)
│   ├── storage.py        # Filesystem storage backend
│   ├── dav.py            # CalDAV/CardDAV protocol handler
│   ├── web.py            # REST API for the SPA
│   └── static/           # Web client (HTML, CSS, JS)
├── manage.py             # User management CLI
├── tests/                # Unit and e2e tests
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
└── docker-compose.yml
```

---

## License

MIT © [snchz](https://github.com/snchz)