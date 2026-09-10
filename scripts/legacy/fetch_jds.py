"""Populate `full_jd` for rows in a pending JSONL that lack it.

Concurrent HTTP fetch → strip HTML → truncate. Skips rows that already have
a JD. Idempotent: safe to re-run.

Usage:
    python3 scripts/fetch_jds.py 2026-09-01              # process today's pending
    python3 scripts/fetch_jds.py --in FILE --out FILE    # explicit paths
    python3 scripts/fetch_jds.py 2026-09-01 --limit 50   # for smoke tests
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.utils.text_utils import strip_html  # noqa: E402


UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept": "text/html,*/*"}
MAX_JD_CHARS = 12000     # trim to keep pending file sane
TIMEOUT = 15


def fetch_one(url: str) -> tuple[str, str]:
    """Return (jd_text, err). jd_text is empty on failure."""
    if not url:
        return "", "empty url"
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code != 200:
            return "", f"http {r.status_code}"
        ctype = r.headers.get("content-type", "")
        if "html" not in ctype and "text" not in ctype:
            return "", f"non-html content-type: {ctype[:40]}"
        text = strip_html(r.text)
        if len(text) < 200:
            # likely JS-rendered page (workday, etc)
            return "", f"too short ({len(text)}c) — probably JS-rendered"
        return text[:MAX_JD_CHARS], ""
    except requests.Timeout:
        return "", "timeout"
    except requests.RequestException as e:
        return "", f"request error: {type(e).__name__}"
    except Exception as e:
        return "", f"unexpected: {type(e).__name__}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("date", nargs="?", default=dt.date.today().isoformat())
    ap.add_argument("--in", dest="in_file", default=None)
    ap.add_argument("--out", dest="out_file", default=None)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="max URLs to fetch (0 = all)")
    ap.add_argument("--only-source", default="simplify_new_grad",
                    help="only fetch for rows from this source (default simplify_new_grad); use 'any' for all")
    args = ap.parse_args()

    in_path = Path(args.in_file) if args.in_file else \
        _ROOT / "data" / "pending" / f"{args.date}.jsonl"
    out_path = Path(args.out_file) if args.out_file else in_path

    if not in_path.exists():
        print(f"[fetch] input not found: {in_path}", file=sys.stderr)
        return 1

    rows = [json.loads(l) for l in in_path.open("r", encoding="utf-8") if l.strip()]
    print(f"[fetch] loaded {len(rows)} rows from {in_path.name}")

    # index rows needing fetch
    def needs_fetch(r: dict) -> bool:
        if r.get("full_jd"):
            return False
        if args.only_source != "any" and r.get("source") != args.only_source:
            return False
        return bool(r.get("url"))

    targets = [(i, r) for i, r in enumerate(rows) if needs_fetch(r)]
    if args.limit:
        targets = targets[: args.limit]
    print(f"[fetch] {len(targets)} rows need JD fetch (workers={args.workers})")

    if not targets:
        print("[fetch] nothing to do")
        return 0

    ok = fail = 0
    errors_by_kind: dict[str, int] = {}

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(fetch_one, r["url"]): (i, r) for i, r in targets}
        done = 0
        for fut in as_completed(futs):
            i, r = futs[fut]
            jd, err = fut.result()
            if jd:
                r["full_jd"] = jd
                r["_jd_fetched"] = True
                ok += 1
            else:
                fail += 1
                errors_by_kind[err] = errors_by_kind.get(err, 0) + 1
                r["_jd_fetch_error"] = err
            done += 1
            if done % 100 == 0 or done == len(targets):
                print(f"[fetch] progress {done}/{len(targets)}  ok={ok} fail={fail}")

    # write back
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[fetch] wrote {out_path}")
    print(f"[fetch] TOTAL ok={ok} fail={fail}")
    print("[fetch] top error kinds:")
    for k, n in sorted(errors_by_kind.items(), key=lambda kv: -kv[1])[:10]:
        print(f"          {n:>5}  {k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
