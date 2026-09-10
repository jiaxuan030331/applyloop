"""Job dataclass — used by the legacy multi-source scrape.py orchestrator.

Live path (linkedin_browser + fetch_linkedin_jd.py + hard_filter.py + ingest.py)
does NOT use this class; it works with plain dicts sourced from voyager JSON.

Kept here in case someone re-enables multi-source scraping — see
scripts/legacy/README.md.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from typing import List

from .utils.text_utils import normalize_company, normalize_title
from .utils.url_utils import canonicalize_url, extract_platform_id


@dataclass
class Job:
    """One scraped posting. Not yet analyzed."""

    source: str
    company: str
    title: str
    url: str
    location: str = ""
    date_posted: str = ""      # ISO date if known, else ""
    date_found: str = ""       # set by orchestrator
    full_jd: str = ""          # plain-text JD (HTML stripped, boilerplate removed)
    external_url: str = ""     # apply-on-company URL when available
    raw: dict = field(default_factory=dict)  # source-specific extras

    # populated after scraping via .compute_keys()
    id: str = ""               # canonical stable id used as jobs.csv primary key
    url_canonical: str = ""
    platform_id: str = ""

    def compute_keys(self) -> None:
        self.url_canonical = canonicalize_url(self.url)
        self.platform_id = extract_platform_id(self.url) or ""
        # Prefer platform id when available (stable across URL changes), else canonical URL
        seed = self.platform_id or self.url_canonical or f"{normalize_company(self.company)}|{normalize_title(self.title)}"
        self.id = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]

    def dedup_keys(self) -> List[str]:
        """Return all keys under which this job may match existing rows."""
        keys = []
        if self.platform_id:
            keys.append(f"pid:{self.platform_id}")
        if self.url_canonical:
            keys.append(f"url:{self.url_canonical}")
        keys.append(
            f"ct:{normalize_company(self.company)}|{normalize_title(self.title)}"
        )
        return keys

    def to_csv_row(self) -> dict:
        return {
            "id": self.id,
            "date_found": self.date_found,
            "date_posted": self.date_posted,
            "source": self.source,
            "company": self.company,
            "title": self.title,
            "location": self.location,
            "job_link": self.url,
            "external_url": self.external_url,
            "full_jd": self.full_jd,
            "fit_score": "",
            "fit_summary": "",
            "what_could_help": "",
            "applied_date": "",
            "feedback": "",
            "interview_received": "",
            "status": "open",
        }

    def to_jsonl_dict(self) -> dict:
        d = asdict(self)
        return d
