# applyloop

A job search run with AI — first as a pipeline, then as an assistant.
Two generations live in this repo, and the distance between them is the
most useful thing here.

**v1** (this directory) scraped LinkedIn daily, deduped, filtered and
bucketed every posting into a board, and drove a fill assistant from it.
It worked, and its own ledger showed why it was wrong: 1,488 postings
ingested, 69% bottom-tier, 933 rows nobody ever acted on, and a feedback
loop with working code and zero data. Automating *recall* produced volume,
not signal — and the careful work drowned in it.

**v2** ([`v2/`](v2/)) inverts the division of labor: the human does recall
(a LinkedIn *Saved* list, five at a time), the model does the careful
reading under written rules it must re-read every session, and small shell
scripts hold the invariants — append-only ledger, resume-diff whitelists,
three-way consistency audits. Four prompt files and ~300 lines of shell
replaced most of the pipeline, and throughput roughly doubled.

| | start here |
|---|---|
| the job-search **method** (kill rules, outreach, resume protocol) | [v2/PLAYBOOK.md](v2/PLAYBOOK.md) *(中文)* |
| the v2 **design story** — what v1's data said, what was cut, what it cost | [v2/README.md](v2/README.md) |
| **adopt it** yourself | [v2/SETUP.md](v2/SETUP.md) *(中文)* |
| the v1 pipeline's design rationale, kept honest | [DESIGN.md](DESIGN.md) |

Built on [Claude Code](https://claude.com/claude-code). Single-user, in
daily use; v2 is current, v1 is archived in place and still runnable.

## What both generations refuse to do

**Never submits.** Forms get filled; the last click is the human's.

**Never invents.** Nothing reaches a resume or a form that is not
traceable to a recorded fact. In v2 this is two script-checked boundaries:
sentences must come from the material library (verbatim at L2; verb-level
bounded rewrites at L3), and every technical term must exist in an
append-only "skills I actually have" list.

**Answers honestly.** Work-authorization and sponsorship questions get the
true answer, always — even when that is what a filter screens for.

## The lesson, in one table

| | v1 | v2 |
|---|---|---|
| recall | scraper + classifier + 5-axis buckets | human's Saved list; optional scout that pre-kills only the certain noes |
| judgment | regex rules; an LLM score column that stayed empty | the model, under prose rules with a feedback loop into them |
| invariants | scattered through pipeline code | `job.sh` / `tailor_check.sh` / `audit.sh` |
| result (per active day) | ~4.6 applications | ~17 applications, tailored resumes included |

The rules that survived the rewrite: the ledger is append-only and
authoritative; every rejection carries a reason and reasons become rules;
truthfulness boundaries are file lookups, never judgment calls.

## v1 layout (archived)

```
jobs.csv                the ledger        agents/     the two operating manuals
rulebook.md             rules + changelog scripts/    classify / ingest / board / export
config/profile.yaml     the candidate     template/   fillable personal files
DESIGN.md               why, incl. what was wrong     tests/      classifier coverage
```

v1's scraping ran against LinkedIn's internal API from inside the user's
own logged-in browser — a grey area discussed honestly in
[SETUP.md](SETUP.md#scraping-honestly) and inherited knowingly by v2's
scout (same stop-on-401, same pacing, no shipped data).

MIT licensed.
