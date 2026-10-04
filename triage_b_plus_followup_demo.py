"""Explain Alex's two approved B+ follow-up branches using synthetic files only.

The queue engine still proposes Review now from recent distribution. A fictional
analyst can record a reasoned Review today override after two valid 404s.
No network requests, persistence, or live-site checks occur.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from triage_queue_demo import instant, read_json, run_scenario, validate_input


EXACT_URL = "https://account-cedarpay.example/verify"


def validate_branch(branch: dict[str, Any]) -> None:
    observations = branch["new_observations"]
    if len(observations) != 2:
        raise ValueError("This comparison requires exactly two follow-up checks")
    vantages: set[str] = set()
    for observation in observations:
        if observation["case_id"] != "B" or observation["check_type"] != "page_reachability":
            raise ValueError("Follow-up checks must concern case B reachability")
        if not observation["target_scope"].startswith(EXACT_URL + " from "):
            raise ValueError("Follow-up must check the exact fictional path")
        context = observation["check_context"]
        vantage = context["vantage_id"]
        if vantage in vantages:
            raise ValueError("The two checks must use distinct fictional vantages")
        vantages.add(vantage)
        if branch["branch_id"] == "two_timeouts":
            if (observation["status"], observation["evidence_code"]) != (
                "check_failed", "reachability_check_timeout"
            ):
                raise ValueError("Timeout branch contains a non-timeout result")
        elif branch["branch_id"] == "two_valid_404s":
            if (observation["status"], observation["evidence_code"]) != (
                "checked_not_found", "exact_path_404"
            ) or context.get("http_status") != 404 or context.get("redirect_observed") is not False:
                raise ValueError("404 branch requires a completed 404 without redirect")
        else:
            raise ValueError("Unknown follow-up branch")


def run_all() -> dict[str, Any]:
    base = read_json("synthetic_cases_v1.json")
    distribution = read_json("synthetic_b_plus_distribution_v1.json")
    followups = read_json("synthetic_b_plus_followups_v1.json")
    if any(item["base_dataset_id"] != base["dataset_id"] for item in (distribution, followups)):
        raise ValueError("Follow-up fixture refers to another baseline")
    if distribution["base_case_id"] != "B" or followups["base_case_id"] != "B":
        raise ValueError("Follow-up fixture refers to another case")
    if base["as_of"] != distribution["as_of"] or instant(followups["as_of"]) <= instant(base["as_of"]):
        raise ValueError("Invalid before/after chronology")

    b_case = next(item for item in base["cases"] if item["case_id"] == "B")
    b_reports = [item for item in base["reports"] if item["case_id"] == "B"]
    before_data = {
        "as_of": base["as_of"], "cases": [b_case], "reports": b_reports,
        "observations": [distribution["new_observation"]],
    }
    before = run_scenario(before_data, "b_plus_before")[0]
    results: dict[str, Any] = {}
    for branch in followups["branches"]:
        validate_branch(branch)
        # Independent branches begin from the same B+ state; neither edits it.
        after_data = {
            "as_of": followups["as_of"], "cases": [b_case], "reports": b_reports,
            "observations": [distribution["new_observation"]] + branch["new_observations"],
        }
        validate_input(after_data)
        after = run_scenario(after_data, f"b_plus_{branch['branch_id']}")[0]
        decision = branch.get("analyst_decision")
        if decision is not None:
            if branch["branch_id"] != "two_valid_404s":
                raise ValueError("Only the 404 branch has an analyst override")
            if (decision["case_id"] != "B" or decision["chosen_band"] != "review_today"
                    or not decision["rationale"] or instant(decision["decided_at"]) < instant(after["generated_at"])):
                raise ValueError("Invalid analyst decision")
            decision = {**decision, "recommendation_id": after["recommendation_id"]}
        results[branch["branch_id"]] = {
            "recommendation_history": [before, after],
            "observation_history": after_data["observations"],
            "analyst_decision": decision,
            "effective_band": decision["chosen_band"] if decision else after["band"],
        }
    return results


def check_expected(results: dict[str, Any]) -> None:
    expected = read_json("expected_b_plus_followups_v1.json")
    if set(results) != {item["branch_id"] for item in expected["expectations"]}:
        raise AssertionError("Unexpected follow-up branches")
    for item in expected["expectations"]:
        result = results[item["branch_id"]]
        before, after = result["recommendation_history"]
        observations = result["observation_history"]
        if before["band"] != "review_now" or after["band"] != item["recommendation_band"]:
            raise AssertionError("Distribution recommendation changed unexpectedly")
        if after["evidence_profile"]["reachability"]["status"] != item["reachability_status"]:
            raise AssertionError("Timeout and 404 evidence were conflated")
        if [row["observation_id"] for row in observations] != after["observation_ids_used"]:
            raise AssertionError("The new recommendation lost observation history")
        if observations[0]["observation_id"] != "O-B-DISTRIBUTION-PLUS":
            raise AssertionError("Distribution evidence was lost")
        decision = result["analyst_decision"]
        if item["branch_id"] == "two_timeouts":
            if decision is not None or result["effective_band"] != "review_now":
                raise AssertionError("Timeouts must not cause a downgrade")
        elif (decision is None or decision["chosen_band"] != item["analyst_decision_band"]
              or decision["recommendation_id"] != after["recommendation_id"]
              or result["effective_band"] != "review_today"):
            raise AssertionError("404 analyst decision was not retained")
        print(f"PASS {item['branch_id']}: recommendation {after['band']}, effective {result['effective_band']}, history retained")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare with separate expected outcomes")
    args = parser.parse_args()
    results = run_all()
    if args.check:
        check_expected(results)
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
