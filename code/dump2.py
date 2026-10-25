import csv, collections, json
from pathlib import Path
R = Path(__file__).resolve().parent
while not (R / "dataset").exists() and R != R.parent:
    R = R.parent
D = R / "dataset"
def rd(n): return list(csv.DictReader(open(D/n, encoding="utf-8-sig", newline="")))
out = []
act = rd("system_activity.csv")
out.append("== SAMPLE ROW PER event_type x result")
seen = set()
for r in act:
    k = (r["event_type"], r["reported_result"])
    if k not in seen:
        seen.add(k)
        out.append(str({x: r[x] for x in ("event_type","source_system","target_system","resource_id","reported_result","details")}))
out.append("\n== CLASSIFY_REQUEST / LINK_RESOURCE_IDENTITY rows")
for r in act:
    if r["event_type"] in ("CLASSIFY_REQUEST", "LINK_RESOURCE_IDENTITY"):
        out.append(str(r))
out.append("\n== audit field_name: " + str(collections.Counter(r["field_name"] for r in rd("user_audit_log.csv"))))
so = {r["case_id"]: r for r in rd("sample_output.csv")}
req = {r["case_id"]: r for r in rd("sample_deletion_requests.csv")}
ids = {r["email"].lower(): r for r in rd("user_identities.csv")}
texts = {}
for e in rd("evidence_files.csv"):
    p = D / e["file_path"]
    if p.suffix.lower() in (".json", ".log", ".txt", ".sql"):
        texts[e["file_id"]] = p.read_text(encoding="utf-8", errors="ignore")
for cid in ("case_02", "case_03", "case_05", "case_29"):
    if cid not in req or cid not in so:
        continue
    r = req[cid]
    out.append(f"\n######## {cid}: {r['email']} requested={r['requested_at']} audit={r['audit_at']} reported={r['reported_status']}")
    out.append("request_text: " + r["request_text"][:300])
    out.append("identity: " + str(ids.get(r["email"].lower())))
    out.append("expected: " + so[cid]["deletion_status"] + " " + so[cid]["steps_json"][:2500])
    em = r["email"].lower()
    for x in [a for a in act if em in a["details"].lower()][:4]:
        out.append("ACT-by-email: " + str(x))
    for fid, t in texts.items():
        if em in t.lower():
            i = t.lower().find(em)
            out.append(f"EVID-by-email {fid}: " + t[max(0, i-200):i+300].replace("\n", " "))
            break
    rids = []
    try:
        for s in json.loads(so[cid]["steps_json"]):
            if s["resource_id"] not in rids:
                rids.append(s["resource_id"])
    except Exception:
        pass
    for rid in rids[:6]:
        for x in [a for a in act if a["resource_id"] == rid][:5]:
            out.append("ACT: " + str({k: x[k] for k in ("event_time","event_type","source_system","target_system","resource_id","reported_result","details")}))
        n = 0
        for fid, t in texts.items():
            if rid in t and n < 2:
                i = t.find(rid)
                out.append(f"EVID {rid} in {fid}: " + t[max(0, i-150):i+350].replace("\n", " "))
                n += 1
ps = (R / "problem_statement.md").read_text(encoding="utf-8", errors="ignore")
i = ps.find("Required Output")
out.append("\n== PROBLEM STATEMENT (from Required Output)\n" + ps[i:])
(R / "dump2.txt").write_text("\n".join(out), encoding="utf-8")
print("wrote dump2.txt", len(out), "lines")