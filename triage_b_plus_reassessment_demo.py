"""Continue the fictional B+ 404 branch with one later failed check.

The review flag is derived from event order. It never edits an observation,
recommendation, or analyst decision. No network requests are made.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from triage_b_plus_followup_demo import EXACT_URL, run_all
from triage_queue_demo import instant, read_json, run_scenario, validate_input


def run_reassessment() -> dict[str, Any]:
    base = read_json("synthetic_cases_v1.json")
    fixture = read_json("synthetic_b_plus_reassessment_v1.json")
    if fixture["base_branch_id"] != "two_valid_404s":
        raise ValueError("The later check must extend the 404 branch")
    branch = run_all()["two_valid_404s"]
    old_recommendation = branch["recommendation_history"][-1]
    decision = branch["analyst_decision"]
    new_observation = fixture["new_observation"]
    if decision is None or decision["recommendation_id"] != old_recommendation["recommendation_id"]:
        raise ValueError("The prior analyst decision is not linked to the 404 recommendation")
    if (new_observation["case_id"] != "B"
            or new_observation["check_type"] != "page_reachability"
            or new_observation["status"] != "check_failed"
            or new_observation["evidence_code"] != "reachability_check_timeout"
            or not new_observation["target_scope"].startswith(EXACT_URL + " from ")
            or new_observation["check_context"].get("failure_phase") != "unknown"):
        raise ValueError("The later observation must be a scoped failed check")
    if not (instant(decision["decided_at"]) < instant(new_observation["observed_at"])
            <= instant(new_observation["recorded_at"]) <= instant(fixture["as_of"])):
        raise ValueError("The later check is not chronologically after the decision")
    observations = branch["observation_history"] + [new_observation]
    b_case = next(item for item in base["cases"] if item["case_id"] == "B")
    b_reports = [item for item in base["reports"] if item["case_id"] == "B"]
    data = {
        "as_of": fixture["as_of"], "cases": [b_case], "reports": b_reports,
        "observations": observations,
    }
    validate_input(data)
    new_recommendation = run_scenario(data, "b_plus_post_404_timeout")[0]
    review = {
        "status": "reassessment_needed",
        "decision_id": decision["decision_id"],
        "trigger_observation_ids": [new_observation["observation_id"]],
        "reason": "A later exact-path check failed after the analyst's Review today decision. Current page status is unresolved; review the decision against all evidence.",
        "automatic_band_change": False,
    }
    return {
        "recommendation_history": branch["recommendation_history"] + [new_recommendation],
        "observation_history": observations,
        "analyst_decision": decision,
        "effective_band": decision["chosen_band"],
        "decision_review": review,
    }


def check_expected(result: dict[str, Any]) -> None:
    expected = read_json("expected_b_plus_reassessment_v1.json")
    before, after_404, after_timeout = result["recommendation_history"]
    observations = result["observation_history"]
    decision = result["analyst_decision"]
    review = result["decision_review"]
    if (before["band"] != "review_now" or after_404["band"] != "review_now"
            or after_timeout["band"] != expected["recommendation_band"]
            or result["effective_band"] != expected["effective_band_until_reassessment"]):
        raise AssertionError("The later failed check changed a band automatically")
    if [item["observation_id"] for item in observations] != expected["retained_observation_ids"]:
        raise AssertionError("An observation was lost or reordered")
    if after_timeout["observation_ids_used"] != expected["retained_observation_ids"]:
        raise AssertionError("The new recommendation lost evidence provenance")
    if after_timeout["evidence_profile"]["reachability"]["status"] != expected["latest_reachability_status"]:
        raise AssertionError("The latest failed check was not reflected in the evidence profile")
    if (decision["decision_id"] != expected["retained_decision_id"]
            or decision["recommendation_id"] != after_404["recommendation_id"]
            or review["decision_id"] != decision["decision_id"]
            or review["status"] != expected["decision_review_status"]
            or review["trigger_observation_ids"] != [expected["trigger_observation_id"]]
            or review["automatic_band_change"] is not False):
        raise AssertionError("Decision review flag did not preserve the original decision")
    print("PASS post-404 timeout: history retained, Review today flagged for reassessment")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = run_reassessment()
    if args.check:
        check_expected(result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
