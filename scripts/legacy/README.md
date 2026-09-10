# scripts/legacy/

Archived on 2026-09-10 during the scraper refactor.

Everything here is **not called** from any live path — kept in git so
someone re-enabling multi-source scraping does not have to reinvent it.

## What's here

| File / dir | Was called from | Why archived |
|---|---|---|
| `scrape.py` | `python3 scripts/scrape.py` (CLI) | multi-source orchestrator; all sources disabled since 2026-09-01 |
| `sources/` | `scrape.py` | one module per ATS (greenhouse / lever / ashby / workday / simplify / jobspy-linkedin) |
| `dedupe.py` | `scrape.py` | cross-source URL/id dedup — LinkedIn-only pipeline dedups on `jid` alone, no library needed |
| `fetch_jds.py` | `scrape.py`, one-off runs | early JD fetcher hitting LinkedIn's `/jobs-guest/`; rate-limits at 5+ concurrent, replaced by authenticated voyager via Chrome extension |
| `probe_ats.py`, `probe_workday.py` | one-off discovery | scripts used while building the multi-source config, not part of the daily loop |
| `bucketize.py` | (deleted 2026-09-10) | became `scripts/classify.py` + `scripts/ingest.py` — see the note at the bottom of this file |
| `utils/` | `fetch_jds.py` | `text_utils.strip_html` — the JD cleaner in `scripts/fetch_linkedin_jd.py` reimplements what's needed |

## Re-enabling

To bring multi-source back, at minimum:

1. Restore `scripts/scrape.py` and `scripts/sources/*` under `scripts/`
2. Move the disabled `sources:` block from
   `config/sources.disabled.yaml` back into `config/sources.yaml`
3. Adapt `scripts/ingest.py` — today it assumes `id = jid` (LinkedIn-only);
   non-LinkedIn sources need a source-scoped dedup key
4. Add per-source JD cleaners equivalent to `clean_jd()` in
   `scripts/fetch_linkedin_jd.py`

See `agents/DAILY_SCRAPER.md` §Non-goals for the rationale behind the
2026-09-01 single-source decision.

## 2026-09-10 — filter consolidation

- `hard_filter.py` (R1-R9) moved here. Its rules were merged into
  `scripts/classify.py` as X1-X9; keeping two filters meant they drifted, and
  `DAILY_SCRAPER.md` was pointing the downstream agent at the stale one.
- `bucketize.py` deleted — it *became* `scripts/classify.py` (rules) plus
  `scripts/ingest.py` (I/O). No behaviour was lost.

Nothing here is on a live path. Read for history, don't call.
