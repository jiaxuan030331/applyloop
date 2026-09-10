"""Classification rules for job postings — drops and buckets.

Pure functions, no I/O beyond loading `config/profile.yaml` at import.
`scripts/ingest.py` is the only caller on the live path.

Two jobs:

  1. **Drop** what the candidate could not or would not take (`drop_reason`).
     Codes X1-X10; every one can be switched off in the profile, and
     `rulebook.md` §5 documents the table.
  2. **Bucket** the survivors along five dimensions so `/batch` can slice
     the board: region (A), employer tier (B), compensation (C), role
     direction (D), and how sure we are it is a campus hire (E).

The split between this file and `config/profile.yaml` is deliberate: the
regexes here encode how job postings are *written* — "3+ years of experience",
"active TS/SCI", "Sr. Staff Engineer" — which is the same for everyone. The
profile encodes who *you* are: where you'd move, which employers you rate,
what pay is worth your time, what you specialise in. Fork this project and
you should only ever edit the profile.

Rules are deliberately coarse. A borderline posting survives carrying a
`flags` note (see `labels.flags` in the profile) for a human
to judge — missing a good job costs more than reading one extra row.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_PROFILE_PATH = Path(__file__).resolve().parents[1] / "config" / "profile.yaml"
with _PROFILE_PATH.open(encoding="utf-8") as _f:
    PROFILE: dict = yaml.safe_load(_f)

_DROPS = PROFILE["drops"]
_L = PROFILE["labels"]
_DL, _FL = _L["drops"], _L["flags"]
_on = _DROPS.get                       # _on("X2_clearance", True)

# ============================================================ A. REGION

_REGIONS = PROFILE["regions"]
_REGION_RE = {k: re.compile(v["match"], re.I)
              for k, v in _REGIONS["buckets"].items() if v.get("match")}
_REGION_NAME = {k: v["name"] for k, v in _REGIONS["buckets"].items()}
# A location that names no city or state at all — "United States", "Remote".
_REMOTE = re.compile(r'^\s*(United States|USA|US|Remote|Anywhere|'
                     r'United States \(Remote\))\s*$', re.I)


def bucket_region(loc: str) -> tuple[str, str]:
    l = (loc or '').strip()
    if not l:
        return _REGIONS["remote"], _REGION_NAME[_REGIONS["remote"]]
    if _REMOTE.match(l):
        return _REGIONS["remote"], _REGION_NAME[_REGIONS["remote"]]
    for key in _REGIONS["order"]:
        rx = _REGION_RE.get(key)
        if rx and rx.search(l):
            return key, _REGION_NAME[key]
    other = _REGIONS["other"]
    return other, _REGION_NAME[other]


# ============================================================ B. COMPANY TIER

_TIERS = PROFILE["tiers"]
_TIER_NAME = {k: v["name"] for k, v in _TIERS["names"].items()}
_TIER_OF: dict[str, str] = {}
for _tier, _members in _TIERS["members"].items():
    for _m in _members:
        _TIER_OF[_m.strip().lower()] = _tier

_ACADEMIC = re.compile(r'\b(universit|college|school district|institute of technology|'
                       r'caltech|stanford|harvard|hospital|health system|medicine|'
                       r'children\'s|research foundation|board of education)\b', re.I)


def bucket_tier(company: str) -> str:
    c = (company or '').strip().lower()
    if c in _TIER_OF:
        return _TIER_OF[c]
    if _ACADEMIC.search(company or ''):
        return _TIERS["academic"]
    return _TIERS["unlisted"]


# ============================================================ C. COMP

_RANGE = re.compile(
    r'\$\s*([\d,]+(?:\.\d+)?)\s*(K|M|)\s*(?:/\s*(?:yr|year|hr|hour))?\s*'
    r'(?:-|–|—|to)\s*\$?\s*([\d,]+(?:\.\d+)?)\s*(K|M|)', re.I)
_SINGLE = re.compile(r'\$\s*([\d,]+(?:\.\d+)?)\s*(K|)\b', re.I)
_HOURLY = re.compile(r'\$\s*(\d+(?:\.\d+)?)\s*(?:/\s*(?:hr|hour)|\s*per hour|\s*hourly)', re.I)
_NON_USD = re.compile(r'(CA\$|C\$|£|€|CAD|GBP|EUR|₹|INR)')


def _num(s: str, suf: str) -> float | None:
    try:
        v = float(s.replace(',', ''))
    except Exception:
        return None
    if suf.upper() == 'K': v *= 1_000
    elif suf.upper() == 'M': v *= 1_000_000
    return v


def parse_comp(jd: str) -> tuple[int | None, int | None, bool]:
    """Return (min_annual, max_annual, non_usd_seen)."""
    if not jd: return (None, None, False)
    non_usd = bool(_NON_USD.search(jd))
    lo = hi = None
    for m in _RANGE.finditer(jd):
        a, b = _num(m.group(1), m.group(2)), _num(m.group(3), m.group(4))
        if a is None or b is None: continue
        # hourly range → annualize
        if b < 300 and a < 300:
            a, b = a * 2080, b * 2080
        if b < 30_000: continue          # bonus / equity / stipend noise
        if hi is None or b > hi: lo, hi = a, b
    if hi is None:
        for m in _HOURLY.finditer(jd):
            v = float(m.group(1)) * 2080
            if v >= 30_000 and (hi is None or v > hi): lo = hi = int(v)
    if hi is None:
        best = None
        for m in _SINGLE.finditer(jd):
            v = _num(m.group(1), m.group(2))
            if v and 30_000 <= v <= 900_000 and (best is None or v > best): best = v
        if best: lo = hi = best
    return (int(lo) if lo else None, int(hi) if hi else None, non_usd)


_BANDS = PROFILE["comp"]["bands"]
_COMP_FLOOR = PROFILE["comp"]["floor_usd"]
_COMP_HIGH_FLOOR = PROFILE["comp"]["suspiciously_high_floor_usd"]
_COMP_NAME = {k: v["name"] for k, v in _BANDS.items()}
# Bands with a `max`, smallest first; anything above them all is the last band.
_BAND_EDGES = sorted(((v["max"], k) for k, v in _BANDS.items() if "max" in v))
_BAND_TOP = [k for k, v in _BANDS.items() if "max" not in v][-1]


def bucket_comp(lo, hi):
    """Bucket by the *ceiling* — what the posting could pay, not its floor."""
    if hi is None:
        return 'C0', _COMP_NAME['C0']
    for edge, key in _BAND_EDGES:
        if key == 'C0':
            continue
        if hi <= edge:
            return key, _COMP_NAME[key]
    return _BAND_TOP, _COMP_NAME[_BAND_TOP]


# ============================================================ D. ROLE

# Hardware and other non-software work. Checked first: without it a title
# like "GPU Verification Engineer" reads as ML infra.
_HARDWARE = re.compile(
    r'\b(asic|vlsi|verilog|rtl\b|physical design|floorplan|floor plan|timing engineer|'
    r'verification engineer|(?:gpu|chip|hardware) architecture|circuits?\b|'
    r'circuit design|soc\b|silicon|semiconductor|mems|pcb|thermal|photonic|optics engineer|'
    r'analog|mixed[- ]signal|memory subsystem|hardware (?:design|developer|engineer)|'
    r'design validation|hardware[- ]in[- ]the[- ]loop|electronics|electrical engineer|'
    r'mechanical|dynamics engineer|turbomachinery|powertrain|aerodynamic|structural|'
    r'manufactur\w+|process engineer|fpga|cad/eda|reverse engineer|firmware|bring up)\b',
    re.I)

# The candidate's own specialty — see `specialty` in config/profile.yaml.
_SPEECH_MM = re.compile(PROFILE["specialty"]["title_match"], re.I)

_SPEECH_STRONG = re.compile(PROFILE["specialty"]["jd_match"], re.I)
_SPEECH_THRESHOLD = PROFILE["specialty"]["jd_threshold"]

_SEARCH_ADS_REC = re.compile(
    r'\b(search|ranking|recommend\w*|recsys|ads?\b|advertis\w+|relevance|'
    r'personaliz\w+|feed\b|monetiz\w+|marketplace ml|query understanding)\b', re.I)

_ML_INFRA = re.compile(
    r'\b(ml infra\w*|ai infra\w*|machine learning infra\w*|ml platform|ai platform|'
    r'mlops|model serving|ml framework|ml systems?|machine learning systems?|systems ml|'
    r'inference|training infra\w*|distributed training|'
    r'developer technology|cuda|triton inference|tensorrt|vllm|hpc\b|'
    r'(?:gpu|kernel|compiler|accelerator)[^,]{0,24}\b(?:infra|platform|software|'
    r'engineer|compute|deep learning|ml|ai)\b|'
    r'\b(?:deep learning|ml|machine learning|ai) (?:gpu|kernel|compiler|systems?)\b)', re.I)

_AI_AGENTIC = re.compile(
    r'\b(ai engineer|ai developer|ai specialist|ai scientist|applied ai|agentic|ai agent|'
    r'llm engineer|genai|gen ai|generative ai|forward deployed|fde\b|'
    r'ai solutions?|ai applications?|llm application|prompt engineer|'
    r'ai product|foundation model|rag\b|ai engineering|ai center of excellence|'
    r'artificial intelligence (?:engineer|developer|consultant))\b', re.I)

_MLE = re.compile(
    r'\b(machine learning engineer|ml engineer|mle\b|applied scientist|'
    r'research (?:engineer|scientist)|deep learning|machine learning|ml\b|'
    r'data scientist|ai/ml|ai & ml|nlp engineer|'
    r'perception engineer|robotics? (?:ml|learning))\b', re.I)

_SWE = re.compile(
    r'\b(software (?:engineer|developer|development engineer|generalist)|'
    r'sw developer|swe\b|sde\b|associate developer|'
    r'engineer,? (?:i|1|software)\b|assoc(?:iate)? engineer,? software|'
    r'backend|back[- ]end|frontend|front[- ]end|full[- ]?stack|platform engineer|'
    r'infrastructure engineer|systems engineer\b|web developer|programmer|'
    r'devops|site reliability|sre\b|cloud engineer|api engineer|'
    r'application (?:engineer|developer)|product engineer|founding engineer|'
    r'mobile (?:engineer|developer)|android engineer|ios engineer|'
    r'integration engineer|middleware engineer|python (?:backend )?developer)\b', re.I)

# A big-company general req: plain SWE title plus new-grad wording and no
# specialisation. These pool SDE and MLE applicants into one pipeline.
_GENERIC_SWE_TITLE = re.compile(
    r'^(?:jr\.?\s*|junior\s*|associate\s*|graduate\s*|new ?grad\s*)?'
    r'(?:software (?:engineer|development engineer|developer)|swe|sde|'
    r'engineer|graduate program)'
    r'(?:\s*[,\-–—(|]\s*(?:i|1|new ?grad|university ?grad(?:uate)?|early ?career|'
    r'entry[- ]level|campus|graduate|20\d\d|full[- ]?time|associate|junior|jr\.?|'
    r'us|usa|remote|multiple positions available|early in career|'
    r'engineering pathways|start|starts|\d{4} start)\s*)*'
    r'[\s)]*$', re.I)

_OTHER_DOMAIN = re.compile(
    r'\b(test engineer|qa\b|quality (?:assurance|engineer)|validation engineer|'
    r'integration & test|civil|construction|hvac|facilities|tunnels|'
    r'business analyst|financial analyst|data analyst|analytics analyst|'
    r'bi (?:analyst|developer)|marketing|product marketing|'
    r'it (?:support|specialist|analyst)|help ?desk|network (?:engineer|operations)|'
    r'telecommunications|support engineer|client success|gtm\b|'
    r'salesforce (?:developer|admin)|sap\b|erp\b|consultant|'
    r'biolog\w+|bioinformatic\w+|biocatalysis|bioassay|bioconjugation|immunology|'
    r'chemist|clinical|laboratory|lab scientist|lab technician|tecnico|'
    r'pharmacokinetics|epidemiolog\w+|neuromodulation|neurolog\w+|cytometry|'
    r'biospecimen|research (?:associate|assistant|analyst|computational scientist)|'
    r'professor|teacher|tchr|lecturer|nurse|therapist|actuar\w+|underwrit\w+|'
    r'quantitative (?:trader|researcher|analyst|engineer|developer|research)|'
    r'quant trader|trading analyst|equity financing|'
    r'game (?:play|design)|gameplay|game designer|3d modeler|animator|'
    r'technical artist|exhibit design|scientist \d|assoc\.? scientist|'
    r'statistical scientist|social science|physical science|graduate students?|'
    r'business transformation|leave analyst|pricing analyst|privacy engineer|'
    r'security engineer|vulnerability|violence prevention|product development engineer)\b',
    re.I)
_RISK = re.compile(r'\b(risk|integrity|fraud|abuse|trust ?& ?safety|compliance|'
                   r'anti[- ]money|aml\b|threat)\b', re.I)

_ROLE_NAME = {k: v["name"] for k, v in PROFILE["roles"].items()}


def bucket_role(title: str, jd: str, tier: str) -> str:
    t = (title or '').strip()
    jd = jd or ''
    # 0) Hardware and other non-software work — decided outright.
    if _HARDWARE.search(t):
        return 'D8'
    # 1) The candidate's specialty: named in the title, or a ML role whose JD
#    is saturated with the terms.
    if _SPEECH_MM.search(t):
        return 'D4'
    if len(_SPEECH_STRONG.findall(jd)) >= _SPEECH_THRESHOLD and (_MLE.search(t) or _AI_AGENTIC.search(t)):
        return 'D4'
    # 2) Search / ads / recommendation.
    if _SEARCH_ADS_REC.search(t):
        return 'D7'
    # 3) ML infrastructure.
    if _ML_INFRA.search(t):
        return 'D6'
    # 4) Applied AI, agents, forward-deployed.
    if _AI_AGENTIC.search(t):
        return 'D5'
    # 5) General ML engineering.
    if _MLE.search(t):
        return 'D3'
    # 6) Clearly some other discipline.
    if _OTHER_DOMAIN.search(t):
        return 'D8'
    if _RISK.search(t) and not _SWE.search(t):
        return 'D8'
    # 7) Software engineering.
    if _SWE.search(t):
        if tier in ('T0', 'T1', 'T2') and _GENERIC_SWE_TITLE.match(t):
            return 'D1'
        return 'D2'
    return 'D8'


# ============================================================ DROPS

_CLEARANCE = re.compile(
    r'\b(security clearance|ts/sci|top secret|secret clearance|'
    r'polygraph|dod clearance|active clearance|clearance (?:is )?required|'
    r'ability to obtain (?:a )?(?:security )?clearance|q clearance|'
    r'public trust clearance|sci\b(?! ?fi))\b', re.I)
# Ranges like "0-3 years" / "1-3 years": take the LOWER bound. Reading the
# upper bound here drops entry-level reqs that happen to span a wide range.
_YOE_RANGE = re.compile(
    r'(\d+)\s*[-–—]\s*(\d+)\s*\+?\s*(?:years?|yrs?)(?:\s+of)?\s+'
    r'(?:[a-z\- ]{0,40}?)?(?:experience|exp\b)', re.I)
# Single value: "3+ years of experience".
_YOE = re.compile(
    r'(?<![-–—\d])(\d+)\s*\+?\s*(?:years?|yrs?)(?:\s+of)?\s+'
    r'(?:relevant\s+|professional\s+|industry\s+|related\s+|hands[- ]on\s+|'
    r'software\s+|engineering\s+|work\s+)*(?:experience|exp\b)', re.I)
_YOE_SOFT = re.compile(r'(?:preferred|nice to have|plus|bonus|ideal|a plus)', re.I)

_AGENCY_NAME = re.compile(
    r'\b(staffing|recruit\w*|resourcing|rpo\b|search group|talent solutions|'
    r'placement|body ?shop|infotech|infosolutions|consultancy)\b', re.I)
# Weak markers: plenty of real companies are called "... Technologies Inc".
# These only raise a flag.
_AGENCY_SOFT = re.compile(
    r'\b(consulting|technologies inc|systems inc|solutions llc|global solutions|'
    r'tech solutions|resources|connections|holdings ltd|group ltd|ventures|'
    r'services llc|partners llc)\b', re.I)
# Title tells that mark an agency repost whatever the company is called:
# "All Levels", a bracketed requisition code, a trailing "| Remote".
_AGENCY_TITLE = re.compile(
    r'(all levels|multiple levels|\[[A-Z]{2}-\d{3,}\]|\|\s*remote\s*$|'
    r'\bwe have several\b|volunteer)', re.I)


# Companies that are never worth an application — see `blocked_companies`
# in config/profile.yaml.
_BLOCKED = {c.strip().lower() for c in PROFILE["blocked_companies"]}
# Title tells that mark an agency repost regardless of the company name:
# "All Levels", a bracketed requisition code, a trailing "| Remote".
_GIG_TITLE = re.compile(r'\b(ai trainer|data annotator|annotator|labeler|'
                        r'freelance|per[- ]task)\b', re.I)

_INTERN = re.compile(r'\b(interns?(?:hips?)?|co[- ]?op|student worker|apprentice|'
                     r'part[- ]time|fellowship|summer 20\d\d)\b', re.I)
_SENIOR = re.compile(
    r'\b(senior|sr\.?|staff|principal|distinguished|head of|director|manager|mgr|'
    r'lead engineer|tech lead|chief|vp|vice president|'
    r'l[4-9]\b|iii\b|iv\b|sde\s*[234]|swe\s*[234]|engineer,?\s*i{2,}\b|'
    r'level\s*[4-9])\b', re.I)
_NO_SPONSOR = re.compile(
    r'do(?:es)? not (?:offer|provide|support|sponsor)[^.]{0,40}sponsor'
    r'|unable to (?:offer|provide|sponsor)|cannot (?:offer|provide|sponsor)'
    r'|will not (?:sponsor|be sponsoring)'
    r'|no (?:visa )?sponsorship (?:available|offered|provided|at this time)'
    r'|without (?:the need for )?(?:current or future )?(?:visa )?sponsorship'
    r'|must be (?:legally )?authorized to work[^.]{0,60}without[^.]{0,40}sponsor'
    r'|not (?:be )?eligible for opt|does not (?:hire|accept) opt'
    r'|only u\.?s\.? citizens?|must be (?:a )?us citizen', re.I | re.S)
_NON_US = re.compile(
    r'\b(canada|toronto|vancouver|ontario|british columbia|united kingdom|london|'
    r'ireland|dublin|germany|berlin|munich|india|bangalore|hyderabad|pune|singapore|'
    r'tokyo|japan|australia|sydney|france|paris|israel|tel aviv|netherlands|amsterdam|'
    r'zurich|switzerland|poland|warsaw|mexico|brazil|spain|madrid|portugal|lisbon|'
    r'sweden|stockholm|korea|seoul|taiwan|taipei|china|shanghai|beijing|shenzhen|'
    r'hong kong|dubai|uae|philippines|vietnam|indonesia|argentina|colombia|chile)\b', re.I)

# ---------- E: campus-hire confidence ----------
_E1_TITLE = re.compile(
    r'\b(new ?grad(uate)?s?|university grad(uate)?|college grad(uate)?|campus|'
    r'early career|early in career|entry[- ]level|recent grad(uate)?|'
    r'graduate program|rotational? program|rotation engineer|'
    r'class of 20\d\d|20(2[6-9])\b|grad\b|graduate)\b'
    r'|(?:engineer|developer|scientist|analyst)\s*[,\-–—]?\s*(i|1)\s*(\(|$|,|-)'
    r'|\b(jr\.?|junior)\b', re.I)
_E1_JD = re.compile(
    r'\b(new grad(uate)?s?|university grad(uate)?|college grad(uate)?|'
    r'campus (?:hire|recruiting|program)|recent grad(uate)?|'
    r'graduating (?:in |by |student)|final year (?:student|of)|'
    r'class of 20\d\d|entry[- ]level|early[- ]career|'
    r'0\s*[-–—]\s*[12]\s*years?|no prior (?:professional )?experience)\b', re.I)
# A stated degree requirement is the clearest positive signal for a new-grad req.
_DEGREE = re.compile(
    r"\b(bachelor'?s?|master'?s?|b\.?s\.?|m\.?s\.?|bs/ms|degree in|"
    r"currently (?:enrolled|pursuing)|academic background)\b", re.I)
# Wording that implies an established engineer.
_SENIORITY_TONE = re.compile(
    r'\b(proven track record|extensive experience|deep expertise|'
    r'mentor(?:ing|ship)? (?:junior|other|team)|lead (?:a |the )?team|'
    r'set (?:the )?technical (?:direction|vision)|own the (?:architecture|roadmap)|'
    r'drive (?:the )?technical strategy|seasoned|battle[- ]tested|'
    r'you have (?:shipped|built and scaled)|industry veteran)\b', re.I)

_PHD = re.compile(r'\b(ph\.?d\.?)\b', re.I)

# ITAR / export control. An F-1 holder is legally ineligible, so this is a
# drop rather than a preference. Only unambiguous wording drops: a lot of
# boilerplate says "for positions requiring access..." without the role
# actually being one, and that only earns a flag.
_ITAR_HARD = re.compile(
    r'(?:must (?:be|qualify as)|required to be|requires? (?:a |an )?)'
    r'[^.]{0,60}\b(?:u\.?s\.? person|us person|protected individual)\b'
    r'|\b(?:itar|international traffic in arms)\b[^.]{0,120}'
    r'\b(?:you must be|must be a|requires? that you)\b'
    r'|to conform to u\.?s\.?[^.]{0,80}export[^.]{0,120}'
    r'\b(?:you must be|must be a)\b',
    re.I | re.S)
_ITAR_SOFT = re.compile(
    r'\b(itar|export[- ]control\w*|export administration regulations|'
    r'u\.?s\.? person|international traffic in arms)\b', re.I)


def norm_key(company: str, title: str) -> tuple[str, str]:
    c = re.sub(r'[^a-z0-9]+', '', (company or '').lower())
    t = (title or '').lower()
    t = re.sub(r'\(.*?\)|\[.*?\]', ' ', t)
    t = re.sub(r'[^a-z0-9]+', ' ', t).strip()
    t = re.sub(r'\b(20\d\d|new grad|university graduate|early career|'
               r'entry level|full time|us|usa)\b', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return (c, t)


def max_yoe(jd: str) -> int | None:
    """Lowest number of years the JD actually requires.

    Ranges resolve to their lower bound, and a number sitting next to
    "preferred" / "nice to have" is not a requirement.
    """
    if not jd: return None
    best = None
    spans = []
    for m in _YOE_RANGE.finditer(jd):
        ctx = jd[max(0, m.start() - 120): m.end() + 120]
        spans.append((m.start(), m.end()))
        if _YOE_SOFT.search(ctx): continue
        try: v = int(m.group(1))          # lower bound
        except Exception: continue
        if 0 <= v <= 20 and (best is None or v > best): best = v
    for m in _YOE.finditer(jd):
        if any(s0 <= m.start() < e0 for s0, e0 in spans): continue
        ctx = jd[max(0, m.start() - 120): m.end() + 120]
        if _YOE_SOFT.search(ctx): continue
        try: v = int(m.group(1))
        except Exception: continue
        if 0 < v <= 20 and (best is None or v > best): best = v
    return best


def drop_reason(r: dict, lo, hi) -> str:
    co = (r['company'] or '').strip()
    col = co.lower()
    jd = r['full_jd'] or ''
    title = r['title'] or ''
    if _on("X5_agency", True) and col in _BLOCKED:
        return f'X5 {_DL["X5"]}'
    if _on("X5_agency", True) and _AGENCY_NAME.search(co):
        return f'X5 {_DL["X5"]}'
    if _on("X5_agency", True) and _GIG_TITLE.search(title):
        return f'X5 {_DL["X5"]}'
    if _on("X5_agency", True) and _AGENCY_TITLE.search(title):
        return f'X5 {_DL["X5"]}'
    if _on("X6_intern", True) and _INTERN.search(title):
        return f'X6 {_DL["X6"]}'
    if _on("X7_senior", True) and _SENIOR.search(title):
        return f'X7 {_DL["X7"]}'
    if _on("X9_non_us", True) and _NON_US.search(r['location'] or ''):
        return f'X9 {_DL["X9"]}'
    if _on("X8_no_sponsor", True) == "drop" and _NO_SPONSOR.search(jd):
        return f'X8 {_DL["X8"]}'
    if _on("X10_itar", True) and _ITAR_HARD.search(jd):
        return f'X10 {_DL["X10"]}'
    if _on("X2_clearance", True) and _CLEARANCE.search(jd):
        return f'X2 {_DL["X2"]}'
    y = max_yoe(jd)
    if _on("X3_yoe", True) and y is not None and y > _DROPS.get("max_yoe", 2):
        return "X3 " + _DL["X3"].format(n=y)
    if _on("X4_comp", True) and hi is not None and hi < _COMP_FLOOR:
        return "X4 " + _DL["X4"].format(k=hi // 1000)
    return ''


_E_NAME = {k: v["name"] for k, v in PROFILE["campus"].items()}


def bucket_campus(title: str, jd: str, lo, hi) -> str:
    """How confident are we that this req is actually open to a new grad?"""
    t = (title or '').strip()
    jd = jd or ''
    # E1 - the posting says so outright.
    if _E1_TITLE.search(t):
        return 'E1'
    if len(_E1_JD.findall(jd)) >= 1:
        return 'E1'
    # E3 - reads like it wants someone with a track record.
    neg = 0
    y = max_yoe(jd)
    if y is not None and y >= 2: neg += 2
    if _SENIORITY_TONE.search(jd): neg += 3
    if lo is not None and lo >= 180_000: neg += 1
    # A req that never mentions a degree is usually hiring on experience.
    if not _DEGREE.search(jd): neg += 1
    if len(jd) >= 400 and neg >= 3:
        return 'E3'
    # E2 - never says, but reads like it: names a degree, lists a broad
    # stack, pays in the new-grad range.
    return 'E2'


def row_flags(r: dict, lo, hi) -> str:
    """Signals too weak to drop on, worth a human's attention."""
    f = []
    if _AGENCY_SOFT.search(r["company"] or ""): f.append(_FL["agency"])
    if _PHD.search(r["title"] or ""): f.append(_FL["phd"])
    if len(r["full_jd"] or "") < 400: f.append(_FL["thin_jd"])
    y = max_yoe(r['full_jd'] or '')
    if y is not None and y == _DROPS.get("max_yoe", 2): f.append(_FL["at_yoe_limit"])
    if hi is not None and hi >= _COMP_HIGH_FLOOR: f.append(_FL["high_floor"])
    if _ITAR_SOFT.search(r["full_jd"] or ""): f.append(_FL["itar"])
    # X8 set to `flag` keeps the posting and marks it instead — see the
    # profile, and rulebook §1.2 for why that is usually the right setting.
    if _on("X8_no_sponsor", True) == "flag" and _NO_SPONSOR.search(r["full_jd"] or ""):
        f.append(_FL["no_sponsor"])
    return '|'.join(f)




# ============================================================ PUBLIC API

BUCKET_NAMES = {
    'region': _REGION_NAME, 'tier': _TIER_NAME, 'role': _ROLE_NAME,
    'campus': _E_NAME, 'comp': _COMP_NAME,
}
DROP_CODES = {k: v.split('{')[0].rstrip('${ ') or v for k, v in _DL.items()}


def classify(row: dict) -> dict:
    """Classify one posting.

    `row` needs company / title / location / full_jd. Returns the bucket_*,
    comp_min/max, flags and drop_reason values for a jobs.csv row. An empty
    `drop_reason` means the posting survives.
    """
    lo, hi, _non_usd = parse_comp(row.get('full_jd') or '')
    region, _ = bucket_region(row.get('location') or '')
    tier = bucket_tier(row.get('company') or '')
    comp, _ = bucket_comp(lo, hi)
    role = bucket_role(row.get('title') or '', row.get('full_jd') or '', tier)
    campus = bucket_campus(row.get('title') or '', row.get('full_jd') or '', lo, hi)
    safe = {'company': row.get('company') or '', 'title': row.get('title') or '',
            'location': row.get('location') or '', 'full_jd': row.get('full_jd') or ''}
    return {
        'bucket_region': region, 'bucket_tier': tier, 'bucket_comp': comp,
        'bucket_role': role, 'bucket_campus': campus,
        'comp_min': str(lo) if lo else '', 'comp_max': str(hi) if hi else '',
        'flags': row_flags(safe, lo, hi),
        'drop_reason': drop_reason(safe, lo, hi),
    }
