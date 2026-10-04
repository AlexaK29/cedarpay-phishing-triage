"""Build the portable B+ investigation view from the synthetic checked scenarios.

No network access, live URLs, or third-party assets are used. Run from any cwd:
  python build_investigation_view.py
"""

from __future__ import annotations

import json
from pathlib import Path

from triage_b_plus_followup_demo import EXACT_URL, run_all
from triage_b_plus_reassessment_demo import run_reassessment
from triage_queue_demo import read_json


HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "investigation_view_template.html"
OUTPUTS = {
    "before": "Alex_B_Plus_Investigation_View.html",
    "two_timeouts": "Alex_B_Plus_Timeouts.html",
    "two_valid_404s": "Alex_B_Plus_404s.html",
    "post_404_timeout": "Alex_B_Plus_404s_Then_Timeout.html",
}
MARKER = "/*__SYNTHETIC_DATA__*/"
INITIAL_MARKER = "/*__INITIAL_SCENARIO__*/"


def payload() -> dict:
    base = read_json("synthetic_cases_v1.json")
    distribution = read_json("synthetic_b_plus_distribution_v1.json")
    followup = run_all()
    case = next(item for item in base["cases"] if item["case_id"] == "B")
    if case["target_url"] != EXACT_URL:
        raise ValueError("The view must show the exact synthetic B+ path")
    before = followup["two_timeouts"]["recommendation_history"][0]
    timeout = followup["two_timeouts"]
    not_found = followup["two_valid_404s"]
    reassessment = run_reassessment()
    if timeout["recommendation_history"][0] != before or not_found["recommendation_history"][0] != before:
        raise ValueError("Alternative branches have different starting recommendations")
    if any(item["observation_id"] != "O-B-DISTRIBUTION-PLUS" for item in (timeout["observation_history"][0], not_found["observation_history"][0])):
        raise ValueError("A branch lost the original distribution observation")
    return {
        "case": case,
        "reports": [item for item in base["reports"] if item["case_id"] == "B"],
        "scenarios": {
            "before": {
                "label": "Before follow-up checks",
                "recommendation_history": [before],
                "observation_history": [distribution["new_observation"]],
                "fixture_decisions": [],
            },
            "two_timeouts": {
                "label": "Two timeouts",
                "recommendation_history": timeout["recommendation_history"],
                "observation_history": timeout["observation_history"],
                "fixture_decisions": [],
            },
            "two_valid_404s": {
                "label": "Two valid 404s",
                "recommendation_history": not_found["recommendation_history"],
                "observation_history": not_found["observation_history"],
                "fixture_decisions": [not_found["analyst_decision"]],
            },
            "post_404_timeout": {
                "label": "Later timeout after two 404s",
                "recommendation_history": reassessment["recommendation_history"],
                "observation_history": reassessment["observation_history"],
                "fixture_decisions": [reassessment["analyst_decision"]],
                "decision_review": reassessment["decision_review"],
            },
        },
        "source_note": "All people, reports, times and URLs are synthetic. No live site was accessed.",
    }


def build() -> list[Path]:
    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count(MARKER) != 1 or template.count(INITIAL_MARKER) != 1:
        raise ValueError("Template must contain exactly one marker of each type")
    # The JSON becomes a JavaScript literal in a local file. Escape HTML-sensitive
    # characters to prevent a fixture string from ending the surrounding script.
    data = json.dumps(payload(), ensure_ascii=False, separators=(",", ":"))
    data = data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    paths: list[Path] = []
    for scenario, filename in OUTPUTS.items():
        html = template.replace(MARKER, data).replace(INITIAL_MARKER, json.dumps(scenario))
        path = HERE / filename
        path.write_text(html, encoding="utf-8")
        paths.append(path)
    index = HERE / "index.html"
    index.write_text((HERE / OUTPUTS["before"]).read_text(encoding="utf-8"), encoding="utf-8")
    paths.append(index)
    return paths


if __name__ == "__main__":
    print("Built " + ", ".join(path.name for path in build()))
