# TASEMS online from the school's own computer (Cloudflare Tunnel)

Decided by the project lead on 28 Nov 2026 for Samanabad Campus (Round 24). TASEMS keeps running on the school's
Windows computer (the TASEMS-Setup installer); a free Cloudflare Tunnel makes it open at
`https://tasems.thearqamschools.com`. No server is rented and no port is opened on the school's router.

## Done once in Cloudflare (lead, 28 Nov 2026)
1. Networking → Tunnels → Create a tunnel → Cloudflared → name `samanabad-tasems`.
2. Windows: install cloudflared and run the given `cloudflared.exe service install <token>` in a Command Prompt
   opened with "Run as administrator" (the tunnel then starts with Windows by itself).
3. The tunnel → Routes → Add route → Published application: subdomain `tasems`, domain `thearqamschools.com`,
   Service URL `http://localhost:8000`. Cloudflare makes the DNS record.
4. The tunnel shows **Healthy**.

Recommended: Zero Trust → Access → Applications → a policy for `tasems.thearqamschools.com` letting in only the
school staff's e-mail addresses, so the TASEMS sign-in page itself is hidden from everyone else.

## On the school's computer (TASEMS v32 or later)
1. Install TASEMS v32. It starts by itself when Windows starts (minimised, no browser) — see the TASEMS shortcut in
   the Windows Startup folder.
2. Open `%LOCALAPPDATA%\TASEMS-data\config.env` in Notepad and add these lines at the end:

   ```
   PUBLIC_URL=https://tasems.thearqamschools.com
   BACKUP_COPY_TO=G:\My Drive\TASEMS backups
   ```

   `BACKUP_COPY_TO` is a folder off this computer's own disk: the Google Drive for desktop folder, or a USB disk
   that stays plugged in. Leave it out if there is none yet.
3. Close the TASEMS window and start TASEMS again. The window then shows the online address too.

## What TASEMS does then
- **Visitor's real address** (sign-in lock, audit log): read from Cloudflare's `CF-Connecting-IP` header, only for
  requests coming through the tunnel on this computer (`apps/core/net.py`). Without this, 20 wrong sign-ins by one
  person would have locked everyone out for 15 minutes.
- **Cookies**: https-only when TASEMS is opened through `https://…`; the office network (`http://192.168.x.x:8000`)
  keeps working.
- **Daily backup**: once a day while TASEMS runs, `Documents\TASEMS backups\tasems-daily-<date>.dump`, copied to
  `BACKUP_COPY_TO`; the last 30 daily backups are kept in each folder. "Backup data" still makes one by hand.

## Keep in mind
- A UPS on this computer. If the power or the internet is off, TASEMS is not online (it still works inside the
  school while the computer runs).
- Do not put the demo copy (option 1 at first start) online with real people using it; real data only in a copy
  started with option 2 (empty school, two-step sign-in).
- Online speed for people outside depends on the school internet's **upload** speed.
