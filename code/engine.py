"""Core deletion-audit engine: identity -> evidence -> policy -> status + ordered steps."""

import re
from collections import defaultdict

import config as C
from common import read_csv, pick, parse_ts, tokens_of
from identity import IdentityGraph
from evidence import EvidenceStore
import rules as R
import llm


# =========================
# OPERATION KEYWORDS
# =========================

STOP_W = (
    "stop", "disabl", "paus", "cancel", "revok",
    "halt", "block", "suspend", "terminat"
)

REMOVE_W = (
    "delet", "purg", "erase", "remov",
    "drop", "wipe", "shred"
)

ANON_W = ("anonym",)

REDACT_W = ("redact", "scrub", "mask")

PROC_W = (
    "sync", "import", "restore", "replicat",
    "backfill", "pipeline", "cron",
    "schedul", "rehydrat"
)

CREATE_W = (
    "creat", "insert", "write", "index",
    "export", "backup", "upsert", "recreat",
    "load", "snapshot", "ingest", "copy",
    "attach", "upload", "provision",
    "signup", "register"
)

NO_EFFECT = (
    "fail", "error", "denied", "skipp",
    "timeout", "block", "stopp",
    "disabl", "cancel", "paus", "suspend"
)

INACTIVE = (
    "stopp", "disabl", "cancel", "paus",
    "suspend", "block", "complet",
    "done", "fail", "off", "terminat"
)


NOT_DELETE_PAT = re.compile(
    r"(do not|don't|dont|never|no longer want( you)? to)"
    r"\s+(delete|erase|remove|close)|"
    r"cancel\w*\s+(my|the|this)?\s*"
    r"(deletion|delete|erasure|request)|"
    r"withdraw|changed my mind|"
    r"keep my account|reactivate",
    re.I
)

DELETE_PAT = re.compile(
    r"delet|erase|erasure|remov|"
    r"close\b.*\baccount|forget|permanent",
    re.I
)


# =========================
# OPERATION CLASSIFICATION
# =========================

def classify(op):

    o = str(op or "").lower().strip()

    if not o:
        return "other"

    if "restore" in o and any(
        w in o for w in ("block", "disabl", "prevent")
    ):
        return "restore_block"

    if any(w in o for w in ANON_W):
        return "anonymize"

    if any(w in o for w in REDACT_W):
        return "redact"

    if any(w in o for w in STOP_W):
        return "stop"

    if any(w in o for w in REMOVE_W):
        return "remove"

    if any(w in o for w in PROC_W):
        return "process"

    if any(w in o for w in CREATE_W):
        return "create"

    return "other"


# =========================
# RESOURCE CLASS
# =========================

class Res:

    def __init__(self, system, resource, category):

        self.system = system
        self.resource = resource
        self.category = category

        self.state = None
        self.exposes = True

        self.evidence = ""
        self.cells = {}

        self.failed_removal = False


# =========================
# MAIN AUDIT ENGINE
# =========================

class Engine:

    def __init__(self, dataset, use_llm=True):

        self.ds = dataset

        if not use_llm:
            llm.ENABLED = False

        self.rules = R.load_rules(
            dataset / "deletion_rules.csv"
        )

        self.graph = IdentityGraph(
            read_csv(dataset / "user_identities.csv"),
            read_csv(dataset / "user_audit_log.csv")
        )

        self.evidence = EvidenceStore(dataset)

        self.acts = []
        self.index = defaultdict(set)

        for i, r in enumerate(
            read_csv(dataset / "system_activity.csv")
        ):

            a = {
                "i": i,
                "row": r,
                "ts": parse_ts(pick(r, "ts")),
                "system": pick(r, "system"),
                "resource": pick(r, "resource"),
                "op": pick(r, "operation"),
                "category": pick(r, "category").upper(),
                "status": pick(r, "status").lower(),
                "evidence": pick(r, "evidence"),
                "job": pick(r, "job"),
                "user": pick(r, "user")
            }

            a["cls"] = classify(a["op"])

            a["tokens"] = tokens_of(
                " ".join(map(str, r.values()))
            )

            if not a["category"]:
                a["category"] = R.infer_category(
                    a["system"],
                    a["resource"],
                    a["op"]
                )

            self.acts.append(a)

            for token in a["tokens"]:
                self.index[token].add(i)

    # =========================
    # DELETION INTENT
    # =========================

    def wants_deletion(self, text):

        text = str(text or "")

        if NOT_DELETE_PAT.search(text):
            return False

        guess = llm.classify_intent(text)

        if guess:
            return guess == "DELETE"

        return bool(DELETE_PAT.search(text))

    # =========================
    # MAIN AUDIT FUNCTION
    # =========================

    def audit(self, case):

        email = pick(case, ["email"])

        req_at = parse_ts(
            pick(case, ["requested_at"])
        )

        audit_at = parse_ts(
            pick(case, ["audit_at"])
        )

        text = pick(case, ["request_text"])

        if not self.wants_deletion(text):
            return "NOT_APPLICABLE", []

        uid = self.graph.resolve(email, req_at)

        if uid is None:
            return "NOT_APPLICABLE", []

        ids = self.graph.identifiers(uid)
        direct = self.graph.direct_identifiers(uid)

        hit = set()

        for token in ids:
            hit |= self.index.get(token, set())

        rows = []

        for i in sorted(hit):

            a = self.acts[i]

            valid_user = (
                not a["user"]
                or a["user"].lower() == uid.lower()
                or a["user"] not in self.graph.user_ids
            )

            valid_time = (
                a["ts"] is None
                or audit_at is None
                or a["ts"] <= audit_at
            )

            if valid_user and valid_time:
                rows.append(a)

        rows.sort(
            key=lambda a: (
                a["ts"].timestamp()
                if a["ts"] else -1,
                a["i"]
            )
        )

        # Check cancellation of deletion request

        for a in rows:

            operation = a["op"].lower()

            cancelled = any(
                word in operation
                for word in ("cancel", "withdraw", "revok")
            )

            deletion_request = any(
                word in operation
                for word in ("delet", "erasure", "request")
            )

            valid_time = (
                req_at is None
                or a["ts"] is None
                or a["ts"] >= req_at
            )

            if cancelled and deletion_request and valid_time:
                return "NOT_APPLICABLE", []

        (
            resources,
            procs,
            blocked_sys,
            blocked_res
        ) = self._fold(rows, direct)

        self._add_evidence_resources(
            resources,
            ids,
            audit_at
        )

        plan = []

        for res in resources.values():

            rule = self.rules.get(res.category)

            text_blob = " ".join(
                map(str, res.cells.values())
            )

            direct_tokens = {
                str(identifier).lower()
                for identifier in direct
            }

            exposes_email = any(
                "@" in token
                and token.lower() in direct_tokens
                for token in tokens_of(text_blob)
            )

            action = R.required_action(
                rule,
                row_cells=res.cells,
                text=text_blob,
                exposes_email=exposes_email,
                restore_blocked=(
                    res.system in blocked_sys
                    or res.resource in blocked_res
                ),
                audit_at=audit_at
            )

            compliant = self._compliant(
                res,
                action
            )

            plan.append(
                (res, action, compliant)
            )

        active = [
            p for p in procs.values()
            if p["active"]
        ]

        incomplete = (
            any(not ok for _, _, ok in plan)
            or bool(active)
        )

        status = (
            "INCOMPLETE"
            if incomplete
            else "COMPLETE"
        )

        steps = self._steps(
            plan,
            active,
            incomplete
        )

        return status, steps

    # =========================
    # ACTIVITY TIMELINE
    # =========================

    def _fold(self, rows, direct):

        resources = {}
        procs = {}

        blocked_sys = set()
        blocked_res = set()

        for a in rows:

            cls = a["cls"]

            bad = any(
                word in a["status"]
                for word in NO_EFFECT
            )

            if cls == "restore_block" and not bad:

                if a["system"]:
                    blocked_sys.add(a["system"])

                if a["resource"]:
                    blocked_res.add(a["resource"])

            if cls in ("process", "stop"):

                key = (
                    a["job"]
                    or a["system"]
                    or a["op"]
                )

                p = procs.setdefault(
                    key,
                    {
                        "key": key,
                        "system": a["system"],
                        "resource": a["resource"],
                        "active": False,
                        "evidence": a["evidence"],
                        "last_ts": None
                    }
                )

                if cls == "process":

                    p.update(
                        active=not any(
                            word in a["status"]
                            for word in INACTIVE
                        ),
                        system=(
                            a["system"]
                            or p["system"]
                        ),
                        resource=(
                            a["resource"]
                            or p["resource"]
                        ),
                        evidence=(
                            a["evidence"]
                            or p["evidence"]
                        )
                    )

                elif not bad and "delet" not in a["op"].lower():
                    p["active"] = False

            if not (
                a["system"] or a["resource"]
            ):
                continue

            if cls in (
                "stop",
                "restore_block",
                "other"
            ):
                continue

            if cls == "process" and not a["category"]:
                continue

            key = (
                a["system"],
                a["resource"] or a["category"]
            )

            res = resources.setdefault(
                key,
                Res(
                    a["system"],
                    a["resource"] or key[1],
                    a["category"]
                )
            )

            res.category = (
                res.category or a["category"]
            )

            if a["evidence"]:
                res.evidence = a["evidence"]

            exposes = any(
                token in direct
                for token in a["tokens"]
            )

            if cls in ("create", "process") and not bad:

                res.state = "PRESENT"
                res.exposes = exposes
                res.cells = dict(a["row"])
                res.failed_removal = False

            elif cls == "remove":

                if bad:
                    res.failed_removal = True

                else:
                    res.state = "REMOVED"
                    res.exposes = False
                    res.failed_removal = False

            elif cls == "anonymize" and not bad:

                res.state = "ANONYMIZED"
                res.exposes = False

            elif cls == "redact" and not bad:

                res.state = "REDACTED"
                res.exposes = False

        return (
            {
                k: v
                for k, v in resources.items()
                if v.state
            },
            procs,
            blocked_sys,
            blocked_res
        )

    # =========================
    # EVIDENCE RESOURCES
    # =========================

    def _add_evidence_resources(
        self,
        resources,
        ids,
        audit_at
    ):

        used = {
            r.evidence
            for r in resources.values()
            if r.evidence
        }

        sig = [
            token
            for token in ids
            if len(token) >= 5
        ]

        for item in self.evidence.linked_to(sig):

            if item["id"] in used:
                continue

            category = (
                item["category"]
                or R.infer_category(
                    item["name"],
                    item["system"]
                )
            ).upper()

            if category not in self.rules:
                continue

            ts = parse_ts(
                pick(item["meta"], "ts")
            )

            if ts and audit_at and ts > audit_at:
                continue

            state = (
                llm.evidence_state(
                    item["text"],
                    category
                )
                if item["text"]
                else None
            )

            if state is None:

                low = item["text"].lower()

                gone = any(
                    word in low
                    for word in (
                        "deleted",
                        "purged",
                        "erased",
                        "anonymized",
                        "redacted",
                        "removed"
                    )
                )

                state = (
                    "REMOVED"
                    if gone
                    and "still" not in low
                    and "present" not in low
                    else "PRESENT"
                )

            if state == "PRESENT":

                r = Res(
                    item["system"] or "evidence",
                    item["name"],
                    category
                )

                r.state = "PRESENT"
                r.exposes = True
                r.evidence = item["id"]
                r.cells = dict(item["meta"])

                resources[
                    (r.system, r.resource)
                ] = r

    # =========================
    # COMPLIANCE CHECK
    # =========================

    @staticmethod
    def _compliant(res, action):

        state = res.state

        if action == "NONE":
            return True

        if action == "DELETE":
            return state == "REMOVED"

        if action == "REDACT":
            return (
                state in ("REDACTED", "REMOVED")
                or (
                    state == "PRESENT"
                    and not res.exposes
                )
            )

        if action == "ANONYMIZE":
            return (
                state in ("ANONYMIZED", "REMOVED")
                or (
                    state == "PRESENT"
                    and not res.exposes
                )
            )

        if action == "RETAIN":
            return state != "REMOVED"

        return False

    # =========================
    # REMEDIATION STEPS
    # =========================

    def _steps(self, plan, active, incomplete):

        steps = []

        def add(phase, system, resource, op, state, ev):

            steps.append({
                "step_no": len(steps) + 1,
                "phase": phase,
                "system_id": system,
                "resource_id": resource,
                "operation": op,
                "state": state,
                "evidence_id": ev
            })

        order = {
            category: i
            for i, category in enumerate(
                C.REMEDIATION_ORDER
            )
        }

        def sort_key(item):

            res = item[0]

            return (
                order.get(res.category, 99),
                res.system,
                res.resource
            )

        todo = sorted(
            [
                item
                for item in plan
                if not item[2]
            ],
            key=sort_key
        )

        OPS = {
            "DELETE": (
                C.OP_DELETE,
                C.STATE_DELETED
            ),
            "REDACT": (
                C.OP_REDACT,
                C.STATE_REDACTED
            ),
            "ANONYMIZE": (
                C.OP_ANONYMIZE,
                C.STATE_ANON
            )
        }

        if incomplete:

            # Report non-compliant resources
            for res, action, ok in todo:

                add(
                    C.PHASE_FINDING,
                    res.system,
                    res.resource,
                    C.OP_REPORT,
                    C.STATE_PRESENT,
                    res.evidence
                )

            # Report active processes
            for p in active:

                add(
                    C.PHASE_FINDING,
                    p["system"],
                    p["resource"] or p["key"],
                    C.OP_REPORT_PROCESS,
                    C.STATE_ACTIVE,
                    p["evidence"]
                )

            # Stop active processes
            for p in active:

                add(
                    C.PHASE_CONTAIN,
                    p["system"],
                    p["resource"] or p["key"],
                    C.OP_STOP,
                    C.STATE_STOPPED,
                    p["evidence"]
                )

            # Remediate resources
            for res, action, ok in todo:

                if action == "RETAIN":
                    continue

                operation, state = OPS.get(
                    action,
                    OPS["DELETE"]
                )

                add(
                    C.PHASE_REMEDIATE,
                    res.system,
                    res.resource,
                    operation,
                    state,
                    res.evidence
                )

        # Verification steps
        for res, action, ok in sorted(
            plan,
            key=sort_key
        ):

            if action == "RETAIN":

                add(
                    C.PHASE_VERIFY,
                    res.system,
                    res.resource,
                    C.OP_VERIFY_RETAINED,
                    C.STATE_RETAINED,
                    res.evidence
                )

            elif action in ("REDACT", "ANONYMIZE"):

                add(
                    C.PHASE_VERIFY,
                    res.system,
                    res.resource,
                    C.OP_VERIFY_CLEAN,
                    (
                        C.STATE_REDACTED
                        if action == "REDACT"
                        else C.STATE_ANON
                    ),
                    res.evidence
                )

            elif action == "DELETE":

                add(
                    C.PHASE_VERIFY,
                    res.system,
                    res.resource,
                    C.OP_VERIFY_ABSENT,
                    C.STATE_DELETED,
                    res.evidence
                )

        # Verify stopped processes
        for p in active:

            add(
                C.PHASE_VERIFY,
                p["system"],
                p["resource"] or p["key"],
                C.OP_VERIFY_PROCESS,
                C.STATE_STOPPED,
                p["evidence"]
            )

        return steps