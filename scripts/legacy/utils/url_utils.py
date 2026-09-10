"""URL canonicalization and platform-specific job-id extraction."""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode


# Query params we always drop (tracking / referral noise).
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gh_src", "gh_jid_referer", "src", "ref", "source",
    "trk", "trkCampaign", "refId", "position", "pageNum",
    "_gl", "fbclid", "gclid", "mc_cid", "mc_eid",
}

# Query params that are meaningful for identifying a specific posting
# on well-known platforms. When present, we keep only these.
_ID_PARAMS_BY_HOST = {
    "boards.greenhouse.io": {"gh_jid"},
    "job-boards.greenhouse.io": {"gh_jid"},
    "www.linkedin.com": {"currentJobId"},
    "linkedin.com": {"currentJobId"},
    "www.indeed.com": {"jk"},
    "indeed.com": {"jk"},
}


def canonicalize_url(url: str) -> str:
    """Return a canonical form of the URL for deduplication.

    - lowercase scheme + host
    - strip default ports
    - drop tracking params
    - keep only known-meaningful params on well-known ATSes
    - strip trailing slash on path
    - drop fragment
    """
    if not url:
        return ""
    try:
        p = urlparse(url.strip())
    except Exception:
        return url.strip()

    scheme = (p.scheme or "https").lower()
    host = (p.netloc or "").lower()
    # strip default ports
    host = host.replace(":80", "").replace(":443", "")

    path = p.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    # query filtering
    params = parse_qsl(p.query, keep_blank_values=False)
    id_params = _ID_PARAMS_BY_HOST.get(host)
    kept = []
    for k, v in params:
        if k in _TRACKING_PARAMS:
            continue
        if id_params is not None and k not in id_params:
            continue
        kept.append((k, v))
    kept.sort()
    query = urlencode(kept)

    return urlunparse((scheme, host, path, "", query, ""))


# --- platform id extraction ---

_RE_GH_JID = re.compile(r"[?&]gh_jid=(\d+)")
_RE_GH_BOARD_PATH = re.compile(r"/(?:embed/)?job/(\d+)")            # boards.greenhouse.io/{co}/jobs/12345
_RE_LEVER_PATH = re.compile(r"/([0-9a-f\-]{20,})", re.IGNORECASE)   # jobs.lever.co/{co}/{uuid}
_RE_ASHBY_PATH = re.compile(r"/([0-9a-f\-]{20,})", re.IGNORECASE)   # jobs.ashbyhq.com/{co}/{uuid}
_RE_LI_JOBID_PATH = re.compile(r"/jobs/view/(\d+)")
_RE_LI_JOBID_Q = re.compile(r"[?&]currentJobId=(\d+)")
_RE_INDEED_JK = re.compile(r"[?&]jk=([0-9a-f]+)")


def extract_platform_id(url: str) -> Optional[str]:
    """Return a `platform:id` string if we can recognize the platform."""
    if not url:
        return None
    try:
        p = urlparse(url)
    except Exception:
        return None
    host = (p.netloc or "").lower()

    if "greenhouse.io" in host:
        m = _RE_GH_JID.search(url) or _RE_GH_BOARD_PATH.search(p.path)
        if m:
            return f"greenhouse:{m.group(1)}"

    if "lever.co" in host:
        m = _RE_LEVER_PATH.search(p.path)
        if m:
            return f"lever:{m.group(1).lower()}"

    if "ashbyhq.com" in host or "ashby.hq" in host:
        m = _RE_ASHBY_PATH.search(p.path)
        if m:
            return f"ashby:{m.group(1).lower()}"

    if "linkedin.com" in host:
        m = _RE_LI_JOBID_PATH.search(p.path) or _RE_LI_JOBID_Q.search(url)
        if m:
            return f"linkedin:{m.group(1)}"

    if "indeed.com" in host:
        m = _RE_INDEED_JK.search(url)
        if m:
            return f"indeed:{m.group(1)}"

    return None
