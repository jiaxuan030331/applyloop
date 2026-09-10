# Rulebook

**What this is.** The shared brain for every agent in this project. Both the
scrape-and-ingest agent and the fill assistant read it before acting, and both
must propose updates when you give feedback, when the market shifts, or when
an interview teaches you something.

Every rule carries a **Why** and a **How to apply**. The Why is not decoration:
six weeks later it is the only thing that lets you judge whether a rule still
holds. Keep the format when you add one.

---

## 1. Hard filters

These encode your situation. The *values* below are yours to set; the
*mechanism* lives in `config/profile.yaml` and `scripts/classify.py`.

### 1.1 Seniority
- **Why:** `<where you are in your career>`
- **How to apply:** drop codes X7 (senior title) and X6 (intern/part-time);
  `drops.max_yoe` in the profile sets how many years you can credibly claim.
  When a posting is ambiguous, keep it and let the flag carry the doubt.

### 1.2 Work authorization
- **Why:** `<your status, and what it forecloses>`
- **How to apply:** X8 drops postings that say outright they will not sponsor.
  Ambiguous wording is kept — plenty of reqs say nothing and sponsor anyway.
  If your status makes this moot, switch X8 off in the profile.

### 1.3 Citizenship / clearance / export control
- **Why:** `<whether these are open to you>` — for many visa holders these are
  categorical legal bars, not preferences.
- **How to apply:** X2 (clearance) and X10 (ITAR / US-person). Conditional
  boilerplate only raises an `ITAR?` flag; read the JD before dismissing it.

### 1.4 Location
- **Why:** `<where you can and want to work>`
- **How to apply:** X9 drops non-US postings. The region buckets A1-A3 in the
  profile are your own geography — redraw them around where you'd actually
  move, and put your preferred metros first.

### 1.5 Education requirements
- **Why:** `<your level>`
- **How to apply:** a PhD requirement raises a `PhD?` flag rather than a drop,
  because "PhD or equivalent experience" is common and negotiable.

### 1.6 Compensation floor
- **Why:** `<the number below which an application isn't worth the hour>`
- **How to apply:** `comp.floor_usd` in the profile; X4 drops a posting whose
  *ceiling* is below it.

### 1.7 Employers to skip
- **Why:** recruiting agencies, outsourcers, and crowd-labelling platforms
  repost other people's jobs or offer contract work.
- **How to apply:** X5, driven by `blocked_companies` in the profile. Add a
  name the first time one wastes your time.

---

## 2. What counts as a good match

The five buckets do the sorting; this section is where you write down what
you actually want, in prose, for the agent proposing a batch.

- **Aim for:** `<...>`
- **Would take:** `<...>`
- **Not worth the hour:** `<...>`

---

## 3. Resume tailoring rules

### 3.1 Skills / stack section
- **Why:** ATS keyword matching is literal.
- **How to apply:** the stack line becomes the union of what you already list
  and what the JD names **that also appears in `experiences.md`**. Never
  invent — see `claimable_skills.md` for the boundary.

### 3.2 Bullet selection
- Reorder so the top two bullets in each section answer the JD's top two
  responsibilities. Never fabricate a metric.

### 3.3 Length
- `<one page? two?>` Trim the oldest and least relevant first.

---

## 4. Deduplication

`scripts/ingest.py` dedups three ways: ① the posting URL against the ledger
② normalised (company, title) against the ledger — job boards repost the same
req under a fresh id, so the URL alone misses them ③ within the incoming batch.
Normalisation strips years, "new grad", "remote" and similar noise words; see
`scripts.models.norm_key`.

---

## 5. Filtering and bucketing — kept in sync with the code

Rules live in `scripts/classify.py`, thresholds and lists in
`config/profile.yaml`. They run once at ingest and write the `bucket_*`,
`flags` and `drop_reason` columns. **This table and those files change
together.**

### Drops — the row stays in the ledger with `status=dropped`

| Code | Test | Switch |
|---|---|---|
| X1 | Duplicate (URL or normalised company+title) | always on |
| X2 | JD requires a security clearance | `drops.X2_clearance` |
| X3 | Explicit years-of-experience above `drops.max_yoe` (a range resolves to its lower bound) | `drops.X3_yoe` |
| X4 | Ceiling below `comp.floor_usd` | `drops.X4_comp` |
| X5 | Agency, outsourcer, crowd-labelling, or board spam | `drops.X5_agency` |
| X6 | Internship / co-op / part-time | `drops.X6_intern` |
| X7 | Senior / staff / principal / lead title | `drops.X7_senior` |
| X8 | JD says outright it will not sponsor | `drops.X8_no_sponsor` |
| X9 | Posting is outside the US | `drops.X9_non_us` |
| X10 | ITAR / export-control US-person requirement | `drops.X10_itar` |

Dropped rows are never deleted — keeping them is what lets you audit a rule
change later, and what `update_row.py reasons` reads.

### Buckets — for everything that survives

| Dimension | Values |
|---|---|
| A region | your geography, drawn in the profile |
| B tier | how highly you rate the employer |
| C comp | band of the posted ceiling |
| D role | direction of the work; D4 is your own specialty |
| E campus | how sure we are the req is open to a new grad |

### Flags — kept, but worth a human look

Set in `labels.flags`: a weak agency signal in the company name, a PhD
mention, a JD too thin to judge, experience demanded right at your ceiling, a
salary floor high enough to suggest the req isn't really entry-level.

### Feedback loop

`update_row.py drop -m` and `lowfit -m` write your reasoning into
`drop_reason`; `update_row.py reasons` reads it back. When the same reason
keeps recurring, that is a rule the classifier is missing — add it, run
`reclassify.py --apply`, and log it in §8.

**When a rule is uncertain, keep the posting and flag it.** Missing a good job
costs more than reading one extra row.

---

## 6. Source quality notes

What each source is actually good for, and what it costs. Update it when a
source starts wasting your time.

---

## 7. Interview signal

*(Empty until your first interview.)* After each one, log the company, the
round, what was asked, and what you wished you had prepared. This is what
turns a rejection into a resume change.

---

## 8. Change log

Every rule change gets a line: what changed, and what evidence prompted it.
Without this the rulebook drifts and nobody can tell whether a rule is load-
bearing or vestigial.

- `<YYYY-MM-DD>` — initialised from template.
