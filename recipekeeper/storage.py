"""Where photo files live.

Online, photos go to Cloudflare R2 (S3-compatible file storage, free up to 10 GB)
when the four R2_* settings are set. Without them, photos are kept in the database,
which is fine on your computer and for a handful of recipes.
"""
from __future__ import annotations

import uuid
from typing import Protocol

from . import config


class StorageError(RuntimeError):
    pass


class Backend(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


def r2_configured() -> bool:
    return all(config.get(n) for n in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"))


class S3Backend:
    """Cloudflare R2, or any S3-compatible store when R2_ENDPOINT is set."""

    def __init__(self) -> None:
        import boto3
        from botocore.config import Config

        endpoint = config.get("R2_ENDPOINT") or f"https://{config.get('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com"
        self.bucket = config.get("R2_BUCKET")
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=config.get("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=config.get("R2_SECRET_ACCESS_KEY"),
            region_name="auto",
            config=Config(retries={"max_attempts": 3, "mode": "standard"},
                          connect_timeout=5, read_timeout=20),
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        except Exception as e:  # botocore raises many kinds
            raise StorageError(f"Couldn't save the photo to R2: {e}") from e

    def get(self, key: str) -> bytes:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except Exception as e:
            raise StorageError(f"Couldn't load the photo from R2: {e}") from e

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except Exception as e:
            raise StorageError(f"Couldn't delete the photo from R2: {e}") from e


_backend: Backend | None = None


def backend() -> Backend | None:
    """The file store, or None when photos should stay in the database."""
    global _backend
    if _backend is None and r2_configured():
        _backend = S3Backend()
    return _backend


def set_backend(b: Backend | None) -> None:
    """For tests, and for switching settings without restarting."""
    global _backend
    _backend = b


def new_key(household_id: int) -> str:
    # Random names, so a photo's address can't be guessed from another's.
    return f"households/{household_id}/photos/{uuid.uuid4().hex}.jpg"
