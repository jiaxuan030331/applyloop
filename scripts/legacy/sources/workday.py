"""Workday public careers-portal scraper.

Every Workday tenant exposes a JSON search API at:
    POST  https://{tenant}.wd{POD}.myworkdayjobs.com/wday/cxs/{tenant}/{SITE}/jobs
    GET   https://{tenant}.wd{POD}.myworkdayjobs.com/wday/cxs/{tenant}/{SITE}/job{externalPath}

Config format (in config/companies.yaml):

    workday:
      - name: salesforce                # display name, used as company field
        tenant: salesforce              # sub-domain slug
        pod: 12                         # pod number
        site: External_Career_Site      # site slug
      - name: uber
        tenant: uber
        pod: 5
        site: uberUS                    # example — verify from their URL
        query: ""                       # optional search text
        max_pages: 20                   # optional cap

To discover tenant/pod/site for a new company: visit their public careers
page and read the URL. E.g. `apple.wd1.myworkdayjobs.com/AppleExternal/` →
tenant=apple, pod=1, site=AppleExternal.
"""

from __future__ import annotations

import datetime as dt
import time
from typing import Iterable

import requests

from .base import Source
from ..models import Job
from ..utils.text_utils import strip_html


PAGE_SIZE = 20
FETCH_TIMEOUT = 20
DETAIL_TIMEOUT = 20


class WorkdaySource(Source):
    name = "workday"

    def __init__(self, config: dict, tenants: list[dict]):
        super().__init__(config)
        self.tenants = tenants
        self.fetch_full_jd = bool(config.get("fetch_full_jd", True))
        self.rate_sleep = float(config.get("rate_sleep", 0.15))  # be polite
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        })

    # ---- URL builders ----

    @staticmethod
    def _base(tenant: str, pod: int, site: str) -> str:
        return f"https://{tenant}.wd{pod}.myworkdayjobs.com/wday/cxs/{tenant}/{site}"

    @staticmethod
    def _public_url(tenant: str, pod: int, site: str, external_path: str) -> str:
        # user-facing URL (the one they'd click)
        return f"https://{tenant}.wd{pod}.myworkdayjobs.com/en-US/{site}{external_path}"

    # ---- one tenant ----

    def _fetch_one(self, cfg: dict) -> Iterable[Job]:
        name = cfg.get("name") or cfg["tenant"]
        tenant, pod, site = cfg["tenant"], int(cfg["pod"]), cfg["site"]
        query = cfg.get("query", "")
        max_pages = int(cfg.get("max_pages", 20))
        base = self._base(tenant, pod, site)

        offset = 0
        pages = 0
        while pages < max_pages:
            body = {
                "appliedFacets": cfg.get("facets", {}),
                "limit": PAGE_SIZE,
                "offset": offset,
                "searchText": query,
            }
            try:
                r = self.session.post(f"{base}/jobs", json=body, timeout=FETCH_TIMEOUT)
                if r.status_code == 404:
                    print(f"[workday] {name}: 404 at {base}/jobs — check tenant/pod/site")
                    return
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                print(f"[workday] {name}: list-page {pages} failed: {e}")
                return

            postings = data.get("jobPostings") or []
            total = data.get("total", 0)
            if not postings:
                break

            for p in postings:
                external_path = p.get("externalPath") or ""
                job_url = self._public_url(tenant, pod, site, external_path)
                title = (p.get("title") or "").strip()
                loc = p.get("locationsText") or ""
                posted_iso = _posted_to_iso(p.get("postedOn") or "")

                full_jd = ""
                if self.fetch_full_jd and external_path:
                    full_jd = self._fetch_detail(base, external_path, name)
                    time.sleep(self.rate_sleep)

                yield Job(
                    source=self.name,
                    company=name,
                    title=title,
                    url=job_url,
                    location=loc,
                    date_posted=posted_iso,
                    full_jd=full_jd,
                    raw={
                        "tenant": tenant, "pod": pod, "site": site,
                        "externalPath": external_path,
                        "bulletFields": p.get("bulletFields"),
                        "postedOn": p.get("postedOn"),
                    },
                )

            offset += PAGE_SIZE
            pages += 1
            if offset >= total:
                break
            time.sleep(self.rate_sleep)

    def _fetch_detail(self, base: str, external_path: str, name: str) -> str:
        try:
            r = self.session.get(f"{base}/job{external_path}", timeout=DETAIL_TIMEOUT)
            if r.status_code != 200:
                return ""
            data = r.json()
        except Exception as e:
            print(f"[workday] {name}: detail fetch failed for {external_path}: {e}")
            return ""
        info = data.get("jobPostingInfo") or {}
        html = info.get("jobDescription") or ""
        return strip_html(html)[:12000]

    # ---- Source interface ----

    def fetch(self) -> Iterable[Job]:
        for cfg in self.tenants:
            try:
                yield from self._fetch_one(cfg)
            except Exception as e:
                print(f"[workday] {cfg.get('name', cfg.get('tenant', '?'))} crashed: {e}")


# ---- helpers ----

def _posted_to_iso(posted_str: str) -> str:
    """Workday returns strings like 'Posted 5 Days Ago' / 'Posted Yesterday' /
    'Posted Today' / 'Posted 30+ Days Ago'. Convert to an ISO date."""
    s = (posted_str or "").lower().strip()
    today = dt.date.today()
    if not s:
        return ""
    if "today" in s:
        return today.isoformat()
    if "yesterday" in s:
        return (today - dt.timedelta(days=1)).isoformat()
    import re
    m = re.search(r"(\d+)\+?\s*day", s)
    if m:
        return (today - dt.timedelta(days=int(m.group(1)))).isoformat()
    m = re.search(r"(\d+)\+?\s*week", s)
    if m:
        return (today - dt.timedelta(weeks=int(m.group(1)))).isoformat()
    m = re.search(r"(\d+)\+?\s*month", s)
    if m:
        return (today - dt.timedelta(days=30 * int(m.group(1)))).isoformat()
    return ""
