"""Lever public postings API.

Endpoint: https://api.lever.co/v0/postings/{company}?mode=json
Each posting: id (uuid), text (=title), hostedUrl, categories {commitment,
department, location, team}, createdAt (ms), descriptionPlain, description
(HTML), lists ([{text, content}]).
"""

from __future__ import annotations

import datetime as dt
from typing import Iterable

import requests

from .base import Source
from ..models import Job
from ..utils.text_utils import strip_html


class LeverSource(Source):
    name = "lever"
    api_tmpl = "https://api.lever.co/v0/postings/{company}?mode=json"

    def __init__(self, config: dict, companies: list[str]):
        super().__init__(config)
        self.companies = companies
        self.fetch_full_jd = bool(config.get("fetch_full_jd", True))

    def fetch(self) -> Iterable[Job]:
        for co in self.companies:
            try:
                r = requests.get(self.api_tmpl.format(company=co), timeout=30)
                if r.status_code == 404:
                    continue
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                print(f"[lever] {co} fetch failed: {e}")
                continue

            # Lever returns {"ok": False, "error": "..."} for unknown slugs
            # instead of a 404 in some cases. Also can return {} rarely.
            if not isinstance(data, list):
                print(f"[lever] {co} non-list response, skipping: {str(data)[:120]}")
                continue

            for row in data:
                cats = row.get("categories") or {}
                created_ms = row.get("createdAt") or 0
                try:
                    posted_iso = (dt.datetime.utcfromtimestamp(created_ms / 1000).date().isoformat()
                                  if created_ms else "")
                except (OverflowError, OSError, ValueError):
                    posted_iso = ""

                if self.fetch_full_jd:
                    parts = [row.get("descriptionPlain") or strip_html(row.get("description", ""))]
                    for lst in row.get("lists", []) or []:
                        head = lst.get("text") or ""
                        body = strip_html(lst.get("content", ""))
                        if head or body:
                            parts.append(f"\n{head}\n{body}")
                    tail = row.get("additionalPlain") or strip_html(row.get("additional", ""))
                    if tail:
                        parts.append(f"\n{tail}")
                    jd = "\n".join(p for p in parts if p).strip()
                else:
                    jd = ""

                yield Job(
                    source=self.name,
                    company=co,
                    title=(row.get("text") or "").strip(),
                    url=(row.get("hostedUrl") or row.get("applyUrl") or "").strip(),
                    location=cats.get("location") or "",
                    date_posted=posted_iso,
                    full_jd=jd,
                    raw={"team": cats.get("team"),
                         "commitment": cats.get("commitment"),
                         "department": cats.get("department"),
                         "id": row.get("id"),
                         "workplaceType": row.get("workplaceType")},
                )
