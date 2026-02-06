"""
Utility functions for dry executor
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict
from agentos.core.time import utc_now_iso



def compute_checksum(data: Dict[str, Any], exclude_keys: list[str] = None) -> str:
    """
    Compute SHA-256 checksum of a data structure.
    
    Args:
        data: Dictionary to compute checksum for
        exclude_keys: Keys to exclude from checksum (e.g., 'checksum' itself)
    
    Returns:
        64-character hex string (SHA-256)
    """
    if exclude_keys is None:
        exclude_keys = ["checksum", "created_at", "timestamp"]
    
    # Create a copy without excluded keys
    filtered_data = {k: v for k, v in data.items() if k not in exclude_keys}
    
    # Serialize to canonical JSON (sorted keys, no whitespace)
    canonical = json.dumps(filtered_data, sort_keys=True, separators=(',', ':'))
    
    # Compute SHA-256
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def generate_id(prefix: str, source_data: str = None) -> str:
    """
    Generate a unique ID with the given prefix.
    
    Args:
        prefix: ID prefix (e.g., 'dryexec', 'graph', 'patchplan')
        source_data: Optional data to use for deterministic ID generation
    
    Returns:
        ID string in format: {prefix}_{hash}
    """
    if source_data:
        # Deterministic ID based on source data
        hash_part = hashlib.sha256(source_data.encode('utf-8')).hexdigest()[:16]
    else:
        # Random ID based on timestamp
        hash_part = hashlib.sha256(
            f"{prefix}_{utc_now_iso()}".encode('utf-8')
        ).hexdigest()[:16]
    
    return f"{prefix}_{hash_part}"


def validate_path_in_intent(path: str, intent: Dict[str, Any]) -> bool:
    """
    Check if a file path is explicitly mentioned in the intent.
    Enforces DE3 (no path fabrication).
    
    Args:
        path: File path to validate
        intent: ExecutionIntent dictionary
    
    Returns:
        True if path is in intent.scope.targets.files or evidence_refs
    """
    # Check in scope.targets.files
    target_files = intent.get("scope", {}).get("targets", {}).get("files", [])
    if path in target_files:
        return True
    
    # Check in evidence_refs (might reference file paths)
    evidence_refs = intent.get("evidence_refs", [])
    for ref in evidence_refs:
        if path in ref or ref.endswith(path):
            return True
    
    # Check in planned_commands evidence_refs
    for cmd in intent.get("planned_commands", []):
        for ref in cmd.get("evidence_refs", []):
            if path in ref or ref.endswith(path):
                return True
    
    return False


def enforce_red_lines(result_data: Dict[str, Any]) -> list[str]:
    """
    Validate that all red lines (DE1-DE6) are enforced in the result.
    
    Args:
        result_data: Dry execution result data
    
    Returns:
        List of violations (empty if all red lines satisfied)
    """
    violations = []
    
    # DE4: All nodes must have evidence_refs
    graph = result_data.get("graph", {})
    for node in graph.get("nodes", []):
        if not node.get("evidence_refs"):
            violations.append(f"DE4 violation: Node {node.get('node_id')} missing evidence_refs")
    
    # DE5: High/critical risk must have requires_review
    review_stub = result_data.get("review_pack_stub", {})
    risk_summary = review_stub.get("risk_summary", {})
    dominant_risk = risk_summary.get("dominant_risk")
    requires_review = review_stub.get("requires_review", [])
    
    if dominant_risk in ["high", "critical"] and not requires_review:
        violations.append(f"DE5 violation: {dominant_risk} risk without requires_review")
    
    # DE6: Must have checksum and lineage
    if not result_data.get("checksum"):
        violations.append("DE6 violation: Missing checksum")
    if not result_data.get("lineage"):
        violations.append("DE6 violation: Missing lineage")
    
    return violations


def extract_evidence_from_intent(intent: Dict[str, Any]) -> list[str]:
    """
    Extract all evidence references from an intent.
    
    Args:
        intent: ExecutionIntent dictionary
    
    Returns:
        List of all evidence_refs found in the intent
    """
    evidence = set()
    
    # Top-level evidence_refs
    evidence.update(intent.get("evidence_refs", []))
    
    # Command-level evidence_refs
    for cmd in intent.get("planned_commands", []):
        evidence.update(cmd.get("evidence_refs", []))
    
    return list(evidence)
