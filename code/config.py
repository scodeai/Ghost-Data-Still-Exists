"""Central configuration. EDIT the ASSUMED constants after reading problem_statement.md
(lines ~100-162: steps_json schema, allowed phases/operations/states)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "dataset"

# ---- steps_json vocabulary (ASSUMED: verify against problem_statement.md) ----
PHASE_FINDING = "FINDING"            # seen in the problem statement example
PHASE_CONTAIN = "CONTAINMENT"        # ASSUMED
PHASE_REMEDIATE = "REMEDIATION"      # ASSUMED
PHASE_VERIFY = "VERIFICATION"        # ASSUMED

OP_REPORT = "REPORT_REMAINING_RECORD"    # the screenshot shows "REPORT_REMAINING_RE..." (cut off)
OP_REPORT_PROCESS = "REPORT_ACTIVE_PROCESS"  # ASSUMED
OP_STOP = "DISABLE_PROCESS"              # ASSUMED
OP_DELETE = "DELETE_RECORD"              # ASSUMED
OP_REDACT = "REDACT_FIELDS"              # ASSUMED
OP_ANONYMIZE = "ANONYMIZE_RECORD"        # ASSUMED
OP_VERIFY_ABSENT = "VERIFY_ABSENT"       # ASSUMED
OP_VERIFY_CLEAN = "VERIFY_NO_DIRECT_IDENTIFIERS"  # ASSUMED
OP_VERIFY_RETAINED = "VERIFY_RETAINED"   # ASSUMED
OP_VERIFY_PROCESS = "VERIFY_PROCESS_STOPPED"      # ASSUMED

STATE_PRESENT = "PRESENT"            # seen in the problem statement example
STATE_ACTIVE = "ACTIVE"              # ASSUMED
STATE_DELETED = "DELETED"            # ASSUMED
STATE_REDACTED = "REDACTED"          # ASSUMED
STATE_ANON = "ANONYMIZED"            # ASSUMED
STATE_RETAINED = "RETAINED"          # ASSUMED
STATE_STOPPED = "STOPPED"            # ASSUMED

# Order in which categories are remediated (derived copies first, source of truth last). ASSUMED.
REMEDIATION_ORDER = [
    "SEARCH_INDEX_ENTRY", "CACHE_ENTRY", "SECONDARY_IDENTIFIER", "SUPPORT_ATTACHMENT",
    "SUPPORT_MESSAGE", "USER_EXPORT", "MARKETING_PROFILE", "ANALYTICS_PROFILE",
    "PRODUCT_TELEMETRY", "EMAIL_DELIVERY_LOG", "BACKUP_ARCHIVE", "USER_PROFILE",
    "ACCOUNT_TOMBSTONE",
]

# Column-name aliases so the code adapts to the real headers (case-insensitive).
ALIASES = {
    "ts": ["timestamp", "occurred_at", "event_time", "event_at", "time", "created_at", "ts", "at", "date", "changed_at"],
    "user": ["user_id", "subject_id", "account_id", "customer_id", "uid"],
    "system": ["system_id", "system", "source_system", "service", "target_system", "store"],
    "resource": ["resource_id", "record_id", "object_id", "entity_id", "target_id", "item_id"],
    "operation": ["operation", "action", "activity_type", "event_type", "event", "type", "activity", "op"],
    "category": ["data_category", "category", "record_type", "resource_type"],
    "status": ["status", "state", "result", "outcome"],
    "evidence": ["evidence_id", "evidence", "evidence_ref", "evidence_file"],
    "job": ["job_id", "process_id", "pipeline_id", "sync_job_id", "task_id"],
    "ev_path": ["path", "file_path", "filepath", "file", "filename", "file_name", "location"],
    "old": ["old_value", "previous_value", "from_value", "before", "old"],
    "new": ["new_value", "to_value", "after", "new"],
    "field": ["field", "attribute", "field_name", "changed_field"],
    "rule_id": ["rule_id"], "rule_cat": ["data_category"], "rule_cond": ["condition"],
    "rule_action": ["required_action", "action"],
}