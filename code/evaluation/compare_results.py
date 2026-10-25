import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "dataset"


def read_csv(filename):
    with open(
        DATASET / filename,
        newline="",
        encoding="utf-8-sig"
    ) as f:
        return list(csv.DictReader(f))


gold = {
    row["case_id"]: row
    for row in read_csv("sample_output.csv")
}

pred = {
    row["case_id"]: row
    for row in read_csv("sample_pred.csv")
}

correct = 0
total = len(gold)

print("\nCLASSIFICATION COMPARISON")
print("=" * 65)

for case_id, expected in gold.items():

    if case_id not in pred:
        print(f"{case_id}: MISSING PREDICTION")
        continue

    actual = pred[case_id]

    expected_status = expected["deletion_status"]
    predicted_status = actual["deletion_status"]

    if expected_status == predicted_status:
        correct += 1
    else:
        print(
            f"{case_id}: "
            f"Expected={expected_status} | "
            f"Predicted={predicted_status}"
        )

accuracy = (correct / total * 100) if total else 0

print("=" * 65)
print(f"Total cases: {total}")
print(f"Correct: {correct}")
print(f"Incorrect: {total - correct}")
print(f"Accuracy: {accuracy:.2f}%")