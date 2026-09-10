"""Coarse hard-reject filter for LinkedIn voyager rows.

Reads:  data/pending/<name>.jsonl  (or .json array)
Writes: data/pending/<name>.filtered.jsonl

Rejects a row if ANY of these is true:
    R1  Sponsorship: JD explicitly does not sponsor / OPT / no visa
    R2  PhD required in JD
    R3  YoE requirement ≥ 2 years in JD
    R4  Title has senior/staff/manager/lead/principal/director/L4+/II+
    R5  Title has intern/contract/student worker/apprentice/fellowship
    R6  Title is clearly non-tech (analyst/accountant/HR/marketing/etc.)
        AND JD has no coding/ML keywords
    R7  Compensation ceiling < $90k detected in JD
    R8  Known recruiting-agency company (Jobright.ai, StaffGreat, etc.)
    R9  Non-US location (LinkedIn queries are US-only but empty locations
        sometimes hide non-US postings)

Uncertain agency → keep, prepend `[agency?]` tag to fit_summary later.

Usage:
    python3 scripts/hard_filter.py --in FILE   (default: data/pending/linkedin_voyager_<today>.enriched.jsonl)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


# ---------- patterns ----------

R1_NO_SPONSOR = re.compile(
    r'do(?:es)? not (?:offer|provide|support|sponsor).{0,40}(?:visa )?sponsor'
    r'|unable to (?:offer|provide|sponsor)'
    r'|cannot (?:offer|provide|sponsor)'
    r'|will not (?:sponsor|be sponsoring)'
    r'|no (?:visa )?sponsorship (?:available|offered|provided|at this time)'
    r'|without (?:the need for )?(?:current or future )?(?:visa )?sponsorship'
    r'|authorized to work in the (?:us|u\.?s\.?)(?:[^.]{0,80}(?:without .{0,40}sponsor|now or in the future))'
    r'|must be (?:legally )?authorized to work.*without .{0,40}sponsor'
    r'|not (?:be )?eligible for opt|does not (?:hire|accept) opt|no opt',
    re.IGNORECASE | re.DOTALL
)

# R10: US-person / citizenship-only / clearance / ITAR — F-1 categorically
# ineligible, hard reject (user 2026-09-10). Kept narrow to avoid matching
# EEO boilerplate ("...regardless of citizenship...").
R10_US_PERSON = re.compile(
    r'must be (?:a )?u\.?s\.? (?:person|citizen)'
    r'|only u\.?s\.? citizens?'
    r'|u\.?s\.? citizenship (?:is )?required'
    r'|(?:active|current) (?:ts\/sci|top secret|secret) clearance'
    r'|(?:obtain|maintain|hold)[^.]{0,40}security clearance'
    r'|security clearance (?:is )?required'
    r'|\bitar\b[^.]{0,80}(?:u\.?s\.? person|citizen|permanent resident)'
    r'|export control[^.]{0,80}u\.?s\.? person',
    re.IGNORECASE
)

R2_PHD_REQ = re.compile(
    r'(?:^|[^a-z])(?:phd|ph\.?d\.?)\s+(?:is\s+)?(?:required|mandatory)'
    r'|requires? (?:a\s+)?(?:phd|ph\.?d\.?)'
    r'|must (?:have|hold|possess) (?:a\s+)?(?:phd|ph\.?d\.?)'
    r'|only (?:phd|ph\.?d\.?)|(?:phd|ph\.?d\.?) candidates? only',
    re.IGNORECASE
)

# YoE ≥ 2 (tightened from 3)
R3_YOE = re.compile(
    r'(?:minimum|at least|require[sd]?|require:?|\+?)\s*(\d+)\+?\s*(?:years?|yrs?)'
    r'(?:\s+of)?\s+(?:relevant\s+|professional\s+|industry\s+)?(?:experience|work exp|exp\b)',
    re.IGNORECASE
)

R4_SENIOR_TITLE = re.compile(
    r'\b(?:senior|sr\.?|staff|principal|distinguished|head of|director|manager|mgr|'
    r'lead|chief|vp|vice president|architect(?! trainee| associate)|'
    r'l[456789]\b|iii\b|iv\b|sde\s*[234]|swe\s*[234]|engineer,?\s*ii|engineer,?\s*iii|'
    r'level\s*[456])\b',
    re.IGNORECASE
)

R5_INTERN = re.compile(
    r'\b(?:intern|internship|student worker|apprentice|apprenticeship|'
    r'fellow(?!ship of)|fellowship|contract(?:or)?|part[- ]time|'
    r'co[- ]op|coop|summer\s+\d{4})\b',
    re.IGNORECASE
)

# Non-tech titles — drop if title clearly non-tech AND JD has no coding/ML keywords
R6_NONTECH_TITLE = re.compile(
    r'\b(?:account executive|account manager|ae\b|customer success|'
    r'sales(?! engineer)|business development|partnerships?|'
    r'counsel|attorney|paralegal|legal|recruiter|talent acquisition|'
    r'marketing|brand|communications|editor|writer|content(?! moderator)|'
    r'copywriter|designer(?! systems)|graphic designer|'
    r'ux(?! engineer)|ui(?! engineer)(?!\/)|'
    r'finance(?! engineer)|accountant|accounting|controller|tax\b|auditor|audit\b|'
    r'executive assistant|office manager|receptionist|facilities|security guard|'
    r'program manager|project manager|product manager(?!,\s*ml)|'
    r'technical writer|support specialist|analyst,\s*(?:business|finance|hr|policy)|'
    r'compliance|hr\b|human resources|people (?:ops|operations)|'
    r'video producer|videographer|photographer|nurse|physician|therapist|clinician)\b',
    re.IGNORECASE
)
CODING_ML_TERMS = re.compile(
    r'\b(?:python|java|c\+\+|golang|rust|typescript|kubernetes|docker|'
    r'machine learning|deep learning|pytorch|tensorflow|sql|api|backend|'
    r'frontend|full[- ]?stack|distributed|algorithm|data structure|ml|ai|llm|'
    r'nlp|computer vision|reinforcement|neural network|coding|programming|'
    r'engineer|scientist|developer|software|architect|devops|mlops|'
    r'ci/cd|linux|microservice|database|infrastructure|cloud|aws|azure|gcp)\b',
    re.IGNORECASE
)

# Compensation ceiling detection.
# Match patterns like "$120,000 - $180,000" and "up to $180K" and "base salary of $80,000"
_COMP_RANGE = re.compile(
    r'\$\s*([\d,]+)(?:\.\d+)?\s*(K|,000|)\s*(?:/(?:yr|year|annum))?\s*[-–—to]{1,4}\s*\$\s*([\d,]+)(?:\.\d+)?\s*(K|,000|)',
    re.IGNORECASE
)
_COMP_UP_TO = re.compile(
    r'up to\s*\$\s*([\d,]+)(?:\.\d+)?\s*(K|,000|)', re.IGNORECASE
)
_COMP_HOURLY = re.compile(
    r'\$\s*(\d+(?:\.\d+)?)\s*(?:/\s*(?:hr|hour|hourly))', re.IGNORECASE
)

def _to_annual_usd(num_str: str, suffix: str) -> int | None:
    try:
        v = float(num_str.replace(',', ''))
        if suffix.upper() == 'K':
            v *= 1000
        return int(v)
    except Exception:
        return None

def check_R7_comp(jd: str) -> tuple[bool, str]:
    """Return (drop_it, reason). Only consider values ≥ $30k annual — below
    that is almost certainly signing bonus / equity / stipend / hourly-not-salary."""
    if not jd: return (False, "")
    MIN_ANNUAL_PLAUSIBLE = 30000
    max_seen: int | None = None
    for m in _COMP_RANGE.finditer(jd):
        hi = _to_annual_usd(m.group(3), m.group(4) or '')
        if hi and hi >= MIN_ANNUAL_PLAUSIBLE and (max_seen is None or hi > max_seen):
            max_seen = hi
    for m in _COMP_UP_TO.finditer(jd):
        hi = _to_annual_usd(m.group(1), m.group(2) or '')
        if hi and hi >= MIN_ANNUAL_PLAUSIBLE and (max_seen is None or hi > max_seen):
            max_seen = hi
    # hourly → annualize
    for m in _COMP_HOURLY.finditer(jd):
        try:
            hourly = float(m.group(1))
            annual = int(hourly * 2080)
            if annual >= MIN_ANNUAL_PLAUSIBLE and (max_seen is None or annual > max_seen):
                max_seen = annual
        except Exception: pass
    if max_seen is not None and max_seen < 90000:
        return (True, f"comp max ${max_seen:,} < $90k")
    return (False, "")


# Known recruiting agencies / job aggregators / bodyshops — drop entirely
KNOWN_AGENCIES = {
    "jobright.ai", "jobright", "staffgreat.com", "staffgreat",
    "alpha associates recruitment", "golden gate recruiting",
    "monarch recruiters", "brooksource", "harvey nash", "hays",
    "tata consultancy services", "tcs", "capgemini", "cognizant",
    "infosys", "wipro", "accenture federal", "genpact",
    "intellipro", "beaconfire", "beaconfire inc.", "beaconfire inc",
    "emonics llc", "amentum", "collabera", "green key resources",
    "adidev technologies inc", "9to9 software solutions",
    "united smart tech", "haystack", "hashlist", "insight global",
    "apex systems", "kforce", "robert half", "aerotek", "cybercoders",
    "ttec", "iterisenterprise", "wired media solutions",
    "tmv global inc", "veridian tech solutions", "unify technologies",
    "eros technologies inc", "genius technology", "j-mack technologies",
    "signature it world inc", "arkhya tech", "maximatek", "fractal",
    "goal solutions", "apetan consulting llc", "the phoenix group",
    "the methodical group", "consumer cellular", "meeboss",
    "carex consulting group", "andromeda systems incorporated",
    "sanctuary software studio", "brookvent", "brookfield",
    "publicis groupe", "expleo", "capco", "sopra steria", "wavestone",
    "cook systems", "ldi connect", "green key",
    "silver spark apparel limited", "silver spark apparel",
    "stott and may", "beaconfire", "onto innovation",
}

def is_known_agency(company: str) -> bool:
    if not company: return False
    c = company.strip().lower()
    return c in KNOWN_AGENCIES

# Ambiguous agency signal — flag but don't drop
_AGENCY_HINTS = re.compile(
    r'\b(?:consulting|staffing|recruitment|recruiter|body ?shop|'
    r'talent solutions|talent acquisition|placement|contingent)\b',
    re.IGNORECASE
)
def maybe_agency(company: str) -> bool:
    if not company: return False
    return bool(_AGENCY_HINTS.search(company))


# Non-US detection — LinkedIn is queried with US filter but sometimes leaks
US_STATES = ["AL","AK","AZ","AR","CA","CO","CT","DE","DC","FL","GA","HI","ID","IL","IN",
             "IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH",
             "NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT",
             "VT","VA","WA","WV","WI","WY"]
US_LOC_RE = re.compile(
    "|".join([rf"\b{s}\b" for s in US_STATES]) +
    "|United States|USA|U\\.S\\.A?\\.?|Remote|Americas?", re.IGNORECASE
)
NON_US_LOC_RE = re.compile(
    r'\b(?:UK|United Kingdom|London|Ireland|Dublin|Canada|Toronto|Vancouver|Montreal|'
    r'India|Bangalore|Bengaluru|Hyderabad|Mumbai|Singapore|Japan|Tokyo|Korea|Seoul|'
    r'China|Beijing|Shanghai|Shenzhen|Australia|Sydney|Melbourne|Germany|Berlin|Munich|'
    r'France|Paris|Netherlands|Amsterdam|Spain|Italy|Milan|Sweden|Stockholm|Poland|'
    r'Warsaw|Israel|Tel Aviv|Brazil|Mexico|Argentina|Chile|Saudi Arabia|UAE|Dubai|'
    r'Switzerland|Zurich|Zürich|Denmark|Copenhagen|Norway|Finland|Belgium|Brussels|'
    r'Austria|Vienna|Portugal|Lisbon|Hong Kong|Taiwan|Taipei|Philippines|Manila|'
    r'Vietnam|Malaysia|Thailand|Indonesia|Jakarta|Turkey|Istanbul|EMEA|APAC|LATAM|'
    r'Europe(?!an))\b',
    re.IGNORECASE
)


# ---------- per-row evaluator ----------

def evaluate(row: dict) -> dict:
    """Return {'keep': bool, 'reasons': [...], 'flags': [...]}."""
    title = row.get('title') or ''
    jd = row.get('full_jd') or ''
    company = row.get('company') or ''
    loc = row.get('location') or ''
    reasons: list[str] = []
    flags: list[str] = []

    # R8: known agency → drop
    if is_known_agency(company):
        reasons.append(f"R8:known-agency({company})")
    elif maybe_agency(company):
        flags.append("agency?")

    # R4: senior title
    if R4_SENIOR_TITLE.search(title):
        reasons.append("R4:senior-title")

    # R5: intern / contract
    if R5_INTERN.search(title):
        reasons.append("R5:intern-or-contract")

    # R9: non-US location
    if loc:
        if NON_US_LOC_RE.search(loc) and not US_LOC_RE.search(loc):
            reasons.append(f"R9:non-us-loc({loc[:60]})")

    # R10: US-person / clearance / ITAR -> hard reject (F-1 ineligible)
    if (jd and R10_US_PERSON.search(jd)) or (title and R10_US_PERSON.search(title)):
        reasons.append("R10:us-person-or-clearance")

    # R1: sponsorship -> FLAG for user decision, not a drop (user 2026-09-10)
    if jd and R1_NO_SPONSOR.search(jd):
        flags.append("no_sponsor?")

    # R2: PhD required
    if jd and R2_PHD_REQ.search(jd):
        reasons.append("R2:phd-required")

    # R3: YoE ≥ 2
    if jd:
        for m in R3_YOE.finditer(jd):
            try:
                y = int(m.group(1))
                if y >= 2:
                    reasons.append(f"R3:yoe-req≥{y}")
                    break
            except Exception: pass

    # R6: non-tech title + no coding/ml keywords in JD
    if R6_NONTECH_TITLE.search(title) and not CODING_ML_TERMS.search(jd):
        reasons.append("R6:non-tech-title")

    # R7: comp ceiling
    drop, why = check_R7_comp(jd)
    if drop:
        reasons.append(f"R7:{why}")

    return {"keep": len(reasons) == 0, "reasons": reasons, "flags": flags}


# ---------- main ----------

def _load(path: Path) -> list[dict]:
    """Support both .jsonl and .json array files."""
    s = path.read_text().strip()
    if not s: return []
    if s[0] == '[':
        return json.loads(s)
    return [json.loads(l) for l in s.splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_file", default=None)
    ap.add_argument("--out", dest="out_file", default=None)
    args = ap.parse_args()

    in_path = Path(args.in_file) if args.in_file else \
        _ROOT / "data" / "pending" / f"linkedin_voyager_{dt.date.today().isoformat()}.enriched.jsonl"
    if args.out_file:
        out_path = Path(args.out_file)
    else:
        out_path = in_path.with_suffix('.filtered.jsonl')

    if not in_path.exists():
        print(f"[filter] input not found: {in_path}", file=sys.stderr); return 1

    rows = _load(in_path)
    reasons_ctr: Counter[str] = Counter()
    kept, dropped, flagged = 0, 0, 0

    with out_path.open('w', encoding='utf-8') as fout:
        for r in rows:
            ev = evaluate(r)
            if not ev["keep"]:
                dropped += 1
                for reason in ev["reasons"]:
                    reasons_ctr[reason.split('(')[0]] += 1
                continue
            if ev["flags"]:
                r["_flags"] = ev["flags"]
                flagged += 1
            fout.write(json.dumps(r, ensure_ascii=False) + "\n")
            kept += 1

    print(f"[filter] input : {in_path.name}  {len(rows)} rows")
    print(f"[filter] output: {out_path.name}  {kept} kept, {dropped} dropped, {flagged} flagged")
    print(f"[filter] top drop reasons:")
    for r, n in reasons_ctr.most_common(15):
        print(f"          {n:>4}  {r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
