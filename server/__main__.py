"""
server/__main__.py

Entry point: python -m server
"""

import os
import sys

import uvicorn

_DEFAULT_SECRET = "change-me-in-production"


def _warn_insecure_config() -> None:
    secret = os.environ.get("KAYENDAR_SECRET_KEY", _DEFAULT_SECRET)
    if secret == _DEFAULT_SECRET:
        print(
            "WARNING: KAYENDAR_SECRET_KEY is unset or uses the insecure default. "
            "Set a long random value before deploying.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    _warn_insecure_config()
    host = os.environ.get("KAYENDAR_HOST", "0.0.0.0")
    port = int(os.environ.get("KAYENDAR_PORT", "8000"))
    reload = os.environ.get("KAYENDAR_DEV", "").lower() in ("1", "true", "yes")

    uvicorn.run(
        "server.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
