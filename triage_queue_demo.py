"""Synthetic, deterministic queue demonstration for Alex's approved examples.

Run with the bundled Python runtime:
  python triage_queue_demo.py
  python triage_queue_demo.py --check

The default path reads only synthetic inputs. --check additionally reads separate
human-approved expected outcomes. This program makes no network requests.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


HERE = Path(__file__).resolve().parent
POLICY_VERSION = "queue-fixture-demo-v1"

# Demo settings chosen to make these fixed-time examples executable. They are
# not calibrated operational thresholds or approved production policy.
RECENT_REPORT_WINDOW = timedelta(minutes=15)
CURRENT_OBSERVATION_WINDOW = timedelta(minutes=30)
VALID_STATUSES = {"observed", "checked_not_found", "check_failed"}
REACHABILITY_CODES = {
    "exact_page_reachable",
    "exact_path_404",
    "reachability_check_timeout",
    "redirect_to_brand_lookalike_login",
}
SUSPICIOUS_CONTENT_CODES = {
    "brand_lookalike_login_capture",
    "redirect_to_brand_lookalike_login",
}


def read_json(name: str) -> dict[str, Any]:
    with (HERE / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp lacks timezone: {value}")
    return parsed


def is_recent(value: str, as_of: str, window: timedelta) -> bool:
    age = instant(as_of) - instant(value)
    return timedelta(0) <= age <= window


def example_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.hostname and parsed.hostname.endswith(".example"))


def validate_input(data: dict[str, Any]) -> None:
    as_of = data["as_of"]
    case_ids: set[str] = set()
    for case in data["cases"]:
        case_id = case["case_id"]
        if case_id in case_ids or not example_url(case["target_url"]):
            raise ValueError(f"Duplicate case or invalid fictional URL: {case_id}")
        case_ids.add(case_id)

    report_ids: set[str] = set()
    for report in data["reports"]:
        report_id = report["report_id"]
        if report_id in report_ids or report["case_id"] not in case_ids:
            raise ValueError(f"Duplicate or orphan report: {report_id}")
        if report["claim_category"] != "suspected_brand_impersonation":
            raise ValueError(f"Unknown claim category: {report_id}")
        if not example_url(report["reported_url"]) or instant(report["received_at"]) > instant(as_of):
            raise ValueError(f"Invalid URL or future report: {report_id}")
        report_ids.add(report_id)

    observation_ids: set[str] = set()
    for observation in data["observations"]:
        observation_id = observation["observation_id"]
        if observation_id in observation_ids or observation["case_id"] not in case_ids:
            raise ValueError(f"Duplicate or orphan observation: {observation_id}")
        if observation["status"] not in VALID_STATUSES or not observation.get("evidence_code"):
            raise ValueError(f"Invalid evidence status or code: {observation_id}")
        if not observation.get("source_ref") or not observation.get("target_scope"):
            raise ValueError(f"Missing provenance or scope: {observation_id}")
        if not (
            instant(observation["observed_at"])
            <= instant(observation["recorded_at"])
            <= instant(as_of)
        ):
            raise ValueError(f"Invalid observation chronology: {observation_id}")
        if observation["evidence_code"] == "rapid_distribution_observed":
            if observation["status"] != "observed":
                raise ValueError("Distribution code requires an observed result")
            if observation.get("delivered_message_count", 0) <= 0:
                raise ValueError("Distribution count must be positive")
            if not (
                instant(observation["window_start"])
                <= instant(observation["window_end"])
                <= instant(observation["observed_at"])
            ):
                raise ValueError("Invalid distribution time window")
        if observation["evidence_code"] == "redirect_to_brand_lookalike_login":
            if not example_url(observation.get("redirect_target_url", "")):
                raise ValueError("Redirect lacks a fictional target")
            if not observation.get("target_capture_ref"):
                raise ValueError("Redirect lacks a captured destination description")
        observation_ids.add(observation_id)


def evidence_profile(observations: list[dict[str, Any]]) -> dict[str, Any]:
    def latest(codes: set[str]) -> dict[str, Any]:
        matches = [item for item in observations if item["evidence_code"] in codes]
        if not matches:
            return {"status": "not_checked"}
        item = max(matches, key=lambda row: instant(row["observed_at"]))
        return {
            "status": item["status"],
            "evidence_code": item["evidence_code"],
            "observed_at": item["observed_at"],
            "observation_id": item["observation_id"],
        }

    return {
        "page_content": latest(SUSPICIOUS_CONTENT_CODES),
        "reachability": latest(REACHABILITY_CODES),
        "distribution": latest({"rapid_distribution_observed"}),
    }


def recommend_case(
    case: dict[str, Any],
    reports: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    as_of: str,
    scenario_id: str,
) -> dict[str, Any]:
    profile = evidence_profile(observations)
    recent_sources = {
        report["source_id"]
        for report in reports
        if report["claim_category"] == "suspected_brand_impersonation"
        and is_recent(report["received_at"], as_of, RECENT_REPORT_WINDOW)
    }
    content = profile["page_content"]
    reachability = profile["reachability"]
    distribution = profile["distribution"]
    active_suspicious_page = (
        content["status"] == "observed"
        and is_recent(content["observed_at"], as_of, CURRENT_OBSERVATION_WINDOW)
        and reachability["status"] == "observed"
        and reachability["evidence_code"]
        in {"exact_page_reachable", "redirect_to_brand_lookalike_login"}
        and is_recent(reachability["observed_at"], as_of, CURRENT_OBSERVATION_WINDOW)
    )
    rapid_distribution = (
        distribution["status"] == "observed"
        and is_recent(distribution["observed_at"], as_of, CURRENT_OBSERVATION_WINDOW)
    )
    multiple_recent_reports = len(recent_sources) >= 2

    if rapid_distribution:
        band = "review_now"
        order_tier = 0
        reasons = ["rapid_distribution_observed", "page_behavior_unverified"]
    elif active_suspicious_page:
        band = "review_now"
        order_tier = 1
        reasons = ["current_suspicious_page_reachable"]
    elif multiple_recent_reports:
        band = "review_now"
        order_tier = 2
        reasons = ["multiple_recent_distinct_sources", "page_behavior_unverified"]
    else:
        band = "review_today"
        order_tier = None
        if reachability["status"] == "check_failed":
            reasons = ["single_report", "reachability_check_failed"]
        elif reachability["status"] == "checked_not_found" and content["status"] == "observed":
            reasons = ["historical_suspicious_capture", "latest_exact_page_check_404"]
        else:
            reasons = ["single_unverified_report"]

    missing: list[str] = []
    if not active_suspicious_page:
        missing.append("current_suspicious_page")
    if reachability["status"] in {"not_checked", "check_failed"}:
        missing.append("page_reachability")
    missing.append("form_submission_behavior")
    if distribution["status"] == "not_checked":
        missing.append("current_distribution")

    return {
        "recommendation_id": f"REC-{scenario_id}-{case['case_id']}",
        "case_id": case["case_id"],
        "generated_at": as_of,
        "policy_version": POLICY_VERSION,
        "band": band,
        "within_band_order": None,
        "reason_codes": reasons,
        "missing_checks": missing,
        "evidence_profile": profile,
        "observation_ids_used": [item["observation_id"] for item in observations],
        "_demo_order_tier": order_tier,
        "_opened_at": case["opened_at"],
    }


def run_scenario(data: dict[str, Any], scenario_id: str) -> list[dict[str, Any]]:
    validate_input(data)
    recommendations = []
    for case in data["cases"]:
        case_id = case["case_id"]
        reports = [item for item in data["reports"] if item["case_id"] == case_id]
        observations = [item for item in data["observations"] if item["case_id"] == case_id]
        recommendations.append(recommend_case(case, reports, observations, data["as_of"], scenario_id))

    review_now = sorted(
        (item for item in recommendations if item["band"] == "review_now"),
        key=lambda item: (item["_demo_order_tier"], instant(item["_opened_at"]), item["case_id"]),
    )
    for rank, item in enumerate(review_now, start=1):
        item["within_band_order"] = rank
    review_today = [item for item in recommendations if item["band"] == "review_today"]
    for item in recommendations:
        del item["_demo_order_tier"]
        del item["_opened_at"]
    # Review-today ordering is deliberately unresolved; list it by case ID for display only.
    return review_now + sorted(review_today, key=lambda item: item["case_id"])


def scenario_inputs() -> dict[str, dict[str, Any]]:
    base = read_json("synthetic_cases_v1.json")
    b_plus = read_json("synthetic_b_plus_distribution_v1.json")
    d_updates = read_json("synthetic_case_d_updates_v1.json")
    if b_plus["base_dataset_id"] != base["dataset_id"] or d_updates["base_dataset_id"] != base["dataset_id"]:
        raise ValueError("A scenario points to the wrong baseline")

    # JSON round-trip creates independent copies. Branch events never alter base input.
    inputs = {"base": base}
    b_input = json.loads(json.dumps(base))
    b_input["observations"].append(b_plus["new_observation"])
    inputs["b_plus"] = b_input
    for branch in d_updates["branches"]:
        branch_input = json.loads(json.dumps(base))
        branch_input["as_of"] = branch["as_of"]
        # These alternatives test D's evidence update only. The policy has no
        # approved rule for aging unrelated A/B cases between 10:00 and 11:10.
        branch_input["cases"] = [item for item in branch_input["cases"] if item["case_id"] == "D"]
        branch_input["reports"] = [item for item in branch_input["reports"] if item["case_id"] == "D"]
        branch_input["observations"] = [
            item for item in branch_input["observations"] if item["case_id"] == "D"
        ]
        branch_input["observations"].extend(branch["new_observations"])
        inputs[f"d_{branch['branch_id']}"] = branch_input
    return inputs


def run_all() -> dict[str, list[dict[str, Any]]]:
    return {name: run_scenario(data, name) for name, data in scenario_inputs().items()}


def check_expected(result: dict[str, list[dict[str, Any]]]) -> None:
    base_expected = read_json("expected_outcomes_v1.json")
    b_expected = read_json("expected_b_plus_distribution_v1.json")
    d_expected = read_json("expected_case_d_updates_v1.json")

    def by_id(scenario: str) -> dict[str, dict[str, Any]]:
        return {item["case_id"]: item for item in result[scenario]}

    base = by_id("base")
    for item in base_expected["expected_cases"]:
        if base[item["case_id"]]["band"] != item["expected_band"]:
            raise AssertionError(f"Base band mismatch for {item['case_id']}")
    if base["A"]["within_band_order"] >= base["B"]["within_band_order"]:
        raise AssertionError("Base A must be ahead of B")
    if base["E"]["evidence_profile"]["reachability"]["status"] != "check_failed":
        raise AssertionError("E timeout was misrepresented")
    print("PASS base: five expected bands, A before B, E check_failed")

    expanded = by_id("b_plus")
    for item in b_expected["expected_cases"]:
        if expanded[item["case_id"]]["band"] != item["expected_band"]:
            raise AssertionError(f"B+ band mismatch for {item['case_id']}")
    if expanded["B"]["within_band_order"] >= expanded["A"]["within_band_order"]:
        raise AssertionError("B+ must be ahead of A")
    if "O-B-DISTRIBUTION-PLUS" not in expanded["B"]["observation_ids_used"]:
        raise AssertionError("B+ lost the distribution observation")
    print("PASS B+: B before A, both Review now, distribution retained")

    for branch in d_expected["branch_expectations"]:
        scenario = f"d_{branch['branch_id']}"
        current = by_id(scenario)["D"]
        if current["band"] != branch["expected_band"]:
            raise AssertionError(f"D band mismatch for {branch['branch_id']}")
        if current["observation_ids_used"] != branch["preserve_observation_ids"]:
            raise AssertionError(f"D lost history in {branch['branch_id']}")
        print(f"PASS {scenario}: {current['band']}, D observation history retained")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare with separate expected outcomes")
    args = parser.parse_args()
    result = run_all()
    if args.check:
        check_expected(result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
