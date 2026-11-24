"""Addresses of files on this computer for the PDF maker (R16-6). Written as proper file URIs — on Windows a folder
like C:\\Program Files\\TASEMS becomes file:///C:/Program%20Files/TASEMS/ — so logos, photos and fonts are found on
every computer, not only on Linux."""

import base64
import functools
from pathlib import Path

from django.conf import settings


def file_uri(path):
    return Path(path).resolve().as_uri()


def dir_uri(path):
    uri = file_uri(path)
    return uri if uri.endswith("/") else uri + "/"


def font_base():
    return dir_uri(Path(settings.BASE_DIR) / "static" / "fonts")


def media_base():
    return dir_uri(settings.MEDIA_ROOT)


@functools.lru_cache(maxsize=4)
def image_data(relative):
    """A picture from static/ written into the page itself (no file address needed), made small enough to repeat on
    every page of a PDF."""
    import io

    from PIL import Image

    image = Image.open(Path(settings.BASE_DIR) / "static" / relative).convert("RGBA")
    if image.width > 1200:
        image = image.resize((1200, round(image.height * 1200 / image.width)), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def banner():
    """The school's colour logo banner sent by the lead (R15-1), as sent (only made smaller)."""
    return image_data("img/arqam-banner.png")
