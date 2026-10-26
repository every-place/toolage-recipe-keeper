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


def premium_emails() -> set[str]:
    """PREMIUM_EMAILS: comma-separated emails whose households get Premium
    when they sign up or log in. Stands in for billing until billing exists."""
    raw = get("PREMIUM_EMAILS") or ""
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


# ---------- FatSecret (nutrition, premium plan) ----------
def fatsecret_configured() -> bool:
    return bool(get("FATSECRET_CLIENT_ID") and get("FATSECRET_CLIENT_SECRET"))


def fatsecret_credentials() -> tuple[str, str]:
    cid, secret = get("FATSECRET_CLIENT_ID"), get("FATSECRET_CLIENT_SECRET")
    if not cid or not secret:
        raise RuntimeError("FATSECRET_CLIENT_ID and FATSECRET_CLIENT_SECRET are not set.")
    return cid, secret


def fatsecret_scope() -> str:
    return get("FATSECRET_SCOPE", "basic")


def fatsecret_proxy() -> str | None:
    """Optional fixed-IP proxy: FatSecret only answers IP addresses listed in its dashboard."""
    return get("FATSECRET_PROXY_URL")
