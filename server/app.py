"""
kayendar/app.py

FastAPI application factory.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import storage
from .dav import router as dav_router
from .web import router as web_router

STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Kayendar",
        description="A lightweight CalDAV/CardDAV server with a modern web client.",
        version="1.0.0",
    )

    # Configure data directory
    data_dir = os.environ.get("KAYENDAR_DATA_DIR", "data")
    storage.set_data_dir(data_dir)

    # Configure auth database path
    from . import auth
    auth.USER_DB_PATH = os.path.join(data_dir, "users.json")

    # Auto-provision admin user if environment variables are set
    admin_user = os.environ.get("KAYENDAR_ADMIN_USER")
    admin_pass = os.environ.get("KAYENDAR_ADMIN_PASSWORD")
    if admin_user and admin_pass:
        try:
            if auth.create_user(admin_user, admin_pass):
                print(f"Auto-provisioned initial admin user: '{admin_user}'")
        except Exception as e:
            print(f"Error auto-provisioning admin user: {e}")

    # Mount DAV endpoints
    app.include_router(dav_router, prefix="/dav")

    # Mount REST API for the web client
    app.include_router(web_router)

    # Serve static files (SPA assets)
    if STATIC_DIR.exists():
        app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

    # Path traversal block middleware
    @app.middleware("http")
    async def block_traversal(request: Request, call_next):
        from urllib.parse import unquote
        from fastapi.responses import Response
        path = unquote(request.url.path)
        if ".." in path or "\\" in path:
            return Response(status_code=400, content="Directory traversal attempt detected.")
        return await call_next(request)

    @app.api_route("/", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD", "REPORT", "PROPFIND", "MKCOL", "MKCALENDAR"])
    async def spa_root(request: Request):
        if request.method not in ("GET", "HEAD"):
            from fastapi.responses import Response
            return Response(status_code=404)
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return HTMLResponse("<h1>Kayendar</h1><p>Static files not found.</p>")

    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD", "REPORT", "PROPFIND", "MKCOL", "MKCALENDAR"])
    async def spa(request: Request, full_path: str):
        # Don't intercept API or DAV routes
        if full_path.startswith("api/") or full_path.startswith("dav/"):
            from fastapi.responses import Response
            return Response(status_code=404)

        if request.method not in ("GET", "HEAD"):
            from fastapi.responses import Response
            return Response(status_code=404)

        basename = os.path.basename(full_path)
        if "." in basename and basename != "index.html":
            from fastapi.responses import Response
            return Response(status_code=404)

        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return HTMLResponse("<h1>Kayendar</h1><p>Static files not found.</p>")

    return app


app = create_app()
