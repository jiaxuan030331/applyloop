# LC mode

Status: ready.

## Format

Default: one unfamiliar Medium-level algorithm problem plus a follow-up, 45 minutes, English, Python. Treat difficulty as an estimate, not an official LeetCode rating for synthetic problems. Prefer a self-contained synthetic problem or a accurately attributed known problem; never claim LeetCode provenance without verification. Do not browse solutions during the interview.

Suggested pacing (adapt naturally):
- 0–5 minutes: statement and candidate clarification.
- 5–15 minutes: proposed approach, examples, correctness, complexity.
- 15–35 minutes: candidate implementation, dry runs, tests, debugging.
- 35–45 minutes: follow-up, tradeoffs, final complexity discussion.

If the candidate has already solved the problem, replace it without penalty and restart the problem timer. Do not reveal category or technique in the title. Include unambiguous constraints and examples; internally check that the problem is solvable and examples agree with the intended requirements before presenting it.

## Artifacts

- problem.md: statement, input/output, constraints, examples, function signature.
- solution.py: top-level English problem docstring containing the statement, examples, constraints, and verified source link when applicable, followed by the candidate-owned Python starter. Always include this for both specified LC numbers and automatically selected problems. Keep its statement consistent with problem.md; do not include solutions or algorithm tags.
- test_solution.py: candidate-owned standard-library unittest tests; runnable via `python3 -m unittest discover -s <session-directory> -p 'test_*.py'` from the hub root when Python is available.
- session.md: settings, lifecycle, timestamps, observable checkpoints, hints.
- feedback.md: written only after the interview ends.

Use a standalone Python function unless a class is relevant to the problem. Avoid unnecessary dependency setup. Confirm Python availability before claiming runnable tests.

## Evaluation

Use six dimensions, each scored 1–4 or N/O (not observed): requirement clarification, algorithm/correctness reasoning, implementation, complexity analysis, tests/edge cases, communication. Anchors: 1 = major gaps; 2 = partial with substantial help; 3 = mostly independent and correct with minor gaps; 4 = independent, correct, clearly justified, and robust. Support each score with evidence, and separately report hint levels. Do not penalize accent; evaluate clarity of reasoning.

Follow-ups should extend constraints or explore time/space tradeoffs. Select them based on what the candidate completed; do not force a second problem into remaining minutes.

## Storage

LC attempts live in modes/lc/sessions/<date-time>-lc[-<problem-number>]/ relative to the hub root. LC progress lives in modes/lc/PROGRESS.md. Use session-local solution.py for new attempts.
