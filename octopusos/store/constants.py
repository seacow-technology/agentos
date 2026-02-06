"""
Database table name constants

Centralized table names to avoid mismatches across codebase.
Always import from here instead of hardcoding strings.

Schema version: v23
"""

# Content Management (v23 schema - NEW system)
CONTENT_TABLE = "content_items"

# Answers Management (v23 schema)
ANSWER_PACKS_TABLE = "answer_packs"
ANSWER_LINKS_TABLE = "answer_pack_links"

# Schema Version Tracking
SCHEMA_VERSION_TABLE = "schema_version"

# Audit (v20+ schema)
TASK_AUDITS_TABLE = "task_audits"

# ============================================
# Legacy Content System (v05 schema - OLD system)
# ============================================
# NOTE: These tables are part of the OLD content system
# and should NOT be confused with the NEW system above.
# They coexist for backward compatibility.

LEGACY_CONTENT_REGISTRY_TABLE = "content_registry"  # OLD system
LEGACY_CONTENT_LINEAGE_TABLE = "content_lineage"    # OLD system
LEGACY_CONTENT_AUDIT_LOG_TABLE = "content_audit_log"  # OLD system
