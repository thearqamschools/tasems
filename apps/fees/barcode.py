"""Code 128 barcode of the voucher number, as inline SVG (bank and counter scanners read it)."""

import io

from barcode import Code128
from barcode.writer import SVGWriter
from django.utils.safestring import mark_safe


def voucher_barcode(number):
    buffer = io.BytesIO()
    Code128(str(number), writer=SVGWriter()).write(
        buffer, options={"module_height": 9, "module_width": 0.28, "quiet_zone": 1, "write_text": False}
    )
    svg = buffer.getvalue().decode()
    svg = svg[svg.index("<svg") :]
    return mark_safe(svg)
