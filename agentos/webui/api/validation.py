"""
Centralized Input Validation for AgentOS WebUI APIs

This module provides reusable Pydantic Field definitions and validators
for common input patterns. Use these to ensure consistent validation
across all API endpoints.

Addresses: M-1 and input validation gaps from BACKLOG_REMAINING.md

Usage:
    from agentos.webui.api.validation import (
        TitleField, ContentField, IdField, EnumField
    )

    class MyRequest(BaseModel):
        title: str = TitleField
        content: str = ContentField
        status: str = EnumField(allowed=["draft", "published"])
"""

from pydantic import Field, validator
from typing import Set, Optional, Any


# ==============================================================================
# Size Limit Constants (L-3, L-4, L-5)
# ==============================================================================

# Payload size limits (in bytes)
MAX_PAYLOAD_SIZE = 1 * 1024 * 1024  # 1 MB (L-3)

# String length limits (in characters)
MAX_TITLE_LENGTH = 500  # L-4
MAX_CONTENT_LENGTH = 50000  # L-5 (50 KB)

# ==============================================================================
# Common Field Definitions
# ==============================================================================

# String Fields with Length Limits
TitleField = Field(
    ...,
    min_length=1,
    max_length=MAX_TITLE_LENGTH,
    description=f"Title (1-{MAX_TITLE_LENGTH} characters)"
)

ShortTextField = Field(
    ...,
    min_length=1,
    max_length=200,
    description="Short text (1-200 characters)"
)

MediumTextField = Field(
    ...,
    min_length=1,
    max_length=1000,
    description="Medium text (1-1000 characters)"
)

ContentField = Field(
    ...,
    min_length=1,
    max_length=MAX_CONTENT_LENGTH,
    description=f"Content (1-{MAX_CONTENT_LENGTH} characters)"
)

LongContentField = Field(
    ...,
    min_length=1,
    max_length=100000,
    description="Long content (1-100,000 characters)"
)

# ID Fields
IdField = Field(
    ...,
    min_length=1,
    max_length=100,
    pattern=r'^[a-zA-Z0-9_\-]+$',
    description="ID (alphanumeric, dash, underscore)"
)

ULIDField = Field(
    ...,
    min_length=26,
    max_length=26,
    pattern=r'^[0-9A-Z]{26}$',
    description="ULID (26-character uppercase alphanumeric)"
)

# Optional variants
OptionalTitleField = Field(
    None,
    min_length=1,
    max_length=MAX_TITLE_LENGTH,
    description=f"Optional title (1-{MAX_TITLE_LENGTH} characters)"
)

OptionalContentField = Field(
    None,
    min_length=1,
    max_length=MAX_CONTENT_LENGTH,
    description=f"Optional content (1-{MAX_CONTENT_LENGTH} characters)"
)

OptionalIdField = Field(
    None,
    min_length=1,
    max_length=100,
    pattern=r'^[a-zA-Z0-9_\-]+$',
    description="Optional ID (alphanumeric, dash, underscore)"
)

# Numeric Fields with Range Limits
PositiveIntField = Field(
    ...,
    ge=1,
    description="Positive integer (>= 1)"
)

NonNegativeIntField = Field(
    ...,
    ge=0,
    description="Non-negative integer (>= 0)"
)

LimitField = Field(
    50,
    ge=1,
    le=1000,
    description="Pagination limit (1-1000, default 50)"
)

OffsetField = Field(
    0,
    ge=0,
    description="Pagination offset (>= 0, default 0)"
)

PercentageField = Field(
    ...,
    ge=0,
    le=100,
    description="Percentage (0-100)"
)

PortField = Field(
    ...,
    ge=1,
    le=65535,
    description="Network port (1-65535)"
)

# Token/Budget Fields
TokenBudgetField = Field(
    8000,
    ge=100,
    le=1000000,
    description="Token budget (100-1,000,000)"
)

# List Fields with Size Limits
SmallListField = Field(
    default_factory=list,
    max_items=10,
    description="Small list (max 10 items)"
)

MediumListField = Field(
    default_factory=list,
    max_items=100,
    description="Medium list (max 100 items)"
)

LargeListField = Field(
    default_factory=list,
    max_items=1000,
    description="Large list (max 1000 items)"
)


# ==============================================================================
# Reusable Validators
# ==============================================================================

def create_enum_validator(field_name: str, allowed_values: Set[str], case_sensitive: bool = False):
    """
    Create a Pydantic validator for enum fields.

    Args:
        field_name: Name of the field to validate
        allowed_values: Set of allowed values
        case_sensitive: Whether validation is case-sensitive

    Returns:
        Pydantic validator function

    Example:
        class MyModel(BaseModel):
            status: str

            _validate_status = create_enum_validator(
                'status',
                {'draft', 'published', 'archived'}
            )
    """
    def validator_func(cls, v):
        if v is None:
            return v

        check_value = v if case_sensitive else v.lower()
        allowed = allowed_values if case_sensitive else {val.lower() for val in allowed_values}

        if check_value not in allowed:
            raise ValueError(
                f"Invalid {field_name} '{v}'. Must be one of: {', '.join(sorted(allowed_values))}"
            )

        return v.lower() if not case_sensitive else v

    return validator(field_name)(validator_func)


def create_metadata_validator(field_name: str = 'metadata', dangerous_keys: Optional[Set[str]] = None):
    """
    Create a Pydantic validator for metadata fields to prevent injection attacks.

    Args:
        field_name: Name of the metadata field
        dangerous_keys: Set of dangerous keys to reject (default: __proto__, constructor, etc.)

    Returns:
        Pydantic validator function

    Example:
        class MyModel(BaseModel):
            metadata: Dict[str, Any] = {}

            _validate_metadata = create_metadata_validator()
    """
    if dangerous_keys is None:
        dangerous_keys = {
            '__proto__',
            'constructor',
            'prototype',
            '$where',
            '$eval',
            'eval',
            'function',
            '<script>',
            'javascript:',
        }

    def validator_func(cls, v):
        if v is None:
            return {}

        # Check for dangerous keys
        for key in v.keys():
            key_lower = key.lower()
            for dangerous in dangerous_keys:
                if dangerous.lower() in key_lower:
                    raise ValueError(
                        f"Metadata key '{key}' contains dangerous pattern '{dangerous}'"
                    )

        # Check for null bytes in keys or string values
        for key, value in v.items():
            if '\x00' in key:
                raise ValueError(f"Metadata key contains null byte: {repr(key)}")

            if isinstance(value, str) and '\x00' in value:
                raise ValueError(f"Metadata value contains null byte for key '{key}'")

        return v

    return validator(field_name)(validator_func)


def sanitize_null_bytes(v: Optional[str]) -> Optional[str]:
    """
    Remove null bytes from strings.

    Args:
        v: String value (or None)

    Returns:
        String with null bytes removed (or None)
    """
    if v is None:
        return None
    return v.replace('\x00', '')


# ==============================================================================
# Common Request Models
# ==============================================================================

class PaginationParams:
    """Mixin for pagination parameters"""
    limit: int = LimitField
    offset: int = OffsetField


class TimestampRange:
    """Mixin for timestamp range filtering"""
    start_time: Optional[str] = Field(None, description="Start timestamp (ISO 8601)")
    end_time: Optional[str] = Field(None, description="End timestamp (ISO 8601)")


# ==============================================================================
# Validation Constants
# ==============================================================================

# Message roles (for chat systems)
VALID_MESSAGE_ROLES = {"user", "assistant", "system"}

# Conversation modes
VALID_CONVERSATION_MODES = {"chat", "discussion", "plan", "development", "task"}

# Execution phases
VALID_EXECUTION_PHASES = {"planning", "execution"}

# HTTP methods
VALID_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}

# Common status values
VALID_STATUS_VALUES = {"active", "inactive", "pending", "completed", "failed", "cancelled"}

# Priority levels
VALID_PRIORITY_LEVELS = {"low", "medium", "high", "critical"}


# ==============================================================================
# JSON Validation Utilities
# ==============================================================================

def validate_no_special_floats(v: Any) -> Any:
    """
    Validate that a value doesn't contain NaN or Infinity.

    This is automatically handled by our JSON validation middleware,
    but can be used as an additional layer of defense.

    Args:
        v: Value to validate

    Returns:
        Original value if valid

    Raises:
        ValueError: If value contains NaN or Infinity
    """
    import math

    if isinstance(v, float):
        if math.isnan(v):
            raise ValueError("NaN is not allowed")
        if math.isinf(v):
            raise ValueError("Infinity is not allowed")

    return v
