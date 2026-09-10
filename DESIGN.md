# Design choices

Why applyloop is built the way it is. Most of these were arrived at by getting them
wrong first; where that happened it is written down, because the failure is
usually the clearest argument for the fix.

---

## Three roles, three sessions, one file

The work splits into two jobs that want opposite things from a session.
Scraping is high-volume and mechanical: hundreds of postings, browser
automation, nothing to think about per row. Filling an application is the
reverse — one posting, read carefully, a dozen judgement calls, and a human
who must approve before anything is submitted.

Running both in one agent means the careful work happens in a context window
already full of job listings. So they are separate Claude Code sessions
(`/scrape` and `/batch`), and the interface between them is a file on disk:

```
/scrape ──▶ jobs.csv ──▶ board.json ──▶ /batch
              ▲                            │
              └────────── status ──────────┘
```

The seam is also where the human belongs. A batch stops and reports before it
touches a form, and that stop is only natural because the two halves were
never one process.

## Files, not a framework

There is no orchestration layer. State is a CSV and five markdown files.

Agents are the fastest-moving part of a project like this — models change,
prompts get rewritten, a session gets abandoned halfway. The ledger has to
outlive all of that. A CSV can be grepped, diffed, opened in Numbers, and
fixed by hand at 2am when something has gone wrong; a database or a bespoke
state format can do none of those under pressure.

The markdown files are prompts *and* documentation at once, which is the point:
`rulebook.md` is read by both agents before they act and by the user when they
want to know why a rule exists. One artifact, so it cannot drift from itself.

## One source of truth, and a derivative

`jobs.csv` is authoritative. `data/board.json` — the candidate list `/batch`
works from — is regenerated from it by `scripts/board.py`, and holds exactly
the rows with `status=open` and no `low_fit` mark.

It did not start that way. The board was originally a list the fill assistant
edited directly, deleting rows as it handled them. Rows deleted from the board
without a corresponding status in the ledger came back the next time the board
was rebuilt, and 43 of them did. Worse, the reasons for removing them existed
only in a chat log.

Making the board a derivative means there is exactly one way to retire a
posting: give it a status. That is now enforced by construction rather than by
asking the agent to remember two writes instead of one.

## The scrape phase

Everything before `enriched.jsonl` is one skill's problem. Four decisions
underneath it:

### Authenticated voyager, not the public endpoint

The first version fetched JDs from LinkedIn's public `/jobs-guest/` from a
Python worker pool. It works up to five in flight, then it doesn't, and
there is no anonymous knob that raises the ceiling. The authenticated
`/voyager/api/` path — hit from inside the user's own tab — handles 4-way
concurrent JD fetches at 100% success across a thousand-plus requests, and
the search endpoint accepts the server-side filters the guest endpoint does
not expose (time window, experience level, sort). So there is no Python
HTTP against LinkedIn on the live path; the browser extension drives the
tab, and Python only parses what the browser dumps to disk.

This has a second effect worth naming. No cookie ever leaves the browser,
no service holds credentials, and there is no way to run the scraper
without your own logged-in Chrome. Someone cloning the repo cannot cause it
to hit LinkedIn on your behalf.

### JS as code, tuned constants in the manual

The browser-side logic is two files under `scripts/browser_snippets/` —
`voyager_search.js` (paged search over one keyword) and `voyager_jd_batch.js`
(4-way concurrent JD fetch with a resumable store). Both install onto
`window.linkedin.*` and take an `opts` dict; every tuned constant — window,
concurrency, batch size, pace — lives in one config table at the top of
`agents/DAILY_SCRAPER.md`, not in the JS.

The split exists because the constants get tuned constantly and the reason
for each value belongs next to the value. Snippets inline in markdown are
opaque to grep, diff, and lint; parameters buried inside snippets drift
away from the rationale that justified them. Two files, one table, one
manual that reads like the whole story.

### The experience filter is a deliberate tradeoff

LinkedIn's `experience:List(2,3)` filter drops anything the poster tagged
Entry or Associate. It cuts query volume by ~75%, at the cost of also
dropping every posting where the poster *left the field blank* — which is
common at healthcare and traditional-industry employers. Mayo Clinic,
Stanford Medicine, and several defense primes vanish this way.

The trade is defensible because those postings would have failed downstream
on X10 anyway (US-person requirement) or land in D8; the ones that
would have survived are rare enough that saving four in five downstream
reads on the ones that wouldn't is the better deal. When the user reports
a specific miss the filter comes off with `experienceList: ""` — the
escape hatch is one keyword away, not a code change.

### The JD loop resumes; it does not retry

`javascript_tool`'s CDP call times out at 45 seconds. A batch of 120 JDs at
4-way concurrent takes about 30 — comfortable, but not so comfortable that
a slow LinkedIn response can't push it over. Rather than shrinking the
batch or wrapping fetches in retries, the store lives on `window.__jd_raw`
and every batch begins with

```
window.__jids.filter(j => !window.__jd_raw[j]).slice(0, 120)
```

A timeout does not lose state; the next call recomputes what is left. Same
for 429s and mid-run session refreshes — stop, wait, resume, the resume
picks up from what already succeeded. A retry loop inside a single JS call
would put a heavier client on LinkedIn's servers *and* still lose state to
the CDP timeout it existed to work around.

## Ingest: the middle

Between "here are 282 postings" and "here are the twelve worth your evening"
sits one script. It does four things.

**Dedup three ways.** Job boards repost the same requisition under a fresh id,
so a URL check alone misses them. `ingest.py` also compares normalised
(company, title) against the ledger and within the incoming batch —
normalisation strips years, "new grad", "remote" and similar decoration. On a
recent run this caught 149 duplicates that the URL check passed.

**Drop what the candidate cannot take.** Nine coarse rules — clearance, ITAR,
senior titles, years of experience, a ceiling below the pay floor, agencies,
internships, non-US, and duplicates — plus one, no-sponsorship language, that
defaults to a flag rather than a drop because the wording is so often
boilerplate. Every rule can be switched off in the profile.

**Dropped rows are not deleted.** They stay in the ledger with `status=dropped`
and the reason that removed them. This costs a few hundred rows and buys two
things: a rule change can be audited against what it would have removed
before, and `update_row.py reasons` has something to read.

**Bucket the rest, five ways** — region, employer tier, pay band, direction of
work, and how confident we are the req is open to a new grad.

Four decisions inside that are worth defending:

### Buckets instead of a fit score

The original design had an LLM score every posting 1–5 for fit. Across 935
rows the column was empty 935 times: the step was expensive, easy to skip, and
skipping it broke nothing loudly. It was replaced by rules.

That turned out to be the better design regardless. A score compresses several
independent facts into one number and destroys the ability to ask the question
you actually have — not "is this a 4?" but "show me campus-confirmed ML infra
roles at strong companies on the west coast". Five orthogonal buckets answer
that; a scalar cannot. They are also deterministic, so the same posting
classifies the same way twice, and reproducible, so a rule change can be
replayed over history.

### Coarse rules, and a flag when unsure

The rules are blunt on purpose. A borderline posting survives carrying a note
— a weak agency signal in the company name, a PhD mention, a JD too thin to
judge — for a human to resolve.

The asymmetry is the whole argument: reading one extra row costs a minute,
missing a job you would have taken costs an application cycle. Anywhere a rule
could go either way, it keeps the row.

The clearest case is ITAR. An unambiguous US-person requirement drops the
posting, because an F-1 holder is legally ineligible and no amount of interest
changes that. But a great deal of boilerplate says "for positions requiring
access to controlled technology…" without the role being one of them — that
only raises a flag. Nine postings drop; thirteen get read.

### Rules in code, values in config

The test for which side something belongs on: *is this about how job postings
are written, or about who you are?*

"3+ years of experience", "Sr. Staff Engineer", "active TS/SCI" are the same
for everyone, so they are regexes in `scripts/classify.py`. Which employers
you rate, where you would move, what pay is worth an hour, what you specialise
in — those are `config/profile.yaml`. Forking should mean editing YAML, never
regexes.

This was not free. The classifier had 265 company names, a pay floor on line
541, region buckets drawn around one city, and a bucket that meant "speech and
multimodal" because that is one candidate's specialty. Pulling them out took a
day and changed no behaviour, which is the correct outcome for a refactor and
was verified by replaying the classifier over all 935 rows: zero drops, zero
revivals, zero bucket changes.

### One classifier, not two

There were two filters for a while — an older rule set and a newer one written
when bucketing arrived. They overlapped, drifted apart, and the scraper manual
told the downstream agent to run the one that was no longer in use. Nobody
noticed because both produced plausible output.

Two implementations of the same policy is not redundancy, it is a fork waiting
to be discovered. They are now one module, and `rulebook.md` §5 carries the
table that must change with it.

## The feedback loop

Every manual rejection carries a reason:

```bash
python3 scripts/update_row.py drop <id> -m "ITAR US-person requirement, F-1 ineligible"
```

Those accumulate in the ledger and are read back with `update_row.py reasons`.
When a reason keeps recurring it is a rule the classifier is missing — add it,
replay it over history with `reclassify.py --apply`, log it in `rulebook.md`
§8.

This is how X10 (ITAR) exists. Five postings had been rejected by hand for the
same reason across two sessions, while the fill assistant's manual referred to
a rule code that had never been implemented. The reasons were sitting in the
ledger the whole time; they just needed reading.

The loop has a failure mode worth naming, because it happened. A rule can be
decided in `rulebook.md` and never reach the code: no-sponsorship was demoted
from a drop to a flag in the rulebook, the classifier kept dropping it, and
ten postings were discarded against a rule that said to keep them. Nothing
surfaced it — both artifacts read as correct on their own. The only reason it
was caught was a line-by-line audit before publishing.

That is an argument for the rule table in `rulebook.md` §5 naming the code
symbol for every rule, which it now does. A rule you cannot trace to a
function is a rule nobody can check.

Two kinds of rejection, because they mean different things:

- `drop -m` — wrong, and here is why. Feeds rule changes.
- `lowfit -m` — not wrong enough to reject, but don't show me again.

Both leave the board. Only the first is evidence about the rules.

## Filling: the batch protocol

The fill side is a conversation, not a pipeline, so its design choices are
mostly about where the human sits in the loop.

**Scope in the user's words, clarified before anything runs.** A batch starts
from a natural-language description ("strong second-tier, reads new-grad but
doesn't say so — give me thirty"), which
the agent translates into bucket filters and reads back with a row count.
Ambiguity — no count, fuzzy direction, a conflict with a standing decision —
is resolved by asking first, because a mistranslated scope wastes an entire
probe-and-report cycle before anyone notices.

**Decision points are explicit, and a todo list is not one.** The sequence is
probe → report → *user picks* → fill. This is a rule because the agent once
started filling forms for roles the user had only parked on a todo list; the
correction — *I decide what gets applied to; then you go do the résumé* — is
now step 5 of the lifecycle.
Between report and decision sits one more gate that grows an asset: the agent
proposes JD terms that would help ("can we claim X?"), and the user's verdicts
accumulate in the claimable-terms library with evidence attached — an ATS
vocabulary built one approval at a time, never by inference.

**Autofill first, audit always.** The browser extension (Simplify) does the
bulk typing; the agent's job is inspection. The order matters — the extension
re-navigates the page and wipes manual fills, so doing careful work first
throws it away (learned twice). The audit is non-negotiable because the
extension invents when its profile has a gap: citizenship became "USA", a
salary sentence appeared from nowhere, a degree discipline got guessed wrong.
Two standing invariants fall out: every form's resume gets swapped (the
extension always uploads its stale stored copy — verify the filename), and no
AI-generated free text survives. Subjective answers are drafted by the agent
**in chat**, in plain language grounded in `experiences.md`, for the user to
edit and paste — the form is the user's editing surface, not the agent's.

**Blockers are recorded, not fought.** Account walls, cross-origin iframes,
and platforms that wedge under synthetic events (Phenom froze two pages
before this rule existed) get a ledger note and a skip. The mechanics learned
in the process go into `platform_notes.md` in the same session they are
learned — that file is the agent's own memory, and the user only ever reads
its results. The alternative — re-discovering per-ATS quirks each session —
was the original state, and it burned most of a batch's budget on solved
problems.

**Bookkeeping defaults to applied.** After handoff the user submits on their
own time and mostly says nothing; chasing per-tab confirmations did not work
in practice. So handed-off tabs are marked `applied` by default, and the user
reports only exceptions — which are recorded with the reason phrased as a
reusable judgement ("no sponsor + mediocre match"), because exception reasons
are the same feedback channel the classifier's rules are tuned from.

## Constraints on the fill assistant

Three that are not negotiable, because each protects something that cannot be
repaired afterwards:

**It never submits.** It fills a form and stops. The last click is the user's,
always.

**Every claim must be traceable.** Nothing reaches a resume or a form that is
not in `experiences.md` (things done, with evidence) or `claimable_skills.md`
(skills honestly held that no bullet spells out). This is what stops a
tailoring pass from drifting into fabrication one plausible sentence at a
time — the boundary is a file lookup, not a judgement call.

**Sponsorship questions are answered honestly.** Always, even when the honest
answer is what a filter is screening for. A false answer here can cost an
offer after it is signed.

## Publishing this without publishing the job hunt

The framework is 54 files. Around it sits transcripts, a home address, EEO
answers per application, tailored resumes, and a record of where one person
applied and what they were offered.

`scripts/export_public.py` builds the public tree by **whitelist** into a
**fresh directory**. Both halves matter. A blacklist fails open — forget one
path and it ships. And scrubbing history after a push does not work: commits
can already be forked, cached by the host, and indexed, and a rewrite fixes
none of that. Clean separation from the first commit is the only version that
actually holds.

The leak scanner reads the owner's real identity out of `experiences.md` and
greps the export for it. The first version matched patterns only — phone
shapes, email shapes, address shapes — reported clean, and had passed three
files that named the owner, including a script that hardcoded his resume
filenames. Patterns do not catch a surname in a filename. Checking for the
actual values does.

It is still only a safety net. Read the diff before the first push.

## On the scraping

The scrape phase calls LinkedIn's internal voyager API from inside the user's
own authenticated browser tab. That is a grey area and this document is not
going to pretend otherwise.

What the design does about it: there is no credential handling anywhere, no
service, and no way to run it without your own logged-in browser. A 302 or 401
halts the run and asks you to refresh — it does not retry, rotate, or route
around a block. It paces itself to roughly what a person reading listings
would generate. And no scraped data ships with the repo; job descriptions
belong to whoever wrote them.

If you want a path with none of that ambiguity, the archived code under
`scripts/legacy/` reads the public Greenhouse, Lever and Ashby APIs instead.
Much smaller coverage, which is exactly why it was replaced — that trade is
yours to make, not this project's to make for you.

## Things still wrong

Written down so they do not get quietly forgotten.

- **The buckets are one person's taxonomy.** The tier list encodes one
  candidate's opinion of 265 employers, and D1–D8 is a slice of the market
  that makes sense for a speech/ML new grad. The mechanism generalises; the
  starting values do not.
- **`data/pending/` grows unboundedly.** `prune_pending.py` handles the raw
  dumps; nothing prunes the enriched ones.
- **Only the classifier is tested.** It is the highest-value target — a quiet
  regex change reshapes the whole board — but `ingest.py` and `board.py` have
  no coverage.
- **No cross-session locking.** Two sessions writing `jobs.csv` at once would
  interleave. `update_row.py` writes atomically via a temp file and rename, so
  the file will not be corrupted, but one session's edit can be lost.
