"""
Audit event emitters for tool invocations

This module provides audit logging for tool invocations to support
compliance, debugging, and security monitoring.

Features:
- Structured logging to Python logger
- Integration with task_audits table
- Policy violation tracking (high priority)
- Graceful degradation on audit failures

Example:
    from agentos.core.capabilities.audit import (
        emit_tool_invocation_start,
        emit_tool_invocation_end,
        emit_policy_violation
    )
    from agentos.core.capabilities.capability_models import ToolDescriptor

    # Log invocation start
    emit_tool_invocation_start(invocation, tool)

    # Execute tool
    result = execute_tool(invocation)

    # Log invocation end
    emit_tool_invocation_end(result, tool)

    # Log policy violation
    emit_policy_violation(invocation, tool, decision, reason)
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from agentos.core.capabilities.capability_models import (
    ToolDescriptor,
    ToolInvocation,
    ToolResult,
    PolicyDecision,
)

if TYPE_CHECKING:
    from agentos.core.capabilities.governance_models.provenance import ProvenanceStamp

logger = logging.getLogger(__name__)


def emit_tool_invocation_start(
    invocation: ToolInvocation,
    tool: ToolDescriptor
) -> None:
    """
    Emit audit event for tool invocation start

    Logs to:
    1. Python logger (structured logging)
    2. task_audits table (if task_id exists)

    Args:
        invocation: ToolInvocation object
        tool: ToolDescriptor for the tool being invoked
    """
    # Structured logging
    logger.info(
        f"Tool invocation started: {tool.name}",
        extra={
            "event_type": "tool_invocation_start",
            "invocation_id": invocation.invocation_id,
            "tool_id": tool.tool_id,
            "tool_name": tool.name,
            "task_id": invocation.task_id,
            "project_id": invocation.project_id,
            "mode": invocation.mode.value,
            "spec_frozen": invocation.spec_frozen,
            "actor": invocation.actor,
            "risk_level": tool.risk_level.value,
            "side_effects": tool.side_effect_tags,
            "timestamp": invocation.timestamp.isoformat(),
        }
    )

    # Write to task_audits table
    if invocation.task_id:
        try:
            from agentos.store import get_writer

            def _write_audit(conn):
                conn.execute("""
                    INSERT INTO task_audits (
                        task_id, event_type, level, payload, created_at
                    ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    invocation.task_id,
                    "tool_invocation_start",
                    "info",
                    json.dumps({
                        "invocation_id": invocation.invocation_id,
                        "tool_id": tool.tool_id,
                        "tool_name": tool.name,
                        "mode": invocation.mode.value,
                        "spec_frozen": invocation.spec_frozen,
                        "risk_level": tool.risk_level.value,
                        "side_effects": tool.side_effect_tags,
                        "actor": invocation.actor,
                        "project_id": invocation.project_id
                    })
                ))
                conn.commit()

            writer = get_writer()
            writer.submit(_write_audit, timeout=5.0)

        except Exception as e:
            # Graceful degradation - don't fail the operation
            logger.warning(f"Failed to write audit to task_audits: {e}")


def emit_tool_invocation_end(
    result: ToolResult,
    tool: ToolDescriptor,
    task_id: Optional[str] = None
) -> None:
    """
    Emit audit event for tool invocation end

    Logs to:
    1. Python logger (structured logging)
    2. task_audits table (if task_id exists)

    Args:
        result: ToolResult object
        tool: ToolDescriptor for the tool
        task_id: Task ID (optional, from invocation context)
    """
    level_name = "info" if result.success else "error"

    # Prepare log message
    status = "succeeded" if result.success else "failed"
    message = f"Tool invocation {status}: {tool.name}"
    if result.error:
        message += f" - {result.error}"

    logger.log(
        logging.INFO if result.success else logging.ERROR,
        message,
        extra={
            "event_type": "tool_invocation_end",
            "invocation_id": result.invocation_id,
            "tool_id": tool.tool_id,
            "tool_name": tool.name,
            "success": result.success,
            "duration_ms": result.duration_ms,
            "side_effects": result.declared_side_effects,
            "error": result.error,
            "started_at": result.started_at.isoformat() if result.started_at else None,
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
        }
    )

    # Write to task_audits table
    if task_id:
        try:
            from agentos.store import get_writer

            def _write_audit(conn):
                conn.execute("""
                    INSERT INTO task_audits (
                        task_id, event_type, level, payload, created_at
                    ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    task_id,
                    "tool_invocation_end",
                    level_name,
                    json.dumps({
                        "invocation_id": result.invocation_id,
                        "tool_id": tool.tool_id,
                        "tool_name": tool.name,
                        "success": result.success,
                        "duration_ms": result.duration_ms,
                        "side_effects": result.declared_side_effects,
                        "error": result.error,
                        "payload_summary": str(result.payload)[:200] if result.payload else None
                    })
                ))
                conn.commit()

            writer = get_writer()
            writer.submit(_write_audit, timeout=5.0)

        except Exception as e:
            # Graceful degradation
            logger.warning(f"Failed to write audit to task_audits: {e}")


def emit_policy_violation(
    invocation: ToolInvocation,
    tool: ToolDescriptor,
    decision: PolicyDecision,
    reason: str
) -> None:
    """
    Emit audit event for policy violation (HIGH PRIORITY)

    Policy violations are critical security events and should always be logged.
    Logs to:
    1. Python logger (WARNING level)
    2. task_audits table (warning level, high priority)

    Args:
        invocation: ToolInvocation object
        tool: ToolDescriptor for the tool
        decision: PolicyDecision with denial details
        reason: Reason for denial
    """
    # Structured warning log
    logger.warning(
        f"Policy violation: {tool.name} - {reason}",
        extra={
            "event_type": "policy_violation",
            "invocation_id": invocation.invocation_id,
            "tool_id": tool.tool_id,
            "tool_name": tool.name,
            "actor": invocation.actor,
            "reason": reason,
            "requires_approval": decision.requires_approval,
            "risk_level": tool.risk_level.value,
            "side_effects": tool.side_effect_tags,
            "mode": invocation.mode.value,
            "timestamp": datetime.now().isoformat(),
        }
    )

    # Write to task_audits table (use ORPHAN if no task_id)
    task_id = invocation.task_id or "ORPHAN"
    try:
        from agentos.store import get_writer

        def _write_audit(conn):
            conn.execute("""
                INSERT INTO task_audits (
                    task_id, event_type, level, payload, created_at
                ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                task_id,
                "policy_violation",
                "warning",  # High priority
                json.dumps({
                    "invocation_id": invocation.invocation_id,
                    "tool_id": tool.tool_id,
                    "tool_name": tool.name,
                    "actor": invocation.actor,
                    "reason": reason,
                    "requires_approval": decision.requires_approval,
                    "risk_level": tool.risk_level.value,
                    "side_effects": tool.side_effect_tags,
                    "mode": invocation.mode.value,
                    "project_id": invocation.project_id,
                    "approval_context": decision.approval_context
                })
            ))
            conn.commit()

        writer = get_writer()
        # Higher priority for violations - use shorter timeout
        writer.submit(_write_audit, timeout=10.0)

    except Exception as e:
        # This is critical - log error but don't fail
        logger.error(f"CRITICAL: Failed to write policy violation audit: {e}", exc_info=True)


def emit_tool_discovery(
    source_type: str,
    tool_count: int,
    error: Optional[str] = None
) -> None:
    """
    Emit audit event for tool discovery

    Args:
        source_type: Source type (extension/mcp)
        tool_count: Number of tools discovered
        error: Error message if discovery failed

    This helps track when tools are discovered or when discovery fails.
    """
    if error:
        logger.error(
            f"Tool discovery failed for {source_type}: {error}",
            extra={
                "event_type": "tool_discovery_failed",
                "source_type": source_type,
                "error": error,
                "timestamp": datetime.now().isoformat(),
            }
        )
    else:
        logger.info(
            f"Tool discovery completed for {source_type}: {tool_count} tools",
            extra={
                "event_type": "tool_discovery_success",
                "source_type": source_type,
                "tool_count": tool_count,
                "timestamp": datetime.now().isoformat(),
            }
        )


def emit_quota_warning(
    invocation: ToolInvocation,
    tool: ToolDescriptor,
    quota_state: dict
) -> None:
    """
    配额警告事件

    当配额使用接近限制(80%以上)时触发警告。

    Args:
        invocation: ToolInvocation object
        tool: ToolDescriptor for the tool
        quota_state: QuotaState as dict
    """
    logger.warning(
        f"Quota warning for {tool.name}",
        extra={
            "event_type": "quota_warning",
            "invocation_id": invocation.invocation_id,
            "tool_id": tool.tool_id,
            "tool_name": tool.name,
            "actor": invocation.actor,
            "quota_state": quota_state,
            "timestamp": datetime.now().isoformat(),
        }
    )

    # Write to task_audits table
    if invocation.task_id:
        try:
            from agentos.store import get_writer

            def _write_audit(conn):
                conn.execute("""
                    INSERT INTO task_audits (
                        task_id, event_type, level, payload, created_at
                    ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    invocation.task_id,
                    "quota_warning",
                    "warning",
                    json.dumps({
                        "invocation_id": invocation.invocation_id,
                        "tool_id": tool.tool_id,
                        "tool_name": tool.name,
                        "actor": invocation.actor,
                        "quota_state": quota_state
                    })
                ))
                conn.commit()

            writer = get_writer()
            writer.submit(_write_audit, timeout=5.0)

        except Exception as e:
            logger.warning(f"Failed to write quota warning audit: {e}")


def emit_quota_exceeded(
    invocation: ToolInvocation,
    tool: ToolDescriptor,
    reason: str
) -> None:
    """
    配额超限事件

    当配额超限导致操作被拒绝时触发。

    Args:
        invocation: ToolInvocation object
        tool: ToolDescriptor for the tool
        reason: Reason for quota exceeded
    """
    logger.error(
        f"Quota exceeded for {tool.name}: {reason}",
        extra={
            "event_type": "quota_exceeded",
            "invocation_id": invocation.invocation_id,
            "tool_id": tool.tool_id,
            "tool_name": tool.name,
            "actor": invocation.actor,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        }
    )

    # Write to task_audits table (use ORPHAN if no task_id)
    task_id = invocation.task_id or "ORPHAN"
    try:
        from agentos.store import get_writer

        def _write_audit(conn):
            conn.execute("""
                INSERT INTO task_audits (
                    task_id, event_type, level, payload, created_at
                ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                task_id,
                "quota_exceeded",
                "error",
                json.dumps({
                    "invocation_id": invocation.invocation_id,
                    "tool_id": tool.tool_id,
                    "tool_name": tool.name,
                    "actor": invocation.actor,
                    "reason": reason,
                    "project_id": invocation.project_id
                })
            ))
            conn.commit()

        writer = get_writer()
        writer.submit(_write_audit, timeout=5.0)

    except Exception as e:
        logger.error(f"Failed to write quota exceeded audit: {e}", exc_info=True)


def emit_provenance_snapshot(provenance: 'ProvenanceStamp') -> None:
    """
    记录溯源快照

    Args:
        provenance: 溯源信息
    """
    logger.info(
        f"Provenance snapshot",
        extra={
            "event_type": "provenance_snapshot",
            "invocation_id": provenance.invocation_id,
            "tool_id": provenance.tool_id,
            "source_id": provenance.source_id,
            "trust_tier": provenance.trust_tier,
            "execution_env": provenance.execution_env.model_dump(),
            "timestamp": provenance.timestamp.isoformat()
        }
    )

    # 写入 task_audits（如果有 task_id）
    if provenance.task_id:
        try:
            from agentos.store import get_writer

            def _write_audit(conn):
                conn.execute("""
                    INSERT INTO task_audits (
                        task_id, event_type, level, payload, created_at
                    ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    provenance.task_id,
                    "provenance_snapshot",
                    "info",
                    json.dumps({
                        "invocation_id": provenance.invocation_id,
                        "capability_id": provenance.capability_id,
                        "tool_id": provenance.tool_id,
                        "source_id": provenance.source_id,
                        "source_version": provenance.source_version,
                        "trust_tier": provenance.trust_tier,
                        "capability_type": provenance.capability_type,
                        "execution_env": provenance.execution_env.model_dump(),
                        "timestamp": provenance.timestamp.isoformat(),
                        "project_id": provenance.project_id,
                        "spec_hash": provenance.spec_hash
                    })
                ))
                conn.commit()

            writer = get_writer()
            writer.submit(_write_audit, timeout=5.0)

        except Exception as e:
            logger.warning(f"Failed to write provenance to task_audits: {e}")


def emit_audit_event(
    event_type: str,
    details: dict,
    task_id: Optional[str] = None,
    level: str = "info"
) -> str:
    """
    Generic audit event emitter

    Args:
        event_type: Event type identifier (e.g., "mcp_attached", "capability_enabled")
        details: Event details as dict
        task_id: Task ID (optional)
        level: Log level (info/warning/error)

    Returns:
        Audit ID for tracking
    """
    audit_id = f"audit_{uuid.uuid4().hex[:12]}"

    # Structured logging
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.log(
        log_level,
        f"Audit event: {event_type}",
        extra={
            "event_type": event_type,
            "audit_id": audit_id,
            "details": details,
            "timestamp": datetime.now().isoformat(),
        }
    )

    # Write to task_audits table if task_id provided
    if task_id:
        try:
            from agentos.store import get_writer

            def _write_audit(conn):
                conn.execute("""
                    INSERT INTO task_audits (
                        task_id, event_type, level, payload, created_at
                    ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    task_id,
                    event_type,
                    level,
                    json.dumps({
                        "audit_id": audit_id,
                        **details
                    })
                ))
                conn.commit()

            writer = get_writer()
            writer.submit(_write_audit, timeout=5.0)

        except Exception as e:
            logger.warning(f"Failed to write audit event to task_audits: {e}")

    return audit_id
