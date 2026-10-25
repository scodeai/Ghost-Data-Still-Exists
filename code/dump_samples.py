import csv, collections
from pathlib import Path
D = Path(__file__).resolve().parent.present / "dataset"
def rd(n): return list(csv.DictReader(open(D/n, encoding="utf-8-sig", newline="")))
out = []
act = rd("system_activity.csv")
for col in ("event_type", "source_system", "target_system", "reported_result"):
    out.append(f"{col}: {dict(collections.Counter(r[col] for r in act))}")
out.append("\nRULES")
out += [str(r) for r in rd("deletion_rules.csv")]
out.append("\nSAMPLE OUTPUT")
so = rd("sample_output.csv")
for st in ("COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"):
    c = sorted([r for r in so if r["deletion_status"] == st], key=lambda r: len(r["steps_json"]))
    for r in c[-2:] + c[:1]:
        out.append(f"{r['case_id']} {st} {r['steps_json'][:1500]}")
out.append("\nEVIDENCE SAMPLES")
ev = rd("evidence_files.csv")
out.append(str(dict(collections.Counter(r["origin"] for r in ev))))
seen = collections.Counter()
for r in ev:
    ext = Path(r["file_path"]).suffix
    if seen[ext] >= 2:
        continue
    seen[ext] += 1
    out.append(f"\n--- {r['file_id']} {r['file_path']}")
    p = D / r["file_path"]
    if ext == ".png":
        out.append("(image)")
    elif ext == ".pdf":
        try:
            from pypdf import PdfReader
            out.append("\n".join((pg.extract_text() or "") for pg in PdfReader(str(p)).pages)[:1500])
        except Exception as e:
            out.append(f"(pdf unreadable: {e})")
    else:
        out.append(p.read_text(encoding="utf-8", errors="ignore")[:1500])
(D.parent / "dump.txt").write_text("\n".join(out), encoding="utf-8")
print("wrote dump.txt")