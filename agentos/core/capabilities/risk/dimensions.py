"""
Risk Dimension Calculators

Each dimension calculator is a pure function that takes execution history
and returns a normalized risk value (0-1).

All calculations are deterministic and based on measurable facts.
"""

import json
from typing import List, Dict, Optional
import statistics


def calc_write_ratio(executions: List[Dict]) -> tuple[float, str]:
    """
    Calculate write operation ratio.

    Risk factor: Extensions that frequently perform write operations
    have higher potential impact.

    Args:
        executions: List of execution records with metadata

    Returns:
        Tuple of (normalized_score, details_string)
        normalized_score: 0-1, proportion of write operations
        details_string: Human-readable explanation
    """
    if not executions:
        return 0.0, "No execution history"

    write_count = 0
    total = len(executions)

    for execution in executions:
        metadata = execution.get('metadata')
        if metadata:
            try:
                meta_dict = json.loads(metadata) if isinstance(metadata, str) else metadata
                # Check for write indicators in metadata
                if is_write_action(meta_dict):
                    write_count += 1
            except (json.JSONDecodeError, TypeError):
                pass

    ratio = write_count / total if total > 0 else 0.0
    details = f"{write_count}/{total} executions involved write operations"
    return ratio, details


def is_write_action(metadata: Dict) -> bool:
    """
    Determine if an action involves write operations.

    Checks metadata for write indicators:
    - action_type contains 'write', 'create', 'update', 'delete', 'modify'
    - has_writes flag is True
    - file_operations contains write-like operations

    Args:
        metadata: Execution metadata dictionary

    Returns:
        True if action involves writes
    """
    if not metadata:
        return False

    # Direct write flag
    if metadata.get('has_writes') or metadata.get('write_access'):
        return True

    # Action type indicators
    action_type = metadata.get('action_type', '').lower()
    write_keywords = ['write', 'create', 'update', 'delete', 'modify', 'remove', 'add']
    if any(keyword in action_type for keyword in write_keywords):
        return True

    # File operation indicators
    file_ops = metadata.get('file_operations', [])
    if isinstance(file_ops, list):
        for op in file_ops:
            if isinstance(op, str) and any(keyword in op.lower() for keyword in write_keywords):
                return True

    # Command indicators (for shell runners)
    command = metadata.get('command', '').lower()
    dangerous_commands = ['rm', 'mv', 'cp', 'mkdir', 'touch', 'chmod', 'chown']
    if any(cmd in command for cmd in dangerous_commands):
        return True

    return False


def calc_external_call(executions: List[Dict]) -> tuple[float, str]:
    """
    Calculate external call risk.

    Risk factor: Extensions that make network/external API calls
    have higher security implications.

    Args:
        executions: List of execution records with metadata

    Returns:
        Tuple of (normalized_score, details_string)
        normalized_score: 0 (no external calls) or 1 (has external calls)
    """
    if not executions:
        return 0.0, "No execution history"

    has_external = False
    external_count = 0

    for execution in executions:
        metadata = execution.get('metadata')
        if metadata:
            try:
                meta_dict = json.loads(metadata) if isinstance(metadata, str) else metadata
                if check_external_access(meta_dict):
                    has_external = True
                    external_count += 1
            except (json.JSONDecodeError, TypeError):
                pass

    if has_external:
        details = f"{external_count}/{len(executions)} executions involved external calls"
        return 1.0, details
    else:
        details = "No external calls detected"
        return 0.0, details


def check_external_access(metadata: Dict) -> bool:
    """
    Check if execution involved external network access.

    Args:
        metadata: Execution metadata dictionary

    Returns:
        True if external access detected
    """
    if not metadata:
        return False

    # Direct network flag
    if metadata.get('network_access') or metadata.get('external_call'):
        return True

    # HTTP/API indicators
    if metadata.get('http_requests') or metadata.get('api_calls'):
        return True

    # URL indicators in command or args
    command = str(metadata.get('command', '')).lower()
    args = str(metadata.get('args', '')).lower()
    network_indicators = ['http://', 'https://', 'curl', 'wget', 'fetch', 'request', 'api']
    if any(indicator in command or indicator in args for indicator in network_indicators):
        return True

    return False


def calc_failure_rate(executions: List[Dict]) -> tuple[float, str]:
    """
    Calculate historical failure rate.

    Risk factor: Extensions with high failure rates may be unstable
    or problematic.

    Args:
        executions: List of execution records with exit_code

    Returns:
        Tuple of (normalized_score, details_string)
        normalized_score: 0-1, proportion of failed executions
    """
    if not executions:
        return 0.0, "No execution history"

    failed_count = 0
    total = len(executions)

    for execution in executions:
        exit_code = execution.get('exit_code')
        status = execution.get('status')

        # Count as failure if:
        # 1. exit_code is non-zero
        # 2. status is 'failed' or 'blocked'
        if exit_code is not None and exit_code != 0:
            failed_count += 1
        elif status in ['failed', 'blocked']:
            failed_count += 1

    rate = failed_count / total if total > 0 else 0.0
    details = f"{failed_count}/{total} executions failed"
    return rate, details


def calc_revoke_count(db_path: str, extension_id: str) -> tuple[float, str]:
    """
    Calculate authorization revoke history.

    Risk factor: Extensions that have been revoked frequently
    may have trust issues.

    Args:
        db_path: Path to database
        extension_id: Extension identifier

    Returns:
        Tuple of (normalized_score, details_string)
        normalized_score: 0-1, normalized by max expected revokes (5)
    """
    import sqlite3

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Count revoked authorizations
        cursor.execute(
            """
            SELECT COUNT(*) FROM extension_authorizations
            WHERE extension_id = ? AND status = 'revoked'
            """,
            (extension_id,)
        )
        revoke_count = cursor.fetchone()[0]
        conn.close()

        # Normalize: cap at 5 revokes = 1.0 risk
        normalized = min(revoke_count / 5.0, 1.0)
        details = f"{revoke_count} authorization(s) revoked"
        return normalized, details

    except Exception as e:
        # If query fails, return neutral score
        return 0.0, f"Unable to query revoke history: {str(e)}"


def calc_duration_anomaly(executions: List[Dict]) -> tuple[float, str]:
    """
    Calculate execution duration anomaly.

    Risk factor: Executions with unusual duration may indicate
    unexpected behavior or resource issues.

    Args:
        executions: List of execution records with duration_ms

    Returns:
        Tuple of (normalized_score, details_string)
        normalized_score: 0-1, degree of deviation from P95
    """
    if not executions:
        return 0.0, "No execution history"

    durations = []
    for execution in executions:
        duration_ms = execution.get('duration_ms')
        if duration_ms is not None and duration_ms > 0:
            durations.append(duration_ms)

    if len(durations) < 3:
        return 0.0, f"Insufficient duration data ({len(durations)} samples)"

    try:
        # Calculate P95
        p95 = statistics.quantiles(durations, n=20)[18]  # 95th percentile

        # Find max duration
        max_duration = max(durations)

        # Calculate anomaly score
        if p95 > 0:
            deviation = (max_duration - p95) / p95
            # Normalize: 2x P95 = 1.0 risk
            normalized = min(deviation / 2.0, 1.0) if deviation > 0 else 0.0
        else:
            normalized = 0.0

        details = f"Max duration: {max_duration}ms, P95: {int(p95)}ms"
        return max(normalized, 0.0), details

    except Exception as e:
        return 0.0, f"Duration calculation error: {str(e)}"
