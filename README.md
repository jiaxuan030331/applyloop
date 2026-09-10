# applyloop

A job search run as a pipeline, by two AI agents and one person.

One agent finds and files openings. Another works through applications and
stops before every submit. You decide what gets applied to — and every time
you reject something and say why, that reason becomes a filter rule, so the
next batch is better than the last. That loop is the point, and the name.

```
  scrape ──▶ filter & bucket ──▶ jobs.csv ──▶ board ──▶ batch ──▶ you decide
                    ▲                                                │
                    └──────── your reasons become rules ─────────────┘
```

Built on [Claude Code](https://claude.com/claude-code). Currently
single-source (LinkedIn, through your own browser session), single-user, and
in daily use.

- **[SETUP.md](SETUP.md)** — what you need and how to make it yours
- **[DESIGN.md](DESIGN.md)** — why it is built this way, including what is
  still wrong with it

## The two agents

| | Entry point | Does | Writes |
|---|---|---|---|
| **Scrape & ingest** | `/scrape [24h\|3d]` | pulls the day's postings, dedups, filters, buckets, reports | new ledger rows, the board, a daily report |
| **Fill assistant** | `/batch <what you want>` | probes each posting, reports, waits for you, tailors a résumé, fills the form | application status, tailored documents |
| **You** | — | decide | anything, via `update_row.py` |

They are separate Claude Code sessions on purpose. Scraping is high-volume and
mechanical; filling an application is one posting read carefully, with a dozen
judgement calls. Running both in one agent means the careful work happens in a
context window already full of job listings.

## The ledger

`jobs.csv` is the source of truth — every posting ever seen, what was decided
about it, and why. Rejected rows are never deleted, only marked, so a rule
change can be audited against what it would have discarded.

`data/board.json` — what the fill assistant selects from — is *derived* from
it: exactly the rows still open. Retiring a posting means giving it a status,
never editing the board.

```bash
python3 scripts/update_row.py drop   <id> -m "why"   # reject, with a reason
python3 scripts/update_row.py lowfit <id> -m "why"   # off the board, not a rejection
python3 scripts/update_row.py reasons                # read your reasons back
```

## Filtering and bucketing

Ten coarse rules drop what you could not or would not take — clearance, export
control, senior titles, years of experience, pay below your floor, agencies,
internships, non-US postings, duplicates. Everything that survives is bucketed
five ways: region, employer tier, pay band, direction of the work, and how
confident we are the req is actually open to someone at your level.

Buckets rather than a single fit score, because the question you have is not
"is this a 4?" but "show me campus-confirmed ML infrastructure roles at strong
companies on the west coast" — five orthogonal dimensions answer that and a
scalar cannot.

Rules are deliberately blunt. When one could go either way it keeps the
posting and attaches a flag, because reading one extra row costs a minute and
missing a job you would have taken costs a cycle.

The rules live in `scripts/classify.py`; everything about *you* —  which
employers you rate, where you would move, what pay is worth an hour, what you
specialise in — lives in `config/profile.yaml`. Forking should mean editing
YAML, never regexes.

## What it will not do

**It never submits.** The fill assistant fills a form and stops. The last
click is yours.

**It never invents.** Nothing reaches a résumé or a form that is not traceable
to `experiences.md` (things you have done, with evidence) or
`claimable_skills.md` (skills you hold that no bullet spells out). The
boundary is a file lookup, not a judgement call — which is what stops a
tailoring pass from drifting into fabrication one plausible sentence at a
time.

**It answers honestly.** Work-authorisation and sponsorship questions get the
true answer, always, even when that is what a filter is screening for.

## Layout

```
jobs.csv                  the ledger
rulebook.md               rules, with the reasoning and a change log
experiences.md            what you have done — the boundary on every claim
config/profile.yaml       everything about you that the classifier needs

scripts/
  classify.py             filter and bucket rules (pure functions)
  ingest.py               handoff → dedup → classify → ledger → report
  board.py                ledger → board
  update_row.py           the only sanctioned writer
  reclassify.py           replay rules over history after a change
  export_public.py        build the shareable tree, by whitelist
  legacy/                 pre-2026-09-01 multi-source code, not on any path

template/                 fillable versions of the five personal files
agents/                   the two operating manuals
tests/                    coverage on the classifier
```

## Status and limits

Single-source and single-user. The scraping runs against LinkedIn's internal
API from inside your own logged-in browser — a grey area, discussed honestly
in [SETUP.md](SETUP.md#scraping-honestly). No scraped data ships with this
repo. The tier list and role buckets encode one person's view of the market;
the mechanism generalises, the starting values do not.

MIT licensed.
