---
name: lc-interview
description: Run a LeetCode mock interview in the user's Interview Hub, selecting a specified LC problem number or a fresh problem, and archive feedback plus overall progress on wrap-up. Also supports resuming and ending these interviews.
---

# LC interview

## Workspace and defaults

Use `<INTERVIEW_HUB>` as the personal hub unless the user explicitly selects another hub. Read its AGENTS.md, hub.json, modes/lc/MODE.md, modes/lc/PROGRESS.md, and docs/evaluation.md. These files provide the maintained interview rules and rubric; do not duplicate or silently reset them. If the hub is unavailable, ask for its location rather than creating an unrelated workspace.

Default to English interview, Python, Medium, 45 minutes, Chinese written debrief. The user's overrides take precedence. A request to configure this skill or inspect progress does not start an interview.

## Invocation and problem selection

- `$lc-interview 239`, `$lc-interview LC 239`, or a named LeetCode URL: prepare that exact problem. Treat a standalone number after the invocation as a problem number; a labeled duration such as “30 minutes” is not a problem number.
- `$lc-interview` without a problem number: select one fresh, self-contained problem at the configured difficulty. Consult modes/lc/PROGRESS.md and modes/lc/sessions/ history to avoid already attempted problems or near-identical variants; a renamed equivalent is not fresh. Synthetic problems are allowed and must be labeled synthetic, without invented LC IDs.
- An explicit resume request continues the relevant unfinished session, with no new problem or overwritten files. Otherwise an invocation means a new attempt. If a session is actively underway and intent is ambiguous, ask whether to resume it or start another.
- For a specific LC number, retrieve and verify the official LeetCode problem identity, statement, constraints, examples, and Python entry point. Use the official problem page; do not read solution/editorial/discussion pages. Paraphrase the statement accurately and link the verified source. If access is blocked or premium-only, request the statement from the user; never substitute or invent a numbered problem. Record source and access date.
- Match the numbered problem's official signature (including a Solution class if applicable). Do not force the generic standalone signature on a specific LC problem.
- For automatic selection, use observed weaknesses to choose useful practice without announcing algorithm tags. Respect an explicitly requested repeat. Record topic tags only after the attempt ends to avoid spoilers.

All attempt paths are relative to the hub root. The LC data directory is `<INTERVIEW_HUB>/modes/lc`; do not use `~/lc` or root-level sessions/ for LC artifacts.

## Conduct and artifacts

Create one unique modes/lc/sessions/<date-time>-lc[-<problem-number>]/ folder per attempt. Include problem.md, solution.py, test_solution.py, and session.md; initialize from hub templates where applicable. Always put the English problem statement, examples, constraints, and verified source link when applicable in a top-level Python docstring in solution.py, for both specified LC problems and automatically selected problems. Keep that content consistent with problem.md and free of solution hints or algorithm tags. Below the docstring, keep starter code empty apart from imports/signature/pass. Preserve existing work. Honor a user-selected working file and archive its saved final snapshot into the attempt folder at wrap-up.

Confirm readiness before starting the interview clock. Keep one concise question per turn, avoid routine progress narration during the interview, allow silence, and use neutral acknowledgments. Do not write candidate code or supply algorithmic hints unless requested. Standard correctness questions and directed debugging probes must be distinguished from independent performance in feedback. Read saved files at checkpoints; use screenshots only when requested or unsaved visible state is relevant and supported. Do not execute candidate code during the interview without a request.

## Wrap-up and overall progress

An explicit wrap-up ends the interview; ending a voice call alone does not. Archive final code, mark session completed, and write a concise Chinese feedback.md using the hub rubric. Respect a request to skip running tests and report verification limits. Unreliable active timing must not be scored as speed.

Update modes/lc/PROGRESS.md in the same wrap-up:

1. Upsert one row per unique session folder, linking its feedback. Store date, verified LC number or synthetic label, title, mode, completion, execution status, and a brief takeaway. Never duplicate a row when wrap-up is repeated. Reattempts get separate rows.
2. Refresh total completed attempts and unique problem count, distinguishing repetitions and setup-only sessions.
3. Summarize broad ability and six rubric dimensions from completed feedback, separating independent work, prompted corrections, and verified code. Base the current assessment mainly on the latest five completed attempts per mode; identify the sample count and avoid treating one problem as a reliable global level.
4. Note strengths, recurring gaps, and up to three next practice priorities. Do not imply unpracticed modes have been assessed. Do not map practice scores to hiring probabilities.

Keep modes/lc/PROGRESS.md a concise readable index, with per-attempt details remaining in session folders. Update the index when a new attempt is prepared as ready, then replace that state on completion; do not count ready/active attempts as completed.
