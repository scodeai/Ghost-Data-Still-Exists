"""Identity resolution: who owned this email at request time? Includes historical identifiers."""
from collections import defaultdict
from common import pick, parse_ts, tokens_of, EMAIL_RE, PHONE_RE
import re


def ident_tokens(val):
    """Identifier tokens of one cell: whole phone numbers as digits (no space-splitting junk)."""
    v = str(val).strip()
    d = re.sub(r"\D", "", v)
    if 7 <= len(d) <= 15 and re.fullmatch(r"[+\d\s\-().]+", v):
        return {d, v.lower()}
    if EMAIL_RE.fullmatch(v):
        return {v.lower()}
    return tokens_of(v)

SKIP_COL_HINTS = ("created", "updated", "_at", "time", "date", "status", "flag", "count")


class IdentityGraph:
    def __init__(self, identities, audit_rows):
        self.owners = defaultdict(list)       # identifier -> [[user_id, start, end]]
        self.idents = defaultdict(set)        # user_id -> all identifiers ever held
        self.user_ids = set()
        self.name_tokens = defaultdict(set)
        for r in identities:
            uid = pick(r, "user")
            if not uid:
                continue
            self.user_ids.add(uid)
            self.idents[uid].add(uid.lower())
            for col, val in r.items():
                c = (col or "").lower()
                if not val or any(h in c for h in SKIP_COL_HINTS):
                    continue
                toks = ident_tokens(val)
                (self.name_tokens if "name" in c else self.idents)[uid].update(toks)
                if "name" not in c:
                    for t in toks:
                        self.owners[t].append([uid, None, None])
        for r in audit_rows:
            uid = pick(r, "user")
            ts = parse_ts(pick(r, "ts"))
            old, new = pick(r, "old"), pick(r, "new")
            if not uid:
                continue
            self.user_ids.add(uid)
            self.idents[uid].add(uid.lower())
            for t in ident_tokens(old) if old else ():
                self.idents[uid].add(t)
                self.owners[t].append([uid, None, ts])
            for t in ident_tokens(new) if new else ():
                self.idents[uid].add(t)
                self.owners[t].append([uid, ts, None])
        # a current owner with unknown start begins when the previous owner's tenure ended
        for t, lst in self.owners.items():
            ends = [o[2] for o in lst if o[2]]
            if ends:
                for o in lst:
                    if o[1] is None and o[2] is None:
                        o[1] = max(ends)

    def resolve(self, identifier, at):
        t = identifier.strip().lower()
        cands = self.owners.get(t, [])
        valid = [o for o in cands if (o[1] is None or at is None or o[1] <= at) and (o[2] is None or at is None or at < o[2])]
        if not valid:
            valid = cands
        if not valid:
            return None
        bounded = [o for o in valid if o[1] or o[2]]
        return (bounded or valid)[0][0]

    def identifiers(self, uid):
        return self.idents.get(uid, set())

    def direct_identifiers(self, uid):
        """Everything except the stable internal user_id (allowed on tombstones)."""
        ids = set(self.idents.get(uid, set())) | set(self.name_tokens.get(uid, set()))
        ids.discard(uid.lower())
        return ids