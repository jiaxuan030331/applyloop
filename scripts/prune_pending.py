"""Delete raw JD dumps older than N days from data/pending/.

`linkedin_jd_<date>.jsonl` is the unparsed voyager response — 8-22MB per day
and regenerable by rescraping. The `enriched` / `voyager` files beside it are
small and are the audit trail, so they are never touched.

    python3 scripts/prune_pending.py            # dry run, 7 days
    python3 scripts/prune_pending.py --apply --days 7
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
PENDING = _ROOT / "data" / "pending"
RAW = re.compile(r"^linkedin_jd_(\d{4}-\d{2}-\d{2})\.jsonl$")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--apply", action="store_true", help="actually delete")
    args = ap.parse_args()

    cutoff = dt.date.today() - dt.timedelta(days=args.days)
    freed = 0
    for f in sorted(PENDING.glob("linkedin_jd_*.jsonl")):
        m = RAW.match(f.name)
        if not m:
            continue
        try:
            d = dt.date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if d >= cutoff:
            continue
        mb = f.stat().st_size / 1e6
        freed += mb
        print(f"  {'delete' if args.apply else 'would delete'}  {f.name}  {mb:.1f}MB")
        if args.apply:
            f.unlink()
    print(f"{'freed' if args.apply else 'would free'} {freed:.1f}MB "
          f"(raw JD older than {cutoff})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
