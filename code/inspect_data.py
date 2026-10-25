"""Run FIRST: prints headers + 3 sample rows of every dataset file so the aliases in config.py can be checked."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
from common import read_csv

for p in sorted(C.DATASET.glob("*.csv")):
    rows = read_csv(p)
    print(f"\n=== {p.name}  ({len(rows)} rows)")
    if rows:
        print("columns:", list(rows[0].keys()))
        for r in rows[:3]:
            print("  ", dict(list(r.items())[:12]))
ev = C.DATASET / "evidence"
if ev.exists():
    files = [f for f in ev.rglob("*") if f.is_file()]
    print(f"\n=== evidence/ ({len(files)} files)", sorted({f.suffix for f in files}))