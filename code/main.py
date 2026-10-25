"""Ghost Data Still Exists - deletion audit agent.
Usage:  python code/main.py [--dataset dataset] [--input deletion_requests.csv] [--out output.csv] [--no-llm]"""
import argparse, csv, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
from common import read_csv, pick, case_sort_key, to_json
from engine import Engine


def run(dataset: Path, input_name: str, out_path: Path, use_llm=True, limit=None):
    eng = Engine(dataset, use_llm=use_llm)
    cases = read_csv(dataset / input_name)
    if limit:
        cases = cases[:limit]
    results = []
    for case in cases:
        cid = pick(case, ["case_id"])
        try:
            status, steps = eng.audit(case)
        except Exception as e:                     # never crash the whole run
            print(f"[warn] {cid}: {e}", file=sys.stderr)
            status, steps = "INCOMPLETE", []
        results.append((cid, status, to_json(steps)))
    results.sort(key=lambda r: case_sort_key(r[0]))
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "deletion_status", "steps_json"])
        w.writerows(results)
    counts = {}
    for _, s, _ in results:
        counts[s] = counts.get(s, 0) + 1
    print(f"wrote {len(results)} rows -> {out_path}  {counts}")
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=str(C.DATASET))
    ap.add_argument("--input", default="deletion_requests.csv")
    ap.add_argument("--out", default=str(C.DATASET / "output.csv"))
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    run(Path(a.dataset), a.input, Path(a.out), use_llm=not a.no_llm, limit=a.limit)