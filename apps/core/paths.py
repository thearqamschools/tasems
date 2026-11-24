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


def image_data(relative):
    """A picture from static/ written into the page itself (no file address needed), made small enough to repeat on
    every page of a PDF."""
    return _image_data(str(Path(settings.BASE_DIR) / "static" / relative), 0)


@functools.lru_cache(maxsize=8)
def _image_data(path, _stamp):
    import io

    from PIL import Image

    image = Image.open(path).convert("RGBA")
    if image.width > 1200:
        image = image.resize((1200, round(image.height * 1200 / image.width)), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def banner():
    """The header picture of date sheets and result cards: the one chosen on the Date sheet page (R17-2), else the
    school's colour logo banner sent by the lead (R15-1) — as sent, only made smaller."""
    from apps.exams.models import PrintHeader

    header = PrintHeader.current()
    if header is not None and header.image:
        try:
            path = header.image.path
            return _image_data(path, Path(path).stat().st_mtime)
        except (OSError, ValueError):
            pass
    return image_data("img/arqam-banner.png")


def banner_url():
    """The same picture for a page on the screen."""
    from django.templatetags.static import static

    from apps.exams.models import PrintHeader

    header = PrintHeader.current()
    if header is not None and header.image:
        return banner()  # uploaded pictures are not served as files in the office app, so it goes in the page
    return static("img/arqam-banner.png")
