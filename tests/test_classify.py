"""Tests for the classifier.

`scripts/classify.py` is the one place where a quiet regex change silently
reshapes the whole board, so it is the one place worth testing. These run
against the profile that is actually checked in — if you retune the profile
and a test fails, the test is telling you the retune had a wider blast radius
than you meant.

    python3 -m pytest tests/ -q          (or: python3 tests/test_classify.py)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.classify import (bucket_campus, bucket_comp, bucket_region,  # noqa: E402
                              bucket_role, bucket_tier, classify, max_yoe,
                              parse_comp)
from scripts.models import norm_key  # noqa: E402

LONG = "x" * 600  # long enough that the "thin JD" flag doesn't fire


def _job(**kw) -> dict:
    return {"company": "Acme", "title": "Software Engineer",
            "location": "New York, NY", "full_jd": LONG, **kw}


# ---------------------------------------------------------------- regions
def test_region_buckets():
    assert bucket_region("San Jose, CA")[0] == "A1"
    assert bucket_region("Seattle, WA")[0] == "A1"
    assert bucket_region("Boston, MA")[0] == "A2"
    assert bucket_region("Chicago, IL")[0] == "A2"
    assert bucket_region("Austin, TX")[0] == "A3"
    # No city named at all -> nationwide/remote, not "other"
    assert bucket_region("United States")[0] == "A4"
    assert bucket_region("")[0] == "A4"


# ------------------------------------------------------------------ comp
def test_comp_band_edges_are_inclusive():
    assert bucket_comp(None, None)[0] == "C0"
    assert bucket_comp(None, 99_999)[0] == "C1"
    assert bucket_comp(None, 100_000)[0] == "C2"
    assert bucket_comp(None, 200_000)[0] == "C2"   # inclusive top
    assert bucket_comp(None, 200_001)[0] == "C3"


def test_parse_comp_forms():
    assert parse_comp("Compensation Range: $148K - $236K")[:2] == (148_000, 236_000)
    assert parse_comp("$120,000 - $180,000 per year")[:2] == (120_000, 180_000)
    # Hourly rates annualise
    lo, hi, _ = parse_comp("$50.00/hr - $60.00/hr")
    assert hi == 60 * 2080
    # Signing bonuses and equity are not salaries
    assert parse_comp("A $5,000 signing bonus")[1] is None


# ------------------------------------------------------------------- yoe
def test_yoe_range_resolves_to_lower_bound():
    """A req spanning 0-3 years is open to a new grad; reading the ceiling
    would drop it."""
    assert max_yoe("We want 0-3 years of experience") == 0
    assert max_yoe("1–3 years of software engineering experience") == 1
    assert max_yoe("3+ years of relevant experience") == 3


def test_yoe_ignores_preferred_context():
    assert max_yoe("5 years of experience preferred") is None


# ------------------------------------------------------------------ drop
def test_drops():
    def why(**kw):
        return classify(_job(**kw))["drop_reason"].split()[0] if \
            classify(_job(**kw))["drop_reason"] else ""

    assert why(title="Senior Software Engineer").startswith("X7")
    assert why(title="Software Engineer Intern").startswith("X6")
    assert why(company="Infosys").startswith("X5")
    assert why(location="Toronto, Canada").startswith("X9")
    assert why(full_jd=LONG + " Requires an active TS/SCI clearance.").startswith("X2")
    assert why(full_jd=LONG + " Requires 5 years of experience.").startswith("X3")
    assert why(full_jd=LONG + " Compensation Range: $60K - $80K").startswith("X4")
    # X8 is not here on purpose: it defaults to `flag`, not `drop` — see
    # test_no_sponsor_is_a_flag_by_default.


def test_no_sponsor_is_a_flag_by_default():
    """rulebook §1.2: "will not sponsor" is often boilerplate and sometimes
    negotiable, so the posting survives carrying a mark and the user weighs it.
    The classifier dropped these for a while after the rulebook said not to,
    which is what this test exists to stop happening again."""
    r = classify(_job(full_jd=LONG + " We do not offer visa sponsorship."))
    assert r["drop_reason"] == ""
    assert "sponsor" in r["flags"]


def test_itar_hard_vs_boilerplate():
    """A real US-person requirement drops; the conditional boilerplate that
    half of tech puts in every JD only earns a flag."""
    hard = classify(_job(full_jd=LONG + " To conform to U.S. export control "
                                        "regulations, you must be a U.S. person."))
    assert hard["drop_reason"].startswith("X10")

    soft = classify(_job(full_jd=LONG + " Export Control Regulations: for "
                                        "positions requiring access to controlled "
                                        "technology, additional checks apply."))
    assert soft["drop_reason"] == ""
    assert "ITAR" in soft["flags"] or soft["flags"] == ""


def test_survivor_has_no_drop_reason():
    r = classify(_job(title="Software Engineer, New Grad",
                      full_jd="Bachelor's degree required. " + LONG))
    assert r["drop_reason"] == ""
    assert r["bucket_tier"] and r["bucket_role"] and r["bucket_campus"]


# ----------------------------------------------------------------- roles
def test_hardware_beats_ml_keywords():
    """'GPU Verification Engineer' is silicon work, not ML infrastructure."""
    assert bucket_role("GPU Verification Engineer", "", "T1") == "D8"
    assert bucket_role("ASIC Physical Design Engineer", "", "T1") == "D8"


def test_role_buckets():
    assert bucket_role("Software Engineer, CUDA Deep Learning Systems", "", "T1") == "D6"
    assert bucket_role("Machine Learning Engineer, RecSys", "", "T1") == "D7"
    assert bucket_role("Applied AI Engineer", "", "T1") == "D5"
    assert bucket_role("Machine Learning Engineer", "", "T2") == "D3"
    # Amazon's standard title must not fall through to "other"
    assert bucket_role("Software Development Engineer", "", "T1") == "D1"
    assert bucket_role("Backend Engineer", "", "T5") == "D2"


# ---------------------------------------------------------------- campus
def test_campus_confidence():
    assert bucket_campus("Software Engineer, New Grad", LONG, None, None) == "E1"
    assert bucket_campus("Software Engineer I", LONG, None, None) == "E1"
    assert bucket_campus("Software Engineer", "Bachelor's degree required. " + LONG,
                         None, None) == "E2"
    senior = ("You have a proven track record of shipping. You will mentor "
              "junior engineers. " + LONG)
    assert bucket_campus("Software Engineer", senior, None, None) == "E3"


# ----------------------------------------------------------------- dedup
def test_norm_key_catches_reposts():
    """The same req reposted with different decoration must collide."""
    a = norm_key("Stripe", "Software Engineer, New Grad (2027)")
    b = norm_key("Stripe", "Software Engineer [Remote] - 2027")
    assert a == b
    assert norm_key("Stripe", "Software Engineer") != norm_key("Stripe", "Data Scientist")


if __name__ == "__main__":
    fns = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"  ok    {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {name}  {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
