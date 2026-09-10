# Daily Scraper — operating manual (v2, 2026-09-10)

You are a Claude session invoked via `/scrape` (see
`.claude/skills/scrape/SKILL.md`). Your job is one thing only:

**Pull today's new LinkedIn postings, enrich each with JD text, and hand off
an `enriched.jsonl` file to the filter agent.** You do not filter, score, or
ingest — those live in other sessions.

This is a production tool that a stranger from GitHub should be able to
follow. Prefer clarity over cleverness; treat the JS snippets in
`scripts/browser_snippets/` as the source of truth for browser-side logic.

---

## Files & data flow

**Read (durable, shared with other sessions):**
- `rulebook.md` §1 (only to know what the filter downstream expects)
- `config/sources.yaml` — the 6 queries and their tuned params
- `jobs.csv` — used only to build the dedup set of already-seen jids

**Write (ephemeral, cleaned up by convention):**
- `data/pending/linkedin_voyager_<date>.json` — raw voyager search cards (dedup-only)
- `data/pending/linkedin_jd_<date>.jsonl` — raw voyager JD bodies, keyed by jid
- `data/pending/linkedin_voyager_<date>.enriched.jsonl` — **the handoff artifact**
  (consumed by `scripts/ingest.py`; see the handoff contract below)

**Never touch:** `jobs.csv`, `rulebook.md` (unless the user asked mid-session),
`experiences.md`, `application_records/`, resumes.

## Handoff contract

The filter agent consumes exactly one file per scrape:

```
data/pending/linkedin_voyager_<YYYY-MM-DD>.enriched.jsonl
```

Each line is one JSON object with:

| Field | Type | Notes |
|---|---|---|
| `jid` | string | LinkedIn job posting id |
| `title` | string | posting title, voyager-authoritative |
| `company` | string | resolved from `included[]` |
| `location` | string | `formattedLocation` |
| `url` | string | `https://www.linkedin.com/jobs/view/<jid>` |
| `source_query` | string | which of the 6 queries surfaced this jid |
| `listed_at_ms` | int/null | LinkedIn's LISTED_DATE timestamp (often a repost, not original) |
| `date_posted` | string | `YYYY-MM-DD` derived from `originalListedAt` or `listedAt` |
| `applies` | int/null | number of applicants (heuristic proxy for competitiveness) |
| `external_url` | string | `applyMethod.companyApplyUrl` when present (~70% of rows) |
| `li_view_url` | string | canonical LinkedIn URL if voyager exposes one |
| `full_jd` | string | cleaned JD text (see `scripts/fetch_linkedin_jd.py`) |
| `_has_jd` | bool | true iff `full_jd` is non-empty |

Order across the file is not meaningful; the filter agent is expected to be
order-independent.

---

## Tuned parameters (change here, not in JS)

The JS in `scripts/browser_snippets/*.js` takes these as `opts` — the manual
is the single source of truth for the numbers.

| Param | Value | Where | Rationale |
|---|---|---|---|
| `timeRange` | `r86400` (24h) | search | volume calibrated 2026-09-10: 6q × 24h → ~490 unique/day. `r259200` (3d) for catch-up, `r604800` (7d) for onboarding a stranger with an empty CSV. |
| `sortBy` | `DD` (date-desc) | search | filter early-exits on stale pages when it can |
| `experienceList` | `2,3` (Entry+Associate) | search | ~75% noise cut, but drops posters who leave the field blank (Mayo, Stanford Med). Most are X8/X10 rejects or land in D8 anyway. Pass `""` when the user reports a specific miss. |
| `geoId` | `103644278` (US) | search | user constraint |
| `pageSize` | `25` | search | LinkedIn max per request |
| `interPageMs` | `150` | search | polite pace; 302/401 has never fired at this cadence |
| `conc` | `4` | JD fetch | 4-way concurrent; 100% success rate observed across 1000+ fetches |
| `pauseMs` | `150` | JD fetch | between chunks |
| `batchSize` | `120` | JD fetch | one `javascript_tool` call has ~45s timeout; 120 jids × ~250ms ≈ 30s |

The 6 queries live in `config/sources.yaml` under
`sources.linkedin_browser.queries`. Adding a query is one line there; no code
change.

---

## Pre-flight

1. Ask the user which Chrome to drive:
   ```
   mcp__claude-in-chrome__list_connected_browsers
   ```
   Even if the list has one entry, still ask — this is a browser-permission
   step the user needs to see. Then `select_browser` with the chosen deviceId.

2. Verify the tab and auth:
   - `tabs_context_mcp` — if no tab in the group, `tabs_create_mcp` + navigate
     to `https://www.linkedin.com/jobs/search/`
   - Confirm auth by hitting voyager once (count=1 anywhere) and expecting
     200. If you get 302/401, tell the user to log in and stop; do not retry.

3. Warn the user: **do not touch LinkedIn in any tab during the scrape.**
   Voyager rotates `JSESSIONID` when the user is active elsewhere, which
   silently breaks concurrent fetches.

---

## Protocol

### 1. Build the dedup set

```python
# in a Bash python -c block
import csv
existing = {r['id'] for r in csv.DictReader(open('jobs.csv'))
            if r.get('source') == 'linkedin' and r.get('id')}
```

Keep this in scratchpad; you'll subtract it after the search step.

### 2. Voyager search — 6 queries, exhaustive, dedup-in-browser

Install the search snippet, then run one query per `javascript_tool` call
(each query is 6-10 pages, ~1-2 seconds; the 45s CDP timeout is not the
binding constraint here but batching 2-3 queries per call is fine):

```
<contents of scripts/browser_snippets/voyager_search.js>

// per-call: run one query, stash into a global map keyed by jid
window.__all = window.__all || new Map();
const r = await window.linkedin.scrapeQuery("<QUERY>", {timeRange: "r86400"});
for (const c of r.cards) if (!window.__all.has(c.jid)) window.__all.set(c.jid, c);
JSON.stringify({kw: r.kw, fetched: r.fetched, stop: r.stop, unique: window.__all.size});
```

Do all 6 queries, then trigger a blob download for the merged unique cards.
Save the downloaded file to `data/pending/linkedin_voyager_<date>.json`.

Sanity check: expected `unique` after 6 queries is ~400-600 in the 24h
window; a `total` per query above ~500 is unusual (LinkedIn's counts are
noisy but not that noisy — investigate before scraping thousands).

### 3. Dedup against jobs.csv, write the JD target list

In Python (Bash tool):

```python
scrape = json.load(open(f'data/pending/linkedin_voyager_{DATE}.json'))
new = [c for c in scrape if c['jid'] not in existing]
```

Log both counts (`raw`, `new`) so the user can compare against yesterday.

### 4. Install jids into the browser

Write a small Python snippet that emits a JS `window.__jids = [...]`
assignment to a scratchpad file (~10KB even for 700 jids). Read that JS in
one call, paste into `javascript_tool`. Also install
`scripts/browser_snippets/voyager_jd_batch.js` in the same call:

```
<contents of voyager_jd_batch.js>
window.__jids = [...];
window.__jd_raw = window.__jd_raw || {};
JSON.stringify({installed: window.__jids.length});
```

### 5. Fetch JDs in batches of 120, resumable

Each subsequent `javascript_tool` call is a batch:

```js
const targets = window.__jids
  .filter(j => !window.__jd_raw[j])
  .slice(0, 120);
const r = await window.linkedin.fetchJDs(targets, {store: window.__jd_raw});
JSON.stringify({...r, remaining: window.__jids.length - Object.keys(window.__jd_raw).length});
```

Repeat until `remaining === 0`. Any 429/403 → stop, wait 5 min, resume; the
`filter(j => !window.__jd_raw[j])` line makes the loop safely resumable
across timeouts and errors.

### 6. Dump JDs to disk

```js
window.linkedin.dumpJDs(window.__jd_raw, `linkedin_jd_${DATE}.jsonl`);
```

The user's browser will trigger a download to `~/Downloads/`. Move it to
`data/pending/`. If the file is >10MB LinkedIn may refuse the auto-download —
tell the user to save it manually from the blob URL tab that opens.

### 7. Parse into enriched.jsonl

```
python3 scripts/fetch_linkedin_jd.py \
  --raw    data/pending/linkedin_jd_<date>.jsonl \
  --scrape data/pending/linkedin_voyager_<date>.dedup.json \
  --out    data/pending/linkedin_voyager_<date>.enriched.jsonl
```

Where `<date>.dedup.json` is the dedup-vs-jobs.csv result from step 3.

### 8. Sign-off message

Report to the user in this exact shape (paste-friendly):

```
✅ scrape done — 2026-09-10
  raw voyager cards:  <N>
  new after dedup:    <M>
  JD fetch success:   <K> / <M>
  handoff file:       data/pending/linkedin_voyager_2026-09-10.enriched.jsonl

Ingest picks it up with:
  python3 scripts/ingest.py --in data/pending/linkedin_voyager_2026-09-10.enriched.jsonl
  python3 scripts/board.py
```

Under the `/scrape` skill you run that ingest yourself — it is phase 2 of the
same session, see `.claude/skills/scrape/SKILL.md`. Stop here only if you were
invoked as a bare scraper without the skill.

---

## Failure modes & what to do

| Symptom | Diagnosis | Action |
|---|---|---|
| voyager 302 | session rotated (user touched LinkedIn) | stop, ask user to leave LinkedIn alone, restart from step 2 |
| voyager 401 | session expired | ask user to log back in, then restart |
| voyager 409 (rare, seen once mid-session) | LinkedIn paging state confused | retry the same query alone once with a fresh JS call |
| voyager 429 | rate-limited | stop, wait 5 min, resume — `__jd_raw` is preserved |
| `javascript_tool` CDP timeout | JS ran past 45s | shrink batch (120 → 60), state is preserved in `window.*` |
| Blob download blocked / silent | Chrome mixed-content policy | tell user to save manually from the auto-opened blob URL tab |
| `formattedExperienceLevel: ""` shows up in your investigation | poster left the field blank | expected; those posters are drops server-side because of `experienceList: "2,3"`. Only relax the filter if the user reports a specific miss. |

## Non-goals — do not attempt

- Guest endpoint (`/jobs-guest/`) — 5-concurrent hard rate limit, cannot auth
  around it. Only the authenticated `/voyager/api/...` path is supported.
- Cookie management — the browser owns the session; you never see or forward
  cookies (Claude's extension blocks direct cookie access, and that's fine).
- Cross-source scraping — this project is single-source LinkedIn since the
  2026-09-01 refactor. Legacy multi-source code lives in `scripts/legacy/`
  and is not called from any live path.
