"""Index evidence files (json/log/txt/csv/sqlite/pdf/images) and link them to users by identifier."""
import json, sqlite3
from pathlib import Path
from common import read_csv, pick, tokens_of


def _read_text(path: Path):
    suf = path.suffix.lower()
    try:
        if suf in (".json", ".log", ".txt", ".csv", ".md", ".jsonl", ".tsv", ".html", ".xml", ".eml"):
            return path.read_text(encoding="utf-8", errors="ignore")
        if suf in (".sqlite", ".db", ".sqlite3", ".sql"):
            if suf == ".sql":
                return path.read_text(encoding="utf-8", errors="ignore")
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            out = []
            for (t,) in con.execute("select name from sqlite_master where type='table'"):
                out.append(f"TABLE {t}")
                for row in con.execute(f'select * from "{t}"'):
                    out.append(" | ".join(map(str, row)))
            con.close()
            return "\n".join(out)
        if suf == ".pdf":
            try:
                from pypdf import PdfReader
                return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
            except Exception:
                return ""
        if suf in (".png", ".jpg", ".jpeg", ".webp"):
            try:
                import pytesseract
                from PIL import Image
                return pytesseract.image_to_string(Image.open(path))
            except Exception:
                import llm
                return llm.ocr_image(path) or ""
    except Exception:
        return ""
    return ""


class EvidenceStore:
    def __init__(self, dataset: Path):
        self.items = []
        self.by_token = {}
        man = dataset / "evidence_files.csv"
        rows = read_csv(man) if man.exists() else []
        for r in rows:
            eid = pick(r, "evidence")  or pick(r, ["evidence_id", "id"])
            rel = pick(r, "ev_path")
            p = None
            for cand in (dataset / rel, dataset / "evidence" / rel, dataset / "evidence" / Path(rel).name):
                if rel and cand.exists() and cand.is_file():
                    p = cand
                    break
            text = _read_text(p) if p else ""
            item = {"id": eid, "path": str(p or rel), "name": Path(rel).name if rel else eid,
                    "system": pick(r, "system"), "category": pick(r, "category"),
                    "text": text, "tokens": tokens_of(text) | tokens_of(" ".join(map(str, r.values()))),
                    "meta": r}
            self.items.append(item)
            for t in item["tokens"]:
                self.by_token.setdefault(t, []).append(len(self.items) - 1)

    def linked_to(self, identifiers):
        idx = set()
        for t in identifiers:
            idx.update(self.by_token.get(t, []))
        return [self.items[i] for i in sorted(idx)]