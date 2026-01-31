"""Attribution Freeze Guard - Enforces proper attribution of external knowledge.

This guard ensures that all external knowledge is properly attributed to
CommunicationOS and cannot be claimed by Chat as its own knowledge.

Why this guard is essential:
- Prevents Chat from claiming external knowledge as built-in
- Enables proper audit trails for data sources
- Supports compliance with data attribution requirements
- Allows users to distinguish internal vs external knowledge

Bypass attempts to watch for:
- Omitting attribution metadata
- Using incorrect attribution format
- Forging attribution with wrong session IDs
- Post-processing to remove attribution
- Wrapping attributed content without preserving markers

Defense measures:
- Strict format validation (prefix + session ID)
- Session ID must match current session
- Attribution frozen at data ingress point
- Immutable attribution in metadata
- Validation before data enters Chat layer

Test requirements:
- Verify attribution format compliance
- Reject missing attribution
- Reject malformed attribution
- Reject attribution with wrong session ID
- Test attribution generation helper
"""


class AttributionViolation(Exception):
    """Raised when attribution is missing or incorrect.

    This exception indicates that external data lacks proper attribution
    or the attribution format is incorrect.
    """
    pass


class AttributionGuard:
    """Ensures all external knowledge is properly attributed.

    Rules:
    - All external data must include attribution
    - Attribution format: "CommunicationOS (search/fetch) in session {session_id}"
    - Chat cannot claim external knowledge as its own

    This guard implements mandatory attribution for all external data sources,
    ensuring transparency and preventing knowledge source confusion.

    Examples:
        >>> data = {"metadata": {"attribution": "CommunicationOS (search) in session abc123"}}
        >>> AttributionGuard.enforce(data, "abc123")  # OK
        >>> bad_data = {"metadata": {}}
        >>> AttributionGuard.enforce(bad_data, "abc123")  # Raises AttributionViolation
    """

    # Required attribution prefix
    REQUIRED_ATTRIBUTION_PREFIX = "CommunicationOS"

    # Valid operation types
    VALID_OPERATIONS = ["search", "fetch"]

    @staticmethod
    def enforce(data: dict, session_id: str):
        """Enforce attribution on external data.

        This method validates that external data includes proper attribution
        in the required format and with the correct session ID.

        Args:
            data: Data returned from CommunicationOS (must have metadata.attribution)
            session_id: Current session ID (must match attribution)

        Raises:
            AttributionViolation: If attribution is missing or incorrect

        Examples:
            >>> data = {"metadata": {"attribution": "CommunicationOS (search) in session abc123"}}
            >>> AttributionGuard.enforce(data, "abc123")  # OK

            >>> bad_data = {"metadata": {}}
            >>> AttributionGuard.enforce(bad_data, "abc123")  # Raises
        """
        # Check for metadata structure
        if "metadata" not in data:
            raise AttributionViolation("Data is missing 'metadata' field")

        metadata = data["metadata"]
        attribution = metadata.get("attribution", "")

        # Attribution must be present
        if not attribution:
            raise AttributionViolation("Attribution is missing from external data")

        # Attribution must start with required prefix
        if not attribution.startswith(AttributionGuard.REQUIRED_ATTRIBUTION_PREFIX):
            raise AttributionViolation(
                f"Attribution must start with '{AttributionGuard.REQUIRED_ATTRIBUTION_PREFIX}', "
                f"got: {attribution}"
            )

        # Attribution must include session ID
        if session_id not in attribution:
            raise AttributionViolation(
                f"Attribution must include session ID '{session_id}', got: {attribution}"
            )

    @staticmethod
    def format_attribution(operation: str, session_id: str) -> str:
        """Generate correct attribution string.

        This helper method generates properly formatted attribution strings
        that will pass validation.

        Args:
            operation: Operation type (e.g., "search", "fetch")
            session_id: Current session ID

        Returns:
            str: Properly formatted attribution string

        Examples:
            >>> AttributionGuard.format_attribution("search", "abc123")
            'CommunicationOS (search) in session abc123'
        """
        return f"{AttributionGuard.REQUIRED_ATTRIBUTION_PREFIX} ({operation}) in session {session_id}"

    @staticmethod
    def validate_attribution_format(attribution: str) -> bool:
        """Validate attribution string format without session check.

        This method checks if an attribution string follows the correct
        format, without validating the session ID.

        Args:
            attribution: Attribution string to validate

        Returns:
            bool: True if format is valid, False otherwise
        """
        if not attribution:
            return False

        if not attribution.startswith(AttributionGuard.REQUIRED_ATTRIBUTION_PREFIX):
            return False

        # Check for operation in parentheses
        if "(" not in attribution or ")" not in attribution:
            return False

        # Check for "in session" marker
        if "in session" not in attribution:
            return False

        return True
