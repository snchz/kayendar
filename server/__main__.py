"""
server/__main__.py

Entry point: python -m server
"""

import os
import sys

import uvicorn

from .config import settings


def _warn_insecure_config() -> None:
    if settings.secret_key == settings.default_secret:
        print(
            "WARNING: KAYENDAR_SECRET_KEY is unset or uses the insecure default. "
            "Set a long random value before deploying.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    _warn_insecure_config()
    reload = os.environ.get("KAYENDAR_DEV", "").lower() in ("1", "true", "yes")

    uvicorn.run(
        "server.app:app",
        host=settings.host,
        port=settings.port,
        reload=reload,
        log_level="info",
    )
