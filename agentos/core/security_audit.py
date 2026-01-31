"""
Security Audit Logging Module

This module provides centralized, structured security event logging for
all security-critical operations in AgentOS.

Features:
- Structured JSON logging for security events
- No sensitive data leakage (passwords, tokens, etc.)
- Consistent event schema across all security modules
- API for querying security events
- Integration with existing audit system

Event Types:
- xss_blocked: XSS attack attempt blocked
- ssrf_blocked: SSRF attack attempt blocked
- csrf_failed: CSRF validation failed
- auth_failed: Authentication failure
- input_rejected: Malformed/malicious input rejected
- permission_denied: Permission check failed
- quota_exceeded: Rate limit/quota exceeded

Usage:
    from agentos.core.security_audit import log_security_event

    log_security_event(
        event_type="xss_blocked",
        details={
            "payload_sample": sanitized_payload[:100],
            "endpoint": request.path,
            "threat_types": ["SCRIPT_TAG", "ONERROR"]
        },
        user_id=user_id,
        session_id=session_id
    )
"""

import json
import logging
import uuid
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional
from enum import Enum


logger = logging.getLogger(__name__)


class SecurityEventType(str, Enum):
    """Security event types."""
    XSS_BLOCKED = "xss_blocked"
    SSRF_BLOCKED = "ssrf_blocked"
    CSRF_FAILED = "csrf_failed"
    AUTH_FAILED = "auth_failed"
    INPUT_REJECTED = "input_rejected"
    PERMISSION_DENIED = "permission_denied"
    QUOTA_EXCEEDED = "quota_exceeded"
    PATH_TRAVERSAL = "path_traversal"
    SQL_INJECTION = "sql_injection"
    COMMAND_INJECTION = "command_injection"


class SecurityAuditLogger:
    """
    Security audit logger with structured event recording.

    This logger provides:
    1. Structured JSON logging
    2. Sensitive data sanitization
    3. Event persistence
    4. Query interface
    """

    def __init__(self, persist_to_db: bool = True):
        """
        Initialize security audit logger.

        Args:
            persist_to_db: Whether to persist events to database
        """
        self.persist_to_db = persist_to_db
        self._setup_logger()

    def _setup_logger(self):
        """Set up structured JSON logger for security events."""
        # Create dedicated security logger
        self.security_logger = logging.getLogger("security")
        self.security_logger.setLevel(logging.WARNING)

        # Ensure security logger has a handler
        if not self.security_logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(logging.WARNING)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.security_logger.addHandler(handler)

    def log_event(
        self,
        event_type: SecurityEventType,
        details: Dict[str, Any],
        severity: str = "warning",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """
        Log a security event with structured data.

        Args:
            event_type: Type of security event
            details: Event-specific details (will be sanitized)
            severity: Log severity (info/warning/error)
            user_id: User ID if available
            session_id: Session ID if available
            task_id: Task ID if available
            ip_address: Source IP address
            user_agent: User agent string

        Returns:
            Event ID for tracking

        Example:
            >>> logger = SecurityAuditLogger()
            >>> event_id = logger.log_event(
            ...     SecurityEventType.XSS_BLOCKED,
            ...     details={"payload": "...", "endpoint": "/api/chat"},
            ...     user_id="user_123",
            ...     session_id="sess_456"
            ... )
        """
        event_id = f"sec_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(UTC).isoformat()

        # Sanitize details to prevent sensitive data leakage
        sanitized_details = self._sanitize_details(details)

        # Build structured event
        event = {
            "event_id": event_id,
            "event_type": event_type.value,
            "timestamp": timestamp,
            "severity": severity,
            "details": sanitized_details,
            "context": {
                "user_id": user_id,
                "session_id": session_id,
                "task_id": task_id,
                "ip_address": ip_address,
                "user_agent": user_agent[:200] if user_agent else None  # Truncate
            }
        }

        # Log to Python logger as JSON
        log_level = getattr(logging, severity.upper(), logging.WARNING)
        self.security_logger.log(
            log_level,
            json.dumps(event, ensure_ascii=False)
        )

        # Persist to database if enabled
        if self.persist_to_db and task_id:
            self._persist_to_db(event, task_id)

        return event_id

    def _sanitize_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize event details to prevent sensitive data leakage.

        Rules:
        - Truncate long strings (max 500 chars)
        - Redact fields with sensitive keywords
        - Limit nested depth
        - Remove binary data

        Args:
            details: Raw event details

        Returns:
            Sanitized details
        """
        sanitized = {}

        # Keywords that indicate sensitive data
        sensitive_keywords = [
            'password', 'passwd', 'pwd',
            'token', 'api_key', 'secret',
            'credential', 'auth',
            'ssn', 'credit_card', 'cvv'
        ]

        for key, value in details.items():
            # Check if key is sensitive
            key_lower = key.lower()
            if any(keyword in key_lower for keyword in sensitive_keywords):
                sanitized[key] = "[REDACTED]"
                continue

            # Sanitize based on type
            if isinstance(value, str):
                # Truncate long strings
                if len(value) > 500:
                    sanitized[key] = value[:500] + "... [truncated]"
                else:
                    sanitized[key] = value
            elif isinstance(value, (dict, list)):
                # Limit nested structures
                sanitized[key] = str(value)[:500]
            elif isinstance(value, bytes):
                # Don't log binary data
                sanitized[key] = f"[BINARY DATA: {len(value)} bytes]"
            else:
                # Primitives (int, float, bool, None)
                sanitized[key] = value

        return sanitized

    def _persist_to_db(self, event: Dict[str, Any], task_id: str):
        """
        Persist security event to database.

        Args:
            event: Security event
            task_id: Task ID for association
        """
        try:
            from agentos.store import get_writer

            def _write_audit(conn):
                conn.execute("""
                    INSERT INTO task_audits (
                        task_id, event_type, level, payload, created_at
                    ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    task_id,
                    f"security_{event['event_type']}",
                    event['severity'],
                    json.dumps(event, ensure_ascii=False)
                ))
                conn.commit()

            writer = get_writer()
            writer.submit(_write_audit, timeout=5.0)

        except Exception as e:
            # Graceful degradation - don't fail on audit errors
            logger.warning(f"Failed to persist security event to DB: {e}")

    def query_events(
        self,
        event_type: Optional[SecurityEventType] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Query security events from database.

        Args:
            event_type: Filter by event type
            user_id: Filter by user ID
            session_id: Filter by session ID
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum number of results

        Returns:
            List of security events
        """
        # TODO: Implement database query
        # This would query the task_audits table
        return []


# ============================================
# Global Logger Instance
# ============================================

_global_security_logger: Optional[SecurityAuditLogger] = None


def get_security_logger() -> SecurityAuditLogger:
    """
    Get global security audit logger instance.

    Returns:
        Shared SecurityAuditLogger instance
    """
    global _global_security_logger
    if _global_security_logger is None:
        _global_security_logger = SecurityAuditLogger()
    return _global_security_logger


def log_security_event(
    event_type: str,
    details: Dict[str, Any],
    severity: str = "warning",
    **context
) -> str:
    """
    Convenience function to log security events.

    Args:
        event_type: Security event type (string or SecurityEventType)
        details: Event details
        severity: Log severity
        **context: Additional context (user_id, session_id, etc.)

    Returns:
        Event ID

    Example:
        >>> log_security_event(
        ...     "xss_blocked",
        ...     {"payload": "...", "endpoint": "/api"},
        ...     user_id="user_123"
        ... )
    """
    logger = get_security_logger()

    # Convert string to enum
    if isinstance(event_type, str):
        try:
            event_type = SecurityEventType(event_type)
        except ValueError:
            # Unknown event type - log as generic
            details["original_event_type"] = event_type
            event_type = SecurityEventType.INPUT_REJECTED

    return logger.log_event(
        event_type=event_type,
        details=details,
        severity=severity,
        user_id=context.get("user_id"),
        session_id=context.get("session_id"),
        task_id=context.get("task_id"),
        ip_address=context.get("ip_address"),
        user_agent=context.get("user_agent")
    )


# ============================================
# Helper Functions for Common Events
# ============================================

def log_xss_blocked(
    payload_sample: str,
    threat_types: List[str],
    endpoint: str,
    **context
) -> str:
    """
    Log XSS attack blocked event.

    Args:
        payload_sample: Sample of blocked payload (truncated)
        threat_types: List of detected threat types
        endpoint: Endpoint where attack was attempted
        **context: Additional context

    Returns:
        Event ID
    """
    return log_security_event(
        SecurityEventType.XSS_BLOCKED,
        details={
            "payload_sample": payload_sample[:200],  # Truncate
            "threat_types": threat_types,
            "endpoint": endpoint
        },
        **context
    )


def log_ssrf_blocked(
    target_url: str,
    reason: str,
    resolved_ips: Optional[List[str]] = None,
    **context
) -> str:
    """
    Log SSRF attack blocked event.

    Args:
        target_url: Blocked target URL
        reason: Reason for blocking
        resolved_ips: Resolved IP addresses (if applicable)
        **context: Additional context

    Returns:
        Event ID
    """
    return log_security_event(
        SecurityEventType.SSRF_BLOCKED,
        details={
            "target_url": target_url,
            "reason": reason,
            "resolved_ips": resolved_ips or []
        },
        **context
    )


def log_csrf_failed(
    endpoint: str,
    reason: str,
    expected_token: Optional[str] = None,
    received_token: Optional[str] = None,
    **context
) -> str:
    """
    Log CSRF validation failure.

    Args:
        endpoint: Endpoint where CSRF failed
        reason: Reason for failure
        expected_token: Expected token (first 8 chars only)
        received_token: Received token (first 8 chars only)
        **context: Additional context

    Returns:
        Event ID
    """
    return log_security_event(
        SecurityEventType.CSRF_FAILED,
        details={
            "endpoint": endpoint,
            "reason": reason,
            "expected_token_prefix": expected_token[:8] if expected_token else None,
            "received_token_prefix": received_token[:8] if received_token else None
        },
        **context
    )


def log_auth_failed(
    username: Optional[str],
    reason: str,
    auth_method: str = "password",
    **context
) -> str:
    """
    Log authentication failure.

    Args:
        username: Username (may be None for API key auth)
        reason: Reason for failure
        auth_method: Authentication method used
        **context: Additional context

    Returns:
        Event ID
    """
    return log_security_event(
        SecurityEventType.AUTH_FAILED,
        details={
            "username": username,
            "reason": reason,
            "auth_method": auth_method
        },
        severity="error",
        **context
    )


def log_input_rejected(
    input_type: str,
    reason: str,
    input_sample: Optional[str] = None,
    **context
) -> str:
    """
    Log malformed/malicious input rejection.

    Args:
        input_type: Type of input (e.g., "session_title", "message")
        reason: Reason for rejection
        input_sample: Sample of rejected input (truncated)
        **context: Additional context

    Returns:
        Event ID
    """
    return log_security_event(
        SecurityEventType.INPUT_REJECTED,
        details={
            "input_type": input_type,
            "reason": reason,
            "input_sample": input_sample[:200] if input_sample else None
        },
        **context
    )


# ============================================
# Testing Helper
# ============================================

def reset_security_logger():
    """Reset global security logger (for testing)."""
    global _global_security_logger
    _global_security_logger = None
