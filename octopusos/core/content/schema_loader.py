"""Content Schema Loader - validates content against JSON schemas."""

import json
from pathlib import Path
from typing import Any, Optional

from jsonschema import Draft7Validator, ValidationError as JsonSchemaValidationError


class SchemaValidationError(Exception):
    """Schema validation failed."""

    pass


class ContentSchemaLoader:
    """Loads and validates content against JSON schemas."""

    def __init__(self, schemas_dir: Optional[Path] = None):
        """Initialize schema loader.

        Args:
            schemas_dir: Path to schemas directory (defaults to agentos/schemas/)
        """
        if schemas_dir is None:
            # Default to agentos/schemas/
            schemas_dir = Path(__file__).parent.parent.parent / "schemas"
        self.schemas_dir = schemas_dir
        self._schema_cache: dict[str, dict] = {}

    def load_schema(self, schema_ref: str) -> dict:
        """Load a JSON schema file.

        Args:
            schema_ref: Schema file path (relative to schemas_dir or absolute)

        Returns:
            Parsed JSON schema dict

        Raises:
            FileNotFoundError: Schema file not found
            json.JSONDecodeError: Invalid JSON
        """
        if schema_ref in self._schema_cache:
            return self._schema_cache[schema_ref]

        # Try relative path first
        schema_path = self.schemas_dir / schema_ref
        if not schema_path.exists():
            # Try absolute path
            schema_path = Path(schema_ref)
            if not schema_path.exists():
                raise FileNotFoundError(f"Schema not found: {schema_ref}")

        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)

        self._schema_cache[schema_ref] = schema
        return schema

    def validate_content_base(self, content: dict) -> tuple[bool, list[str]]:
        """Validate content against content_base.schema.json.

        Args:
            content: Content dict to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        try:
            schema = self.load_schema("content/content_base.schema.json")
            validator = Draft7Validator(schema)
            errors = list(validator.iter_errors(content))

            if errors:
                error_messages = [self._format_error(e) for e in errors]
                return False, error_messages

            return True, []

        except Exception as e:
            return False, [f"Schema validation error: {str(e)}"]

    def validate_content_type(self, content: dict, type_schema_ref: str) -> tuple[bool, list[str]]:
        """Validate content's spec field against type-specific schema.

        Args:
            content: Content dict (must contain 'spec' field)
            type_schema_ref: Path to type-specific schema

        Returns:
            Tuple of (is_valid, error_messages)
        """
        try:
            schema = self.load_schema(type_schema_ref)
            validator = Draft7Validator(schema)

            # Validate the 'spec' field only
            spec = content.get("spec", {})
            errors = list(validator.iter_errors(spec))

            if errors:
                error_messages = [self._format_error(e) for e in errors]
                return False, error_messages

            return True, []

        except Exception as e:
            return False, [f"Type schema validation error: {str(e)}"]

    def validate_full(self, content: dict, type_schema_ref: str) -> tuple[bool, list[str]]:
        """Validate content against both base schema and type-specific schema.

        Args:
            content: Content dict to validate
            type_schema_ref: Path to type-specific schema

        Returns:
            Tuple of (is_valid, error_messages)
        """
        # Step 1: Validate base schema
        is_valid_base, base_errors = self.validate_content_base(content)
        if not is_valid_base:
            return False, ["Base schema validation failed:"] + base_errors

        # Step 2: Validate type-specific schema
        is_valid_type, type_errors = self.validate_content_type(content, type_schema_ref)
        if not is_valid_type:
            return False, ["Type schema validation failed:"] + type_errors

        return True, []

    def _format_error(self, error: JsonSchemaValidationError) -> str:
        """Format validation error for human-readable output.

        Args:
            error: jsonschema ValidationError

        Returns:
            Formatted error string
        """
        path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
        return f"  {path}: {error.message}"
