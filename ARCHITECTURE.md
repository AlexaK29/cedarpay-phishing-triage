# Architecture and decision record

## Product boundary

**User:** an investigating fraud or brand-protection analyst reviewing incoming suspected phishing reports.  
**Version 1 decision:** which case to investigate next.  
**Output:** a review band, within-band order for the approved Review now examples, reasons, missing checks, and evidence provenance. The analyst can record a separate decision. The prototype does not confirm phishing or initiate takedown.

## Data flow

```text
Report[] ──exact-page grouping──> Case
                                  │
Observation[] ────────────────────┤
                                  v
                        deterministic policy
                                  │
                                  v
                       Recommendation history
                                  │
                                  v
                  investigation view + AnalystDecision
                                  │
                                  v
                       effective review band
```

The five entities have different responsibilities:

| Entity | Meaning | Important boundary |
|---|---|---|
| Report | What a fictional customer claimed | A claim is not a page observation. |
| Case | One investigation work item for one exact fictional page | Both original B reports remain available. |
| Observation | A time-stamped check or authorized synthetic signal | Its source, target scope, result and limitation stay attached. |
| Recommendation | Versioned system output with reasons and referenced observations | It is urgency for review, not a safety or phishing verdict. |
| AnalystDecision | A human choice linked to a recommendation | It changes the effective band without rewriting the recommendation. |

`not_checked` is derived when no relevant observation exists. `check_failed` means a check was attempted but returned no usable result. `checked_not_found` is a completed negative result within the recorded scope. `observed` means the described signal was captured. None of these statuses alone establishes malicious intent.

In the B+ fixture, two customer Reports are separate from one authorized synthetic telemetry Observation of 300 message deliveries. A reported claim does not become verified delivery data merely because it appears in the same Case. The demonstration retains old Observations and Recommendations in its generated snapshots; it does not implement an enforced, durable append-only event store.

## Why urgency and evidence are separate

In B+, fictional authorized message telemetry records 300 deliveries of the exact link to 300 distinct recipients in eight minutes. This is a strong signal of possible near-term exposure, but it does not show page content, clicks or credential collection. The policy can therefore propose **Review now** while the evidence profile still says `page_content = not_checked`.

Two later timeout attempts remain `check_failed`; they do not show that the page is down. Two alternative valid 404 responses, from independent fictional vantages and without redirect, become `checked_not_found` for the exact path at those times. The current demonstration policy still proposes Review now from recent delivery. A fictional analyst then chooses Review today with a recorded rationale. That choice does not erase the delivery observation or earlier recommendation.

The timeout and 404 branches are alternative synthetic futures from one starting state. They must never be combined into one case timeline.

The later-timeout page continues **only** from the 404 branch. It appends a third `check_failed` Observation after the analyst's Review today decision, then saves a new Recommendation. A derived `reassessment_needed` flag references that decision and the new observation. The flag does not modify the decision or effective band and does not assert that the page is active. A later analyst choice would be a new AnalystDecision. The older 404s and recommendation remain visible and exportable.

## Implementation choices

- **Deterministic policy:** same fixture, timestamp and policy version produce the same recommendation. The data files and expected outcomes are separate.
- **Structured evidence codes:** policy rules read controlled codes such as `exact_path_404` rather than interpreting free-text customer claims as verified facts.
- **Explicit provenance:** observation IDs, source references, timestamps, exact target scope and limitations are retained in the recommendation and investigation view.
- **Standalone presentation:** the build script embeds synthetic snapshots into four local HTML pages. Branch navigation uses ordinary links. No server, live URL request, account or third-party asset is needed.
- **Human decision isolation:** the form adds a browser-session decision with a rationale. Export produces a JSON audit snapshot. Reset clears only decisions entered in that tab.

## Verification

`triage_queue_demo.py --check` checks the five base cases, A/B and B+/A order, and D's DNS-only versus suspicious-redirect branches. `triage_b_plus_followup_demo.py --check` checks the timeout and 404 alternatives. `triage_b_plus_reassessment_demo.py --check` checks retained 404s, the later timeout, the review flag and unchanged bands. `check_investigation_view.mjs` checks page startup states, evidence labels, manual decisions, export, reset and direct page entry. Alex completed a six-step local browser walkthrough of the original view and confirmed the later continuation's requested elements on 4 October 2026. The agent's browser tool could not open local `file://` pages, so the visual acceptance is user-reported rather than agent-observed.

## What remains open

This is an illustrative policy, not a production detector. The 15/30-minute demo windows and rapid-distribution signal are not calibrated thresholds. There is no general aging rule, Normal queue entry rule, cross-organization risk calibration, ground-truth accuracy measure, multi-user transaction store, or authorization workflow for real investigations. The local browser export is a demo artifact, not durable server-side persistence.
