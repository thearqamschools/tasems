"""Printing straight to a network receipt printer (ESC/POS over TCP, port 9100), with no print window.

Used for the Parent Tree slip on the SPEEDX 400UL (80 mm, 48 characters a line, LAN) — project lead, 28 Oct 2026.
Works when TASEMS runs on a computer in the same office network as the printer (the offline Windows copy); a
server on the internet cannot reach an office printer."""

import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor
from functools import cache
from pathlib import Path

from django.conf import settings
from PIL import Image

WIDTH = 48  # characters per line, font A, 80 mm paper
DEFAULT_PORT = 9100
ESC, GS = b"\x1b", b"\x1d"
INIT = ESC + b"@"
CENTER, LEFT = ESC + b"a\x01", ESC + b"a\x00"
BOLD_ON, BOLD_OFF = ESC + b"E\x01", ESC + b"E\x00"
BIG, NORMAL = GS + b"!\x11", GS + b"!\x00"  # double width and height
FEED_AND_CUT = ESC + b"d\x04" + GS + b"V\x42\x00"


class PrinterError(Exception):
    pass


def address(value):
    """'192.168.1.50' or '192.168.1.50:9100' → (host, port)."""
    host, _, port = (value or "").strip().partition(":")
    if not host:
        raise PrinterError("No printer address.")
    return host, int(port) if port.isdigit() else DEFAULT_PORT


def text(value):
    return str(value).encode("cp437", "replace")


def line(value=""):
    return text(value) + b"\n"


def columns(values, widths):
    """One table row; a value too long for its column (e.g. a long name) carries on in the next line."""
    rest = [str(v or "-") for v in values]
    out = b""
    while any(rest):
        cells = []
        for i, w in enumerate(widths):
            value = rest[i]
            cut = value[:w] if len(value) <= w or " " not in value[:w] else value[: value[:w].rindex(" ")]
            cells.append(cut.ljust(w))
            rest[i] = value[len(cut) :].strip()
        out += line(" ".join(cells).rstrip())
    return out


@cache
def logo_raster(width=192):
    """The official logo as a black-and-white raster image (GS v 0), cached."""
    path = Path(settings.BASE_DIR) / "static" / "img" / "arqam-logo-512.png"
    image = Image.open(path).convert("RGBA")
    background = Image.new("RGBA", image.size, "white")
    image = Image.alpha_composite(background, image).convert("L").resize((width, width))
    image = image.point(lambda p: 0 if p < 140 else 255, "1")
    row_bytes = (width + 7) // 8
    data = bytearray()
    pixels = image.load()
    for y in range(width):
        for xb in range(row_bytes):
            byte = 0
            for bit in range(8):
                x = xb * 8 + bit
                if x < width and pixels[x, y] == 0:
                    byte |= 0x80 >> bit
            data.append(byte)
    return GS + b"v0\x00" + bytes([row_bytes % 256, row_bytes // 256, width % 256, width // 256]) + bytes(data)


def parent_tree(branch, father_name, printed_at, rows):
    """The Parent Tree slip as ESC/POS bytes (same content as the on-screen slip)."""
    dash = line("-" * WIDTH)
    out = INIT + CENTER + logo_raster() + b"\n"
    out += BOLD_ON + BIG + line("THE ARQAM SCHOOLS") + NORMAL + BOLD_OFF
    if branch.address:
        out += line(branch.address)
    if branch.contact_numbers:
        out += line(f"({', '.join(branch.contact_numbers)})")
    out += dash + BOLD_ON + line("Parent Tree") + BOLD_OFF + LEFT
    out += line(f"Parent Name: {father_name or '-'}")
    out += line(f"Date: {printed_at:%d/%m/%Y %I:%M %p}")
    widths = (6, 5, 16, 10, 7)  # 44 + 4 spaces = 48 characters
    out += dash + BOLD_ON + columns(("Campus", "Code", "Student Name", "Class", "Section"), widths) + BOLD_OFF + dash
    for r in rows:
        out += columns((r["campus"], r["code"], r["name"], r["class"], r["section"]), widths)
    out += dash + CENTER + line("Thank you") + FEED_AND_CUT
    return out


def send(printer_address, data, timeout=5):
    host, port = address(printer_address)
    try:
        with socket.create_connection((host, port), timeout=timeout) as conn:
            conn.sendall(data)
    except OSError as error:
        raise PrinterError(str(error)) from error


def test_page(printer_address, printed_at):
    """A short slip to check which printer this is."""
    out = INIT + CENTER + BOLD_ON + BIG + line("TASEMS") + NORMAL + line("Test print") + BOLD_OFF
    out += line(f"Printer: {printer_address}") + line(f"{printed_at:%d/%m/%Y %I:%M %p}")
    out += line("The Arqam Schools") + FEED_AND_CUT
    return out


def local_networks():
    """The office networks this computer is on (e.g. 192.168.1.0/24), from its own IPv4 addresses."""
    addresses = set()
    try:  # the address used to reach other networks; nothing is sent
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("10.255.255.255", 1))
            addresses.add(probe.getsockname()[0])
    except OSError:
        pass
    try:
        addresses.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    networks = []
    for address in sorted(addresses):
        ip = ipaddress.ip_address(address)
        if ip.is_private and not ip.is_loopback and not ip.is_link_local:
            network = ipaddress.ip_network(f"{address}/24", strict=False)
            if network not in networks:
                networks.append(network)
    return networks


def _answers(host, port, timeout):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def find_printers(networks=None, port=DEFAULT_PORT, timeout=0.4):
    """Addresses on the office network that accept print jobs on port 9100 (receipt and other network printers)."""
    networks = local_networks() if networks is None else networks
    hosts = [str(h) for network in networks for h in network.hosts()]
    with ThreadPoolExecutor(max_workers=64) as pool:
        found = [h for h, ok in zip(hosts, pool.map(lambda h: _answers(h, port, timeout), hosts), strict=True) if ok]
    return found
