"""Schema for `jobs.csv` — the project's source of truth.

Three roles write here, so the schema is the contract between them:

  /scrape (scrape-and-ingest)  appends new rows, fills the bucket_* columns
  /batch  (fill assistant)     sets status / applied_date / drop_reason / feedback
  the user                     edits anything, via scripts/update_row.py

Never hand-edit jobs.csv. Use `scripts/update_row.py`.

Schema history
  2026-09-10  dropped fit_score / fit_summary / what_could_help (935 rows, all
              empty — five-dimension bucketing replaced them). Added the five
              bucket_* columns plus low_fit and drop_reason.
"""

from __future__ import annotations

import re
from typing import List

CSV_FIELDS: List[str] = [
    # --- identity & provenance -------------------------------------------
    "id",                # sha1(li:<jid>)[:16]
    "date_found",        # ISO date this row entered the ledger
    "date_posted",       # ISO date LinkedIn reports
    "source",            # "linkedin"
    # --- the posting -----------------------------------------------------
    "company",
    "title",
    "location",
    "job_link",          # LinkedIn canonical URL
    "external_url",      # company ATS URL (Apply-on-company), when known
    "full_jd",           # cleaned JD text
    # --- derived buckets (written at ingest, see scripts/classify.py) ----
    "bucket_region",     # A1..A4  — labels in config/profile.yaml
    "bucket_tier",       # T0..T5  — how highly the employer rates
    "bucket_comp",       # C0..C3  — band of the posted ceiling
    "bucket_role",       # D1..D8  — direction of the work
    "bucket_campus",     # E1..E3  — confidence it is open to a new grad
    "comp_min",
    "comp_max",
    "flags",             # pipe-joined; weak signals worth a human look
    # --- judgement & outcome ---------------------------------------------
    "low_fit",           # "Y" = poor fit, but not wrong enough to drop
    "drop_reason",       # why this row is out: X-code (auto) or free text (manual)
    "applied_date",
    "feedback",          # user's own notes on this posting
    "interview_received",
    "status",
]

# --- status vocabulary ----------------------------------------------------
# A row is "live" only while status == open and low_fit is empty; that is
# exactly what data/board.json is built from.
STATUS_OPEN      = "open"        # untouched — the only state on the board
STATUS_APPLIED   = "applied"     # submitted; applied_date must be set
STATUS_REACHOUT  = "reachout"    # referral asked for / waiting on a reply
STATUS_DROPPED   = "dropped"     # rejected; drop_reason must be set
STATUS_CLOSED    = "closed"      # posting is gone / link is dead
STATUS_DUPLICATE = "duplicate"   # another record of the same posting

STATUSES = {
    STATUS_OPEN: "open",
    STATUS_APPLIED: "applied",
    STATUS_REACHOUT: "awaiting reply",
    STATUS_DROPPED: "dropped",
    STATUS_CLOSED: "closed",
    STATUS_DUPLICATE: "duplicate",
}
# Statuses the board must never surface again.
TERMINAL_STATUSES = {STATUS_APPLIED, STATUS_REACHOUT, STATUS_DROPPED,
                     STATUS_CLOSED, STATUS_DUPLICATE}


def blank_row() -> dict:
    return {f: "" for f in CSV_FIELDS}


# --- dedup key ------------------------------------------------------------
_TITLE_NOISE = re.compile(
    r'\b(20\d\d|new grad|university graduate|early career|entry level|'
    r'full time|remote|onsite|hybrid|us|usa)\b', re.I)


def norm_key(company: str, title: str) -> tuple[str, str]:
    """Dedup key. LinkedIn reposts the same job under new jids, so the URL
    alone is not enough — normalised (company, title) catches the reposts."""
    c = re.sub(r'[^a-z0-9]+', '', (company or '').lower())
    t = re.sub(r'\(.*?\)|\[.*?\]', ' ', (title or '').lower())
    t = _TITLE_NOISE.sub(' ', t)
    t = re.sub(r'[^a-z0-9]+', ' ', t).strip()
    return (c, re.sub(r'\s+', ' ', t))
