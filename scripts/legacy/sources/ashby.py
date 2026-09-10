"""Ashby public job-board API.

Endpoint: https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true
Returns {jobs: [...]}. Each job: id, title, department, team, locationName,
employmentType, isRemote, jobUrl, publishedAt (iso), descriptionHtml.
"""

from __future__ import annotations

import datetime as dt
from typing import Iterable

import requests

from .base import Source
from ..models import Job
from ..utils.text_utils import strip_html


class AshbySource(Source):
    name = "ashby"
    api_tmpl = "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"

    def __init__(self, config: dict, boards: list[str]):
        super().__init__(config)
        self.boards = boards
        self.fetch_full_jd = bool(config.get("fetch_full_jd", True))

    def fetch(self) -> Iterable[Job]:
        for board in self.boards:
            try:
                r = requests.get(self.api_tmpl.format(slug=board), timeout=30)
                if r.status_code == 404:
                    continue
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                print(f"[ashby] {board} fetch failed: {e}")
                continue

            for row in data.get("jobs", []):
                published = row.get("publishedAt") or ""
                try:
                    posted_iso = (dt.datetime.fromisoformat(published.replace("Z", "+00:00"))
                                  .date().isoformat()) if published else ""
                except Exception:
                    posted_iso = ""

                yield Job(
                    source=self.name,
                    company=board,
                    title=(row.get("title") or "").strip(),
                    url=(row.get("jobUrl") or "").strip(),
                    location=row.get("locationName") or "",
                    date_posted=posted_iso,
                    full_jd=strip_html(row.get("descriptionHtml", "")) if self.fetch_full_jd else "",
                    raw={"id": row.get("id"),
                         "department": row.get("department"),
                         "team": row.get("team"),
                         "employmentType": row.get("employmentType"),
                         "isRemote": row.get("isRemote"),
                         "compensation": row.get("compensation")},
                )
