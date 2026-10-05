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
 /scout Nd ─▶ voyager search ─▶ scout.py: dedup · blacklist · title/yoe/closed/stale rules
                (browser only fetches;        │
                 results go to disk)          ▼
                                   parallel judge subagents (≤30 evidence rows each)
                                   0 → queue · −1 → human picks · ≤−2 → drop
                                              │
 /saved-jobs-triage ◀── 5 at a time, tabs left on the apply page ─┘
        │  fact cards; ledger records only "seen"
        ▼
   the human ──▶ /job-apply ──▶ on request: /resume-tailor · form answers · reach out
                                                          (find the HM, or ask for a ref link)
        ▲
        │  weekly
 /inbox ─▶ read-only Gmail: rejections · OAs (auto vs. real) · interviews
        │      ─▶ email_signals.tsv ─▶ market-feedback report
        └────▶ interview signal ─▶ interview_hub/actual_interviews/<role>/
                                     (context + JD + resume → a voice mock-interview agent)
```

State lives in flat files: `ledger/jobs.tsv` (append-only; records only
that a posting was *seen*), `ledger/email_signals.tsv` (outcomes from the
inbox), `cards/` (fact-card cache), `applications/` (written only when a
resume was tailored), `outreach/` (messages, written on request). `bin/job.sh` is the only sanctioned query/write path —
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
| "did you submit?" never answered | silence-means-applied + a `pending` roll-call — *later abandoned, see below* |
| same req, two ids | URL + numeric-id normalization in `lookup` |
| free-text status values | enum validation in `check` |

Count after: 0. The general lesson matches v1's: **a rule that lives only
in prose is a rule nobody can check.** v2 keeps judgment in prose and
moved every checkable invariant into scripts.

## Closing the loop (week 3)

v1's README ends on the number that mattered most: *interview-signal
column filled — 0 of 1,488.* Three weeks into v2 the same question came
due, and the ledger couldn't answer it either. A review of the live system
found three loops that collected data but never closed:

| loop | what the data showed | change |
|---|---|---|
| submission status | 113 of 534 postings stuck in an open state; nothing could force "I submitted" to be written down | the ledger now records only **seen / not seen** — a cursor, not a status machine. Outcomes come from the inbox instead |
| outreach | 104 message drafts, 28 ever marked sent; of 67 drafted in the last two weeks, 2 went out. Drafts were written before any recipient existed | messages are written **on request**, after the funnel layer is diagnosed (find the hiring manager vs. ask for a referral link) and a named person is found |
| skill gaps | 70 tailoring passes re-added the same handful of words; the gap report was 144 lines, and 28 words carried contradictory "can / can't" labels written at different dates | the report re-derives each label from the current vocabulary file and prints only what crosses a threshold; frequent words were stored back into the baselines once |

Scout had the opposite problem — too much input. A day's search left
hundreds of postings for one context to score, and misses crept in. The
deterministic rules (dedup, blacklist, title level, years, closed or stale
posts) moved into `bin/scout.py`; only the judgment calls go to parallel
subagents, ≤30 evidence rows each, and the merge step refuses to proceed
if any row lacks a verdict. Score 0 is queued automatically; score −1 is
listed for the human to pick from.

### What the inbox said

`/inbox` reads Gmail read-only, in parallel weekly slices, with three recall
paths: outcome keywords, a keyword-free sweep of every ATS sender
(including spam), and LinkedIn messages. The keyword-free sweep added 10
of the 82 signals found for the first four weeks.

| | count |
|---|---|
| applications (approx.) | 250 |
| rejections | 62 |
| OAs | 14 — **13 judged automatic** (≤24 h after the confirmation email, or the email itself says every applicant gets it) |
| interviews / role-specific calls | 5 |
| passed screening, then stopped by a hard constraint | 1 |

Two readings held up; most others did not survive the sample size:

- **Of the 7 positive outcomes, 4 came through a person** — a referral to
  the hiring manager, a career-fair conversation, a manager answering
  outreach, a referral link. The 3 that came from cold applications all
  ran into the visa question later.
- **Rejections carry almost no information about direction.** Of 45
  rejected postings with a fact card on file, none met a strict definition
  of "clean" (explicit new-grad signal, no stated sponsorship limit,
  graduation window explicitly compatible). Every rejection was already
  explained by sponsorship, window, a seniority mismatch the scout had
  under-scored, or a stale post. Rejections within two days of applying are
  reported separately and never used as evidence about direction.

Without the automatic-OA filter, "move forward" would have been inflated
about threefold.

### Hand-off to interview prep

An interview signal opens `interview_hub/actual_interviews/<company>_<role>/`
with `context.md` (round, time, format, interviewer, official prep
material, how the opportunity came about, open questions — every line
tagged with its source), the fact card, and the resume actually sent. The
hub is a file-driven mock-interview workspace run by a separate voice
agent; it reads the folder and builds the practice session. Nothing in
the hub claims access to real company questions.

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
- **Inbox classification is model judgment** over email text; the 24-hour
  automatic-OA heuristic and "role-specific call vs. coffee chat" are
  calibrated on one person's mailbox. Every row keeps the evidence quote.
- **Feedback samples are small.** Weekly reports print counts next to
  every ratio and say "not enough to tell" when that is the answer.
- v2's live files are Chinese-first. Structure is language-agnostic;
  the docs you're reading cover the design in English.

## Layout

```
PLAYBOOK.md        the method itself, code-free (Chinese)
SETUP.md           adopt this: prerequisites, templates, first run (Chinese)
skills/            six Claude Code skills — scout, saved-jobs-triage,
                   job-apply, resume-tailor, inbox, ask (Chinese; sanitized
                   copies of the live system, personal constants <like this>)
templates/         skeletons for the personal files the skills read
bin/               job.sh (ledger verbs) · scout.py (search pipeline) ·
                   inbox.py (feedback merge + report) · tailor_check.sh
                   (resume audit) · audit.sh (consistency)
browser/           voyager search / JD fetch / evidence rows / apply-link
                   and corner-scan snippets, plus browser pitfalls
config/            scout queries · third-party blacklist · gaps skip-list
interview_hub/     file-driven mock-interview workspace (framework only;
                   actual_interviews/ is filled by /inbox, keep it private)
```
