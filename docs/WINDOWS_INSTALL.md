# TASEMS-Setup.exe — install TASEMS on one Windows computer

The offline test copy as a normal Windows installer, like the diary software: no Rancher Desktop or Docker,
no internet, no hosting. Everything TASEMS needs is inside the installer (about 62 MB).

## Install
1. Double-click **TASEMS-Setup.exe**. If Windows shows "Windows protected your PC", click **More info →
   Run anyway** (the installer is not signed with a paid certificate).
2. Next → Install → Finish ("Start TASEMS now" ticked). No administrator password is needed.
3. The first time, a black TASEMS window asks:
   - **1** = with fictional demo data and demo logins (for testing), or
   - **2** = an empty school with two-step sign-in, like the real server.
   Type 1 or 2 and press Enter. The first start takes a few minutes; then the browser opens TASEMS.
4. If Windows Firewall asks about Python, click **Allow** (needed only for other office computers to open it).

## Every day
- Double-click **TASEMS** on the desktop. Keep the black window open while working; **close it to stop**.
- On this computer: http://localhost:8000
- Other computers on the same office network: the address shown in the black window, e.g. http://192.168.1.10:8000

## Start menu → TASEMS
| Shortcut | What it does |
|---|---|
| TASEMS | Start (or open, if already running) |
| Make master login | A login that can do everything in every branch |
| Backup data | Saves all data to Documents\TASEMS backups |
| Stop database | Stops the database if the window was closed in an unusual way |
| Uninstall TASEMS | Removes the program; the data is kept |

## Demo logins (choice 1)
Password: **ArqamOffline2026** — demo-network, demo-headoffice, demo-director, demo-principal,
demo-accountant, demo-admissions, demo-teacher, demo-qari; parents at /parents/login/ with 0300-7000001.

## Where things are
- Program: `%LOCALAPPDATA%\TASEMS` (replaced by a newer TASEMS-Setup.exe)
- Data: `%LOCALAPPDATA%\TASEMS-data` (database, uploaded photos, keys made on this computer; kept on update
  and uninstall). To start completely fresh: uninstall, delete this folder, install again.
- Problems: `%LOCALAPPDATA%\TASEMS-data\logs`

## A new version
Run the new TASEMS-Setup.exe over the old one. Data is kept; new tables are added automatically on start.

## What is inside (all free, open source)
Python 3.12 for Windows, Django and the project's libraries, PostgreSQL 16 (only on this computer, port 55432,
not reachable from other computers), GTK (for PDFs), waitress (web server). Built on Linux with
`windows/build_installer.sh` (NSIS).

## How it was checked (23 Oct 2026)
- The launcher on Linux with PostgreSQL 16: first start (database made, demo data), second start (data kept),
  signing in from another address, PDF, stop.
- The Windows Python with all its libraries under Wine: TASEMS served by waitress, sign-in from another
  address, dashboard, PDF made with the bundled GTK.
- Not checkable without a Windows computer: the installer screens, shortcuts, and PostgreSQL's Windows
  programs (Wine cannot run them). The first install on a real computer is the final check.
