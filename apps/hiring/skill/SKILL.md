---
name: tasems-cv-reader
description: Reads job applicants' CVs (photos or PDFs) for The Arqam Schools and fills TASEMS's CV template, one row per CV, then returns the Excel file (and a ZIP of the Excel plus the CV files) ready to import into TASEMS → Hiring → Import CVs. Use when the user gives CVs or asks to put CVs into TASEMS.
---

# TASEMS CV reader

The Arqam Schools enter job applicants' CVs into TASEMS (the school's management system) by importing an Excel file
made from `CV-template.xlsx` (in this skill's folder). Your job: read every CV the user gives and fill that
template, so the office does not type the CVs by hand.

## Steps

1. Copy `CV-template.xlsx` from this skill's folder. Fill only its first sheet, **CVs**. The sheets **Lists** and
   **How to fill** give the allowed values and what each column means; follow them.
2. **One row per CV.** Several photos of the same CV (page 1, page 2) are one row; put all their file names in
   **CV File**, separated by commas, exactly as uploaded.
3. Copy only what the CV says. Leave a cell **empty** when the CV does not say it. Never invent or guess a mobile
   number, CNIC, date, year or name.
4. Values chosen from a list (**Applied For**, **Came By**, **Can Teach**, **Level**, **Gender**) must be written
   exactly as in the **Lists** sheet. Several subjects or levels: separate with commas.
5. **Received On**: today, unless the user gives a date. **Came By**: as the user says, else leave empty.
6. **Education**: `Degree | Institute | Year; Degree | Institute | Year` (highest first).
   **Experience**: `School | Post | Level | Years; …`. **Experience (Years)**: total years, a number.
7. Leave **Relevant** and **Reason** empty: the school decides.
8. Keep the header row and the column order as they are.

## What to give back

- `TASEMS-CVs.xlsx`: the filled template.
- If you can make files: `TASEMS-CVs.zip` containing `TASEMS-CVs.xlsx` and every CV file the user uploaded, names
  unchanged. TASEMS reads the Excel and attaches each CV file to its row by the **CV File** column.
- A short list of CVs you could not read well, with the reason (blurred photo, page missing …).

The user then uploads the ZIP (or the Excel alone) in TASEMS → Hiring → Import CVs, checks the list TASEMS shows,
and presses Import.
