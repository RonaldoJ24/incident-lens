# Phase 5 exploratory pilot protocol

**Status: UNRUN.** This is an executable planning artifact only. No
participants have been contacted, recruited, or measured. The protocol must
not be treated as evidence until a separately dated results record is filled
in.

## Purpose and limits

Run a small usability and investigation pilot with **3–5 willing engineers**
using the authored local fixtures. Each participant completes two matched
investigation tasks. The pilot describes task completion, correctness against a
reviewed answer key, and structured feedback; it does not test a live
connector, provider quality, production reliability, or business impact. The
connector status remains `blocked` unless the owned-app access gate is
separately satisfied.

The facilitator must record the app build, fixture revision, and protocol
version before the first session. Use a fresh guest session and the same
authored fixture set for every participant. Do not substitute customer logs,
credentials, or a live endpoint.

## Participants, consent, and privacy

- The target is 3–5 engineers who volunteer after explicit authorization to
  conduct the pilot. Stop at five; do not add participants to make a result
  look balanced. No outreach or recruitment is part of this repository task.
- Before the session, explain the two tasks, timing, data collected, voluntary
  withdrawal, and the exploratory-only interpretation. Obtain affirmative
  consent before starting. A participant may stop at any time without giving a
  reason; delete that participant's raw notes on request.
- Assign `P01` through `P05`; keep names, contact details, and employment
  information out of the results file. Do not record audio, video, screen
  captures, customer data, secrets, or free-form personal information.
- Use only the authored/synthetic fixtures. Store the coded timing and answer
  sheet in an access-controlled local location, redact accidental sensitive
  text, and delete raw notes within 30 days. Keep only the coded results table
  and aggregate descriptive summary if consent permits.
- Quote feedback only with separate, explicit permission. Otherwise paraphrase
  it without identifying details.

## Matched tasks and declared order

Use the same instructions and interaction surface for both tasks:

1. Select the assigned authored case and its displayed time window.
2. Run the bounded read-only check.
3. Inspect the finding, evidence drawer, and execution timeline.
4. State the suspected service, the supported conclusion or uncertainty, and
   at least one evidence item that supports the statement.

Task A is the authored **checkout failure** case. Task B is the authored
**degraded performance** case. The facilitator keeps a reviewed answer key
with the expected service, conclusion category, evidence identifiers, and
uncertainty boundary; do not show it before the participant submits an answer.
The two packets should be comparable in instructions, available evidence, and
maximum time, even though their conclusions differ.

Declare the participant count `N` and order table before the first session.
Assign rows in order and do not reorder them after data collection starts:

| Participant | Order | Count if N=3 | Count if N=4 | Count if N=5 |
| --- | --- | ---: | ---: | ---: |
| P01 | A then B | A→B | A→B | A→B |
| P02 | B then A | B→A | B→A | B→A |
| P03 | A then B | A→B | A→B | A→B |
| P04 | B then A | — | B→A | B→A |
| P05 | A then B | — | — | A→B |

This is counterbalanced by a declared alternating order. With three or five
participants the two orders differ by one participant; that imbalance is
reported, not corrected after the fact.

## Procedure and exact measures

1. Record the protocol version, app build, fixture revision, participant code,
   consent, and assigned order. Create a fresh guest session.
2. Give a two-minute unscored orientation covering only navigation and the
   meaning of the submit signal. Do not explain the answer or coach diagnosis.
3. Read the task prompt, then start a monotonic timer immediately after the
   prompt is complete. Stop when the participant says “done” after stating all
   required answer fields, or at **900 seconds**, whichever comes first.
4. Reset the guest session and clear the screen between tasks. Apply the same
   prompt, timer, and no-coaching rule to the second task. Allow a two-minute
   break between tasks if requested; exclude that break from task time.
5. Record help requests, cancellation, abandonment, timeout, and any protocol
   deviation. A facilitator may clarify the procedure but may not suggest a
   service, cause, evidence item, or certainty level.

Definitions:

- `task_time_s` is monotonic seconds from the end of the task prompt to the
  final answer signal. A timeout is recorded as `900` with `timed_out=true`;
  it is not treated as a completed answer.
- `correct=1` only when the answer matches all required fields in the reviewed
  key: service, conclusion category, at least one supporting evidence ID, and
  the key's uncertainty boundary. Otherwise `correct=0`. A timeout or
  abandonment is `correct=0`.
- Record `evidence_supported=1` when the cited item is actually present and
  supports the stated conclusion; otherwise `0`. Record `help_requested` and
  `protocol_deviation` separately rather than adjusting time or correctness.
- After each task, collect the structured feedback below. Do not average
  feedback into a success claim.

## Structured feedback

Immediately after each task, ask for a 1–5 rating (1 = strongly disagree,
5 = strongly agree):

1. I understood what the task required.
2. I could find the evidence needed for my answer.
3. The timeline made the system's actual work understandable.
4. I could distinguish a fresh analysis from a stored replay.
5. I trusted the uncertainty or missing-evidence language.
6. The interaction required reasonable effort.

Then ask these fixed open questions and capture short, non-identifying notes:

- What was most useful?
- What was confusing, missing, or unexpectedly slow?
- Which evidence changed or supported your answer?
- What would you change before using this for an incident review?
- May a non-identifying sentence from this feedback be quoted? (yes/no)

## Results template (UNRUN)

The following table is intentionally blank. `—` means no measurement exists;
it must not be replaced with an assumed value.

**Run status: UNRUN — no participants contacted and no data collected.**

| Participant | Order | A time (s) | A correct | A evidence supported | B time (s) | B correct | B evidence supported | Notes |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| P01 | — | — | — | — | — | — | — | — |
| P02 | — | — | — | — | — | — | — | — |
| P03 | — | — | — | — | — | — | — | — |
| P04 | — | — | — | — | — | — | — | — |
| P05 | — | — | — | — | — | — | — | — |

| Summary field | Value |
| --- | --- |
| Declared N (3–5) | — |
| A→B / B→A counts | — / — |
| A task time median and range | — |
| B task time median and range | — |
| A correct count / attempted | — |
| B correct count / attempted | — |
| Feedback rating summaries | — |
| Protocol deviations | — |

## Interpretation rule

If the pilot is run, report the coded rows, order counts, medians/ranges, and
correctness counts exactly as observed, including missing data and deviations.
With fewer than three completed participants, label the pilot incomplete and do
not summarize patterns. In all cases this is exploratory descriptive evidence:
do not calculate or claim statistical significance, causal effects, broad user
impact, production readiness, or generalization beyond these sessions. A live
connector result cannot be substituted for this pilot and remains a separate
blocked gate.
