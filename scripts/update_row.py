"""Edit jobs.csv — the only sanctioned writer.

Never hand-edit the CSV: a stray quote in a JD will silently shear the file.

Two forms.

**Verbs** (what you and /batch use day to day). Each takes one or more job
ids and rebuilds data/board.json afterwards, so a posting you act on leaves
the board immediately:

    update_row.py drop      <id>... [-m "too front-end"]  reject; -m optional
    update_row.py lowfit    <id>... [-m "..."]           poor fit — off the board,
                                                         but not a rejection
    update_row.py applied   <id>... [-d 2026-09-10]      submitted
    update_row.py reachout  <id>... [-m "referral sent"] waiting on a reply
    update_row.py closed    <id>...                      link is dead
    update_row.py reopen    <id>...                      undo any of the above
    update_row.py show      <id>...                      print these rows

`drop` and `lowfit` are the user-feedback channel: `drop -m` says "wrong, and
here's why", `lowfit` says "not wrong enough to delete, but don't show me
again". Both accumulate in the ledger; read them back with
`update_row.py reasons` when tuning scripts/classify.py.

**Raw field assignment** (escape hatch, unchanged):

    update_row.py <id> field=value [field=value ...]
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

csv.field_size_limit(sys.maxsize)
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.models import (CSV_FIELDS, STATUS_APPLIED, STATUS_CLOSED,  # noqa: E402
                            STATUS_DROPPED, STATUS_OPEN, STATUS_REACHOUT)
from scripts.classify import DROP_CODES  # noqa: E402

JOBS_CSV = _ROOT / "jobs.csv"
VERBS = {"drop", "lowfit", "applied", "reachout", "closed", "reopen",
         "show", "reasons"}


def _load() -> list[dict]:
    if not JOBS_CSV.exists() or JOBS_CSV.stat().st_size == 0:
        print(f"no ledger yet at {JOBS_CSV.name} — nothing to edit. "
              f"Run a scrape first.")
        raise SystemExit(1)
    return list(csv.DictReader(JOBS_CSV.open(encoding="utf-8")))


def _save(rows: list[dict]) -> None:
    """Atomic: write a sibling temp file, then rename over jobs.csv."""
    with tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8",
                                     dir=str(JOBS_CSV.parent), delete=False) as tmp:
        w = csv.DictWriter(tmp, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in CSV_FIELDS})
        name = tmp.name
    Path(name).replace(JOBS_CSV)


def _apply(rows: list[dict], ids: list[str], updates: dict) -> list[dict]:
    want, hit = set(ids), []
    for r in rows:
        if r.get("id") in want:
            r.update(updates)
            hit.append(r)
    missing = want - {r["id"] for r in hit}
    for m in sorted(missing):
        print(f"  [warn] no such id: {m}")
    return hit


def _rebuild_board() -> None:
    sys.stdout.flush()
    subprocess.run([sys.executable, str(_ROOT / "scripts" / "board.py")], check=False)


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0 if argv else 2

    # ---- raw form: update_row.py <id> field=value ... -------------------
    if argv[0] not in VERBS:
        return _raw_form(argv)

    ap = argparse.ArgumentParser(prog="update_row.py")
    ap.add_argument("verb", choices=sorted(VERBS))
    ap.add_argument("ids", nargs="*")
    ap.add_argument("-m", "--reason", default="", help="free-text comment")
    ap.add_argument("-d", "--date", default=dt.date.today().isoformat())
    ap.add_argument("--no-board", action="store_true", help="skip board rebuild")
    args = ap.parse_args(argv)

    rows = _load()

    if args.verb == "reasons":
        return _reasons(rows)

    if not args.ids:
        print("need at least one job id")
        return 2

    if args.verb == "show":
        for r in rows:
            if r["id"] in set(args.ids):
                print(f"\n{r['id']}  {r['company']} — {r['title']}")
                print(f"  {r['bucket_tier']} {r['bucket_role']} {r['bucket_campus']} "
                      f"{r['bucket_region']} {r['bucket_comp']}  flags={r['flags'] or '—'}")
                print(f"  status={r['status']}  low_fit={r['low_fit'] or '—'}  "
                      f"applied={r['applied_date'] or '—'}")
                if r["drop_reason"]:
                    print(f"  drop_reason: {r['drop_reason']}")
                if r["feedback"]:
                    print(f"  feedback: {r['feedback']}")
                print(f"  {r['job_link']}")
        return 0

    updates = {
        "drop":     {"status": STATUS_DROPPED,
                     "drop_reason": args.reason or "dropped by hand, no reason given"},
        "lowfit":   {"low_fit": "Y",
                     "drop_reason": args.reason or "poor fit, no reason given"},
        "applied":  {"status": STATUS_APPLIED, "applied_date": args.date},
        "reachout": {"status": STATUS_REACHOUT, "applied_date": args.date,
                     **({"feedback": args.reason} if args.reason else {})},
        "closed":   {"status": STATUS_CLOSED},
        "reopen":   {"status": STATUS_OPEN, "low_fit": "", "drop_reason": "",
                     "applied_date": ""},
    }[args.verb]

    hit = _apply(rows, args.ids, updates)
    if hit:
        _save(rows)
        for r in hit:
            print(f"  {args.verb}: {r['id']}  {r['company']} — {r['title'][:52]}")
        if not args.no_board:
            _rebuild_board()
    return 0 if hit else 1


def _reasons(rows: list[dict]) -> int:
    """Read back the accumulated user feedback — what got trimmed and why."""
    manual = [r for r in rows if r.get("drop_reason")
              and not r["drop_reason"].startswith("X")]
    auto = [r for r in rows if (r.get("drop_reason") or "").startswith("X")]
    print(f"{len(auto)} filtered automatically:")
    # X4 carries the actual figure; group on the bare X-code
    for code, n in Counter(r["drop_reason"].split()[0] for r in auto).most_common():
        print(f"  {n:5d}  {code} {DROP_CODES.get(code, '')}")
    print(f"\n{len(manual)} dropped or marked poor-fit by hand:")
    for r in manual:
        tag = "lowfit" if r.get("low_fit") else "drop  "
        print(f"  {tag} [{r['bucket_tier']} {r['bucket_role']}] "
              f"{r['company'][:22]:22s} {r['title'][:40]:40s} ← {r['drop_reason']}")
    if manual:
        print("\nA reason that keeps recurring is a rule scripts/classify.py is "
              "missing. Add it, then log the change in rulebook.md §8.")
    return 0


def _raw_form(argv: list[str]) -> int:
    job_id, assignments = argv[0], argv[1:]
    if not assignments:
        print("usage: update_row.py <id> field=value [...]  (or a verb; see --help)")
        return 2
    updates = {}
    for a in assignments:
        if "=" not in a:
            print(f"bad update: {a!r} (expected field=value)")
            return 2
        k, v = a.split("=", 1)
        if k not in CSV_FIELDS:
            print(f"unknown field: {k!r}\nknown: {', '.join(CSV_FIELDS)}")
            return 2
        updates[k] = v
    rows = _load()
    hit = _apply(rows, [job_id], updates)
    if not hit:
        return 1
    _save(rows)
    print(f"  updated {job_id}: " + ", ".join(f"{k}={v!r}" for k, v in updates.items()))
    _rebuild_board()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
