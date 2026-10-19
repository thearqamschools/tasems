# Design system

One place for how every TASEMS screen looks and behaves. **Live examples:** sign in with a staff
account and open `/design-system/` (Settings → Design system). Decisions: D-055 (approach), D-061 (colours).

| Part | File |
| --- | --- |
| Tokens and components (one stylesheet, numbered sections) | `static/css/tasems.css` |
| Behaviours (sidebar, branch picker, confirmation dialog, double-submit guard) | `static/js/tasems.js` |
| Icons (Lucide, ISC licence, only the ones used) | `static/icons/icons.svg` + `{% icon "name" %}` (`tasems_tags`) |
| Page frame (sidebar, top bar, dialog) | `templates/base.html` |
| Form field (label, required mark, help, error) | `templates/includes_field.html` |
| Menu (groups, permissions) | `apps/accounts/context_processors.py` |

No outside services: fonts, icons and scripts are served by TASEMS itself. No build step.

## Colours

From the official logo (measured from `static/img/arqam-logo.png`):

| Token | Value | Use |
| --- | --- | --- |
| `--brand` | `#3E4095` | Primary buttons, links, active states (8.9:1 on white) |
| `--brand-strong` | `#2B2D6E` | Sidebar, hover |
| `--accent` | `#ED3237` | Active-menu marker, sidebar edge, icons, bars — **not small text** (4.1:1) |
| `--accent-ink` | `#C41F26` | Red text that must be readable (5.9:1) |
| `--ok` / `--attention` / `--danger` | `#1F6B3A` / `#8A5A00` (bar `#D99A1E`) / `#B42318` | Status only |

Every text/background pair passes WCAG AA (4.5:1). Status colours are separate from the brand so a red
badge always means a problem.

## Typography

Noto Sans (English), Noto Nastaliq Urdu (Urdu, line height 2.1). Scale: `--step--2` 12px · `--step--1` 14px ·
`--step-0` 16px · `--step-1` 19px · `--step-2` 26px · `--step-3` 34px. Numbers use tabular figures and stay
left-to-right inside Urdu text (`class="num"`).

## Components

| Component | Markup |
| --- | --- |
| Page header | `<h1>` + `<p class="lede">`; with actions on the right: `<div class="page-header">…</div>` |
| Buttons | `.button` (primary) · `.secondary` · `.quiet` · `.danger` · size `.sm`; icon inside with `{% icon %}` |
| Action row | `<div class="actions">` |
| Card | `.card`, title `.card-title` |
| KPI figure | `<div class="figures"><a class="figure" href=…><div class="value">…</div><div class="label">…</div></a></div>`; tones `.ok`, `.attention`, `.danger` |
| Table | `<div class="table-wrap"><table>…</table></div>`; numbers `<td class="num">`; totals in `<tfoot>` |
| Filter bar | `<form method="get" class="card">` with `.form-grid` and `.actions` — styled automatically |
| Form field | `{% include "includes_field.html" %}` — required `*`, help text, error state |
| Badge | `.badge` · `.ok` · `.attention` · `.danger` · `.muted` |
| Messages | Django messages framework — shown in the frame with an icon per level |
| Callout | `<div class="callout attention">{% icon "triangle-alert" %}<div>…</div></div>` |
| Empty state | `<div class="card empty-state">{% icon "inbox" %}<p>…</p><div class="actions">…</div></div>` |
| Risky action | `<form method="post" data-confirm="What will happen" data-confirm-button="Cancel voucher">` + `.button.danger` |
| Disclosure | `<details><summary>…</summary>…</details>` (used for actions that need a reason) |
| Tabs, pagination | `<nav class="tabs">` with `aria-current="page"`; `<nav class="pagination">` |
| Quick actions | `<nav class="quick-actions">` of links with an icon |
| Meter | `<span class="meter"><span style="inline-size:42%"></span></span>` (`.wide` for full width) |
| Horizontal bars | `<ul class="hbars">` rows of label, `.hbar-track` > `.hbar-fill`, value |
| Column chart | `apps/dashboards/charts.column_chart(points)` + `{% include "dashboards/_columns.html" with chart=… title=… %}` (D-064) |
| Money figures | add `class="money"` so "Hide amounts" can mask them; charts of money pass `money=True` |
| Link cards | `<div class="setup-cards"><a class="setup-card" href=…>{% icon … %}<div><strong>…</strong><p>…</p></div></a></div>` (Setup hub) |
| Form labels | plain, translated labels set in the form (`apps/setup/forms.LABELS`), never the model field's English name |

## Behaviours (`static/js/tasems.js`)

- **Confirmation dialog:** any form with `data-confirm` asks first; the same button (with its name/value) is
  sent after "Yes, continue". Without JavaScript the form submits as before.
- **Double-submit guard:** every POST form shows "busy" on the pressed button and ignores further presses, so
  a payment cannot be saved twice. Resets after 8 s (downloads) and when coming back with the Back button.
- **Sidebar:** collapse remembered per browser; slides in on phones; Escape closes it.
- **Branch picker:** type to filter; Enter opens the first match.
- **Scope chooser:** a form with `data-scope-form` shows only the field marked `data-scope-only="<scope>"` that
  matches the chosen "Where" (head office, region or branch). Without JavaScript all fields show.

## Rules

1. Use tokens (`var(--brand)`), never new hex values in templates.
2. Logical properties only (`margin-inline-start`, not `margin-left`) so Urdu mirrors correctly.
3. Show an action only to people allowed to use it (same permission check as the view).
4. Every new label in `{% trans %}` and in `locale/ur`; strings inside `<script>` go through `escapejs`.
5. Touch targets at least 44 px (`--control-h`); check new screens at 390 px wide and in Urdu.
6. The official logo is used as provided (D-051).
