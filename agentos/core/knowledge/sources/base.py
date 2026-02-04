"""
Base Source Module
==================

This module provides the abstract base class and data structures for all knowledge sources
in the AgentOS knowledge management system.

Key Components:
    - Document: Immutable document representation with content and metadata
    - SourceStatus: Enum defining lifecycle states of knowledge sources
    - ValidationResult: Result object for configuration validation
    - HealthCheckResult: Result object for health status checks
    - BaseSource: Abstract base class for all knowledge source implementations

Architecture:
    BaseSource defines the contract that all knowledge sources must implement:
    1. fetch() - Retrieve documents from the source
    2. validate() - Verify configuration correctness
    3. health_check() - Monitor source availability and performance
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class Document:
    """
    Immutable document data structure.

    Represents a single document retrieved from a knowledge source with its content
    and associated metadata. Documents are immutable to ensure data integrity
    throughout the processing pipeline.

    Attributes:
        content (str): The main textual content of the document. This is the primary
            data that will be indexed and searched. Should be preprocessed and cleaned
            before creating the Document instance.
        metadata (Dict[str, Any]): Additional information about the document such as:
            - source_id: Identifier of the source this document came from
            - uri: Original location of the document
            - timestamp: When the document was fetched or last modified
            - title: Document title if available
            - author: Document author if available
            - chunk_id: Identifier if document is part of a chunked larger document
            - Any source-specific metadata fields

    Example:
        >>> doc = Document(
        ...     content="Machine learning is a subset of AI.",
        ...     metadata={
        ...         "source_id": "wiki_001",
        ...         "uri": "https://en.wikipedia.org/wiki/Machine_learning",
        ...         "timestamp": "2025-02-01T10:00:00Z",
        ...         "title": "Machine Learning"
        ...     }
        ... )
    """
    content: str
    metadata: Dict[str, Any]


class SourceStatus(str, Enum):
    """
    Enumeration of knowledge source lifecycle states.

    Defines all possible states a knowledge source can be in during its lifecycle.
    These states are used for monitoring, UI display, and controlling source behavior.

    States:
        PENDING: Source is registered but not yet initialized or validated.
            Next states: ACTIVE, ERROR

        ACTIVE: Source has been validated and is operational but not yet indexed.
            Can fetch documents but indexing hasn't started.
            Next states: INDEXED, INACTIVE, ERROR

        INDEXED: Source has been successfully indexed and is fully operational.
            This is the normal operational state.
            Next states: INACTIVE, ERROR

        INACTIVE: Source has been manually disabled or paused.
            Configuration is valid but source is not being actively used.
            Next states: ACTIVE, ERROR

        ERROR: Source encountered a recoverable error (e.g., temporary network issue).
            Automatic retry may be possible.
            Next states: ACTIVE, FAILED

        FAILED: Source encountered an unrecoverable error (e.g., invalid credentials,
            missing resource). Manual intervention required.
            Next states: ACTIVE (after manual fix)

    State Transitions:
        PENDING -> ACTIVE -> INDEXED (normal flow)
        * -> INACTIVE (manual pause)
        * -> ERROR (temporary failure)
        * -> FAILED (permanent failure)
    """
    PENDING = "pending"
    ACTIVE = "active"
    INDEXED = "indexed"
    INACTIVE = "inactive"
    ERROR = "error"
    FAILED = "failed"


class ValidationResult:
    """
    Result object for configuration validation operations.

    Encapsulates the outcome of validating a source's configuration. Provides
    a standardized way to communicate validation success or failure with
    detailed error messages.

    Attributes:
        valid (bool): True if configuration is valid, False otherwise.
        error (Optional[str]): Human-readable error message if validation failed.
            Should be None if valid is True. Should provide actionable information
            for fixing the configuration if valid is False.

    Example:
        >>> # Success case
        >>> result = ValidationResult(valid=True)
        >>> print(result.to_dict())
        {'valid': True, 'error': None}

        >>> # Failure case
        >>> result = ValidationResult(
        ...     valid=False,
        ...     error="Missing required field 'uri' in configuration"
        ... )
        >>> print(result.to_dict())
        {'valid': False, 'error': "Missing required field 'uri' in configuration"}
    """

    def __init__(self, valid: bool, error: Optional[str] = None):
        """
        Initialize a validation result.

        Args:
            valid (bool): Whether the configuration is valid.
            error (Optional[str]): Error message if validation failed. Should be None
                if valid is True.
        """
        self.valid = valid
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the validation result to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary with 'valid' and 'error' keys. Suitable for
                JSON serialization and API responses.
        """
        return {"valid": self.valid, "error": self.error}


class HealthCheckResult:
    """
    Result object for health check operations.

    Encapsulates the outcome of checking a source's health and availability.
    Provides detailed metrics about the source's operational status.

    Attributes:
        healthy (bool): True if source is healthy and operational, False otherwise.
        metrics (Dict[str, Any]): Dictionary of health metrics such as:
            - response_time_ms: Time taken to connect to source
            - document_count: Number of documents available
            - last_fetch_time: Timestamp of last successful fetch
            - error_rate: Percentage of failed operations
            - Any source-specific health metrics
        error (Optional[str]): Human-readable error message if health check failed.
            Should be None if healthy is True.

    Example:
        >>> # Healthy source
        >>> result = HealthCheckResult(
        ...     healthy=True,
        ...     metrics={
        ...         "response_time_ms": 150,
        ...         "document_count": 1000,
        ...         "last_fetch_time": "2025-02-01T10:00:00Z"
        ...     }
        ... )

        >>> # Unhealthy source
        >>> result = HealthCheckResult(
        ...     healthy=False,
        ...     metrics={"response_time_ms": 5000},
        ...     error="Connection timeout after 5000ms"
        ... )
    """

    def __init__(
        self,
        healthy: bool,
        metrics: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        """
        Initialize a health check result.

        Args:
            healthy (bool): Whether the source is healthy.
            metrics (Optional[Dict[str, Any]]): Dictionary of health metrics.
                Defaults to empty dict if not provided.
            error (Optional[str]): Error message if health check failed. Should be
                None if healthy is True.
        """
        self.healthy = healthy
        self.metrics = metrics or {}
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the health check result to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary with 'healthy', 'metrics', and 'error' keys.
                Suitable for JSON serialization and API responses.
        """
        return {
            "healthy": self.healthy,
            "metrics": self.metrics,
            "error": self.error
        }


class BaseSource(ABC):
    """
    Abstract base class for all knowledge sources.

    This class defines the contract that all knowledge source implementations must
    follow. It provides a unified interface for fetching documents, validating
    configurations, and monitoring source health.

    Architecture:
        - All concrete source implementations (LocalSource, WebSource, DatabaseSource)
          must inherit from this class
        - Implements the Template Method pattern for source lifecycle management
        - Provides common initialization logic while requiring subclasses to implement
          source-specific operations

    Lifecycle:
        1. __init__: Initialize with configuration
        2. validate(): Verify configuration is correct
        3. fetch(): Retrieve documents from source
        4. health_check(): Monitor source availability (periodic)

    Attributes:
        source_id (str): Unique identifier for this source instance. Used for tracking,
            logging, and associating documents with their source.
        config (Dict[str, Any]): Complete configuration dictionary including all
            settings needed by the source.
        uri (str): Primary location/address of the source. Format depends on source type:
            - LocalSource: file:///path/to/directory
            - WebSource: http://example.com/api
            - DatabaseSource: postgresql://host:port/database
        options (Dict[str, Any]): Source-specific options such as:
            - refresh_interval: How often to re-fetch documents
            - max_documents: Limit on number of documents to fetch
            - filters: Query filters or selection criteria
            - Any source-specific parameters
        auth_config (Dict[str, Any]): Authentication configuration such as:
            - type: "none", "basic", "token", "oauth"
            - credentials: username, password, token, etc.
            - Any authentication-specific settings

    Example:
        >>> # This is an abstract class, use a concrete implementation
        >>> from agentos.core.knowledge.sources.local import LocalSource
        >>> source = LocalSource(
        ...     source_id="local_docs_001",
        ...     config={
        ...         "uri": "file:///data/documents",
        ...         "options": {"file_pattern": "*.txt"},
        ...         "auth_config": {"type": "none"}
        ...     }
        ... )
        >>> validation = source.validate()
        >>> if validation.valid:
        ...     documents = source.fetch()
    """

    def __init__(self, source_id: str, config: Dict[str, Any]):
        """
        Initialize the base source with configuration.

        This constructor extracts common configuration fields that all sources need.
        Subclasses should call super().__init__() and then initialize their
        source-specific fields.

        Args:
            source_id (str): Unique identifier for this source instance. Must be
                unique within the knowledge repository.
            config (Dict[str, Any]): Configuration dictionary containing:
                - uri (str): Source location/address (required)
                - options (Dict[str, Any]): Source-specific options (optional)
                - auth_config (Dict[str, Any]): Authentication settings (optional)
                - Any additional source-specific configuration

        Raises:
            KeyError: If required configuration fields are missing. Subclasses should
                validate their specific requirements in the validate() method.
        """
        self.source_id = source_id
        self.config = config
        self.uri = config.get("uri")
        self.options = config.get("options", {})
        self.auth_config = config.get("auth_config", {})

    @abstractmethod
    def fetch(self) -> List[Document]:
        """
        Fetch documents from the source.

        This is the primary operation of a knowledge source. Implementations should:
        1. Connect to the source using the configured URI and authentication
        2. Retrieve raw data according to the configured options and filters
        3. Transform raw data into Document objects with appropriate metadata
        4. Handle errors gracefully and log failures
        5. Return an empty list if no documents are available

        Returns:
            List[Document]: List of documents retrieved from the source. May be empty
                if no documents are available or if an error occurred. Documents should
                be fully populated with content and metadata.

        Raises:
            Exception: Implementation-specific exceptions for unrecoverable errors.
                Examples: authentication failures, invalid URIs, network errors.
                Temporary errors should be logged but not raised.

        Example:
            >>> documents = source.fetch()
            >>> for doc in documents:
            ...     print(f"Fetched: {doc.metadata.get('title')}")
            ...     print(f"Content length: {len(doc.content)}")
        """
        pass

    @abstractmethod
    def validate(self) -> ValidationResult:
        """
        Validate the source configuration.

        This method checks whether the source is properly configured and can be
        initialized. Implementations should verify:
        1. Required configuration fields are present
        2. URI format is valid for the source type
        3. Authentication credentials are provided if required
        4. Options have valid values and types
        5. Source can be accessed (optional connectivity check)

        This method should be called before attempting to fetch documents. It should
        be fast and not perform heavy operations.

        Returns:
            ValidationResult: Object indicating whether configuration is valid.
                - If valid: ValidationResult(valid=True)
                - If invalid: ValidationResult(valid=False, error="description")

        Example:
            >>> result = source.validate()
            >>> if not result.valid:
            ...     print(f"Configuration error: {result.error}")
            ...     return
            >>> # Proceed with fetch
            >>> documents = source.fetch()
        """
        pass

    @abstractmethod
    def health_check(self) -> HealthCheckResult:
        """
        Perform a health check on the source.

        This method verifies that the source is currently operational and measures
        its performance characteristics. Implementations should:
        1. Attempt to connect to the source
        2. Measure response time and other performance metrics
        3. Verify that the source contains accessible data
        4. Check for any degraded performance conditions
        5. Return detailed metrics for monitoring

        This method is typically called periodically by a monitoring system. It should
        complete quickly (under 5 seconds) to avoid blocking the health check loop.

        Returns:
            HealthCheckResult: Object containing health status and metrics.
                - If healthy: HealthCheckResult(healthy=True, metrics={...})
                - If unhealthy: HealthCheckResult(healthy=False, metrics={...}, error="...")

        Example:
            >>> result = source.health_check()
            >>> if result.healthy:
            ...     print(f"Response time: {result.metrics['response_time_ms']}ms")
            ... else:
            ...     print(f"Health check failed: {result.error}")
            ...     # Trigger alert or retry logic
        """
        pass
