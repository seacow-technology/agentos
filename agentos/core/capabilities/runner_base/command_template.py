"""
Command Template Parser and Validator

Provides safe command template parsing with parameter substitution.
Prevents command injection by using strict token-based substitution.

Part of PR-E4: ShellRunner
"""

import logging
import re
import shlex
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)


class CommandTemplateError(Exception):
    """Base exception for command template errors"""
    pass


class TemplateParseError(CommandTemplateError):
    """Error parsing command template"""
    pass


class TemplateValidationError(CommandTemplateError):
    """Error validating template arguments"""
    pass


class CommandTemplate:
    """
    Safe command template parser and renderer

    Templates use {param_name} syntax for parameter substitution.
    Parameters are safely tokenized to prevent command injection.

    Example:
        >>> template = CommandTemplate("postman login --with-api-key {api_key}")
        >>> argv = template.render({"api_key": "PMAK-12345"})
        >>> assert argv == ["postman", "login", "--with-api-key", "PMAK-12345"]

        >>> template = CommandTemplate("echo {message}")
        >>> argv = template.render({"message": "Hello World"})
        >>> assert argv == ["echo", "Hello World"]

    Security:
        - Parameters are inserted as separate argv elements (no shell interpolation)
        - No command chaining allowed (no ; or && or |)
        - No shell expansion (no $ or ` or *)
        - Each parameter is a single token
    """

    # Regex to find {param_name} placeholders
    PARAM_PATTERN = re.compile(r'\{([a-zA-Z0-9_]+)\}')

    # Dangerous characters that should not appear in templates
    DANGEROUS_CHARS = [';', '&&', '||', '|', '`', '$', '>', '<', '\n', '\r']

    def __init__(self, template: str):
        """
        Initialize command template

        Args:
            template: Command template string with {param} placeholders

        Raises:
            TemplateParseError: If template contains dangerous characters
        """
        self.template = template.strip()
        self._validate_template_safety()
        self.params = self._extract_params()

    def _validate_template_safety(self):
        """
        Validate template doesn't contain dangerous characters

        Raises:
            TemplateParseError: If dangerous characters found
        """
        for char in self.DANGEROUS_CHARS:
            if char in self.template:
                raise TemplateParseError(
                    f"Template contains dangerous character '{char}': {self.template}"
                )

    def _extract_params(self) -> List[str]:
        """
        Extract parameter names from template

        Returns:
            List of unique parameter names

        Example:
            >>> template = CommandTemplate("cmd --flag {param1} --opt {param2}")
            >>> assert template.params == ["param1", "param2"]
        """
        matches = self.PARAM_PATTERN.findall(self.template)
        # Return unique params in order of first appearance
        seen = set()
        params = []
        for param in matches:
            if param not in seen:
                params.append(param)
                seen.add(param)
        return params

    def validate_args(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate that all required parameters are provided

        Args:
            args: Dictionary of parameter values

        Returns:
            Tuple of (valid: bool, error_message: Optional[str])

        Example:
            >>> template = CommandTemplate("cmd {param1} {param2}")
            >>> valid, error = template.validate_args({"param1": "val1"})
            >>> assert valid is False
            >>> assert "param2" in error
        """
        missing_params = [p for p in self.params if p not in args]

        if missing_params:
            return False, f"Missing required parameters: {', '.join(missing_params)}"

        return True, None

    def render(self, args: Dict[str, Any]) -> List[str]:
        """
        Render template with arguments to argv list

        Args:
            args: Dictionary of parameter values

        Returns:
            List of command arguments (argv)

        Raises:
            TemplateValidationError: If required parameters missing

        Example:
            >>> template = CommandTemplate("postman collection run {path} --env {env}")
            >>> argv = template.render({"path": "collection.json", "env": "prod"})
            >>> assert argv == ["postman", "collection", "run", "collection.json", "--env", "prod"]

        Security:
            - Each parameter becomes a separate argv element
            - No shell interpolation occurs
            - Arguments with spaces are kept as single elements
        """
        # Validate arguments
        valid, error = self.validate_args(args)
        if not valid:
            raise TemplateValidationError(error)

        # Start with template
        rendered = self.template

        # Replace each parameter with a unique placeholder
        # We'll use a marker that won't conflict with user input
        placeholders = {}
        for i, param in enumerate(self.params):
            placeholder = f"__PARAM_{i}__"
            placeholders[placeholder] = str(args[param])
            rendered = rendered.replace(f"{{{param}}}", placeholder)

        # Split into tokens using shlex (handles quotes properly)
        try:
            tokens = shlex.split(rendered)
        except ValueError as e:
            raise TemplateValidationError(f"Failed to parse template: {e}")

        # Replace placeholders with actual values
        argv = []
        for token in tokens:
            # Check if token contains any placeholder
            final_token = token
            for placeholder, value in placeholders.items():
                if placeholder in final_token:
                    # Replace placeholder with actual value
                    final_token = final_token.replace(placeholder, value)
            argv.append(final_token)

        return argv

    def get_command_name(self) -> str:
        """
        Get the command name (first token)

        Returns:
            Command name (e.g., "postman", "curl")

        Example:
            >>> template = CommandTemplate("postman login --api-key {key}")
            >>> assert template.get_command_name() == "postman"
        """
        tokens = shlex.split(self.template.split('{')[0])  # Get part before first param
        if not tokens:
            return ""
        return tokens[0]

    def __repr__(self) -> str:
        return f"CommandTemplate('{self.template}', params={self.params})"


def parse_template(template_str: str) -> CommandTemplate:
    """
    Parse command template string

    Args:
        template_str: Template string

    Returns:
        CommandTemplate instance

    Raises:
        TemplateParseError: If template is invalid

    Example:
        >>> template = parse_template("echo {message}")
        >>> assert template.params == ["message"]
    """
    return CommandTemplate(template_str)


def validate_template_list(templates: List[str]) -> Tuple[bool, List[str]]:
    """
    Validate a list of command templates

    Args:
        templates: List of template strings

    Returns:
        Tuple of (all_valid: bool, error_messages: List[str])

    Example:
        >>> valid, errors = validate_template_list([
        ...     "echo {msg}",
        ...     "cmd; rm -rf /",  # Invalid - contains ;
        ... ])
        >>> assert valid is False
        >>> assert len(errors) == 1
    """
    errors = []
    for template_str in templates:
        try:
            CommandTemplate(template_str)
        except CommandTemplateError as e:
            errors.append(f"Template '{template_str}': {e}")

    return len(errors) == 0, errors
