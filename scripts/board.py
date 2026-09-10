"""Rebuild `data/board.json` — the candidate list `/batch` selects from.

The board is a pure derivative of jobs.csv: every row whose status is `open`
and whose `low_fit` is empty. Anything the fill assistant or the user has
acted on (applied / reachout / dropped / closed / duplicate) or that the
filter flagged as low-fit is excluded, so a posting can never resurface after
it has been dealt with.

Rebuild it after every ingest, and after any batch that changed statuses:

    python3 scripts/board.py
    python3 scripts/board.py --stats     # show the slice counts, write nothing
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

csv.field_size_limit(sys.maxsize)
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.models import STATUS_OPEN  # noqa: E402
from scripts.classify import BUCKET_NAMES  # noqa: E402

JOBS_CSV = _ROOT / "jobs.csv"
BOARD = _ROOT / "data" / "board.json"

# board.json keys are terse because the whole board is loaded at once.
def to_card(r: dict) -> dict:
    return {
        "id": r["id"],
        "c": r["company"], "t": r["title"], "l": r["location"],
        "a": r["bucket_region"], "b": r["bucket_tier"], "m": r["bucket_comp"],
        "d": r["bucket_role"], "e": r["bucket_campus"],
        "lo": int(r["comp_min"]) if r["comp_min"] else None,
        "hi": int(r["comp_max"]) if r["comp_max"] else None,
        "f": r["flags"], "dp": r["date_posted"][:10],
        "u": r["job_link"], "x": r["external_url"],
    }


def live_rows(rows: list[dict]) -> list[dict]:
    return [r for r in rows
            if (r.get("status") or STATUS_OPEN) == STATUS_OPEN
            and not (r.get("low_fit") or "").strip()]


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
    ap.add_argument("--stats", action="store_true", help="print counts, write nothing")
    args = ap.parse_args()

    rows = load_ledger()
    if rows is None:
        return 1
    live = live_rows(rows)
    cards = sorted((to_card(r) for r in live),
                   key=lambda c: (c["b"], c["e"], c["d"], c["c"]))

    by_status = Counter(r.get("status") or STATUS_OPEN for r in rows)
    n_lowfit = sum(1 for r in rows if (r.get("low_fit") or "").strip())
    print(f"jobs.csv {len(rows)} rows -> board {len(cards)}")
    print("  status " + " · ".join(f"{k} {v}" for k, v in by_status.most_common())
          + f" · low_fit {n_lowfit}")
    for dim, key in (("tier", "b"), ("role", "d"), ("campus", "e")):
        name = {"b": "tier", "d": "role", "e": "campus"}[key]
        c = Counter(x[key] for x in cards)
        print(f"  {dim} " + " · ".join(
            f"{k}({BUCKET_NAMES[name].get(k, k)}) {c[k]}" for k in sorted(c)))

    if args.stats:
        return 0
    BOARD.parent.mkdir(parents=True, exist_ok=True)
    BOARD.write_text(json.dumps(cards, ensure_ascii=False, separators=(",", ":")),
                     encoding="utf-8")
    print(f"  → {BOARD.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
