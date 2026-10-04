# CedarPay — Explainable Phishing Triage (synthetic portfolio)

**Status:** Public synthetic portfolio. Alex completed the original six-step browser walkthrough on 3 October 2026 and confirmed the later reassessment page's requested elements on 4 October 2026. [Open the live investigation demo](https://alexak29.github.io/cedarpay-phishing-triage/).

## The decision

An investigating fraud or brand-protection analyst receives reports of a suspected financial-brand impersonation page. The prototype answers one triage question: **How urgently should the analyst investigate this case, relative to other work?** It recommends a review band and explains the evidence; the analyst retains the final decision. **Review now** means investigate promptly, not that an active phishing page has been confirmed. **Review today** means keep the case in the same-day workflow. Neither band is a phishing verdict, credential-theft finding, or takedown instruction.

## My contribution

I defined the analyst's decision, selected the evidence distinctions and expected priority outcomes for the synthetic cases, challenged conclusions that exceeded the observations, and reviewed the AI-assisted implementation step by step. This portfolio demonstrates my investigation reasoning and ability to explain the design. The implementation used AI assistance and no live site checks.

## What the prototype demonstrates

- A small data contract separating customer **Reports**, grouped **Cases**, time-stamped **Observations**, system **Recommendations**, and human **AnalystDecisions**.
- Four distinct evidence states: `not_checked`, `observed`, `checked_not_found`, and `check_failed`. `not_checked` is derived when no relevant check exists; it is not a stored check result.
- A deterministic queue demonstration using synthetic, separate input and expected-outcome files.
- Local investigation pages that [start before follow-up checks](index.html), open the [two-timeout](Alex_B_Plus_Timeouts.html) and [two-valid-404](Alex_B_Plus_404s.html) alternatives, or [continue the 404 branch with a later timeout](Alex_B_Plus_404s_Then_Timeout.html).
- A reasoned manual decision that changes the effective review band without overwriting the system recommendation or source observations. The view can export an audit JSON snapshot.

## B+ example

An authorized **fictional** message log records 300 deliveries of the exact reported link to 300 distinct fictional recipients in eight minutes. That supports urgent investigation but says nothing about clicks, page content, credential collection or victim impact.

B+ also retains two original fictional customer reports. Those reports are claims; the 300 deliveries come from a separate synthetic telemetry Observation. The two sources are deliberately kept distinct.

| Alternative follow-up | What was observed | System recommendation | Example effective band |
|---|---|---|---|
| No page check yet | Distribution only | Review now | Review now |
| Two timeouts | Two checks failed to return a usable result | Review now | Review now |
| Two valid 404s | Exact path returned 404 from two independent fictional vantages at recorded times, without redirect | Review now | Review today after a separately recorded fictional analyst decision |
| Later timeout after two 404s | A third check returned no usable result after the analyst's decision; both 404s remain in history | Review now | Review today, flagged for human reassessment; no automatic band change |

The 404 responses are scoped negative observations. They do not establish that the whole domain is safe, that a campaign ended, or that no one received the link. The system still recommends immediate review because the delivery signal remains recent in this example; the analyst may choose same-day review after examining the 404s and recording a rationale.

In the later-timeout continuation, the failed check does not prove the page became active or invalidate the earlier 404s. It triggers a **reassessment needed** flag on the older analyst decision. The decision stays effective until an analyst records a new choice. The analyst can investigate possible changes in site behavior, but this fixture has no evidence that the actor changed tactics. The flag is a review prompt, not an automated priority change.

## Architecture

See the [architecture and decision record](ARCHITECTURE.md) for entity boundaries, evidence states, human override behavior and open limitations.

```text
Synthetic Reports + Observations
        ↓
Input validation and evidence profile
        ↓
Versioned queue recommendation with reasons and missing checks
        ↓
Investigation view: timeline + recommendation + analyst decision
        ↓
Effective band and exportable audit snapshot
```

The [queue demo](triage_queue_demo.py), [B+ follow-up demo](triage_b_plus_followup_demo.py), and [reassessment demo](triage_b_plus_reassessment_demo.py) use local JSON fixtures. [build_investigation_view.py](build_investigation_view.py) turns their outputs into four standalone HTML pages with embedded synthetic data, so the view needs no server or network connection. Branch controls are ordinary links to those pages. Browser-session decisions do not modify the input files; export a JSON copy before navigating away or closing the tab.

## Run locally

Open `index.html` in a modern desktop browser. To rebuild the four scenario pages after editing a fixture, run:

```shell
python build_investigation_view.py
python triage_queue_demo.py --check
python triage_b_plus_followup_demo.py --check
python triage_b_plus_reassessment_demo.py --check
node check_investigation_view.mjs
```

The Python programs use only the standard library. Node is needed only for the local interaction-logic check.

## Limits and safety

All names, reports, recipients, times, and `.example` URLs are fictional. The prototype does **not** fetch a page, use a VPN or proxy, ingest real messages, prove phishing, submit a form, or initiate a takedown. Its 15/30-minute demo windows and the B+ distribution signal are fixture settings, not calibrated operational thresholds. The local snapshots preserve the demonstrated history, but this prototype has no write-once database or enforced immutable audit store. There is no general aging rule, distribution cutoff, Normal queue policy, or measured detection accuracy yet.

This project is intended to show evidence handling and analyst judgment, including what remains unknown. Alex reviewed the original three scenarios locally, confirmed the reassessment continuation's requested elements, and approved the contribution wording. The synthetic-only package passed local release checks and is published through GitHub Pages.
