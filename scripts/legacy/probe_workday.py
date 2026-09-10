"""Probe a list of candidate companies to discover their Workday tenant+pod+site.

Two-phase:
  1. For each candidate, sweep pods {1,2,3,4,5,6,10,12} with site='External'.
     If ANY pod returns 200 or 422 → tenant exists on that pod. Skip DNS-failed pods.
  2. For each (tenant, pod) hit, try site-slug variants until one returns 200.

Output: prints yaml-ready config lines for discovered tenants.

Usage:
    python3 scripts/probe_workday.py                     # default candidate list
    python3 scripts/probe_workday.py --candidates FILE   # one tenant per line
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import socket
import sys
from typing import Optional
from urllib.parse import quote

import requests

# Curated candidate tenant slugs — grouped for readability.
DEFAULT_CANDIDATES = [
    # ---- big tech / consumer ----
    "uber", "lyft", "airbnb", "doordash", "instacart", "pinterest",
    "snap", "twitter", "linkedin", "spotify", "reddit",
    "adobe", "autodesk", "cadence", "synopsys",
    "hp", "hpe", "dell", "cisco", "juniper", "arista",
    # ---- ai / infra / data ----
    "snowflake", "mongodb", "confluent", "twilio", "datadog", "elastic",
    "hashicorp", "cloudflare", "fastly", "servicenow", "workday",
    "vmware", "nutanix", "veeam", "splunk", "newrelic", "dynatrace",
    "palantir", "peloton", "roblox", "zoom", "unity", "epic",
    # ---- security ----
    "paloaltonetworks", "crowdstrike", "zscaler", "fortinet", "okta",
    "sentinelone", "cloudflare", "proofpoint", "rapid7", "tenable",
    # ---- semi / hardware ----
    "amd", "intel", "qualcomm", "broadcom", "marvell", "asml",
    "applied", "kla", "lamresearch", "onsemi", "analog", "microchip",
    # ---- ecommerce / retail ----
    "ebay", "etsy", "wayfair", "shopify", "instacart", "target",
    "walmart", "costco", "homedepot", "lowes", "bestbuy",
    "nike", "starbucks",
    # ---- finance / payments ----
    "visa", "mastercard", "paypal", "block", "square", "capitalone",
    "jpmorgan", "chase", "goldmansachs", "morganstanley", "wellsfargo",
    "citi", "bankofamerica", "deutschebank", "ubs", "credit-suisse",
    "fidelity", "vanguard", "blackrock", "statestreet", "bnymellon",
    "americanexpress", "amex", "hsbc", "barclays",
    # ---- pharma / medtech ----
    "moderna", "pfizer", "merck", "jnj", "johnsonandjohnson",
    "astrazeneca", "bms", "bristolmyerssquibb", "roche", "genentech",
    "gsk", "regeneron", "novartis", "bayer", "lilly", "amgen", "gilead",
    "illumina", "vertex", "biogen", "ginkgobioworks", "recursion",
    "verily", "flatiron",
    # ---- health insurance / providers ----
    "kaiserpermanente", "kp", "humana", "cvs", "cvshealth", "unitedhealth",
    "unitedhealthgroup", "uhg", "optum", "elevance", "anthem", "cigna",
    "aetna",
    # ---- defense / consulting / industrial ----
    "accenture", "deloitte", "ey", "ernstyoung", "kpmg", "pwc",
    "boozallen", "leidos", "caci", "saic", "northropgrumman",
    "lockheedmartin", "rtx", "raytheon", "boeing", "ge", "geaerospace",
    "hondaus", "toyota", "ford", "gm",
    # ---- other adjacencies ----
    "bloomberg", "reuters", "thomson", "twosigma", "citadel", "milleman",
    "worldquant", "millennium", "hrt", "dawn",
]

SITE_VARIANTS = [
    "External",
    "External_Career_Site",
    "external",
    "Careers",
    "careers",
    "us_careers",
    "US_External",
    "USExternal",
    "US_Careers",
    "Public",
    "Corporate",
    "PROFESSIONAL_CAREERS",
]

POD_ORDER = [1, 3, 5, 2, 4, 6, 10, 12]


def cap(t: str) -> str:
    return t[:1].upper() + t[1:]


def make_site_candidates(tenant: str) -> list[str]:
    T = cap(tenant)
    per_tenant = [
        f"{T}External",
        f"{T}ExternalCareerSite",
        f"{T}CareerSite",
        f"{T}Careers",
        f"{T}Career_Site",
        f"{T}_External",
        f"{T}_Careers",
        f"{T}",
    ]
    # Dedup while preserving order
    seen = set()
    out = []
    for s in per_tenant + SITE_VARIANTS:
        if s not in seen:
            out.append(s); seen.add(s)
    return out


def probe(tenant: str, pod: int, site: str, timeout: float = 5.0) -> tuple[int, Optional[int]]:
    """Return (http_status, total_jobs_or_None).  status=0 means DNS/network fail."""
    url = f"https://{tenant}.wd{pod}.myworkdayjobs.com/wday/cxs/{tenant}/{quote(site)}/jobs"
    try:
        r = requests.post(url, json={"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""},
                          headers={"Content-Type": "application/json", "Accept": "application/json"},
                          timeout=timeout, allow_redirects=False)
        if r.status_code == 200:
            try:
                return 200, int(r.json().get("total", 0))
            except Exception:
                return 200, None
        return r.status_code, None
    except requests.exceptions.ConnectionError:
        return 0, None
    except requests.RequestException:
        return -1, None


def dns_probe(tenant: str, pod: int) -> bool:
    """Fast DNS check for {tenant}.wd{pod}.myworkdayjobs.com."""
    try:
        socket.gethostbyname(f"{tenant}.wd{pod}.myworkdayjobs.com")
        return True
    except socket.gaierror:
        return False


def find_pod(tenant: str) -> Optional[int]:
    """Return first pod on which the tenant resolves via DNS."""
    for pod in POD_ORDER:
        if dns_probe(tenant, pod):
            return pod
    return None


def discover_one(tenant: str) -> Optional[dict]:
    pod = find_pod(tenant)
    if pod is None:
        return None
    # confirm with a probe (a resolving DNS still might not host workday)
    status, total = probe(tenant, pod, "External")
    if status == 0 or status == -1:
        return None
    if status == 200:
        return {"tenant": tenant, "pod": pod, "site": "External", "total": total}
    # tenant on wd{pod}, site slug wrong — iterate variants
    for site in make_site_candidates(tenant):
        status, total = probe(tenant, pod, site)
        if status == 200:
            return {"tenant": tenant, "pod": pod, "site": site, "total": total}
    # nothing found — mark as tenant-resolves-but-no-site
    return {"tenant": tenant, "pod": pod, "site": None, "total": None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default=None,
                    help="file with one candidate tenant per line (default: built-in list)")
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()

    if args.candidates:
        cands = [l.strip() for l in open(args.candidates) if l.strip() and not l.startswith("#")]
    else:
        cands = DEFAULT_CANDIDATES

    print(f"[probe] {len(cands)} candidates, workers={args.workers}", file=sys.stderr)

    hits: list[dict] = []
    partial: list[dict] = []
    missed: list[str] = []

    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(discover_one, t): t for t in cands}
        done = 0
        for fut in cf.as_completed(futs):
            t = futs[fut]
            r = fut.result()
            done += 1
            if r is None:
                missed.append(t)
                print(f"  [{done}/{len(cands)}] {t}: no workday tenant", file=sys.stderr)
            elif r["site"] is None:
                partial.append(r)
                print(f"  [{done}/{len(cands)}] {t}: pod={r['pod']} but no site slug matched", file=sys.stderr)
            else:
                hits.append(r)
                print(f"  [{done}/{len(cands)}] {t}: pod={r['pod']} site={r['site']} total={r['total']}", file=sys.stderr)

    print()
    print(f"# discovered {len(hits)} workday tenants, {len(partial)} partial, {len(missed)} miss")
    print()
    print("# --- YAML entries — paste into config/companies.yaml under `workday:` ---")
    for h in sorted(hits, key=lambda x: -(x["total"] or 0)):
        print(f"  - {{name: {h['tenant']}, tenant: {h['tenant']}, pod: {h['pod']}, site: {h['site']}}}  # total={h['total']}")
    if partial:
        print()
        print("# --- these have a workday DNS entry but no site slug matched (try manually) ---")
        for p in partial:
            print(f"#   {p['tenant']} pod={p['pod']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
