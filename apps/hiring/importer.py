"""CVs from an Excel file, or a ZIP of the Excel file and the CV files (project lead, 13 Nov 2026).

The office gives the scanned CVs and TASEMS's template to Claude (their own Claude account), which fills one row per
CV; the filled Excel — with the CV files in the same ZIP — is uploaded here. Nothing is saved until the office has
seen the check and pressed Import. A row whose mobile or CNIC is already in the CV bank adds a CV to that person."""

import datetime as dt
import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from django.utils import timezone
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from . import services as S
from .models import LEVELS, SUBJECTS, Candidate, CandidateCV, Post

FILE_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
MAX_ROWS = 1000

# (key, heading, required, help for the person or Claude filling it)
COLUMNS = [
    (
        "cv_file",
        "CV File",
        False,
        "File name of this CV in the ZIP, e.g. CV-001.jpg (several pages: CV-001-1.jpg, CV-001-2.jpg)",
    ),
    ("received_on", "Received On", False, "Date the CV came, e.g. 13/11/2026 (empty: today)"),
    ("channel", "Came By", False, "In hand, WhatsApp, Email, Advertisement, Online, Referred or Other"),
    ("post", "Applied For", True, "A post from the list, e.g. Teacher, Qari, Typist"),
    ("campus", "Campus", False, "Campus name, or empty"),
    ("full_name", "Name", True, "Candidate's name"),
    ("father_name", "Father / Husband Name", False, ""),
    ("gender", "Gender", False, "Female or Male"),
    ("mobile", "Mobile", False, "e.g. 0300-1234567"),
    ("cnic", "CNIC", False, "13 digits, e.g. 33100-1234567-1"),
    ("email", "Email", False, ""),
    ("address", "Address", False, "As written on the CV"),
    ("qualification", "Highest Qualification", False, "e.g. M.Sc Chemistry"),
    ("experience_years", "Experience (Years)", False, "Total years of teaching / work, e.g. 3 or 2.5"),
    ("salary_asked", "Salary Asked (Rs)", False, "Only if written on the CV"),
    ("subjects", "Can Teach", False, "Subjects separated by commas, from the list"),
    ("levels", "Level", False, "Early Years, Primary, Middle, Matric, Hifz-e-Quran, separated by commas"),
    ("education", "Education", False, "Degree | Institute | Year; next degree | institute | year"),
    ("experience", "Experience", False, "School | Post | Level | Years; next school | post | level | years"),
    ("relevance", "Relevant", False, "Relevant, Keep for later, Not relevant (empty: not checked yet)"),
    ("relevance_note", "Reason", False, ""),
    ("notes", "Notes", False, "Anything else useful from the CV"),
]
CHANNELS = {
    "inhand": "in_hand", "hand": "in_hand", "byhand": "in_hand", "walkin": "in_hand", "whatsapp": "whatsapp",
    "email": "email", "mail": "email", "advertisement": "advert", "advert": "advert", "ad": "advert",
    "online": "online", "website": "online", "referred": "referred", "reference": "referred", "other": "other",
}  # fmt: skip
RELEVANCE = {
    "relevant": "relevant", "yes": "relevant", "keepforlater": "later", "later": "later", "notrelevant": "not_relevant",
    "irrelevant": "not_relevant", "no": "not_relevant", "notcheckedyet": "unchecked", "": "unchecked",
}  # fmt: skip
LEVEL_WORDS = {"earlyyears": "early_years", "primary": "primary", "middle": "middle", "matric": "matric",
               "high": "matric", "hifz": "hifz", "hifzequran": "hifz", "hifzquran": "hifz"}  # fmt: skip


def key(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def _date(value):
    if value in (None, ""):
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%d/%m/%y", "%d %b %Y", "%d-%b-%Y"):
        try:
            return dt.datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError


SUBJECT_ALIASES = {
    "math": "maths", "mathematics": "maths", "islamiat": "islamiyat", "quran": "nazra", "nazraquran": "nazra",
    "computerscience": "computer", "it": "computer", "drawing": "art", "gk": "general_knowledge",
    "sst": "social_studies", "pakstudy": "pak_studies",
}  # fmt: skip


def _subjects_table():
    table = {}
    for code, label in SUBJECTS:
        table[key(code)] = code
        table[key(str(label))] = code
    table.update(SUBJECT_ALIASES)
    return table


def _list(text, table):
    found, unknown = [], []
    for part in re.split(r"[,;/]", text or ""):
        if not part.strip():
            continue
        code = table.get(key(part))
        if code and code not in found:
            found.append(code)
        elif not code:
            unknown.append(part.strip())
    return found, unknown


def _rows(text, size):
    out = []
    for chunk in (text or "").split(";"):
        parts = [p.strip() for p in chunk.split("|")]
        if any(parts):
            out.append((parts + [""] * size)[:size])
    return out


@dataclass
class Row:
    number: int
    data: dict
    notes: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    same: Candidate | None = None
    files: list = field(default_factory=list)  # names inside the ZIP


@dataclass
class Check:
    rows: list = field(default_factory=list)
    errors: list = field(default_factory=list)  # about the whole file

    @property
    def good(self):
        return [r for r in self.rows if not r.errors]

    @property
    def bad(self):
        return [r for r in self.rows if r.errors]


def open_upload(name, content):
    """(excel bytes, {lower-case file name: bytes of a CV file}) from an .xlsx or a .zip."""
    if name.lower().endswith(".zip"):
        files, excel = {}, None
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            for info in z.infolist():
                if info.is_dir() or info.file_size > 20 * 1024 * 1024:
                    continue
                base = PurePosixPath(info.filename).name
                if base.startswith((".", "~$")) or "__MACOSX" in info.filename:
                    continue
                if base.lower().endswith(".xlsx") and excel is None:
                    excel = z.read(info)
                elif PurePosixPath(base).suffix.lower() in FILE_TYPES:
                    files[base.lower()] = z.read(info)
        return excel, files
    return content, {}


def check(name, content, *, branch):
    result = Check()
    try:
        excel, files = open_upload(name, content)
    except zipfile.BadZipFile:
        result.errors.append("This ZIP file could not be opened.")
        return result, {}
    if excel is None:
        result.errors.append("No Excel file (.xlsx) found. Put the filled template in the ZIP with the CV files.")
        return result, files
    try:
        wb = load_workbook(io.BytesIO(excel), read_only=True, data_only=True)
    except Exception:  # noqa: BLE001 - any unreadable file gets the same message
        result.errors.append("The Excel file could not be opened. Save it as .xlsx and try again.")
        return result, files
    sheet = wb.worksheets[0]
    rows = sheet.iter_rows(values_only=True)
    header = [key(h) for h in (next(rows, None) or ())]
    where = {}
    for k, heading, _req, _help in COLUMNS:
        for i, h in enumerate(header):
            if h in (key(heading), key(k)):
                where[k] = i
    if "full_name" not in where or "post" not in where:
        result.errors.append("Use TASEMS's CV template: the columns Name and Applied For were not found.")
        return result, files
    posts = {key(p.name): p for p in Post.objects.all()}
    from apps.organisation.models import Campus

    campuses = {key(c.name): c for c in Campus.objects.filter(branch=branch)}
    subjects, levels = _subjects_table(), {**LEVEL_WORDS, **{key(c): c for c, _l in LEVELS}}
    seen_mobiles = {}
    today = timezone.localdate()
    for number, values in enumerate(rows, start=2):
        if number > MAX_ROWS + 1:
            result.errors.append(f"Only the first {MAX_ROWS} rows are read.")
            break
        raw = {k: (values[i] if i < len(values) else None) for k, i in where.items()}
        if not any(_text(v) for v in raw.values()):
            continue
        row = Row(number, {})
        d = row.data
        d["full_name"] = _text(raw.get("full_name"))[:150]
        if not d["full_name"]:
            row.errors.append("Name is empty")
        post = posts.get(key(raw.get("post")))
        if post is None:
            row.errors.append(f"Post “{_text(raw.get('post'))}” is not in the posts list (Setup → Hiring posts)")
        d["post"] = post
        try:
            d["received_on"] = _date(raw.get("received_on")) or today
        except ValueError:
            d["received_on"] = today
            row.notes.append(f"date “{_text(raw.get('received_on'))}” not understood: today used")
        if d["received_on"] > today:
            d["received_on"] = today
            row.notes.append("date in the future: today used")
        d["channel"] = CHANNELS.get(key(raw.get("channel")), "other")
        campus_name = _text(raw.get("campus"))
        d["campus"] = campuses.get(key(campus_name)) if campus_name else None
        if campus_name and d["campus"] is None:
            row.notes.append(f"campus “{campus_name}” not found: left empty")
        for k, size in (("father_name", 150), ("mobile", 30), ("email", 254), ("address", 250),
                        ("qualification", 120), ("relevance_note", 200)):  # fmt: skip
            d[k] = _text(raw.get(k))[:size]
        d["notes"] = _text(raw.get("notes"))
        d["cnic"] = S.digits(raw.get("cnic"))[:13]
        if d["cnic"] and len(d["cnic"]) != 13:
            row.notes.append("CNIC is not 13 digits: kept as written")
            d["cnic"] = _text(raw.get("cnic"))[:15]
        if d["email"] and "@" not in d["email"]:
            row.notes.append("email not valid: left out")
            d["email"] = ""
        gender = key(raw.get("gender"))
        d["gender"] = "male" if gender in ("male", "m", "man") else "female"
        for k in ("experience_years", "salary_asked"):
            text = _text(raw.get(k)).replace(",", "")
            match = re.search(r"\d+(\.\d+)?", text)
            d[k] = (float(match.group()) if k == "experience_years" else int(float(match.group()))) if match else None
        if d["experience_years"] is not None and d["experience_years"] > 60:
            d["experience_years"] = None
            row.notes.append("experience over 60 years: left out")
        d["subjects"], unknown = _list(_text(raw.get("subjects")), subjects)
        if unknown:
            row.notes.append("subjects not in the list: " + ", ".join(unknown))
        d["levels"], unknown = _list(_text(raw.get("levels")), levels)
        if unknown:
            row.notes.append("levels not in the list: " + ", ".join(unknown))
        relevance = RELEVANCE.get(key(raw.get("relevance")))
        d["relevance"] = relevance or "unchecked"
        if relevance is None:
            row.notes.append(f"“{_text(raw.get('relevance'))}” is not a relevance: not checked yet")
        d["education"] = _rows(_text(raw.get("education")), 3)
        d["experience"] = _rows(_text(raw.get("experience")), 4)
        for name_ in re.split(r"[,;]", _text(raw.get("cv_file"))):
            name_ = PurePosixPath(name_.strip()).name.lower()
            if not name_:
                continue
            matches = [n for n in files if n == name_ or PurePosixPath(n).stem == PurePosixPath(name_).stem]
            if matches:
                row.files.extend(m for m in matches if m not in row.files)
            else:
                row.notes.append(f"file “{name_}” not in the ZIP")
        mobile = S.mobile_key(d["mobile"])
        if len(mobile) >= 7 and mobile in seen_mobiles:
            row.notes.append(f"same mobile as row {seen_mobiles[mobile]}: added to that person")
        elif len(mobile) >= 7:
            seen_mobiles[mobile] = number
        if not row.errors:
            row.same = S.find_same_person(branch, d["mobile"], d["cnic"])
        result.rows.append(row)
    if not result.rows and not result.errors:
        result.errors.append("No CV rows found in the Excel file.")
    return result, files


def run_import(result, files, *, branch, user):
    """Saves the good rows. Returns (new people, CVs added to people already in the CV bank)."""
    from django.core.files.base import ContentFile
    from django.db import transaction

    from .models import CVFile, Education, Experience

    new = added = 0
    by_mobile = {}
    with transaction.atomic():
        for row in result.good:
            d = row.data
            mobile = S.mobile_key(d["mobile"])
            person = row.same or (by_mobile.get(mobile) if len(mobile) >= 7 else None)
            if person is None:
                person = Candidate.objects.create(
                    branch=branch, created_by=user, last_received_on=d["received_on"], post=d["post"],
                    campus=d["campus"], full_name=d["full_name"], father_name=d["father_name"], gender=d["gender"],
                    mobile=d["mobile"], cnic=d["cnic"], email=d["email"], address=d["address"],
                    qualification=d["qualification"], experience_years=d["experience_years"],
                    salary_asked=d["salary_asked"], subjects=d["subjects"], levels=d["levels"],
                    relevance=d["relevance"], relevance_note=d["relevance_note"], notes=d["notes"],
                )  # fmt: skip
                for degree, institute, year in d["education"]:
                    year_ = int(year) if str(year).isdigit() and 1950 <= int(year) <= 2100 else None
                    Education.objects.create(branch=branch, candidate=person, degree=(degree or institute)[:120],
                                             institute=institute[:150], year=year_)  # fmt: skip
                for organisation, post, level, years in d["experience"]:
                    level_ = LEVEL_WORDS.get(key(level), "")
                    match = re.search(r"\d+(\.\d+)?", years or "")
                    Experience.objects.create(branch=branch, candidate=person, organisation=(organisation or "—")[:150],
                                              post=post[:100], level=level_,
                                              years=float(match.group()) if match else None)  # fmt: skip
                new += 1
            else:
                added += 1
                if d["received_on"] >= person.last_received_on or person.binned_at:
                    person.last_received_on = max(person.last_received_on, d["received_on"])
                    person.binned_at = None
                    person.save(update_fields=["last_received_on", "binned_at", "updated_at"])
            if len(mobile) >= 7:
                by_mobile.setdefault(mobile, person)
            cv = CandidateCV.objects.create(
                branch=branch, candidate=person, received_on=d["received_on"], channel=d["channel"], post=d["post"],
                entered_by=user, note=f"Imported from Excel (row {row.number})",
            )  # fmt: skip
            for name in row.files:
                if name in files:
                    f = CVFile(branch=branch, cv=cv, original_name=name[:150])
                    f.file.save(name, ContentFile(files[name]), save=True)
    return new, added


def template_workbook():
    """The CV template: one row per CV, a list of allowed values, and drop-downs where a value is chosen."""
    wb = Workbook()
    ws = wb.active
    ws.title = "CVs"
    ws.append([h + (" *" if required else "") for _k, h, required, _help in COLUMNS])
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="E3E4F5")
    widths = [18, 13, 13, 16, 14, 22, 22, 9, 15, 17, 22, 30, 22, 10, 12, 26, 20, 45, 45, 14, 22, 30]
    for i, width in enumerate(widths):
        ws.column_dimensions[chr(65 + i)].width = width
    ws.freeze_panes = "A2"
    lists = wb.create_sheet("Lists")
    posts = [p.name for p in Post.objects.filter(is_active=True)]
    columns = [
        ("Applied For (posts)", posts),
        ("Came By", ["In hand", "WhatsApp", "Email", "Advertisement", "Online", "Referred", "Other"]),
        ("Can Teach (subjects)", [str(label) for _c, label in SUBJECTS]),
        ("Level", [str(label) for _c, label in LEVELS]),
        ("Relevant", ["Relevant", "Keep for later", "Not relevant"]),
        ("Gender", ["Female", "Male"]),
    ]
    for i, (heading, values) in enumerate(columns, start=1):
        letter = chr(64 + i)
        lists[f"{letter}1"] = heading
        lists[f"{letter}1"].font = Font(bold=True)
        for j, value in enumerate(values, start=2):
            lists[f"{letter}{j}"] = value
        lists.column_dimensions[letter].width = 26
    for col, lists_col, count in (("D", "A", len(posts)), ("C", "B", 7), ("T", "E", 3), ("H", "F", 2)):
        rule = DataValidation(type="list", formula1=f"=Lists!${lists_col}$2:${lists_col}${count + 1}", allow_blank=True)
        rule.add(f"{col}2:{col}{MAX_ROWS + 1}")
        ws.add_data_validation(rule)
    guide = wb.create_sheet("How to fill")
    guide.append(["Column", "What to write"])
    for _k, heading, required, help_ in COLUMNS:
        guide.append([heading + (" *" if required else ""), help_])
    guide.append([])
    guide.append(["Rule", "One row per CV. Leave a cell empty when the CV does not say. Do not change the headings."])
    guide.column_dimensions["A"].width = 26
    guide.column_dimensions["B"].width = 100
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
