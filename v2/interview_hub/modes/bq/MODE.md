# Behavioral and situational interview

Status: ready.

## Scope and prerequisites

Behavioral experiences and nontechnical business scenarios. No programming required.
Target defaults: general nontechnical role; level unspecified, no seniority assumptions.
A source profile may hold user-provided candidate recollections; label them as such, never as verified company questions.
The general company-composition mode remains planned.
Read hub.json, this file, PROGRESS.md, and the selected round.json before starting or resuming.

## Round settings

Default duration: 30 minutes; six main questions, normally one follow-up each; no self-introduction.
Prepare up to 30 seconds and aim for two minutes per answer; follow-up preparation is optional.
These are practice settings inspired by the PDF, not official timing guarantees.
Language follows hub defaults unless overridden in the round; this prepared round uses Chinese.
Use an external countdown; record actual timezone-aware start, pause/resume and end timestamps.
Remain ready until readiness is confirmed and the first question is presented. Ask one question at a time.
Respect silence. Give requested hints only and log their level; no unsolicited answer coaching.
At the time limit noticed during interaction, wrap up rather than silently extending.

## Question and evidence handling

Use sources/<profile>/questions.json. Read previous attempts before fresh selection; avoid repeats and equivalent questions unless requested.
A round specifies the main question order. Do not announce future questions in chat.
Choose a source follow-up only when it fits the answer; otherwise ask an original neutral evidence probe and label provenance in the log.
Do not assume the source follow-up's scenario occurred in the candidate's experience.
Do not prewrite future hints or reference answers in session files. Reference answers are only eligible for post-interview discussion.
Record candidate statements faithfully in answer.md, distinguishing quotation from summary. Do not invent experience, results or metrics.

## Artifacts and lifecycle

rounds/<id>/round.json links six separate attempt folders under sessions/; round session.md tracks overall timing and stage.
Each attempt has problem.md, answer.md, session.md and solution.py (noncoding placeholder only).
On presentation mark the attempt active; after answering mark answered pending round debrief. Never score mid-round.
On pause record both round and current attempt state; on end stop questioning and write feedback.md for each prepared attempt and the round, marking unreached questions unattempted and N/O.
Use templates/session.md and templates/feedback.md. Preserve existing attempts; never overwrite candidate text.
Upsert PROGRESS.md by attempt path and refresh completed counts and provisional assessment. Ready or unattempted entries are not completed attempts.

## Evaluation

Follow docs/evaluation.md's six 1–4 scores with evidence and N/O for unobserved dimensions.
Retain its six labels: requirements clarification = understanding the prompt/constraints; algorithm and correctness = reasoning and action rationale; implementation = N/O unless actual code was observed; complexity = resource/tradeoff analysis only if observed; testing and edge cases = verification and contingency evidence; communication = clarity, personal contribution and consistency.
Explain these BQ interpretations in feedback. Do not force coding criteria or aggregate a hiring score.
Separate independent answers from improvement after assistance. Candidate claims are self-reported, not externally verified.
No code execution is needed for oral answers. Unknown active duration means no speed assessment.
Chinese debrief: concise evidence, assistance, validation limitations, strengths and at most three next steps.
