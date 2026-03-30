from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

_root_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
_env_path = Path(__file__).resolve().parent.parent / ".env"
# Load root .env first, then backend .env (only fills missing vars)
load_dotenv(_root_env_path)
load_dotenv(_env_path, override=False)


@dataclass(frozen=True)
class Settings:
    astra_db_api_endpoint: str = field(default_factory=lambda: os.environ.get("ASTRA_DB_API_ENDPOINT", ""))
    astra_db_token: str = field(default_factory=lambda: os.environ.get("ASTRA_DB_APPLICATION_TOKEN", os.environ.get("ASTRA_DB_TOKEN", "")))
    astra_db_keyspace: str = field(default_factory=lambda: os.environ.get("ASTRA_DB_KEYSPACE", "default_keyspace"))
    jwt_secret: str = field(default_factory=lambda: os.environ.get("JWT_SECRET", "dev-secret-change-me"))
    jwt_expiry_minutes: int = field(default_factory=lambda: int(os.environ.get("JWT_EXPIRY_MINUTES", "60")))


settings = Settings()
