"""Certificate reference numbers (project lead, 23 Oct 2026): TAS-<HO or branch initials>-<city code>-0001.

TAS stands for The Arqam Schools; HO is used for a head office campus; the city code is the branch's (FSD for
Faisalabad, LHR for Lahore). Each branch has its own series."""

import re

# City codes given by the project lead. Other cities: head office sets the code on the branch (Setup → Branches).
CITY_CODES = {"faisalabad": "FSD", "lahore": "LHR"}
SKIP_WORDS = {"the", "arqam", "school", "schools", "campus", "branch", "head", "office"}


def city_code(city):
    return CITY_CODES.get((city or "").strip().lower(), "")


def initials(name):
    """Initials of the branch's own name, e.g. "Gulberg Colony Campus" → "GC"."""
    name = re.sub(r"\(.*?\)", " ", name or "")
    words = [w for w in re.findall(r"[A-Za-z0-9]+", name) if w.lower() not in SKIP_WORDS]
    return "".join(w[0] for w in words).upper()


def make_prefix(name, code, is_head_office, city, city_code_value, taken):
    """The reference start for a branch, unique among `taken` (a set of prefixes already used)."""
    part = "HO" if is_head_office else (initials(name) or code.upper())
    city_part = (city_code_value or city_code(city) or (city or "")[:3]).upper()
    prefix = f"TAS-{part}-{city_part}"
    n = 2
    candidate = prefix
    while candidate in taken:  # two branches with the same initials in one city
        candidate = f"TAS-{part}{n}-{city_part}"
        n += 1
    return candidate
