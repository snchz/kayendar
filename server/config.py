"""
server/config.py

Centralized configuration settings for Kayendar.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir_env: str = "KAYENDAR_DATA_DIR"
    default_data_dir: str = "data"
    default_secret: str = "change-me-in-production"

    @property
    def data_dir(self) -> Path:
        return Path(os.environ.get(self.data_dir_env, self.default_data_dir))

    @property
    def users_db_path(self) -> Path:
        return self.data_dir / "users.json"

    @property
    def collections_dir(self) -> Path:
        return self.data_dir / "collections"

    @property
    def secret_key(self) -> str:
        return os.environ.get("KAYENDAR_SECRET_KEY", self.default_secret)

    @property
    def secure_cookies(self) -> bool:
        return os.environ.get("KAYENDAR_SECURE_COOKIES", "").lower() in ("1", "true", "yes")

    @property
    def log_debug(self) -> bool:
        return os.environ.get("KAYENDAR_LOG_DEBUG", "false").lower() in ("true", "1", "yes")

    @property
    def host(self) -> str:
        return os.environ.get("KAYENDAR_HOST", "0.0.0.0")

    @property
    def port(self) -> int:
        return int(os.environ.get("KAYENDAR_PORT", "8000"))

    @property
    def admin_user(self) -> str | None:
        return os.environ.get("KAYENDAR_ADMIN_USER")

    @property
    def admin_password(self) -> str | None:
        return os.environ.get("KAYENDAR_ADMIN_PASSWORD")


settings = Settings()
