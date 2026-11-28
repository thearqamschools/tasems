"""Round 21 (project lead, 27 Nov 2026): result card and date sheet finishing — room to sign on every card, however
many subjects; the three totals alike with Obtained a little bolder; the DATE SHEET tab as in the school's design."""

from pathlib import Path

from django.conf import settings

from apps.exams.views_year import _card_cell

TEMPLATES = Path(settings.BASE_DIR) / "templates" / "exams"


def test_card_rows_close_up_as_subjects_grow():
    cells = [float(_card_cell(n)[:-2]) for n in (5, 7, 9, 11, 13, 16)]
    assert cells == sorted(cells, reverse=True) and cells[0] == 2.4


def test_card_keeps_room_to_sign_in_the_earlier_layout():
    """R22-1: the earlier black-and-white card with the v30 header (no Urdu) and the room to sign kept."""
    card = (TEMPLATES / "exam_card_document.html").read_text()
    assert 'class="signroom"' in card and "THE ARQAM SCHOOLS" in card and "banner" not in card
    assert "TOTAL MARKS" in card and "PERCENTAGE" in card and "Remarks:" in card


def test_date_sheet_tab_has_the_designs_corners():
    sheet = (TEMPLATES / "date_sheet_document.html").read_text()
    assert "border-radius: 12mm 2mm 3mm 1mm" in sheet
