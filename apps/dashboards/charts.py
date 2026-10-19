"""Column charts drawn on the server as SVG (DECISIONS D-064): no chart library, works on slow links and in print.

Mark specs follow the TASEMS design system: columns at most 24 px wide, 4 px rounded ends square at the
baseline, hairline gridlines, one series in the brand colour, the latest value labelled, every column a
keyboard-focusable hit area with its value in a tooltip, and the same numbers in a table view.
"""

from decimal import Decimal

WIDTH = 640
HEIGHT = 200
PAD_TOP = 22
PAD_BOTTOM = 26
PAD_LEFT = 40
PAD_RIGHT = 8
BAR_MAX = 24
RADIUS = 4


def compact(value):
    """1234 → 1.2K, 1500000 → 1.5M (axis ticks only; exact values stay in tooltips and the table)."""
    value = float(value)
    for limit, suffix in ((1_000_000, "M"), (1_000, "K")):
        if abs(value) >= limit:
            text = f"{value / limit:.1f}".rstrip("0").rstrip(".")
            return f"{text}{suffix}"
    return f"{value:.0f}"


def _nice_max(value):
    if value <= 0:
        return 1
    magnitude = 10 ** (len(str(int(value))) - 1)
    for step in (1, 2, 2.5, 5, 10):
        if step * magnitude >= value:
            return step * magnitude
    return 10 * magnitude


def _column_path(x, y, w, base):
    h = base - y
    if h <= 0:
        return ""
    r = min(RADIUS, h, w / 2)
    return (
        f"M{x:.1f},{base:.1f} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
        f"H{x + w - r:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} V{base:.1f} Z"
    )


def column_chart(points, *, percent=False, money=False):
    """`points`: list of {"label": short axis label, "title": full label, "value": number or None,
    "text": formatted value}. Returns geometry for templates/dashboards/_columns.html."""
    values = [float(p["value"]) for p in points if p["value"] is not None]
    top = 100 if percent else _nice_max(max(values) if values else 0)
    plot_w = WIDTH - PAD_LEFT - PAD_RIGHT
    plot_h = HEIGHT - PAD_TOP - PAD_BOTTOM
    base = PAD_TOP + plot_h
    slot = plot_w / max(len(points), 1)
    bar_w = min(BAR_MAX, slot * 0.6)
    every = 1 if len(points) <= 16 else 5
    bars = []
    for i, p in enumerate(points):
        x = PAD_LEFT + i * slot + (slot - bar_w) / 2
        value = None if p["value"] is None else float(p["value"])
        y = base - (value / top) * plot_h if value else base
        last = i == len(points) - 1
        bars.append(
            {
                **p,
                "x": round(x, 1),
                "w": round(bar_w, 1),
                "y": round(y, 1),
                "cx": round(x + bar_w / 2, 1),
                "path": _column_path(x, y, bar_w, base) if value else "",
                "hit_x": round(PAD_LEFT + i * slot, 1),
                "hit_w": round(slot, 1),
                "show_label": i % every == 0 or last,
                "is_last": last,
            }
        )
    ticks = []
    for k in range(5):
        v = top * k / 4
        ticks.append({"y": round(base - plot_h * k / 4, 1), "text": f"{v:.0f}%" if percent else compact(v)})
    return {
        "width": WIDTH,
        "height": HEIGHT,
        "base": base,
        "left": PAD_LEFT,
        "right": WIDTH - PAD_RIGHT,
        "label_y": base + 17,
        "bars": bars,
        "ticks": ticks,
        "money": money,
        "empty": not any(values),  # nothing to compare: the template shows an empty state instead
    }


def percent(part, whole):
    if not whole:
        return None
    return round(Decimal(100) * Decimal(part) / Decimal(whole))
