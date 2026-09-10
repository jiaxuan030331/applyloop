"""SimplifyJobs / New-Grad-Positions curated list.

Reads the raw listings.json from the repo. Fields we care about:
  company_name, title, url, locations (list), date_posted (unix seconds),
  active, is_visible, sponsorship, terms.
"""

from __future__ import annotations

import datetime as dt
from typing import Iterable

import requests

from .base import Source, SourceError
from ..models import Job


class SimplifyNewGradSource(Source):
    name = "simplify_new_grad"
    default_url = (
        "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/"
        "dev/.github/scripts/listings.json"
    )

    def fetch(self) -> Iterable[Job]:
        url = self.config.get("listings_url") or self.default_url
        max_age_days = int(self.config.get("max_age_days", 30))
        active_only = bool(self.config.get("active_only", True))
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            listings = r.json()
        except Exception as e:
            raise SourceError(f"simplify fetch failed: {e}") from e

        cutoff = None
        if max_age_days > 0:
            cutoff = dt.datetime.utcnow() - dt.timedelta(days=max_age_days)

        for row in listings:
            if active_only and not row.get("active", True):
                continue
            if row.get("is_visible") is False:
                continue

            posted_ts = row.get("date_posted") or row.get("date_updated")
            posted_dt = None
            if isinstance(posted_ts, (int, float)):
                try:
                    posted_dt = dt.datetime.utcfromtimestamp(posted_ts)
                except (OverflowError, OSError, ValueError):
                    posted_dt = None
            if cutoff and posted_dt and posted_dt < cutoff:
                continue

            locations = row.get("locations") or []
            if isinstance(locations, list):
                loc = ", ".join(str(x) for x in locations)
            else:
                loc = str(locations)

            j = Job(
                source=self.name,
                company=row.get("company_name", "").strip(),
                title=row.get("title", "").strip(),
                url=row.get("url", "").strip(),
                location=loc,
                date_posted=posted_dt.date().isoformat() if posted_dt else "",
                full_jd="",   # simplify list doesn't include the JD body
                raw={"sponsorship": row.get("sponsorship"),
                     "terms": row.get("terms"),
                     "season": row.get("season"),
                     "id": row.get("id")},
            )
            yield j
