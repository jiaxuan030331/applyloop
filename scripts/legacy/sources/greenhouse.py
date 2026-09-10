"""Greenhouse public board API.

Endpoint: https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true
Returns jobs with full HTML content and absolute_url + location + updated_at.
"""

from __future__ import annotations

import datetime as dt
from typing import Iterable

import requests

from .base import Source, SourceError
from ..models import Job
from ..utils.text_utils import strip_html


class GreenhouseSource(Source):
    name = "greenhouse"
    api_tmpl = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"

    def __init__(self, config: dict, boards: list[str]):
        super().__init__(config)
        self.boards = boards
        self.fetch_full_jd = bool(config.get("fetch_full_jd", True))

    def fetch(self) -> Iterable[Job]:
        for board in self.boards:
            try:
                r = requests.get(self.api_tmpl.format(board=board), timeout=30)
                if r.status_code == 404:
                    # unknown board slug, skip quietly
                    continue
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                # per-board failure shouldn't kill the run
                print(f"[greenhouse] {board} fetch failed: {e}")
                continue

            for jrow in data.get("jobs", []):
                updated = jrow.get("updated_at") or jrow.get("created_at") or ""
                try:
                    posted_iso = dt.datetime.fromisoformat(
                        updated.replace("Z", "+00:00")
                    ).date().isoformat() if updated else ""
                except Exception:
                    posted_iso = ""

                loc = (jrow.get("location") or {}).get("name", "")
                jd = strip_html(jrow.get("content", "")) if self.fetch_full_jd else ""

                yield Job(
                    source=self.name,
                    company=board,   # company slug; can be prettified later
                    title=jrow.get("title", "").strip(),
                    url=jrow.get("absolute_url", "").strip(),
                    location=loc,
                    date_posted=posted_iso,
                    full_jd=jd,
                    raw={"gh_id": jrow.get("id"),
                         "internal_job_id": jrow.get("internal_job_id"),
                         "departments": [d.get("name") for d in jrow.get("departments", [])],
                         "offices": [o.get("name") for o in jrow.get("offices", [])]},
                )
