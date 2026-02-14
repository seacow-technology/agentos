"""Central audit allowlists for WebUI timeline-style pages.

These are explicit enums (reviewable + versionable) to keep /action-log and
/decision-timeline from degrading into "log garbage dumps" as audit volume grows.

Notes:
- These event_type strings correspond to compat_audit_events.event_type
  written via octopusos.webui.api.compat_state.audit_event(...).
- include_noise=1 on the endpoints bypasses these allowlists for debugging.
"""

from __future__ import annotations

import re


# Naming convention for audit event types.
# Keep this tight so allowlists remain reviewable and stable.
_EVENT_TYPE_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")


# Action-like audit events (execution, side effects, writes, dispatches).
#
# Criteria:
# - Represents an execution step or a mutation with observable side effects.
# - Excludes read-only probes and UI-only/telemetry noise.
ACTION_EVENT_TYPES: tuple[str, ...] = (
    # Dispatch / execution
    # - Capability/dispatch layer actions
    "capability_dispatch",
    # - Remote execution actions
    "remote_execute",
    "remote_connection_delete",

    # Content + context mutations (side effects visible to users/agents)
    "context_attach",
    "context_detach",
    "context_refresh",
    "content_update",
    "snippet_create",
    "snippet_update",
    "snippet_delete",
    "answer_pack_create",
    "skill_install",

    # Mode changes (mutates runtime behavior)
    "communication_mode_set",
    "demo_mode_enable",
    "demo_mode_disable",

    # Budget/config writes (mutates runtime config)
    "budget_global_update",

    # Local shell (terminal)
    "shell.session.create",
    "shell.input",
    "shell.detach",
    "shell.resume",
    "shell.session.close",

    # SSH inventory + connections
    "ssh.host.create",
    "ssh.host.update",
    "ssh.host.delete",
    "ssh.connection.open",
    "ssh.connection.detach",
    "ssh.connection.attach",
    "ssh.connection.close",
    "ssh.exec.requested",
    "ssh.exec.completed",
    "known_hosts.missing",
    "known_hosts.trusted",
    "ssh.auth_ref_compat_used",
    "ssh.connection.expired",

    # Keychain + known_hosts
    "keychain.secret.create",
    "keychain.secret.update",
    "keychain.secret.delete",
    "known_hosts.add",
    "known_hosts.remove",
    "known_hosts.replace.confirm_required",
    "known_hosts.replaced",

    # SFTP operations
    "sftp.session.open",
    "sftp.upload",
    "sftp.download",
    "sftp.list",
    "sftp.remove",
    "sftp.remove.confirm_required",

    # Aggregated logs query
    "logs.query",
    "logs.export",

    # Execution aliases runtime management
    "execution_aliases.upsert.confirm_required",
    "execution_aliases.upsert",
    "execution_aliases.delete.confirm_required",
    "execution_aliases.delete",
    "execution_aliases.reload",
    "execution_aliases.export",
    "execution_aliases.db_init.confirm_required",
    "execution_aliases.db_init",

    # SSH provider selection governance
    "ssh_provider.upsert.confirm_required",
    "ssh_provider.upsert",
    "ssh_provider.reload",
    "ssh_provider.db_init.confirm_required",
    "ssh_provider.db_init",
    "ssh_provider.export",
)


# Decision-like audit events (verdicts, gates, approvals).
#
# Criteria:
# - Represents an explicit allow/confirm/block decision or governance verdict.
# - Intentionally narrow; expand only with strong justification.
DECISION_EVENT_TYPES: tuple[str, ...] = (
    # Policy enforcement decisions
    "execution_policy_create",
    "execution_policy_update",
    "execution_policy_delete",

    # Review queue decisions
    "review_queue_approve",
    "review_queue_reject",

    # Marketplace governance decisions
    "capability_approve",
    "capability_reject",
    "publisher_trust_patch",
)


def validate_audit_allowlists() -> None:
    """Fail-fast invariants for allowlists.

    Called by unit tests to prevent regressions:
    - disjoint sets (no event is both "action" and "decision")
    - non-empty lists
    - naming convention
    """

    action = set(ACTION_EVENT_TYPES)
    decision = set(DECISION_EVENT_TYPES)

    if not action:
        raise AssertionError("ACTION_EVENT_TYPES must be non-empty")
    if not decision:
        raise AssertionError("DECISION_EVENT_TYPES must be non-empty")

    overlap = sorted(action & decision)
    if overlap:
        raise AssertionError(f"Allowlist overlap not allowed: {overlap}")

    bad = sorted([x for x in (action | decision) if not _EVENT_TYPE_RE.match(x)])
    if bad:
        raise AssertionError(f"Invalid event_type naming: {bad}")
