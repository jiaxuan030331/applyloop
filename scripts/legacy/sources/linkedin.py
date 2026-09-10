"""LinkedIn source via python-jobspy (unofficial, no auth).

Runs a list of search queries against LinkedIn's public jobs search. Merges
results, dedups within-source, yields Job objects. Full JD included when
`linkedin_fetch_description=True` (adds ~1 request per posting).

Config in sources.yaml:
  linkedin:
    enabled: true
    queries:                # list of search terms
      - "machine learning engineer new grad"
      - "applied scientist new grad"
      - ...
    location: "United States"
    hours_old: 720           # ~30 days
    results_per_query: 100   # LinkedIn caps somewhere around 1000; 100/query is safe
    fetch_full_jd: true      # slower but gives LLM the JD text
    li_at_cookie: ""         # optional: paste your `li_at` for higher quota
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Iterable

from .base import Source
from ..models import Job


class LinkedInSource(Source):
    name = "linkedin"

    def __init__(self, config: dict, _unused=None):
        super().__init__(config)
        self.queries = list(config.get("queries", []))
        self.location = config.get("location", "United States")
        self.hours_old = int(config.get("hours_old", 720))
        self.results_per_query = int(config.get("results_per_query", 100))
        self.fetch_full_jd = bool(config.get("fetch_full_jd", True))
        # Cookie is optional. If set as env var LI_AT, prefer that (safer than
        # committing to yaml).
        self.li_at = os.environ.get("LI_AT") or config.get("li_at_cookie", "") or ""

    def fetch(self) -> Iterable[Job]:
        try:
            from jobspy.linkedin import LinkedIn
            from jobspy.model import ScraperInput, Site, Country, DescriptionFormat
        except ImportError:
            print("[linkedin] jobspy not installed — pip3 install python-jobspy")
            return

        seen_urls: set[str] = set()
        for q in self.queries:
            print(f"[linkedin] query: {q!r}  target={self.results_per_query} rows")
            try:
                lin = LinkedIn()
                # Inject session cookie for the authenticated (voyager) path,
                # if available. Never persisted — env var / config only.
                if self.li_at:
                    lin.session.cookies.set("li_at", self.li_at, domain=".linkedin.com")
                inp = ScraperInput(
                    site_type=[Site.LINKEDIN],
                    search_term=q,
                    location=self.location,
                    country=Country.USA,
                    results_wanted=self.results_per_query,
                    hours_old=self.hours_old,
                    linkedin_fetch_description=self.fetch_full_jd,
                    distance=50,
                    description_format=DescriptionFormat.MARKDOWN,
                )
                resp = lin.scrape(inp)
                jobs = resp.jobs if resp else []
            except Exception as e:
                print(f"[linkedin] query {q!r} failed: {e}")
                continue

            if not jobs:
                print(f"[linkedin] query {q!r} returned 0 rows")
                continue

            emitted = 0
            for jp in jobs:
                url = getattr(jp, "job_url", "") or ""
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                posted_iso = ""
                dp = getattr(jp, "date_posted", None)
                if isinstance(dp, dt.datetime):
                    posted_iso = dp.date().isoformat()
                elif isinstance(dp, dt.date):
                    posted_iso = dp.isoformat()
                elif isinstance(dp, str) and dp:
                    posted_iso = dp[:10]

                loc_obj = getattr(jp, "location", None)
                if hasattr(loc_obj, "display_location"):
                    loc = loc_obj.display_location()
                else:
                    loc = str(loc_obj) if loc_obj else ""

                yield Job(
                    source=self.name,
                    company=str(getattr(jp, "company_name", "") or "").strip(),
                    title=str(getattr(jp, "title", "") or "").strip(),
                    url=url,
                    location=loc,
                    date_posted=posted_iso,
                    full_jd=str(getattr(jp, "description", "") or "")[:12000],
                    raw={
                        "job_type":  [str(t) for t in (getattr(jp, "job_type", None) or [])],
                        "is_remote": getattr(jp, "is_remote", None),
                        "linkedin_query": q,
                        "linkedin_apply_url": getattr(jp, "job_url_direct", None),
                    },
                )
                emitted += 1
            print(f"[linkedin] query {q!r} emitted {emitted} new rows (dedup within source)")
