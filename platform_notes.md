# Platform notes — ATS mechanics learned by doing

Maintained by the fill assistant **autonomously**: append what you learn in
the same session you learn it (selectors that lie, what wedges a page, what
needs the user's native dialog). The user only reads results.

## Quick matrix (2026-09-10)

| Platform | Automation | Notes |
|---|---|---|
| Ashby (jobs.ashbyhq.com + custom domains rendering inline, e.g. jobs.valarlabs.com) | ✅ full | file_upload works; comboboxes are type-to-filter; Yes/No buttons use aria-pressed |
| Greenhouse new domain (job-boards.greenhouse.io) | ✅ full | see mechanics below |
| Lever / Polymer | ✅ full | simple flat forms |
| Greenhouse old domain (boards.greenhouse.io) as embedded iframe — Stripe, DigitalOcean, Nuro, IXL | ❌ | extension has no permission inside the cross-origin iframe; Simplify can fill it but we cannot inspect or swap the resume → user manual |
| Phenom (careers.chewy.com / careers.cisco.com / careers.rocket.com — /us/en/apply?step= wizards) | ❌ | see Phenom section → user manual |
| avature (Intuit) | ⚠️ partial | no JS injection; uploads + password user-only; labels lie, trust `find` |
| careers.roblox.com | ❌ | extension lacks site access |

## Simplify (applies everywhere)

- Run autofill FIRST, then inspect and fix — its re-navigation
  (`?gh_src=Simplify`) can wipe manually-filled fields.
- Profile-backed fields reliable; AI free-text always invents (citizenship=
  USA, salary sentences, fake tech integrations) — rewrite every subjective
  answer in chat for the user.
- Always uploads its own stored resume, which is usually stale —
  swap the correct PDF into the form's file input and **verify the filename**.
- Its Documents-page upload is native-dialog-only: the stored resume cannot
  be re-seeded programmatically.
- Sidebar "Completed" list is not verification — dump the form and check.
- Education dates sometimes filled wrong mid-run then self-corrected — only
  trust the final state.

## Greenhouse (job-boards.greenhouse.io) — learned 2026-09-09 on Twitch/Scale

- Real `input[type=file]` (`#resume`, `#cover_letter`) → `file_upload` works.
  Easy to hit the Cover Letter slot by mistake; verify filename after.
- Plain text inputs batch fine via `form_input` (7 in one call OK).
- Custom `Select...` dropdowns: **one per round trip** — scroll into view,
  click to open, wait 1s, click the option, screenshot to verify. Batched
  clicks outrun the open animation. Typing + Enter does NOT select.
- `element.value` lies on these widgets (reads empty while UI shows a
  value); filled comboboxes keep the value in a sibling div. Verify by
  visible text / screenshot, not DOM value.
- Number inputs (education years) are native — form_input works.
- Forms often end in reCAPTCHA — user solves at submit.

## avature (Intuit) — 2026-09-09

- JS injection blocked (domain not in extension allowlist): everything via
  find / read_page / form_input / screenshots.
- Selects are native; `form_input` sets them, but the visible label often
  does not refresh — `find` reads the true value; trust it over screenshots.
- The résumé "My Computer" button is a real file input but ignores synthetic
  change events — user clicks it and uses the native dialog.
- The application doubles as account registration (password mid-form) —
  user-only.
- Education: degree select first; school is searchable ("University of
  California, Los Angeles" with comma); "Did you graduate = No" spawns
  "actively pursuing?" → Yes.

## Phenom (careers.chewy.com / careers.cisco.com / careers.rocket.com) — 2026-09-10

- Our extension's `file_upload` synthetic upload **wedges the page
  permanently** (all script injection times out; no recovery). Chewy and
  Cisco both confirmed. Never file_upload on a Phenom domain.
- Simplify tolerance varies: Cisco survived Simplify autofill (fields filled
  fine); Chewy and Rocket wedged even on Simplify autofill.
- Consequence: resume swap is impossible programmatically → Phenom domains
  are **user-manual** end to end. If fields did get autofilled before a
  wedge, the user still must redo the resume via the native dialog.
- Job pages render via a chatbot-laden SPA; job content can take several
  seconds; cookie dialog "Save Preferences" = necessary-only.

## Google careers (2026-09-08)

- Own résumé parser fills work history + ~55 skills; parse needs heavy
  correction (invented employers, junk entries). **Deleting parsed skill
  chips does not persist** — they return on reload.
- Referral attaches inside the form itself.
