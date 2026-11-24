---
name: tasems-marks-reader
description: Reads a photo or scan of a hand-filled TASEMS marks sheet (The Arqam Schools — one exam, one class section) and fills the matching TASEMS marks Excel, ready to import in TASEMS → Exams & Results → the section → Bring in marks from Excel. Use when the user gives a photo / scan of a marks sheet or asks to put hand-written marks into TASEMS.
---

# TASEMS marks reader

Teachers of The Arqam Schools fill the marks of an exam by hand on the sheet TASEMS prints ("Sheet to fill by
hand"). The office then needs the same marks in TASEMS's **marks Excel** for that section ("Marks sheet (Excel)",
downloaded from the same page). Your job: read the photo(s) and fill that Excel, so nobody types the marks again.

## What the user gives you

1. The **marks Excel** of the section, downloaded from TASEMS (sheet **Marks**). Ask for it if it is missing: it
   holds the students' codes and the hidden column keys TASEMS needs. Never make a new workbook.
2. One or more **photos / scans** of the hand-filled sheet of the same exam and section.

## Steps

1. Open the Excel. Row 2 has the headings: ADM.NO., Name, then each subject with its total in brackets
   (e.g. `English (40)`), then Attentive, Punctual, Neatness, Participation. Row 3 is hidden: **do not change it**.
2. For each student on the photo, find their row in the Excel **by ADM.NO.** (the admission number column); check the name
   matches. Fill:
   - each subject: the marks written (whole or half marks); `A` if written as absent / A / Abs.
   - Attentive, Punctual, Neatness, Participation: `E` (Excellent), `G` (Good) or `F` (Fair) as ticked or written;
     `G` if nothing is marked.
3. A mark more than the subject's total, or a cell you cannot read clearly: **leave it empty** and list it.
   Never guess a number.
4. Do not add or remove rows or columns, and do not change admission numbers, names, headings or the hidden row.

## What to give back

- The filled Excel, named like the one received (e.g. `Marks <exam> <section>.xlsx`).
- A short list: cells left empty and why (unclear, above the total, student not on the photo), and any student on
  the photo who is not in the Excel.

The user then chooses the Excel in TASEMS ("Show the Excel's marks"), checks the marks on the screen and presses
**Save marks**. TASEMS checks every mark again against the totals.
