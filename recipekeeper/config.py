"""Settings, read from environment variables (or a .env file on your computer)."""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

load_dotenv(ROOT / ".env")


def get(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, "").strip()
    if not value or value.startswith("paste-"):
        return default
    return value


_dev_secret = secrets.token_urlsafe(32)


def secret_key() -> str:
    """Signs login cookies. Without SECRET_KEY set, a random one is used and
    everyone is logged out whenever the server restarts."""
    return get("SECRET_KEY") or _dev_secret


def cookie_secure() -> bool:
    return get("COOKIE_SECURE") == "1"


def data_dir() -> Path:
    path = Path(get("RECIPES_DATA_DIR") or ROOT / "data")
    path.mkdir(parents=True, exist_ok=True)
    return path
