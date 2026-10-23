# TASEMS on one office computer (offline test copy)

For testing everything built so far **before** putting it online. No Render or other hosting is needed.
Checked on 23 Oct 2026: the offline start script, the database set-up (row-level security on), demo data and
signing in from another computer by its network address (http://IP:8000) all work.

## What it is
- TASEMS runs on one Windows computer inside a free "container" program, with its own database.
- Open it on that computer at **http://localhost:8000**, or from other computers on the same office network
  (Wi-Fi/LAN) at **http://THAT-COMPUTER-IP:8000**.
- Internet is needed **once** (to download the program and build TASEMS, about 1–2 GB). After that it works
  without internet.
- Data stays on that computer only. Parents cannot reach it, and other branches cannot reach it.
- It does not update by itself: for a new version, replace the folder and run START again (data is kept).

## Computer needed
- Windows 10 or 11, 64-bit; 8 GB RAM (16 GB better); 15 GB free disk; virtualisation switched on in the
  BIOS (most computers already have it on).

## One-time installation
1. Install **Rancher Desktop** (free, open source): https://rancherdesktop.io → download for Windows →
   install. When it asks, choose the container engine **dockerd (moby)**. Restart if Windows asks.
   *Docker Desktop also works, but it is free only for organisations under 250 staff, so Rancher Desktop is
   used here (no paid service).*
2. Open Rancher Desktop and wait until it says it is running.
3. Copy the TASEMS folder to the computer, e.g. `C:\TASEMS` (from the ZIP you were sent).
4. Open `C:\TASEMS\offline` and double-click:
   - **START-TASEMS.bat** — with fictional demo data and demo logins (no two-step sign-in), or
   - **START-EMPTY-REAL-TEST.bat** — empty school, two-step sign-in on (authenticator app), like the real server.
   The first start takes 10–20 minutes.
5. Double-click **MAKE-MASTER-LOGIN.bat** and type a username, e-mail (can be left empty) and password. This
   login can do everything in every branch (Setup, users and roles, all modules).

## Logins with demo data (START-TASEMS.bat)
Password for every demo login: **ArqamOffline2026**

| Login | What it is |
|---|---|
| demo-network | Network administrator: both head offices, all branches, Setup |
| demo-headoffice | Faisalabad head office |
| demo-director | Director of the Samanabad campus: everything in the branch |
| demo-principal | Principal |
| demo-accountant | Accountant |
| demo-admissions | Admin (admissions) |
| demo-teacher | Class teacher (Class 4) |
| demo-qari | Qari (Hifz) |
| Parent: /parents/login/ | mobile 0300-7000001 |

## Every day
| File (in the offline folder) | What it does |
|---|---|
| START-TASEMS.bat | Starts TASEMS (or keeps it running) and opens it |
| STOP-TASEMS.bat | Stops it; data is kept |
| BACKUP-DATA.bat | Saves all data to the `backups` folder |
| MAKE-MASTER-LOGIN.bat | Makes another master login |
| RESET-ALL-DATA.bat | Deletes all data on this computer (asks you to type DELETE) |

Rancher Desktop must be open before START. After a computer restart, open Rancher Desktop, then START.

## A new version
Replace the TASEMS folder with the new one (keep the `backups` folder), then double-click START-TASEMS.bat.
The data is kept: it lives inside Rancher Desktop, not in the folder.

## Going online later
The same system goes on the online server. Test data from this computer can be moved there with a backup
file, but starting the real server with clean data (imported from the old software's Excel) is recommended.
