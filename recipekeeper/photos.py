"""Photo uploads: fix rotation, shrink, and save as JPEG so the app stays fast."""
from __future__ import annotations

import io

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_SIDE = 1600
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class PhotoError(ValueError):
    pass


def prepare(data: bytes) -> tuple[bytes, int, int]:
    """Return (jpeg_bytes, width, height). Raises PhotoError for non-images."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise PhotoError("That photo is too large (over 20 MB).")
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)  # phones store rotation separately
    except (UnidentifiedImageError, OSError) as e:
        raise PhotoError("That file isn't a photo we can read.") from e
    if img.mode not in ("RGB", "L"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        img = background
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.convert("RGB").save(out, "JPEG", quality=82, optimize=True)  # also drops location data
    return out.getvalue(), img.width, img.height
