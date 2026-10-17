# UI/UX redesign plan

Goal: turn the existing staff screens into a modern, consistent, enterprise-quality interface **without changing
the stack** (Django templates, server-rendered, D-002/D-019) and without breaking any working screen.

## 1. Technology decision (proposed as D-055)

| Option | Fit with TASEMS | Decision |
| --- | --- | --- |
| **Extend the existing CSS design tokens into a component library** (`tasems.css` split into tokens, layout, components) | Already in place, RTL-safe (logical properties), no build step | **Adopt** |
| **HTMX** (≈14 KB, served locally) | Already approved in D-002; partial page updates for filters, search, modals without a JS framework | **Adopt** |
| **Lucide icons** (ISC licence) as a local SVG sprite of only the icons used | Works in templates via `<svg><use>`; ~30 KB | **Adopt** |
| **Charts:** Chart.js (MIT, served locally, loaded only on dashboard pages) | Interactive tooltips; ~70 KB gzip; no CDN | **Adopt for dashboards** (fallback table always shown) |
| Tailwind CSS | Needs a Node build step and rewriting all 72 templates' classes; duplicates existing tokens | **Not adopted** |
| shadcn/ui | React-only; would require a frontend framework migration (disallowed by the brief and D-019) | **Not adopted** — its visual language (neutral surfaces, 1-px borders, 8-px radius, quiet buttons) is used as inspiration |

Everything stays served from our own server (no CDNs): fast on slow links, works if outside services are blocked.

## 2. App shell (applies to every staff page through `base.html`)

- **Collapsible left sidebar** with grouped navigation and icons; collapses to icons on desktop, slides in on
  mobile; state remembered per browser. Mirrors to the right in Urdu (RTL).
- **Navigation groups** (only items the user's permissions allow appear, as today):
  1. **Overview** — Dashboard, Network (head office)
  2. **Students** — Students, Admissions, Parents, Attendance, Promotion & certificates
  3. **Academics** — Daily Diary, Exams & Results, Timetable, Hifz
  4. **Finance** — Fees, Collections, Defaulters, Accounts, Royalty
  5. **People** — Staff, Staff attendance, Leave, Payroll, My attendance
  6. **Operations** — Inventory, Notices
  7. **Reports** — Reports centre
  8. **Settings** — Branches, Sessions & classes, Fee setup, Users & roles, (Advanced → Django admin)
- **Top bar:** page title + breadcrumb, **searchable branch selector** (grouped Head office → Region → Branch,
  type to filter, works for 350+ branches), global student search (name / admission no. / mobile), language
  switch, user menu (profile, two-step sign-in, sign out).
- DEMO bar kept exactly as today.

## 3. Components (one place, reused everywhere)

| Component | Notes |
| --- | --- |
| Page header | Title, short description, primary action on the right, secondary actions in a menu |
| KPI card | Value, label, change vs. last period, optional sparkline, link to the detail |
| Data table | Sticky header, zebra-free with row hover, numeric columns right-aligned (`.num`), status badges, row actions menu, pagination, column for selection when bulk actions exist |
| Filter bar | Same layout on every list: search, 2–4 filters, "Clear", Export (Excel/PDF); HTMX updates the table without a full reload |
| Forms | Two-column on desktop, one on mobile; labels above fields; inline errors; sections with headings; sticky Save bar on long forms |
| Badges | Status colours from tokens: success, attention, danger, neutral, info |
| Empty state | Icon, one sentence explaining why it is empty, the next action |
| Loading state | Skeleton rows for HTMX requests; button spinner on submit; progress page for long PDFs |
| Toasts | Replace the current message list; same Django messages framework |
| Modal / drawer | Confirmations (cancel voucher, reverse payment) and quick views |
| Tabs | Student profile, staff profile, branch profile |

## 4. Role-specific dashboards

| Role | Dashboard contents |
| --- | --- |
| Head office | Network KPIs; attendance % today by branch; month collection vs. billed; royalty due; defaulters; admissions funnel; branches with registers/diaries missing; filter by head office/region |
| Principal | Today: registers taken, absent students, staff present/late, diaries published; month: collection, defaulters, admissions follow-ups due; class-wise strength chart |
| Class teacher | My sections: take register, write diary, marks pending, absent streaks |
| Accountant | Today's collection by channel, vouchers due, defaulters, recent payments, quick "Receive by Voucher ID" |
| Admissions | Follow-ups due today, visits today, funnel this month, conversions by source |
| Staff (self) | My attendance, leave balance |

Dashboards read the summary tables (e.g. `SectionAttendance`, D-022), never scan per-student rows at network level.

## 5. Visual language

- **Brand:** official logo unchanged (D-051). Colour tokens stay in one place; current green `#0f5c4d` is a
  placeholder per `tasems.css`. **Needs the official brand colours** (hex codes) from the project lead.
- **Type:** Noto Sans (English), Noto Nastaliq Urdu with generous line height (already bundled). Scale: 12/14/16/20/24/32.
- **Spacing:** 4-px grid; cards 16–24 px padding; consistent 8-px radius.
- **Density:** comfortable by default; tables use compact rows for long lists.
- **Accessibility:** WCAG AA contrast, visible focus ring (kept), keyboard-usable sidebar and menus, 44-px touch targets on phones.
- **Printable documents:** keep WeasyPrint templates; refresh vouchers/result cards/certificates with the same
  tokens and logo; add print styles for lists (Ctrl+P prints the table only).

## 6. UX fixes already identified

1. Hide actions a user is not allowed to perform (Remarks, Ratings, Receive, Take register on a non-school day) — show a short reason instead of a 403 page.
2. Branch switcher usable at 350+ branches.
3. Large print jobs run in the background with a progress page and download link.
4. Consistent filter bars and Export buttons across modules.

## 7. Rollout without breakage

- New shell lands first behind the same URLs and the same `nav_items` permission logic; page content blocks unchanged.
- Modules are then restyled one at a time; tests (55 of them check page HTML) run after each.
- Parent portal (`base_parent.html`) and PDF templates are restyled separately, after staff screens.
- Screenshots of every role's main pages before and after each milestone, kept in the pull request.
