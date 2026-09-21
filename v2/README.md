# applyloop v2 — the assistant that replaced the pipeline

v1 (the root of this repo) was a pipeline: scrape everything, classify
everything, rank everything, then apply. v2 is an assistant: a human picks
what to look at, a model reads it carefully under written rules, and a
handful of shell scripts guard the invariants. This document is the design
story — what v1's own data said, what was cut, what survived, and what the
rewrite cost.

For the job-search *method* itself (kill rules, outreach discipline, the
three-level resume protocol), read **[PLAYBOOK.md](PLAYBOOK.md)** (Chinese).
To run this yourself: **[SETUP.md](SETUP.md)**.

## The numbers that killed v1

Eleven days of running v1 produced, by its own ledger:

| metric | value |
|---|---|
| postings ingested | 1,488 |
| bottom-tier (T5) share | 69% |
| rows stuck in `open`, never acted on | 933 (63%) |
| applications + outreach actually sent | 51 |
| interview-signal column filled | 0 of 1,488 |

The pipeline was excellent at what didn't matter. Recall was automated —
so recall was enormous, mostly junk, and the board became a queue nobody
drains. Meanwhile the feedback loop that justified the architecture (email
→ interview signals → rule tuning) had working code, an OAuth setup, and
zero rows of data, because nothing forced anyone to run it.

Six days of v2 produced 100+ applications with tailored resumes, from a
system that is four prompt files, two TSVs, and ~300 lines of shell.

## What actually changed

One sentence: **work moved to the executor suited for it.**

| kind of work | v1 | v2 |
|---|---|---|
| recall (what's worth a look) | scraper + classifier + 5-axis buckets | the human's LinkedIn *Saved* list; optional `scout` that only pre-kills the certain noes |
| judgment (read a JD, weigh a posting) | regex rules + an LLM score column that stayed empty | the model, reading under prose rules (`rules.md`) it must re-read every session |
| invariants (dedup, formats, truthfulness bounds) | scattered through the pipeline | small scripts: `job.sh` (ledger verbs), `tailor_check.sh` (resume diff whitelist), `audit.sh` (cross-consistency) |

Three v1 ideas survived, generalized:

- **The ledger is append-only and authoritative.** Current state = last row
  per key. Status changes are new rows; nothing is edited or deleted, so any
  rule change can be replayed against history.
- **Rejections carry reasons, and reasons become rules.** Every correction
  the user makes is written into `rules.md` with a date and source. That
  file is the constitution; every entry skill reads it first.
- **The tailoring boundary is a file lookup, not a judgment call.** A resume
  line is either verbatim from the material library (script-verified), or a
  rewrite of a recorded fact whose verb may not exceed the recorded claim
  level (`used` can't become `built`). A separate append-only vocabulary
  list bounds individual terms. This is what keeps a hundred tailoring
  passes from drifting into fiction one plausible sentence at a time.

## Architecture

```
 /scout Nd ──▶ voyager search ──▶ evidence-row screening ──▶ click *Save*
                                        (JD never enters context)      │
                                                                       ▼
                                                          LinkedIn Saved list
                                                                       │
 /saved-jobs-triage ◀──── 5 at a time, tabs left on the apply page ────┘
        │  fact cards (facts only — no scores, no verdicts)
        ▼
   the human decides ──▶ /job-apply ──▶ tier A: apply + message   ──▶ ledger
                              │         tier B: ask first, 5-day timer
                              ▼
                        /resume-tailor  (L1 skills-line / L2 structure /
                                         L3 reword — script-audited)
```

State lives in flat files: `ledger/jobs.tsv` (append-only), `cards/`
(fact-card cache), `applications/` (immutable records), `outreach/`
(message archive). `bin/job.sh` is the only sanctioned query/write path —
`lookup` dedups by key, URL, *and* the long numeric id inside the URL
(job boards expose the same req under multiple URL shapes).

### Token discipline: evidence rows, not documents

v1 died partly of context weight. v2's scout fetches JDs into the
*browser's* memory and compresses each one, browser-side, into a ~300-char
evidence row (citizenship/clearance hits, years-of-experience phrase,
sponsorship sentence, graduation window, stack keywords —
`browser/jd_screen.js`). The model judges evidence rows; full text never
enters the context window. A hundred postings cost ~20k tokens instead of
~500k, and every drop still quotes the exact sentence that killed it.

### Sessions as the context log

Every card-producing action records `(session id, job key, status)` via
`job.sh logbatch`. Later, `job.sh trace <company>` returns the status
history, the fact card, the archives, *and* a `claude --resume <id>`
command — the full deliberation that produced a decision is one command
away, because the conversation itself is the log.

## The drift audit (what prompt-enforced protocols cost)

v2's first week was run with protocols enforced only by prompts. A
three-way reconciliation (`audit.sh`) then found **68 inconsistencies**:
52 tailored resumes with no application record, submissions filed under
"waiting", duplicate ledger entries under different ids. Each class got a
mechanism, not a reminder:

| failure | mechanism |
|---|---|
| resume produced, no record written | the tailor now writes a stub record itself when invoked directly |
| "did you submit?" never answered | silence-means-applied bookkeeping + a `pending` roll-call verb |
| same req, two ids | URL + numeric-id normalization in `lookup` |
| free-text status values | enum validation in `check` |

Count after: 0. The general lesson matches v1's: **a rule that lives only
in prose is a rule nobody can check.** v2 keeps judgment in prose and
moved every checkable invariant into scripts.

## Honest limitations

- **Writes are still prompt-initiated.** Scripts validate after the fact
  (`check`/`audit`); a session that skips the protocol isn't blocked at
  write time. The single-writer verb exists in v1 and hasn't been ported.
- **Single-user calibration.** Kill rules, resume versions, message tone —
  all one F-1 ML-new-grad's. The *mechanism* generalizes; the values don't.
- **The session-id capture has a race** when two sessions run at once
  (documented in `job.sh`; benign at this workflow's cadence).
- **The scraping question is inherited from v1** — scout drives the user's
  own authenticated browser tab, stops on 401/302, never retries, and
  ships no scraped data. See the root DESIGN.md's "On the scraping" for
  the honest discussion; the trade-offs are unchanged.
- v2's live files are Chinese-first. Structure is language-agnostic;
  the docs you're reading cover the design in English.

## Layout

```
PLAYBOOK.md        the method itself, code-free (Chinese)
SETUP.md           adopt this: prerequisites, templates, first run (Chinese)
skills/            four Claude Code skills — scout, saved-jobs-triage,
                   job-apply, resume-tailor (Chinese; sanitized copies of
                   the live system, personal constants marked <like this>)
templates/         skeletons for the four personal files the skills read
bin/               job.sh (ledger verbs) · tailor_check.sh (resume audit)
                   · audit.sh (three-way reconciliation)
browser/           voyager search / JD batch fetch / evidence-row screening
config/            scout search queries
```
