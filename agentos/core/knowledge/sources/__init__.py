"""
Knowledge Sources Package
=========================

This package provides the knowledge source infrastructure for AgentOS.

Knowledge sources are external data providers that supply documents to be indexed
and searched within the knowledge management system. This package defines:

1. Base abstractions (BaseSource, Document, SourceStatus)
2. Concrete implementations (LocalSource, WebSource, DatabaseSource, etc.)
3. Source lifecycle management and monitoring utilities

Exported Classes:
    - BaseSource: Abstract base class for all knowledge sources
    - Document: Immutable document representation
    - SourceStatus: Enum defining source lifecycle states
    - ValidationResult: Configuration validation result object
    - HealthCheckResult: Health check result object

Usage:
    >>> from agentos.core.knowledge.sources import BaseSource, Document, SourceStatus
    >>> from agentos.core.knowledge.sources.local import LocalSource
    >>>
    >>> # Create a local file source
    >>> source = LocalSource(
    ...     source_id="my_docs",
    ...     config={
    ...         "uri": "file:///path/to/docs",
    ...         "options": {"file_pattern": "*.txt"}
    ...     }
    ... )
    >>>
    >>> # Validate configuration
    >>> validation = source.validate()
    >>> if not validation.valid:
    ...     print(f"Error: {validation.error}")
    ...
    >>> # Fetch documents
    >>> documents = source.fetch()
    >>> for doc in documents:
    ...     print(f"Fetched: {doc.metadata['title']}")

Architecture:
    All knowledge sources follow a common lifecycle:
    1. Creation: Instantiate with source_id and config
    2. Validation: Verify configuration correctness
    3. Fetching: Retrieve documents from source
    4. Monitoring: Periodic health checks

    Sources can be in various states (PENDING, ACTIVE, INDEXED, INACTIVE, ERROR, FAILED)
    as defined by the SourceStatus enum.
"""

from agentos.core.knowledge.sources.base import (
    BaseSource,
    Document,
    SourceStatus,
    ValidationResult,
    HealthCheckResult,
)

__all__ = [
    "BaseSource",
    "Document",
    "SourceStatus",
    "ValidationResult",
    "HealthCheckResult",
]
