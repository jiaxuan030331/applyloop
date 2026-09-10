"""Probe Greenhouse / Lever / Ashby with a wide candidate list.

For each candidate slug, hit each platform's public API. Report all boards
that return real postings. Output is YAML-ready to paste into
config/companies.yaml.

Usage:
    python3 scripts/probe_ats.py                    # default 200+ candidate slugs
    python3 scripts/probe_ats.py --candidates FILE
    python3 scripts/probe_ats.py --min-jobs 3       # skip boards with <3 postings
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import sys
from typing import Optional

import requests

# ---- candidate slugs (deduped, lowercased) ----
# Grouped for readability but flat when consumed.
DEFAULT_CANDIDATES = sorted(set([
    # ---- AI / LLM / foundation model ----
    "anthropic", "openai", "cohere", "mistral", "xai", "adept", "character",
    "characterai", "inflection", "groq", "together", "fireworks", "cerebras",
    "modal", "wandb", "weightsandbiases", "huggingface", "runway", "runwayml",
    "suno", "pika", "midjourney", "stability", "stabilityai", "perplexity",
    "perplexityai", "cursor", "anysphere", "codeium", "windsurf", "sourcegraph",
    "poolside", "magic", "mosaicml", "eleven-labs", "elevenlabs", "deepgram",
    "assemblyai", "cartesia", "play", "playht", "sanas", "rev",
    # ---- dev tools / infra / data ----
    "vercel", "supabase", "netlify", "render", "fly", "railway",
    "datadog", "pagerduty", "grafana", "grafanalabs", "chronosphere", "cribl",
    "snowflake", "mongodb", "elastic", "confluent", "cockroachlabs",
    "cockroach", "yugabyte", "weaviate", "pinecone", "clickhouse",
    "materializeinc", "materialize", "starburst", "trino",
    "zapier", "hubspot", "segment", "retool", "amplitude", "mixpanel", "heap",
    "hex", "posthog", "linear", "notion", "figma", "airtable", "coda",
    "miro", "canva", "loom",
    "temporal", "camunda", "prefect", "dagster",
    # ---- payments / fintech ----
    "stripe", "plaid", "moderntreasury", "mercury", "brex", "ramp", "rho",
    "robinhood", "coinbase", "kraken", "gemini", "circle", "chainalysis",
    "ripple", "wise", "checkout", "adyen",
    "block", "square",
    # ---- large-tech / consumer / social ----
    "airbnb", "reddit", "pinterest", "discord", "dropbox", "roblox",
    "spotify", "twitch", "twitter", "snap", "quora",
    "cloudflare", "fastly", "hashicorp", "twilio", "okta", "auth0",
    # ---- growth marketplaces / logistics / gig ----
    "faire", "zulily", "poshmark", "instacart", "doordash", "uber",
    "uberats", "grubhub", "shipt", "flexport", "shipbob", "convoy",
    "gopuff", "handy",
    # ---- robotics / AV / hardware startups ----
    "waymo", "cruise", "zoox", "auroraaus", "aurora", "motional", "nuro",
    "cognata", "wayve", "torc", "applied", "cover",
    "figureai", "figure", "physicalintelligence", "boston-dynamics",
    "matterport", "skydio",
    # ---- biotech / medtech (many on Greenhouse) ----
    "moderna", "vertexpharma", "recursion", "recursionpharmaceuticals",
    "ginkgobioworks", "verily", "flatironhealth", "flatiron", "tempus",
    "foundationmedicine", "23andme", "colorhealth", "color",
    "hinge", "hingehealth", "ro", "hims", "hers", "cedar",
    "devoted", "devotedhealth", "oscarhealth", "onemedical",
    "doximity", "tempusai", "insitro",
    # ---- crypto ----
    "opensea", "chainlink", "solana", "polygon", "avalanche", "matic",
    # ---- security ----
    "sentinelone", "wiz", "wizinc", "abnormal", "sublimesecurity",
    "arcticwolf", "huntress", "expel", "socure", "alloy", "unit21",
    # ---- hedge funds / trading (many on Greenhouse or custom) ----
    "twosigma", "citadel", "janestreet", "hudsonrivertrading", "hrt",
    "deshaw", "point72", "drw", "optiver", "imc", "worldquant", "millennium",
    "belvedere", "tower-research", "flowtraders", "sig", "susquehanna",
    "hbtcapital", "quadraturecapital",
    # ---- observability / mgmt / other tech-adjacent ----
    "gitlab", "circleci", "sentry", "launchdarkly", "arize", "arizeai",
    "weightsbiases", "unqork", "webflow", "framer", "gumroad",
    "asana", "monday", "clickup", "coda", "fellow", "loom",
    # ---- misc unicorns / hot ----
    "epic", "epicgames", "unity", "roblox-corp",
    "peloton", "warbyparker", "allbirds", "chime", "affirm",
    "toast", "toasttab", "instabase",
    # ---- health insurance / hospital adjacencies ----
    "clover", "cloverhealth", "commure", "included", "includedhealth",
    "carbonhealth", "spring", "springhealth", "lyra", "lyrahealth",
    # ---- climate / energy startups ----
    "commonwealthfusion", "helion", "climax", "climatex",
    # ---- gaming ----
    "riot", "riotgames", "epicgames", "supercell", "unity-technologies",
    # ---- storage / kv / infra ----
    "planetscale", "neon", "railway",
    # ---- other explicit user-of-interest ----
    "notion", "linear-app", "linear",
    "salesforce", "workday",   # for greenhouse (unlikely to be)
]))

# Ashby occasionally uses different slugs — try a few variants
ASHBY_ALIASES = {
    "characterai": "character",
    "character": "character",
    "elevenlabs": "elevenlabs",
    "eleven-labs": "elevenlabs",
    "perplexityai": "perplexityai",
    "runwayml": "runwayml",
    "wandb": "wandb",
    "weightsandbiases": "wandb",
    "huggingface": "huggingface",
    "wizinc": "wiz",
    "cockroachlabs": "cockroachlabs",
    "cockroach": "cockroachlabs",
    "grafanalabs": "grafana",
    "sublimesecurity": "sublimesecurity",
}


def probe_greenhouse(slug: str, timeout: float = 8.0) -> Optional[int]:
    try:
        r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
                         timeout=timeout)
        if r.status_code == 200:
            return len(r.json().get("jobs", []))
    except Exception:
        pass
    return None


def probe_lever(slug: str, timeout: float = 8.0) -> Optional[int]:
    try:
        r = requests.get(f"https://api.lever.co/v0/postings/{slug}?mode=json",
                         timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                return len(data)
    except Exception:
        pass
    return None


def probe_ashby(slug: str, timeout: float = 8.0) -> Optional[int]:
    try:
        r = requests.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true",
            timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            return len(data.get("jobs", []))
    except Exception:
        pass
    return None


def probe_all(slug: str) -> dict:
    gh = probe_greenhouse(slug)
    lv = probe_lever(slug)
    # Ashby: try the slug itself + alias
    ashby_slug = ASHBY_ALIASES.get(slug, slug)
    ab = probe_ashby(ashby_slug)
    return {"slug": slug, "greenhouse": gh, "lever": lv, "ashby": ab,
            "ashby_slug": ashby_slug if ab is not None else None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default=None)
    ap.add_argument("--min-jobs", type=int, default=1)
    ap.add_argument("--workers", type=int, default=20)
    args = ap.parse_args()

    if args.candidates:
        cands = [l.strip() for l in open(args.candidates) if l.strip() and not l.startswith("#")]
    else:
        cands = DEFAULT_CANDIDATES

    print(f"[probe] {len(cands)} candidate slugs, workers={args.workers}", file=sys.stderr)
    results: list[dict] = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for res in ex.map(probe_all, cands):
            results.append(res)

    gh_hits = [r for r in results if (r["greenhouse"] or 0) >= args.min_jobs]
    lv_hits = [r for r in results if (r["lever"] or 0) >= args.min_jobs]
    ab_hits = [r for r in results if (r["ashby"] or 0) >= args.min_jobs]

    def line(name, count):
        return f"# {name}: {count} boards with ≥{args.min_jobs} jobs"

    print(line("greenhouse", len(gh_hits)))
    print(line("lever",      len(lv_hits)))
    print(line("ashby",      len(ab_hits)))
    print()

    print("# --- copy into config/companies.yaml under `greenhouse:` ---")
    for r in sorted(gh_hits, key=lambda x: -(x["greenhouse"] or 0)):
        print(f"  - {r['slug']}       # {r['greenhouse']} jobs")
    print()
    print("# --- copy under `lever:` ---")
    for r in sorted(lv_hits, key=lambda x: -(x["lever"] or 0)):
        print(f"  - {r['slug']}       # {r['lever']} jobs")
    print()
    print("# --- copy under `ashby:` ---")
    for r in sorted(ab_hits, key=lambda x: -(x["ashby"] or 0)):
        note = f" (alias for {r['slug']})" if r["ashby_slug"] and r["ashby_slug"] != r["slug"] else ""
        print(f"  - {r['ashby_slug']}       # {r['ashby']} jobs{note}")

    # Cross-tab: which candidates appear on nothing at all
    zero = [r for r in results if not any(r.get(k) for k in ("greenhouse", "lever", "ashby"))]
    print()
    print(f"# {len(zero)} candidates found on NONE of gh/lever/ashby (may use workday/custom)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
