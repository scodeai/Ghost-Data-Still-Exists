import csv
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "dataset"

EXPECTED_FILE = DATASET / "sample_output.csv"
PREDICTED_FILE = DATASET / "sample_pred.csv"


def read_results(path):
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    required = {"case_id", "deletion_status", "steps_json"}

    if not rows:
        raise ValueError(f"No records found in {path.name}")

    if not required.issubset(rows[0]):
        raise ValueError(
            f"{path.name} must contain: {sorted(required)}"
        )

    results = {}

    for row in rows:
        case_id = row["case_id"].strip()

        if case_id in results:
            raise ValueError(f"Duplicate case_id: {case_id}")

        try:
            steps = json.loads(row["steps_json"] or "[]")
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid steps_json in {path.name}, {case_id}"
            ) from error

        if not isinstance(steps, list):
            raise ValueError(
                f"steps_json must be a list in {path.name}, {case_id}"
            )

        results[case_id] = {
            "status": row["deletion_status"].strip(),
            "steps": steps,
        }

    return results


def normalize_step(step):
    """
    Compare step content without step_no.

    step_no is excluded because step-set F1 generally
    compares step membership rather than sequence.
    This diagnostic is not necessarily identical to
    the official challenge evaluator.
    """
    if not isinstance(step, dict):
        return json.dumps(step, sort_keys=True, default=str)

    return json.dumps(
        {
            key: value
            for key, value in step.items()
            if key != "step_no"
        },
        sort_keys=True,
        default=str,
    )


def calculate_f1(expected_steps, predicted_steps):
    expected = Counter(normalize_step(s) for s in expected_steps)
    predicted = Counter(normalize_step(s) for s in predicted_steps)

    matches = sum((expected & predicted).values())

    expected_count = sum(expected.values())
    predicted_count = sum(predicted.values())

    if expected_count == 0 and predicted_count == 0:
        return 1.0

    if expected_count == 0 or predicted_count == 0:
        return 0.0

    precision = matches / predicted_count
    recall = matches / expected_count

    if precision + recall == 0:
        return 0.0

    return 2 * precision * recall / (precision + recall)


def main():
    expected = read_results(EXPECTED_FILE)
    predicted = read_results(PREDICTED_FILE)

    total = len(expected)
    correct = 0
    status_errors = []
    step_errors = []

    print("\n" + "=" * 65)
    print("GHOST DATA CHALLENGE - DIAGNOSTIC REPORT")
    print("=" * 65)

    for case_id, gold in expected.items():
        pred = predicted.get(case_id)

        if pred is None:
            status_errors.append((case_id, gold["status"], "MISSING"))
            step_errors.append((case_id, 0.0))
            continue

        if gold["status"] == pred["status"]:
            correct += 1
        else:
            status_errors.append(
                (case_id, gold["status"], pred["status"])
            )

        f1 = calculate_f1(gold["steps"], pred["steps"])

        if f1 < 1.0:
            step_errors.append((case_id, f1))

    accuracy = correct / total * 100 if total else 0

    print(f"\nTotal cases: {total}")
    print(f"Correct classifications: {correct}")
    print(f"Classification accuracy: {accuracy:.2f}%")
    print(f"Incorrect classifications: {len(status_errors)}")
    print(f"Cases with step differences: {len(step_errors)}")

    print("\n" + "-" * 65)
    print("CLASSIFICATION ERRORS")
    print("-" * 65)

    for case_id, gold_status, pred_status in status_errors:
        print(
            f"{case_id}: "
            f"Expected={gold_status} | "
            f"Predicted={pred_status}"
        )

    print("\n" + "-" * 65)
    print("STEP-SET DIFFERENCES")
    print("-" * 65)

    for case_id, f1 in step_errors:
        print(f"{case_id}: Diagnostic F1={f1:.3f}")

    # Show detailed differences for up to three cases.
    selected = []

    for case_id, _, _ in status_errors:
        if case_id not in selected:
            selected.append(case_id)

    for case_id, _ in step_errors:
        if case_id not in selected:
            selected.append(case_id)

    print("\n" + "=" * 65)
    print("DETAILED COMPARISON - FIRST 3 PROBLEM CASES")
    print("=" * 65)

    for case_id in selected[:3]:
        gold = expected[case_id]
        pred = predicted.get(case_id)

        print(f"\nCASE: {case_id}")
        print(f"Expected status: {gold['status']}")
        print(
            f"Predicted status: "
            f"{pred['status'] if pred else 'MISSING'}"
        )

        print("\nEXPECTED STEPS:")
        print(json.dumps(gold["steps"], indent=2))

        print("\nPREDICTED STEPS:")
        print(
            json.dumps(
                pred["steps"] if pred else [],
                indent=2
            )
        )

        print("-" * 65)

    print("\nDIAGNOSTIC COMPLETE")

   
if __name__ == "__main__":
    main()