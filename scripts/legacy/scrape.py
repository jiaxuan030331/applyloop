"""Daily scrape orchestrator.

Usage:
    python3 scripts/scrape.py                      # runs everything enabled
    python3 scripts/scrape.py --source greenhouse  # single source
    python3 scripts/scrape.py --dry-run            # scrape + dedup, don't write

Reads:
    config/sources.yaml
    config/companies.yaml
    jobs.csv                (for dedup)
    data/pending/*.jsonl    (for dedup within the day)

Writes:
    data/raw/<YYYY-MM-DD>/<source>.jsonl    raw per-source dumps
    data/pending/<YYYY-MM-DD>.jsonl         new deduped jobs (fit_summary blank)

The pending file is what the daily agent consumes to add fit_summary /
what_could_help before calling ingest.py.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import yaml

# allow `python3 scripts/scrape.py` from repo root
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.dedupe import Deduper                              # noqa: E402
from scripts.legacy.models_job import Job                       # noqa: E402
from scripts.sources.simplify import SimplifyNewGradSource      # noqa: E402
from scripts.sources.greenhouse import GreenhouseSource         # noqa: E402
from scripts.sources.lever import LeverSource                   # noqa: E402
from scripts.sources.ashby import AshbySource                   # noqa: E402
from scripts.sources.workday import WorkdaySource               # noqa: E402
from scripts.sources.linkedin import LinkedInSource             # noqa: E402


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_sources(sources_cfg: dict, companies_cfg: dict, only: list[str] | None):
    """Return list of instantiated Source objects, respecting --source filter."""
    active = []
    src_map = sources_cfg.get("sources", {}) or {}

    def enabled(name: str) -> bool:
        if only and name not in only:
            return False
        return src_map.get(name, {}).get("enabled", False)

    if enabled("simplify_new_grad"):
        active.append(SimplifyNewGradSource(src_map["simplify_new_grad"]))

    if enabled("greenhouse"):
        boards = companies_cfg.get("greenhouse", []) or []
        active.append(GreenhouseSource(src_map["greenhouse"], boards))

    if enabled("lever"):
        cos = companies_cfg.get("lever", []) or []
        active.append(LeverSource(src_map["lever"], cos))

    if enabled("ashby"):
        boards = companies_cfg.get("ashby", []) or []
        active.append(AshbySource(src_map["ashby"], boards))

    if enabled("workday"):
        tenants = companies_cfg.get("workday", []) or []
        active.append(WorkdaySource(src_map["workday"], tenants))

    if enabled("linkedin"):
        active.append(LinkedInSource(src_map["linkedin"]))

    return active


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", action="append", help="restrict to source name (repeatable)")
    ap.add_argument("--dry-run", action="store_true", help="don't write output files")
    ap.add_argument("--date", default=None, help="override run date (YYYY-MM-DD)")
    args = ap.parse_args()

    root = _ROOT
    sources_cfg = load_yaml(root / "config" / "sources.yaml")
    companies_cfg = load_yaml(root / "config" / "companies.yaml")
    jobs_csv = root / "jobs.csv"

    today = args.date or dt.date.today().isoformat()

    raw_dir = root / "data" / "raw" / today
    pending_dir = root / "data" / "pending"
    pending_file = pending_dir / f"{today}.jsonl"
    if not args.dry_run:
        raw_dir.mkdir(parents=True, exist_ok=True)
        pending_dir.mkdir(parents=True, exist_ok=True)

    d = Deduper.from_csv(jobs_csv)
    # already-staged jobs from an earlier run today
    d.load_pending([pending_file])
    print(f"[scrape] loaded {len(d)} dedup keys from ledger + pending")

    sources = build_sources(sources_cfg, companies_cfg, args.source)
    if not sources:
        print("[scrape] no sources enabled — check config/sources.yaml and --source flag")
        return 1

    totals = {"scraped": 0, "new": 0, "by_source": {}}

    with (pending_file.open("a", encoding="utf-8") if not args.dry_run else _NullFile()) as pending_fh:
        for src in sources:
            scraped = 0
            new_here = 0
            raw_path = raw_dir / f"{src.name}.jsonl"
            raw_fh = raw_path.open("w", encoding="utf-8") if not args.dry_run else _NullFile()
            try:
                for job in src.fetch():
                    scraped += 1
                    job.date_found = today
                    job.compute_keys()
                    # dump raw regardless of dedup so we can inspect coverage
                    raw_fh.write(json.dumps(job.to_jsonl_dict(), ensure_ascii=False) + "\n")
                    if d.is_new(job):
                        d.remember(job)
                        pending_fh.write(json.dumps(job.to_jsonl_dict(), ensure_ascii=False) + "\n")
                        new_here += 1
            finally:
                raw_fh.close()

            totals["scraped"] += scraped
            totals["new"] += new_here
            totals["by_source"][src.name] = {"scraped": scraped, "new": new_here}
            print(f"[scrape] {src.name}: scraped={scraped} new={new_here}")

    print(f"[scrape] TOTAL scraped={totals['scraped']} new={totals['new']}")
    if not args.dry_run:
        print(f"[scrape] pending written → {pending_file}")
    return 0


class _NullFile:
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def write(self, *a, **kw): pass
    def close(self): pass


if __name__ == "__main__":
    raise SystemExit(main())
