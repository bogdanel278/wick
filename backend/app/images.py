import io
import re
import warnings

from PIL import Image

MAX_BYTES = 4_500_000  # 4.5 MB; the model API limit is 5 MB
MAX_SIDE = 8000
Image.MAX_IMAGE_PIXELS = MAX_SIDE * MAX_SIDE

HINT_RE = re.compile(r"[A-Za-z0-9/._:-]*")
HINT_MAX = 20


class BadImage(Exception):
    pass


def sniff(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def check_image(data: bytes, media_type: str) -> None:
    """Decode with Pillow and enforce format and dimension limits. Raises BadImage."""
    expected = "PNG" if media_type == "image/png" else "JPEG"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as im:
                im.verify()
            with Image.open(io.BytesIO(data)) as im:
                fmt, (w, h) = im.format, im.size
    except Exception as e:  # corrupt, truncated, decompression bomb, ...
        raise BadImage("Image could not be decoded.") from e
    if fmt != expected:
        raise BadImage("Image content does not match its type.")
    if w < 1 or h < 1 or w > MAX_SIDE or h > MAX_SIDE:
        raise BadImage(f"Image dimensions must be at most {MAX_SIDE} px on each side.")


def clean_hint(name: str, value: str | None) -> str | None:
    """Return the hint or None if empty. Raises ValueError with a clear message."""
    if value is None or value == "":
        return None
    if len(value) > HINT_MAX or not HINT_RE.fullmatch(value):
        raise ValueError(f"{name} must be at most {HINT_MAX} characters using only letters, digits and / . _ : -")
    return value
