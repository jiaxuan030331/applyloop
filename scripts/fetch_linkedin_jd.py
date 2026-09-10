"""Parse + clean LinkedIn voyager job responses fetched by Chrome extension.

**No HTTP.** Fetching happens in the browser via `mcp__claude-in-chrome__*`
tools driving the user's authenticated LinkedIn tab. See
`agents/DAILY_SCRAPER.md` §Protocol.

Consumes:
    --raw    JSONL of `{jid, body}` — the raw voyager JD responses dumped
             from the browser (`window.linkedin.dumpJDs` in the browser).
    --scrape JSON list of card stubs from `voyagerJobsDashJobCards` — the
             dedup-vs-jobs.csv survivors from the search stage.

Produces:
    --out    the enriched JSONL the filter agent consumes. Schema is
             documented in `agents/DAILY_SCRAPER.md` §Handoff contract.

Two public functions worth reusing:
    parse_voyager_job(body) -> dict     — pluck fields from one voyager body
    clean_jd(raw_text) -> str           — strip login/EEO boilerplate from a JD
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


# ---------- JD cleaning ----------

SECTION_START_RE = re.compile(
    r'(?:^|\n|\.)\s*'
    r'(About (?:the )?(?:role|team|job|position|opportunity|company|us)|'
    r'The Role|Your Role|What You(?:\'| w)ill Do|What you will do|'
    r'Responsibilities?|Key Responsibilities|Duties|Day[- ]to[- ]day|'
    r'(?:Basic|Minimum|Required) Qualifications?|'
    r'(?:Preferred|Nice[- ]to[- ]have|Bonus) Qualifications?|'
    r'Qualifications?|Requirements?|Skills(?: and Experience)?|Experience|'
    r'Preferred Skills|Nice to Have|Preferred Experience|'
    r'Compensation(?: Range)?|Salary(?: Range)?|Pay Range|Benefits|'
    r'What We Offer|Perks|Why Join|Total Rewards|'
    r'Employment Type|Job Type|Location|Additional Information)'
    r'\s*[:\-–—]?\s*',
    re.IGNORECASE
)

NOISE_LINE_PATTERNS = [
    r'^\s*(Sign in with|Sign in|Sign up|Join now|Join or sign in|Report this job|Save|Apply|Set alert|Report)\b.*$',
    r'^\s*(Email or phone|Password|Forgot password|Continue|New to LinkedIn|By clicking Continue)\b.*$',
    r'^\s*(Use AI to assess|Tailor my resume|Am I a good fit|Get AI-powered advice)\b.*$',
    r'^\s*(See who \w+ has hired|People also viewed|Similar jobs|Show more jobs)\b.*$',
    r'^\s*Over \d+ applicants?\s*$',
    r'^\s*\d+ (?:day|week|month|hour)s?\s+ago\s*$',
    r'^\s*Actively (?:reviewing|hiring)\s*$',
    r'^\s*Promoted\s*$',
    r'^\s*Show more\s*$',
    r'^\s*Show less\s*$',
    r'^\s*(User Agreement|Privacy Policy|Cookie Policy)\b.*$',
    r'^\s*(Equal Opportunity Employer|E-Verify|Affirmative Action|Reasonable Accommodation).*$',
    r'^\s*.{0,80}(?:equal opportunity|discriminate|drug[- ]free workplace|criminal histor).{0,200}$',
]
NOISE_RE = re.compile('|'.join(NOISE_LINE_PATTERNS), re.IGNORECASE | re.MULTILINE)


def strip_html_to_text(s: str) -> str:
    s = html.unescape(s or "")
    s = re.sub(r'<script[^>]*>.*?</script>', ' ', s, flags=re.DOTALL)
    s = re.sub(r'<style[^>]*>.*?</style>', ' ', s, flags=re.DOTALL)
    s = re.sub(r'<br[^>]*/?>', '\n', s, flags=re.IGNORECASE)
    s = re.sub(r'</(?:p|div|li|h[1-6]|tr)>', '\n', s, flags=re.IGNORECASE)
    s = re.sub(r'<li[^>]*>', '\n• ', s, flags=re.IGNORECASE)
    s = re.sub(r'<[^>]+>', ' ', s)
    return s


def clean_jd(raw_text: str) -> str:
    """Strip noise, keep from first meaningful section start."""
    if not raw_text: return ""
    text = raw_text
    text = re.sub(r'[ \t\r]+', ' ', text)
    text = re.sub(r'\n{2,}', '\n', text).strip()
    m = SECTION_START_RE.search(text)
    if m:
        text = text[m.start():]
    text = NOISE_RE.sub('', text)
    text = re.sub(r'\n{2,}', '\n', text).strip()
    return text[:12000]


# ---------- voyager response parser ----------

def _dig_included_by_type(inc: list, type_suffix: str) -> list:
    return [x for x in inc if (x.get('$type', '') or '').endswith(type_suffix)]


def parse_voyager_job(body: dict) -> dict:
    """Extract useful fields from a /voyager/api/jobs/jobPostings/{id} response
    (decorationId WebFullJobPosting-65). Return dict with all fields safe to
    JSON-serialize."""
    data = body.get('data', {}) or {}
    inc = body.get('included', []) or []

    # description: data.description.text is HTML-ish
    desc_obj = data.get('description') or {}
    full_jd_raw = ""
    if isinstance(desc_obj, dict):
        full_jd_raw = desc_obj.get('text') or ""
    full_jd = clean_jd(strip_html_to_text(full_jd_raw)) if full_jd_raw else ""

    # location + comp + core fields
    loc = data.get('formattedLocation') or ""
    listed_at_ms = data.get('originalListedAt') or data.get('listedAt') or 0
    listed_iso = ""
    if listed_at_ms:
        try:
            listed_iso = dt.datetime.fromtimestamp(
                listed_at_ms / 1000, tz=dt.timezone.utc).date().isoformat()
        except Exception: pass
    applies = data.get('applies')

    # external apply URL — voyager exposes this in applyMethod.companyApplyUrl
    apply_method = data.get('applyMethod') or {}
    external_url = ""
    if isinstance(apply_method, dict):
        external_url = apply_method.get('companyApplyUrl') or apply_method.get('easyApplyUrl') or ""
    # LinkedIn's canonical view URL is data.jobPostingUrl
    li_view_url = data.get('jobPostingUrl') or ""

    # title — sometimes in data.title, sometimes we need to dig into included[]
    title = data.get('title') or ""
    if not title:
        for x in _dig_included_by_type(inc, 'JobPosting') + _dig_included_by_type(inc, 'FullJobPosting'):
            if x.get('title'):
                title = x['title']; break

    # company: data.companyDetails.company is a URN, resolved in included[]
    company = ""
    cd = data.get('companyDetails') or {}
    if isinstance(cd, dict):
        comp_urn = cd.get('company')
        for x in inc:
            t = (x.get('$type') or '').split('.')[-1]
            if x.get('entityUrn') == comp_urn and t in ('Company', 'MiniCompany'):
                company = x.get('name') or x.get('universalName') or ""
                break
        if not company:
            # some responses inline name
            company = cd.get('companyName') or ""

    return {
        "title": title,
        "company": company,
        "location": loc,
        "date_posted": listed_iso,
        "applies": applies,
        "external_url": external_url,
        "li_view_url": li_view_url,
        "full_jd": full_jd,
    }


# ---------- merge with scrape ----------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True,
                    help="JSONL of {jid, body} raw voyager getJob responses "
                         "(dumped by Chrome extension)")
    ap.add_argument("--scrape", required=True,
                    help="linkedin_voyager_<date>.json (list of {jid,title,company,location,url,source_query})")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    raw_path = Path(args.raw)
    scrape_path = Path(args.scrape)
    out_path = Path(args.out)

    scrape_rows = json.loads(scrape_path.read_text())
    scrape_by_jid = {str(r['jid']): r for r in scrape_rows if r.get('jid')}

    enriched_by_jid: dict[str, dict] = {}
    with raw_path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                item = json.loads(line)
                jid = str(item.get('jid') or '')
                body = item.get('body') or {}
            except Exception as e:
                print(f"[jd] bad raw line skipped: {e}")
                continue
            if not jid or not body:
                continue
            parsed = parse_voyager_job(body)
            enriched_by_jid[jid] = parsed

    # Merge with scrape base
    out_rows = []
    for jid, row in scrape_by_jid.items():
        p = enriched_by_jid.get(jid, {})
        merged = {**row}
        # prefer voyager-parsed fields (they're more authoritative)
        for k in ('title', 'company', 'location', 'date_posted',
                  'external_url', 'full_jd'):
            v = p.get(k) or ""
            if v: merged[k] = v
        merged['applies'] = p.get('applies')
        merged['_has_jd'] = bool(p.get('full_jd'))
        out_rows.append(merged)

    with out_path.open('w', encoding='utf-8') as f:
        for r in out_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    total = len(out_rows)
    with_jd = sum(1 for r in out_rows if r.get('_has_jd'))
    with_ext = sum(1 for r in out_rows if r.get('external_url'))
    print(f"[jd] wrote {out_path}   {total} rows | {with_jd} with JD | {with_ext} with external_url")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
