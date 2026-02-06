"""
Action validators - Dynamic schema validation for action payloads

Each action 'kind' has its own schema with required and optional fields.
This provides the balance between open-domain flexibility and minimal constraints.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ValidationResult:
    """Result of action validation"""
    valid: bool
    error: Optional[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


# Action schemas - defines required and optional fields for each action kind
ACTION_SCHEMAS = {
    "command": {
        "required": ["cmd"],
        "optional": ["args", "working_dir", "timeout", "env"],
        "description": "Execute shell command"
    },
    "file": {
        "required": ["path", "operation"],
        "optional": ["intent", "content_hint", "backup"],
        "description": "File operation (create/update/delete)",
        "operation_values": ["create", "update", "delete", "declare"]
    },
    "api": {
        "required": ["endpoint", "method"],
        "optional": ["headers", "body", "timeout", "auth"],
        "description": "API call",
        "method_values": ["GET", "POST", "PUT", "DELETE", "PATCH"]
    },
    "agent": {
        "required": ["agent_type", "task"],
        "optional": ["context", "inputs", "timeout", "mode"],
        "description": "Delegate to sub-agent"
    },
    "check": {
        "required": ["check_type", "target"],
        "optional": ["expected", "threshold", "timeout"],
        "description": "Verification action",
        "check_type_values": ["build", "test", "lint", "run", "exists", "contains"]
    },
    "rule": {
        "required": ["constraint"],
        "optional": ["scope", "enforcement", "priority"],
        "description": "Execution constraint",
        "enforcement_values": ["hard", "soft", "warn"]
    },
    "note": {
        "required": ["message"],
        "optional": ["level", "tags"],
        "description": "Human-readable note",
        "level_values": ["info", "warning", "error", "debug"]
    }
}


def validate_action(action: Dict[str, Any], strict: bool = False) -> ValidationResult:
    """
    Validate an action payload against its schema
    
    Args:
        action: Action dict with 'kind' and 'payload'
        strict: If True, reject unknown fields in payload
        
    Returns:
        ValidationResult with validation status
        
    Example:
        >>> action = {"kind": "command", "payload": {"cmd": "ls -la"}}
        >>> result = validate_action(action)
        >>> result.valid
        True
        
        >>> action = {"kind": "command", "payload": {}}
        >>> result = validate_action(action)
        >>> result.valid
        False
        >>> result.error
        'Missing required field: cmd'
    """
    kind = action.get("kind")
    
    # Check if kind is valid
    if kind not in ACTION_SCHEMAS:
        return ValidationResult(
            valid=False,
            error=f"Unknown action kind: {kind}. Must be one of: {', '.join(ACTION_SCHEMAS.keys())}"
        )
    
    schema = ACTION_SCHEMAS[kind]
    payload = action.get("payload", {})
    
    if not isinstance(payload, dict):
        return ValidationResult(
            valid=False,
            error=f"Payload must be a dict, got {type(payload).__name__}"
        )
    
    warnings = []
    
    # Check required fields
    for field in schema["required"]:
        if field not in payload:
            return ValidationResult(
                valid=False,
                error=f"Missing required field: {field}"
            )
        
        # Check for empty values
        if payload[field] is None or payload[field] == "":
            return ValidationResult(
                valid=False,
                error=f"Required field '{field}' cannot be empty"
            )
    
    # Check enum values if defined
    if kind == "file" and "operation" in payload:
        if payload["operation"] not in schema["operation_values"]:
            return ValidationResult(
                valid=False,
                error=f"Invalid operation: {payload['operation']}. Must be one of: {', '.join(schema['operation_values'])}"
            )
    
    if kind == "api" and "method" in payload:
        if payload["method"] not in schema["method_values"]:
            return ValidationResult(
                valid=False,
                error=f"Invalid method: {payload['method']}. Must be one of: {', '.join(schema['method_values'])}"
            )
    
    if kind == "check" and "check_type" in payload:
        if payload["check_type"] not in schema["check_type_values"]:
            warnings.append(
                f"Unknown check_type: {payload['check_type']}. "
                f"Known types: {', '.join(schema['check_type_values'])}"
            )
    
    if kind == "rule" and "enforcement" in payload:
        if payload["enforcement"] not in schema["enforcement_values"]:
            return ValidationResult(
                valid=False,
                error=f"Invalid enforcement: {payload['enforcement']}. Must be one of: {', '.join(schema['enforcement_values'])}"
            )
    
    if kind == "note" and "level" in payload:
        if payload["level"] not in schema["level_values"]:
            warnings.append(
                f"Unknown level: {payload['level']}. "
                f"Known levels: {', '.join(schema['level_values'])}"
            )
    
    # Check for unknown fields if strict mode
    if strict:
        known_fields = set(schema["required"] + schema["optional"])
        unknown_fields = set(payload.keys()) - known_fields
        if unknown_fields:
            warnings.append(
                f"Unknown fields in payload: {', '.join(unknown_fields)}"
            )
    
    return ValidationResult(valid=True, warnings=warnings)


def validate_actions(actions: List[Dict[str, Any]], strict: bool = False) -> ValidationResult:
    """
    Validate a list of actions
    
    Args:
        actions: List of action dicts
        strict: If True, reject unknown fields
        
    Returns:
        ValidationResult with validation status
    """
    all_warnings = []
    
    for i, action in enumerate(actions):
        result = validate_action(action, strict=strict)
        
        if not result.valid:
            return ValidationResult(
                valid=False,
                error=f"Action[{i}] validation failed: {result.error}"
            )
        
        if result.warnings:
            for warning in result.warnings:
                all_warnings.append(f"Action[{i}]: {warning}")
    
    return ValidationResult(valid=True, warnings=all_warnings)


def get_action_schema(kind: str) -> Optional[Dict[str, Any]]:
    """
    Get schema for a specific action kind
    
    Args:
        kind: Action kind
        
    Returns:
        Schema dict or None if kind is unknown
    """
    return ACTION_SCHEMAS.get(kind)


def get_available_kinds() -> List[str]:
    """Get list of all available action kinds"""
    return list(ACTION_SCHEMAS.keys())


def get_schema_documentation() -> str:
    """
    Generate human-readable documentation of all action schemas
    
    Returns:
        Markdown-formatted documentation
    """
    lines = ["# Action Schemas\n"]
    
    for kind, schema in ACTION_SCHEMAS.items():
        lines.append(f"## {kind}")
        lines.append(f"\n{schema['description']}\n")
        
        lines.append("**Required fields:**")
        for field in schema["required"]:
            lines.append(f"- `{field}`")
        
        lines.append("\n**Optional fields:**")
        for field in schema["optional"]:
            lines.append(f"- `{field}`")
        
        # Add enum values if present
        for key in schema:
            if key.endswith("_values"):
                enum_name = key.replace("_values", "")
                lines.append(f"\n**Valid {enum_name} values:**")
                for value in schema[key]:
                    lines.append(f"- `{value}`")
        
        lines.append("")  # Empty line between schemas
    
    return "\n".join(lines)
