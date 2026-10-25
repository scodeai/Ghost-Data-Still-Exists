import csv, re, json
from datetime import datetime, timezone
from config import ALIASES

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\-\s().]{7,}\d")
TOKEN_RE = re.compile(r"[^\s,;|\"'<>()\[\]{}:=]+")
TRUTHY = {"1", "true", "yes", "y", "t", "active", "enabled"}


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def pick(row, key_or_names, default=""):
    names = ALIASES.get(key_or_names, [key_or_names]) if isinstance(key_or_names, str) else key_or_names
    low = {(k or "").lower().strip(): v for k, v in row.items()}
    for n in names:
        v = low.get(n)
        if v not in (None, ""):
            return str(v).strip()
    return default


def parse_ts(s):
    if not s:
        return None
    s = str(s).strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        try:
            d = datetime.strptime(s[:10], "%Y-%m-%d")
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def norm_token(t):
    t = t.strip().strip(".,;!?").lower()
    return t


def tokens_of(text):
    """Normalized identifier-like tokens of a text; phone numbers also as digit strings."""
    out = set()
    for raw in TOKEN_RE.findall(str(text)):
        t = norm_token(raw)
        if len(t) < 2:
            continue
        out.add(t)
        digits = re.sub(r"\D", "", t)
        if 7 <= len(digits) <= 15 and len(digits) >= len(t) - 4:
            out.add(digits)
    for m in EMAIL_RE.findall(str(text)):
        out.add(m.lower())
    for m in PHONE_RE.findall(str(text)):          # phones written with spaces/dashes
        d = re.sub(r"\D", "", m)
        if 7 <= len(d) <= 15:
            out.add(d)
    return out


def truthy(v):
    return str(v).strip().lower() in TRUTHY


def case_sort_key(cid):
    m = re.match(r"^(.*?)(\d+)$", cid)
    return (m.group(1), int(m.group(2))) if m else (cid, 0)


def to_json(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))