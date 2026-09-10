"""Promote a scraper handoff file into jobs.csv, classified.

This is the middle of the pipeline: `/scrape` produces an enriched JSONL and
stops; this script turns it into ledger rows and a board the fill assistant
can work from.

    scrape  →  enriched.jsonl  →  [ingest]  →  jobs.csv  →  board.py  →  board.json
                                      ↓
                             daily_reports/<date>.md

What it does
  1. Reads the handoff JSONL (scraper shape: jid/url/company/title/.../full_jd).
  2. Dedups against jobs.csv on URL *and* normalised (company, title), and
     within the batch itself — LinkedIn reposts jobs under fresh jids.
  3. Classifies every survivor (scripts/classify.py): drops the clearly-unfit,
     buckets the rest along five dimensions.
  4. Appends to jobs.csv. Dropped rows are appended too, with
     status=dropped and drop_reason set — the ledger keeps a record of what
     was rejected and why, so a rule change can be audited later.
  5. Writes data/daily_reports/<date>.md.

Usage
    python3 scripts/ingest.py --in data/pending/linkedin_voyager_2026-09-10.enriched.jsonl
    python3 scripts/ingest.py --in <file> --dry-run     # classify + report, write nothing
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

csv.field_size_limit(sys.maxsize)
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.models import (CSV_FIELDS, STATUS_DROPPED, STATUS_OPEN,  # noqa: E402
                            blank_row, norm_key)
from scripts.classify import BUCKET_NAMES, DROP_CODES, classify  # noqa: E402

JOBS_CSV = _ROOT / "jobs.csv"
REPORTS = _ROOT / "data" / "daily_reports"


def read_handoff(path: Path) -> list[dict]:
    rows = []
    for n, line in enumerate(path.open(encoding="utf-8"), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"  [warn] {path.name}:{n} unparseable, skipped ({e.msg})")
    return rows


def read_ledger() -> list[dict]:
    if not JOBS_CSV.exists() or JOBS_CSV.stat().st_size == 0:
        return []
    return list(csv.DictReader(JOBS_CSV.open(encoding="utf-8")))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="scraper handoff JSONL")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src = Path(args.inp)
    if not src.exists():
        print(f"handoff file not found: {src}")
        return 1

    raw = read_handoff(src)
    ledger = read_ledger()
    seen_url = {r["job_link"] for r in ledger if r.get("job_link")}
    seen_key = {norm_key(r["company"], r["title"]) for r in ledger}

    dup_url = dup_key = dup_batch = 0
    fresh: list[dict] = []
    batch_keys: set = set()
    for r in raw:
        url = r.get("url") or ""
        if url and url in seen_url:
            dup_url += 1
            continue
        k = norm_key(r.get("company", ""), r.get("title", ""))
        if k in seen_key:
            dup_key += 1
            continue
        if k in batch_keys:
            dup_batch += 1
            continue
        batch_keys.add(k)
        fresh.append(r)

    kept, dropped = [], []
    for r in fresh:
        row = blank_row()
        jid = str(r.get("jid") or "")
        row.update({
            "id": hashlib.sha1(f"li:{jid}".encode()).hexdigest()[:16] if jid
                  else hashlib.sha1((r.get("url") or "").encode()).hexdigest()[:16],
            "date_found": args.date,
            "date_posted": r.get("date_posted", ""),
            "source": r.get("source", "linkedin"),
            "company": r.get("company", ""),
            "title": r.get("title", ""),
            "location": r.get("location", ""),
            "job_link": r.get("url", ""),
            "external_url": r.get("external_url", ""),
            "full_jd": r.get("full_jd", ""),
        })
        row.update(classify(row))
        if row["drop_reason"]:
            row["status"] = STATUS_DROPPED
            dropped.append(row)
        else:
            row["status"] = STATUS_OPEN
            kept.append(row)

    print(f"handoff {len(raw)}  ->  deduped -{dup_url + dup_key + dup_batch} "
          f"(url {dup_url} / company+title {dup_key} / within batch {dup_batch})"
          f"  ->  new {len(fresh)}  ->  kept {len(kept)} · dropped {len(dropped)}")

    if args.dry_run:
        print("[dry-run] nothing written")
    else:
        write_header = not JOBS_CSV.exists() or JOBS_CSV.stat().st_size == 0
        with JOBS_CSV.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            if write_header:
                w.writeheader()
            for row in kept + dropped:
                w.writerow(row)
        print(f"  -> jobs.csv +{len(kept) + len(dropped)} rows "
              f"({len(ledger) + len(kept) + len(dropped)} total)")

    report = build_report(args.date, src, len(raw), dup_url, dup_key, dup_batch,
                          kept, dropped)
    if not args.dry_run:
        REPORTS.mkdir(parents=True, exist_ok=True)
        out = REPORTS / f"{args.date}.md"
        out.write_text(report, encoding="utf-8")
        print(f"  → {out.relative_to(_ROOT)}")
    else:
        print("\n" + report)
    return 0


def _tally(rows: list[dict], key: str, names: dict) -> str:
    c = Counter(r[key] for r in rows)
    return " · ".join(f"{k} {names.get(k, k)} **{c[k]}**" for k in sorted(c))


def build_report(date, src, n_raw, dup_url, dup_key, dup_batch, kept, dropped) -> str:
    """Shallow report: volume, what the filter removed, where the survivors sit,
    and the handful of rows worth a human's attention today."""
    L = [f"# Ingest — {date}", "",
         f"Source `{src.relative_to(_ROOT) if src.is_relative_to(_ROOT) else src}`", "",
         "## Volume", "",
         f"- handoff **{n_raw}** rows",
         f"- deduped **-{dup_url + dup_key + dup_batch}** "
         f"(url {dup_url} · company+title {dup_key} · within batch {dup_batch})",
         f"- filtered **-{len(dropped)}**",
         f"- **onto the board: {len(kept)}**", ""]

    if dropped:
        L += ["## What the filter removed", "", "| Reason | Rows |", "|---|---|"]
        # X4 carries the actual figure; group on the bare X-code
        for code, n in Counter(r["drop_reason"].split()[0] for r in dropped).most_common():
            L.append(f"| {code} {DROP_CODES.get(code, '')} | {n} |")
        L.append("")

    if kept:
        L += ["## Where the new postings landed", "",
              "- **tier** " + _tally(kept, "bucket_tier", BUCKET_NAMES["tier"]),
              "- **role** " + _tally(kept, "bucket_role", BUCKET_NAMES["role"]),
              "- **campus** " + _tally(kept, "bucket_campus", BUCKET_NAMES["campus"]),
              "- **region** " + _tally(kept, "bucket_region", BUCKET_NAMES["region"]),
              ""]
        good = [r for r in kept if r["bucket_tier"] in ("T0", "T1", "T2")]
        if good:
            L += [f"## Worth reading first — {len(good)} at T0-T2", "",
                  "| tier | campus | role | company | title | location | pay |",
                  "|---|---|---|---|---|---|---|"]
            for r in sorted(good, key=lambda x: (x["bucket_tier"], x["bucket_role"])):
                pay = f"{int(r['comp_max'])//1000}k" if r["comp_max"] else "—"
                L.append(f"| {r['bucket_tier']} | {r['bucket_campus']} | {r['bucket_role']} "
                         f"| {r['company']} | {r['title'][:58]} | {r['location'][:24]} | {pay} |")
            L.append("")
        flagged = [r for r in kept if r["flags"]]
        if flagged:
            L += [f"## Flagged for a human look — {len(flagged)}", ""]
            for code, n in Counter(
                    f for r in flagged for f in r["flags"].split("|")).most_common():
                L.append(f"- `{code}` × {n}")
            L.append("")

    L += ["---", "",
          "Next: `python3 scripts/board.py` to rebuild `data/board.json`, "
          "then `/batch <scope>`."]
    return "\n".join(L)


if __name__ == "__main__":
    raise SystemExit(main())
