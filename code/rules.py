"""
Policy rules from deletion_rules.csv
Condition evaluation using heuristics and LLM fallback.
"""

import re
from common import read_csv, pick, truthy, parse_ts, EMAIL_RE
import llm


# =====================================================
# 1. RULE CLASS
# =====================================================

class Rule:
    def __init__(self, r):
        self.id = pick(r, "rule_id")
        self.category = pick(r, "data_category").upper()
        self.condition = pick(r, "condition")
        self.action = pick(r, "required_action").upper()
        self.row = r


# =====================================================
# 2. LOAD ALL DELETION RULES
# =====================================================

def load_rules(path):
    """
    Load all deletion policies from deletion_rules.csv.
    Returns a dictionary indexed by data category.
    """

    rules = {}

    for row in read_csv(path):
        rule = Rule(row)

        if not rule.category:
            raise ValueError(
                f"Missing data_category for rule {rule.id}"
            )

        if rule.action not in {
            "DELETE",
            "REDACT",
            "ANONYMIZE",
            "RETAIN"
        }:
            raise ValueError(
                f"Invalid required_action for rule {rule.id}: {rule.action}"
            )

        if rule.category in rules:
            raise ValueError(
                f"Duplicate rule category: {rule.category}"
            )

        rules[rule.category] = rule

    return rules


# =====================================================
# 3. CATEGORY IDENTIFICATION
# =====================================================

CATEGORY_HINTS = [
    ("tombstone", "ACCOUNT_TOMBSTONE"),
    ("legal", "LEGAL_HOLD_RECORD"),
    ("backup", "BACKUP_ARCHIVE"),
    ("archive", "BACKUP_ARCHIVE"),
    ("security", "SECURITY_AUDIT_LOG"),
    ("audit_log", "SECURITY_AUDIT_LOG"),
    ("email_delivery", "EMAIL_DELIVERY_LOG"),
    ("delivery", "EMAIL_DELIVERY_LOG"),
    ("marketing", "MARKETING_PROFILE"),
    ("export", "USER_EXPORT"),
    ("telemetry", "PRODUCT_TELEMETRY"),
    ("analytics", "ANALYTICS_PROFILE"),
    ("attachment", "SUPPORT_ATTACHMENT"),
    ("support", "SUPPORT_MESSAGE"),
    ("cache", "CACHE_ENTRY"),
    ("search", "SEARCH_INDEX_ENTRY"),
    ("index", "SEARCH_INDEX_ENTRY"),
    ("secondary", "SECONDARY_IDENTIFIER"),
    ("profile", "USER_PROFILE"),
    ("account", "USER_PROFILE"),
]


def infer_category(*texts):
    """
    Infer data category when the activity record
    does not contain an explicit category.
    """

    blob = " ".join(
        str(t).lower() for t in texts if t
    )

    for keyword, category in CATEGORY_HINTS:
        if keyword in blob:
            return category

    return ""


# =====================================================
# 4. CHECK BOOLEAN COLUMNS
# =====================================================

def _col_truthy(row, *hints):
    """
    Find a matching column and evaluate its boolean value.
    """

    for key, value in row.items():
        column = str(key or "").lower()

        if any(hint in column for hint in hints):
            return truthy(value), True

    return False, False


# =====================================================
# 5. EVALUATE POLICY CONDITIONS
# =====================================================

def condition_met(
    rule,
    row_cells: dict,
    text: str,
    exposes_email: bool,
    restore_blocked: bool,
    audit_at
):
    """
    Determine whether a policy condition is satisfied.
    """

    cond = rule.condition.lower().strip()

    # Rule applies unconditionally
    if cond in ("", "always"):
        return True

    # Legal hold
    if "legal hold" in cond or "hold" in cond:

        value, found = _col_truthy(
            row_cells,
            "hold"
        )

        if found:
            return value

    # Backup restoration blocked
    elif "restore" in cond and "block" in cond:

        return restore_blocked

    # Retention period
    elif "retention" in cond or "supplied" in cond:

        for key, value in row_cells.items():

            column = str(key or "").lower()

            if any(
                hint in column
                for hint in (
                    "retain_until",
                    "retention_end",
                    "expires",
                    "expiry"
                )
            ):

                date = parse_ts(value)

                if date and audit_at:
                    return date > audit_at

        value, found = _col_truthy(
            row_cells,
            "within_retention",
            "retained"
        )

        if found:
            return value

    # Email exposure
    elif "email" in cond:

        return exposes_email

    # Support attachments belonging only to subject
    elif "only" in cond and "belong" in cond:

        value, found = _col_truthy(
            row_cells,
            "shared",
            "other_user",
            "multi"
        )

        if found:
            return not value

    # Shared support conversations
    elif "shared" in cond or "order" in cond:

        value, found = _col_truthy(
            row_cells,
            "shared",
            "order"
        )

        if found:
            return value

    # Analytics or telemetry attribution
    elif "attribut" in cond:

        value, found = _col_truthy(
            row_cells,
            "attribut",
            "linked"
        )

        if found:
            return value

    # LLM fallback
    judged = llm.judge_condition(
        rule.condition,
        text
    )

    if judged is not None:
        return judged

    # Preserve the existing fallback behavior
    return True


# =====================================================
# 6. FALLBACK POLICY ACTIONS
# =====================================================

FALLBACK_ACTION = {
    "RETAIN": "DELETE",
    "REDACT": "DELETE",
    "DELETE": "DELETE",
    "ANONYMIZE": "NONE"
}


# =====================================================
# 7. DETERMINE REQUIRED ACTION
# =====================================================

def required_action(rule, **kwargs):
    """
    Return the required action for a resource.
    """

    if rule is None:
        return "DELETE"

    condition_satisfied = condition_met(
        rule,
        **kwargs
    )

    if condition_satisfied:
        return rule.action

    return FALLBACK_ACTION.get(
        rule.action,
        "DELETE"
    )