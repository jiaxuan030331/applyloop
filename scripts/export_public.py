"""Export the shareable framework into a clean directory.

This repo holds two things that must never be mixed: a framework, and one
person's job hunt. The second includes transcripts, a home address, EEO
answers, tailored resumes, and a record of every application. So the public
version is built by **whitelist**, into a fresh directory with its own git
history — not by deleting files from a copy of this one.

That asymmetry is deliberate. A blacklist fails open: forget one path and it
ships. And scrubbing history after the fact does not work — once a commit is
pushed it can be forked, cached by the host, and indexed, and a rewrite fixes
none of that.

    python3 scripts/export_public.py --out ../applyloop-public
    python3 scripts/export_public.py --out ../applyloop-public --force

Then:

    cd ../applyloop-public && git init && git add -A && git commit
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

# Whitelist. Directories copy recursively, minus EXCLUDE_SUFFIXES.
INCLUDE_FILES = [
    "README.md",
    "SETUP.md",
    "DESIGN.md",
    "LICENSE",
    "CLAUDE.md",
    "platform_notes.md",
    "requirements.txt",
    "config/sources.yaml",
    "config/sources.disabled.yaml",
    "config/companies.yaml",
]
INCLUDE_DIRS = [
    "scripts",
    "agents",
    "tests",
    "template",
    ".claude/skills",
]
EXCLUDE_SUFFIXES = {".pyc", ".docx", ".pdf", ".csv", ".jsonl"}
EXCLUDE_DIR_NAMES = {"__pycache__", ".git"}

# Files that must be present in template/ but absent from the export root:
# shipping a filled-in copy of any of these is the failure mode this whole
# script exists to prevent.
PERSONAL_BASENAMES = {
    "experiences.md", "application_answers.md", "rulebook.md",
    "claimable_skills.md", "profile.yaml", "jobs.csv", "board.json",
    "plan.txt", "claimable_terms.json",
}

# Phone numbers, loosely: parenthesised area code, dashes, dots, or a leading
# +1. The first version matched only the dashed form and went blind the day
# the identity block was reformatted to put the area code in parentheses —
# hence the deliberate looseness, and hence no example written out here.
_PHONE = r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"

# Anything matching these in exported content is a leak. Tuned to catch the
# shapes of personal data, not specific values, so it keeps working after the
# templates change.
LEAK_PATTERNS = [
    (re.compile(_PHONE), "phone number"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@(?!example\.)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
     "email address"),
    (re.compile(r"\b\d{1,5}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\s+"
                r"(?:St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Blvd|Ln|Lane|Ct|Way)\b"),
     "street address"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "SSN-shaped number"),
]
# Paths where a match is expected and fine. Keep this list as short as you
# can stand: every entry is a place the scanner stops looking.
#   LICENSE          — the copyright line names you on purpose
#   template/        — placeholder examples, not real values
#   scripts/legacy/  — archived, not on any live path
LEAK_ALLOW = re.compile(r"^(LICENSE$|template/|scripts/legacy/)")


def owner_tokens() -> list[str]:
    """Pull the owner's real identity out of the private repo, so the scan
    checks for *their* data rather than guessing at patterns.

    Regexes catch data shaped like a phone number. They do not catch a
    surname sitting in a filename, which is exactly how the first version of
    this script leaked three files.
    """
    src = _ROOT / "experiences.md"
    if not src.exists():
        return []
    text = src.read_text(encoding="utf-8", errors="replace")
    tokens: set[str] = set()
    for rx in (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
               _PHONE,
               r"github\.com/[A-Za-z0-9_-]+"):
        tokens.update(re.findall(rx, text))
    # Name: the identity bullet's capitalised words, plus the local part of
    # the email (people name files after both).
    m = re.search(r"^-\s+([A-Z][a-z]+(?: [A-Z][a-z]+)+)", text, re.M)
    if m:
        tokens.update(w for w in m.group(1).split() if len(w) > 2)
    for t in list(tokens):
        if "@" in t:
            tokens.add(t.split("@")[0])
    found = sorted(t for t in tokens if len(t) > 3)
    # A scanner that silently finds nothing is worse than no scanner: if the
    # identity block is reformatted and the patterns stop matching, that must
    # surface as a failure, not as a clean report.
    if not any("@" in t for t in found):
        found.append("!! could not find an email in experiences.md — "
                     "the identity scan may be blind")
    return found


def walk(d: Path):
    for p in sorted(d.rglob("*")):
        if any(part in EXCLUDE_DIR_NAMES for part in p.parts):
            continue
        if p.is_file() and p.suffix not in EXCLUDE_SUFFIXES:
            yield p


# What a forked user fills in. If the exported .gitignore does not cover
# these, `git add -A` in their clone publishes their home address.
MUST_BE_IGNORED = [
    "config/profile.yaml", "experiences.md", "application_answers.md",
    "rulebook.md", "claimable_skills.md", "jobs.csv", "data/board.json",
    "application_records/x", "resumes/x",
]


def check_gitignore(out: Path) -> list[str]:
    """A fork's own personal files must be unstageable by default.

    `git check-ignore` needs a repository, and the export is not one yet, so
    this borrows a throwaway git dir rather than initialising one inside the
    export (which would then ship a .git).
    """
    if not (out / ".gitignore").exists():
        return ["no .gitignore in the export"]
    with tempfile.TemporaryDirectory() as gitdir:
        subprocess.run(["git", "init", "-q", "--bare", gitdir],
                       capture_output=True, check=False)
        r = subprocess.run(
            ["git", f"--git-dir={gitdir}", f"--work-tree={out}",
             "check-ignore", "--no-index", "--stdin"],
            cwd=out, input="\n".join(MUST_BE_IGNORED),
            capture_output=True, text=True)
    if r.returncode not in (0, 1):
        return [f"could not verify .gitignore: {r.stderr.strip()[:120]}"]
    covered = set(r.stdout.split())
    return [f".gitignore does not cover {p} — a fork would commit it"
            for p in MUST_BE_IGNORED if p not in covered]


def scan_for_leaks(out: Path) -> list[str]:
    problems = check_gitignore(out)
    owner = owner_tokens()
    if not owner:
        problems.append("(could not read experiences.md — identity scan skipped)")
    for p in walk(out):
        rel = p.relative_to(out).as_posix()
        if p.name in PERSONAL_BASENAMES and not rel.startswith("template/"):
            problems.append(f"{rel}: personal file outside template/")
        if LEAK_ALLOW.match(rel):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for rx, what in LEAK_PATTERNS:
            m = rx.search(text)
            if m:
                line = text[:m.start()].count("\n") + 1
                problems.append(f"{rel}:{line}: possible {what} — {m.group()[:40]!r}")
        for tok in owner:
            i = text.find(tok)
            if i >= 0:
                line = text[:i].count("\n") + 1
                problems.append(f"{rel}:{line}: owner identity {tok!r}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="destination directory")
    ap.add_argument("--force", action="store_true", help="overwrite if it exists")
    args = ap.parse_args()

    out = Path(args.out).expanduser().resolve()
    if out.exists():
        if not args.force:
            print(f"{out} exists — pass --force to overwrite")
            return 1
        if (out / ".git").exists():
            print(f"{out} has a .git directory; refusing to overwrite it.\n"
                  f"Delete it yourself if that is really what you want.")
            return 1
        shutil.rmtree(out)
    out.mkdir(parents=True)

    n = 0
    for rel in INCLUDE_FILES:
        src = _ROOT / rel
        if not src.exists():
            print(f"  [warn] missing: {rel}")
            continue
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        n += 1
    for rel in INCLUDE_DIRS:
        src = _ROOT / rel
        if not src.exists():
            print(f"  [warn] missing dir: {rel}")
            continue
        for p in walk(src):
            dst = out / p.relative_to(_ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
            n += 1

    # The public .gitignore is a different file from this repo's: here the
    # personal files are tracked on purpose, there they must never be. See
    # template/gitignore.
    shutil.copy2(_ROOT / "template" / "gitignore", out / ".gitignore")
    n += 1

    # Directories the pipeline writes into; ship them empty so a fresh clone
    # runs without mkdir errors.
    for d in ("data/pending", "data/daily_reports", "application_records", "resumes"):
        (out / d).mkdir(parents=True, exist_ok=True)
        (out / d / ".gitkeep").touch()

    print(f"exported {n} files -> {out}")

    problems = scan_for_leaks(out)
    if problems:
        print(f"\n!! {len(problems)} possible leak(s) — DO NOT PUBLISH until these "
              f"are explained:\n")
        for p in problems:
            print(f"   {p}")
        return 2

    print("\nleak scan clean.\n"
          f"  cd {out} && git init && git add -A && git commit\n"
          "Read the diff before the first push. This script is a safety net, "
          "not a guarantee.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
