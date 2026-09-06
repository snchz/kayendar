import logging
import os
from pathlib import Path
from urllib.parse import unquote

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from . import auth, storage
from .config import settings
from .dav import router as dav_router
from .web import router as web_router

STATIC_DIR = Path(__file__).parent / "static"
logger = logging.getLogger("kayendar")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Kayendar",
        description="A lightweight CalDAV/CardDAV server with a modern web client.",
        version="1.0.0",
    )

    # Configure data directory
    data_dir = str(settings.data_dir)
    storage.set_data_dir(data_dir)

    # Auto-provision admin user if environment variables are set
    admin_user = settings.admin_user
    admin_pass = settings.admin_password
    if admin_user and admin_pass:
        try:
            if auth.create_user(admin_user, admin_pass):
                logger.info("Auto-provisioned initial admin user: '%s'", admin_user)
        except Exception as e:
            logger.error("Error auto-provisioning admin user: %s", e, exc_info=True)

    # Public unauthenticated calendar share feed
    @app.get("/dav/share/{token}.ics")
    async def public_calendar_share(token: str):
        share = storage.get_share_by_token(token)
        if not share:
            return Response(status_code=404, content="Share not found", media_type="text/plain")
        ics_text = storage.export_collection_ics(share["username"], share["slug"])
        return Response(
            content=ics_text,
            media_type="text/calendar; charset=utf-8",
            headers={"Content-Disposition": f'inline; filename="{share["slug"]}.ics"'},
        )

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
        path = unquote(request.url.path)
        if ".." in path or "\\" in path:
            return Response(status_code=400, content="Directory traversal attempt detected.")
        return await call_next(request)

    def _serve_spa_response() -> Response:
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return HTMLResponse("<h1>Kayendar</h1><p>Static files not found.</p>")

    all_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD", "REPORT", "PROPFIND", "MKCOL", "MKCALENDAR"]

    @app.api_route("/", methods=all_methods)
    async def spa_root(request: Request):
        if request.method not in ("GET", "HEAD"):
            return Response(status_code=404)
        return _serve_spa_response()

    @app.api_route("/{full_path:path}", methods=all_methods)
    async def spa(request: Request, full_path: str):
        # Don't intercept API or DAV routes
        if full_path.startswith("api/") or full_path.startswith("dav/"):
            return Response(status_code=404)

        if request.method not in ("GET", "HEAD"):
            return Response(status_code=404)

        # Allow specific static files directly under STATIC_DIR like manifest.webmanifest, sw.js, favicon.ico
        candidate = STATIC_DIR / full_path
        if candidate.is_file() and full_path in ("manifest.webmanifest", "sw.js", "favicon.ico", "robots.txt"):
            media_type = "application/manifest+json" if full_path.endswith(".webmanifest") else "application/javascript" if full_path.endswith(".js") else None
            return FileResponse(str(candidate), media_type=media_type)

        basename = os.path.basename(full_path)
        if "." in basename and basename != "index.html":
            return Response(status_code=404)

        return _serve_spa_response()

    return app


app = create_app()
