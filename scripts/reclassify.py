"""Re-run scripts/classify.py over jobs.csv after a rule change.

Rules drift as the user's feedback accumulates (`update_row.py reasons` is
where you read that feedback). When you add or loosen a rule, existing rows
still carry the old verdict — this replays the classifier over them.

**Rows the user or /batch already acted on are never touched.** applied /
reachout / closed / duplicate are decisions, not classifications; and a
manual `drop` / `lowfit` outranks any rule. Only `status=open` rows and rows
auto-dropped by an earlier rule (drop_reason starting `X`) get re-judged.

    python3 scripts/reclassify.py              # dry run — show what would change
    python3 scripts/reclassify.py --apply
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

csv.field_size_limit(sys.maxsize)
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.models import CSV_FIELDS, STATUS_DROPPED, STATUS_OPEN  # noqa: E402
from scripts.classify import classify  # noqa: E402

JOBS_CSV = _ROOT / "jobs.csv"
BUCKETS = ("bucket_region", "bucket_tier", "bucket_comp", "bucket_role",
           "bucket_campus", "comp_min", "comp_max", "flags")


def reclassifiable(r: dict) -> bool:
    st = r.get("status") or STATUS_OPEN
    if st == STATUS_OPEN:
        return not (r.get("low_fit") or "").strip()
    # auto-dropped rows can come back if a rule loosened; manual drops cannot
    return st == STATUS_DROPPED and (r.get("drop_reason") or "").startswith("X")


def load_ledger():
    """Read jobs.csv, or explain why there isn't one yet.

    A fresh clone has no ledger until the first ingest, and a new user is
    quite likely to reach for this script before running one.
    """
    if not JOBS_CSV.exists() or JOBS_CSV.stat().st_size == 0:
        print(f"no ledger yet at {JOBS_CSV.name} — run a scrape, or ingest an "
              f"existing handoff file:\n"
              f"    python3 scripts/ingest.py --in <handoff.jsonl>")
        return None
    return list(csv.DictReader(JOBS_CSV.open(encoding="utf-8")))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    rows = load_ledger()
    if rows is None:
        return 1
    newly_dropped, revived, rebucketed = [], [], Counter()
    skipped = 0

    for r in rows:
        if not reclassifiable(r):
            skipped += 1
            continue
        before_drop = r.get("drop_reason", "")
        before_bkt = {k: r.get(k, "") for k in BUCKETS}
        c = classify(r)
        for k in BUCKETS:
            if before_bkt[k] != c[k]:
                rebucketed[k] += 1
        r.update(c)
        if c["drop_reason"] and not before_drop:
            r["status"] = STATUS_DROPPED
            newly_dropped.append(r)
        elif not c["drop_reason"] and before_drop:
            r["status"] = STATUS_OPEN
            revived.append(r)

    print(f"reclassified {len(rows) - skipped} rows "
          f"({skipped} skipped: already acted on / manually dropped)")
    print(f"  newly dropped {len(newly_dropped)} · revived {len(revived)}")
    if rebucketed:
        print("  bucket changes " + " · ".join(f"{k.replace('bucket_', '')} {v}"
                                       for k, v in rebucketed.most_common()))
    for label, group in (("newly dropped", newly_dropped), ("revived", revived)):
        if not group:
            continue
        print(f"\n{label}:")
        for code, n in Counter(
                (r["drop_reason"] or "—").split()[0] for r in group).most_common():
            print(f"  {n:4d}  {code}")
        for r in group[:12]:
            print(f"       {r['bucket_tier']} {r['company'][:22]:22s} "
                  f"{r['title'][:44]:44s} ← {r['drop_reason'] or 'now kept'}")
        if len(group) > 12:
            print(f"       … and {len(group) - 12} more")

    if not args.apply:
        print("\n[dry-run] nothing written. Re-run with --apply, "
              "then scripts/board.py")
        return 0

    with JOBS_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in CSV_FIELDS})
    print("\nwrote jobs.csv. Next: python3 scripts/board.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
