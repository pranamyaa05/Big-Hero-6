"""Photo intake: validate, downscale and re-encode uploaded images so only clean JPEGs reach the planner."""
from __future__ import annotations
import io
from PIL import Image, UnidentifiedImageError

Image.MAX_IMAGE_PIXELS = 50_000_000
ALLOWED = {"JPEG", "PNG", "WEBP", "GIF"}


class ImageError(ValueError):
    pass


def clean_image(data: bytes, max_side: int = 1568) -> tuple[str, bytes]:
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError) as e:
        raise ImageError("that file is not a readable image") from e
    if fmt not in ALLOWED:
        raise ImageError(f"{fmt or 'unknown'} images are not supported; use JPEG, PNG, WEBP or GIF")
    img = img.convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)          # re-encoding also strips EXIF (location, camera)
    return "image/jpeg", buf.getvalue()
