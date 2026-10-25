"""Scores the agent on sample_deletion_requests.csv against sample_output.csv.
sample_output.csv is used ONLY here for scoring - never for predictions."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C
from common import read_csv
from main import run


def key(s):
    return (s.get("phase"), s.get("system_id"), s.get("resource_id"), s.get("operation"))


def main():
    out = C.DATASET / "sample_pred.csv"
    run(C.DATASET, "sample_deletion_requests.csv", out)
    pred = {r["case_id"]: r for r in read_csv(out)}
    gold = {r["case_id"]: r for r in read_csv(C.DATASET / "sample_output.csv")}
    ok, conf, f1s, ordr = 0, {}, [], []
    for cid, g in gold.items():
        p = pred.get(cid)
        if not p:
            continue
        ok += p["deletion_status"] == g["deletion_status"]
        conf[(g["deletion_status"], p["deletion_status"])] = conf.get((g["deletion_status"], p["deletion_status"]), 0) + 1
        gs = [key(s) for s in json.loads(g["steps_json"] or "[]")]
        ps = [key(s) for s in json.loads(p["steps_json"] or "[]")]
        inter = len(set(gs) & set(ps))
        prec, rec = inter / len(set(ps)) if ps else (1.0 if not gs else 0.0), inter / len(set(gs)) if gs else (1.0 if not ps else 0.0)
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
        common = [k for k in gs if k in ps]
        pos = [ps.index(k) for k in common]
        ordr.append(1.0 if pos == sorted(pos) else 0.0)
    n = len(gold)
    print(f"\nstatus accuracy : {ok}/{n} = {ok / max(n, 1):.1%}")
    print(f"step-set F1     : {sum(f1s) / max(len(f1s), 1):.3f}")
    print(f"order correct   : {sum(ordr) / max(len(ordr), 1):.1%}")
    print("confusion (gold -> pred):")
    for (g, p), c in sorted(conf.items()):
        print(f"  {g:15s} -> {p:15s} {c}")
    print("\nMismatched cases:", [c for c in gold if c in pred and pred[c]["deletion_status"] != gold[c]["deletion_status"]][:20])


if __name__ == "__main__":
    main()