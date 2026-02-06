"""Schema validation utilities"""

import json
from pathlib import Path
from typing import Any, Optional

import jsonschema
from jsonschema import Draft7Validator


def _load_schema(schema_name: str) -> dict:
    """Load a JSON schema by name"""
    schema_path = Path(__file__).parent.parent.parent / "schemas" / f"{schema_name}.schema.json"
    with open(schema_path, encoding="utf-8") as f:
        return json.load(f)


def validate_factpack(data: dict) -> tuple:
    """
    Validate FactPack against schema
    
    Returns:
        (is_valid, errors): Tuple of validation result and error messages
    """
    try:
        schema = _load_schema("factpack")
        validator = Draft7Validator(schema)
        errors = list(validator.iter_errors(data))
        
        if not errors:
            return True, []
        
        error_messages = []
        for error in errors:
            path = ".".join(str(p) for p in error.path) if error.path else "root"
            error_messages.append(f"{path}: {error.message}")
        
        return False, error_messages
    except Exception as e:
        return False, [f"Schema validation error: {str(e)}"]


def validate_agent_spec(data: dict) -> tuple:
    """
    Validate AgentSpec against schema
    
    Returns:
        (is_valid, errors): Tuple of validation result and error messages
    """
    try:
        schema = _load_schema("agent_spec")
        validator = Draft7Validator(schema)
        errors = list(validator.iter_errors(data))
        
        if not errors:
            return True, []
        
        error_messages = []
        for error in errors:
            path = ".".join(str(p) for p in error.path) if error.path else "root"
            error_messages.append(f"{path}: {error.message}")
        
        return False, error_messages
    except Exception as e:
        return False, [f"Schema validation error: {str(e)}"]


def validate_memory_item(data: dict) -> tuple:
    """
    Validate MemoryItem against schema
    
    Returns:
        (is_valid, errors): Tuple of validation result and error messages
    """
    try:
        schema = _load_schema("memory_item")
        validator = Draft7Validator(schema)
        errors = list(validator.iter_errors(data))
        
        if not errors:
            return True, []
        
        error_messages = []
        for error in errors:
            path = ".".join(str(p) for p in error.path) if error.path else "root"
            error_messages.append(f"{path}: {error.message}")
        
        return False, error_messages
    except Exception as e:
        return False, [f"Schema validation error: {str(e)}"]


def validate_memory_pack(data: dict) -> tuple:
    """
    Validate MemoryPack against schema
    
    Returns:
        (is_valid, errors): Tuple of validation result and error messages
    """
    try:
        schema = _load_schema("memory_pack")
        validator = Draft7Validator(schema)
        errors = list(validator.iter_errors(data))
        
        if not errors:
            return True, []
        
        error_messages = []
        for error in errors:
            path = ".".join(str(p) for p in error.path) if error.path else "root"
            error_messages.append(f"{path}: {error.message}")
        
        return False, error_messages
    except Exception as e:
        return False, [f"Schema validation error: {str(e)}"]


def validate_task_definition(data: dict) -> tuple:
    """
    Validate TaskDefinition against schema
    
    Returns:
        (is_valid, errors): Tuple of validation result and error messages
    """
    try:
        schema = _load_schema("task_definition")
        validator = Draft7Validator(schema)
        errors = list(validator.iter_errors(data))
        
        if not errors:
            return True, []
        
        error_messages = []
        for error in errors:
            path = ".".join(str(p) for p in error.path) if error.path else "root"
            error_messages.append(f"{path}: {error.message}")
        
        return False, error_messages
    except Exception as e:
        return False, [f"Schema validation error: {str(e)}"]


def validate_review_pack(data: dict) -> tuple:
    """
    Validate ReviewPack against schema
    
    Returns:
        (is_valid, errors): Tuple of validation result and error messages
    """
    try:
        schema = _load_schema("review_pack")
        validator = Draft7Validator(schema)
        errors = list(validator.iter_errors(data))
        
        if not errors:
            return True, []
        
        error_messages = []
        for error in errors:
            path = ".".join(str(p) for p in error.path) if error.path else "root"
            error_messages.append(f"{path}: {error.message}")
        
        return False, error_messages
    except Exception as e:
        return False, [f"Schema validation error: {str(e)}"]


def validate_execution_policy(data: dict) -> tuple:
    """
    Validate ExecutionPolicy against schema
    
    Returns:
        (is_valid, errors): Tuple of validation result and error messages
    """
    try:
        schema = _load_schema("execution_policy")
        validator = Draft7Validator(schema)
        errors = list(validator.iter_errors(data))
        
        if not errors:
            return True, []
        
        error_messages = []
        for error in errors:
            path = ".".join(str(p) for p in error.path) if error.path else "root"
            error_messages.append(f"{path}: {error.message}")
        
        return False, error_messages
    except Exception as e:
        return False, [f"Schema validation error: {str(e)}"]


def validate_file(file_path: str) -> tuple:
    """
    Auto-detect and validate a JSON file
    
    Returns:
        (is_valid, errors, detected_type): Validation result, errors, and detected schema type
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {str(e)}"], None
    except Exception as e:
        return False, [f"Error reading file: {str(e)}"], None
    
    # Try to detect schema type
    if "evidence" in data and "repo_root" in data:
        is_valid, errors = validate_factpack(data)
        return is_valid, errors, "factpack"
    elif "allowed_paths" in data and "workflows" in data:
        is_valid, errors = validate_agent_spec(data)
        return is_valid, errors, "agent_spec"
    elif "scope" in data and "type" in data and "id" in data and data.get("id", "").startswith("mem-"):
        is_valid, errors = validate_memory_item(data)
        return is_valid, errors, "memory_item"
    elif "memories" in data and "agent_type" in data:
        is_valid, errors = validate_memory_pack(data)
        return is_valid, errors, "memory_pack"
    elif "task_id" in data and "execution_mode" in data:
        is_valid, errors = validate_task_definition(data)
        return is_valid, errors, "task_definition"
    elif "patches" in data and "run_id" in data:
        is_valid, errors = validate_review_pack(data)
        return is_valid, errors, "review_pack"
    elif "mode" in data and "question_budget" in data:
        is_valid, errors = validate_execution_policy(data)
        return is_valid, errors, "execution_policy"
    else:
        return False, ["Unknown schema type. Expected one of: FactPack, AgentSpec, MemoryItem, MemoryPack, TaskDefinition, ReviewPack, ExecutionPolicy."], None
