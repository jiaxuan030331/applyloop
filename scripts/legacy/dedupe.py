"""Deduplication against the existing jobs.csv ledger.

The scraper runs `Deduper` once per session:

    d = Deduper.from_csv("jobs.csv")
    if d.is_new(job):
        d.remember(job)
        yield job
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Set

from .models import Job
from .utils.url_utils import canonicalize_url, extract_platform_id
from .utils.text_utils import normalize_company, normalize_title


class Deduper:
    def __init__(self) -> None:
        self._keys: Set[str] = set()

    # ---- construction ----

    @classmethod
    def from_csv(cls, csv_path: str | Path) -> "Deduper":
        d = cls()
        p = Path(csv_path)
        if not p.exists():
            return d
        with p.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                d._load_row(row)
        return d

    def load_pending(self, pending_paths: Iterable[str | Path]) -> None:
        """Also treat rows already staged in a pending JSONL as seen, so a
        re-run on the same day doesn't re-emit them."""
        import json
        for p in pending_paths:
            path = Path(p)
            if not path.exists():
                continue
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    self._load_row({
                        "job_link": obj.get("url", ""),
                        "company": obj.get("company", ""),
                        "title": obj.get("title", ""),
                    })

    # ---- key population ----

    def _load_row(self, row: dict) -> None:
        url = row.get("job_link", "")
        pid = extract_platform_id(url) or ""
        canon = canonicalize_url(url)
        if pid:
            self._keys.add(f"pid:{pid}")
        if canon:
            self._keys.add(f"url:{canon}")
        self._keys.add(
            f"ct:{normalize_company(row.get('company', ''))}|"
            f"{normalize_title(row.get('title', ''))}"
        )

    # ---- interface ----

    def is_new(self, job: Job) -> bool:
        return not any(k in self._keys for k in job.dedup_keys())

    def remember(self, job: Job) -> None:
        for k in job.dedup_keys():
            self._keys.add(k)

    def __len__(self) -> int:
        return len(self._keys)
