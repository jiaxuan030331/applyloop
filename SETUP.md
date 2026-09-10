# Setup

applyloop is a job-application pipeline driven by two Claude Code sessions. One scrapes
and files postings; the other fills applications. You are the third role, and
the only one that decides anything.

## What you need

- **Python 3.10+** (the code uses `X | None` annotations)
- **[Claude Code](https://claude.com/claude-code)**
- **The Claude Chrome extension**, with `linkedin.com` granted site permission
- **A LinkedIn account you are logged into** in that Chrome profile

The scrape phase drives *your* browser against *your* session. Nothing in this
repo stores or forwards a cookie, and there is no HTTP client in the live path
— see [Scraping, honestly](#scraping-honestly) below.

## Install

```bash
git clone <your fork> applyloop && cd applyloop
pip3 install -r requirements.txt
python3 tests/test_classify.py        # should print 13/13
```

## Make it yours

The repo ships with templates. Copy them into place and fill them in — this is
the whole configuration step, and it is worth doing slowly.

```bash
cp template/profile.yaml            config/profile.yaml
cp template/experiences.md          experiences.md
cp template/application_answers.md  application_answers.md
cp template/rulebook.md             rulebook.md
cp template/claimable_skills.md     claimable_skills.md
```

| File | What it is |
|---|---|
| `config/profile.yaml` | Everything the classifier needs to know about you: where you'd work, which employers you rate, your pay floor, your specialty, which filter rules to run |
| `experiences.md` | What you have actually done. **Nothing may appear on a resume that isn't traceable here** — that constraint is the point |
| `application_answers.md` | Your standard answers to the questions every form asks |
| `rulebook.md` | The shared brain. Both agents read it; both propose changes to it |
| `claimable_skills.md` | Skills you can honestly claim that no bullet spells out |

Then put your resume in `resumes/` and edit `config/sources.yaml` so the search
queries match the roles you want.

Start with the drop rules switched conservatively. Every rule in
`profile.yaml` under `drops:` can be turned off, and it is much easier to
tighten a filter after you have seen what it would have removed than to
discover months later that it quietly ate a whole category.

## Run it

```
/scrape 24h              # scrape, ingest, filter, bucket, report
/batch <what you want>   # work a batch of applications
```

`/scrape` writes to `jobs.csv` and rebuilds `data/board.json`. `/batch` reads
the board, probes each posting, reports back, and waits for you to decide
before touching a form. It never submits.

Between sessions, the ledger is yours:

```bash
python3 scripts/update_row.py drop   <id> -m "why"   # reject, with a reason
python3 scripts/update_row.py lowfit <id> -m "why"   # off the board, not a rejection
python3 scripts/update_row.py reasons                # read your own feedback back
```

Those reasons are the feedback loop. When the same one keeps recurring, that
is a rule your classifier is missing — add it to `config/profile.yaml` or
`scripts/classify.py`, run `python3 scripts/reclassify.py --apply`, and log it
in `rulebook.md` §8.

## Scraping, honestly

The scrape phase calls LinkedIn's internal voyager API from inside your own
authenticated browser tab. That is a grey area: you are reading pages you
could read by hand, at a pace a human could plausibly sustain, but it is not
an API LinkedIn documents or supports.

What this project does about that:

- **Your session, your risk.** There is no credential handling here, no
  scraping service, and no way to run it without your own logged-in browser.
- **It stops when told to.** A 302 or 401 halts the run and asks you to
  refresh — it does not retry, rotate, or work around a block.
- **It paces itself** and does not parallelise beyond what one person reading
  job listings would generate.
- **No scraped data ships with this repo.** Job descriptions are their
  authors' content.

Don't extend it into something that hammers the endpoint. If you want a
supported path, the archived `scripts/legacy/` code hits Greenhouse, Lever and
Ashby public APIs instead — smaller coverage, no grey area.

## What isn't here

Your `jobs.csv`, board, resumes, transcripts and application records are
personal data and are gitignored. If you fork this, keep it that way: a
repository of where you applied and what you were paid is not something to
push to a public remote.
