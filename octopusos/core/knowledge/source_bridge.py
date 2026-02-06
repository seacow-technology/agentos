"""
SourceBridge - Knowledge Sources and KB System Bridge
======================================================

This module provides the bridge layer connecting knowledge_sources (user configuration)
and kb_sources/kb_chunks (indexed data). It orchestrates the synchronization workflow
between source configuration and indexed knowledge base.

Key Responsibilities:
    - Synchronize knowledge sources to kb_sources/kb_chunks
    - Update source status throughout the lifecycle
    - Coordinate between Source implementations, Indexer, and Chunker
    - Provide health monitoring for knowledge sources

Architecture Contract (CASE-002 Task 1):
    SourceBridge serves as the connector between two domains:
    1. knowledge_sources: User configuration (managed by KnowledgeSourceRepo)
    2. kb_sources/kb_chunks: Indexed data (managed by ProjectKBIndexer)

    The bridge does NOT manage knowledge_sources lifecycle (no CRUD),
    it only READS configuration and WRITES indexed data.

Workflow:
    1. Read source configuration from knowledge_sources
    2. Validate source configuration
    3. Update status to 'active'
    4. Fetch documents from source
    5. Write to kb_sources and kb_chunks
    6. Update status to 'indexed' or 'error'
"""

import hashlib
import logging
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentos.core.knowledge.source_repo import KnowledgeSourceRepo
from agentos.core.knowledge.sources.base import BaseSource, Document, SourceStatus, ValidationResult, HealthCheckResult
from agentos.core.knowledge.sources.local import LocalSource
from agentos.core.project_kb.chunker import MarkdownChunker
from agentos.core.project_kb.indexer import ProjectKBIndexer
from agentos.core.project_kb.service import ProjectKBService
from agentos.core.project_kb.types import Source, Chunk
from agentos.core.time import utc_now_ms

# Configure logging
logger = logging.getLogger(__name__)


class SyncResult:
    """
    Synchronization result object.

    Encapsulates the outcome of synchronizing a knowledge source to the knowledge base.
    Provides both success/failure status and detailed metrics for monitoring.

    Attributes:
        success (bool): True if synchronization completed successfully
        chunk_count (int): Number of chunks indexed (0 if failed)
        error (Optional[str]): Error message if synchronization failed
        duration_ms (int): Time taken in milliseconds

    Example:
        >>> result = SyncResult(success=True, chunk_count=150, duration_ms=2500)
        >>> print(result.to_dict())
        {'success': True, 'chunk_count': 150, 'error': None, 'duration_ms': 2500}

        >>> result = SyncResult(success=False, error="Path not found", duration_ms=100)
        >>> print(result.to_dict())
        {'success': False, 'chunk_count': 0, 'error': 'Path not found', 'duration_ms': 100}
    """

    def __init__(
        self,
        success: bool,
        chunk_count: int = 0,
        error: Optional[str] = None,
        duration_ms: int = 0
    ):
        """
        Initialize a synchronization result.

        Args:
            success: Whether synchronization succeeded
            chunk_count: Number of chunks indexed (default: 0)
            error: Error message if failed (default: None)
            duration_ms: Duration in milliseconds (default: 0)
        """
        self.success = success
        self.chunk_count = chunk_count
        self.error = error
        self.duration_ms = duration_ms

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert result to dictionary for serialization.

        Returns:
            Dictionary with success, chunk_count, error, duration_ms keys
        """
        return {
            "success": self.success,
            "chunk_count": self.chunk_count,
            "error": self.error,
            "duration_ms": self.duration_ms
        }


class SourceBridge:
    """
    Bridge layer connecting knowledge_sources and kb_sources/kb_chunks.

    This class orchestrates the synchronization of knowledge sources from user
    configuration to the indexed knowledge base. It coordinates between multiple
    subsystems:
    - KnowledgeSourceRepo: Manages source configuration
    - BaseSource implementations: Fetch documents from various sources
    - ProjectKBIndexer: Writes indexed data
    - MarkdownChunker: Splits documents into chunks

    Architecture:
        SourceBridge follows the Contract 1A transition bridge pattern:
        - READ from knowledge_sources (via KnowledgeSourceRepo)
        - WRITE to kb_sources/kb_chunks (via ProjectKBIndexer)
        - UPDATE knowledge_sources status fields only
        - NO CRUD operations on knowledge_sources

    Synchronization Workflow (7 Steps):
        1. Read source configuration from knowledge_sources
        2. Create appropriate BaseSource instance
        3. Validate source configuration
        4. Update status to 'active'
        5. Fetch documents from source
        6. Write to kb_sources and kb_chunks
        7. Update status to 'indexed' or 'error'

    Attributes:
        source_repo: Repository for knowledge source configuration
        kb_service: ProjectKB service (provides indexer and chunker)
        chunker: Document chunker (MarkdownChunker)

    Example:
        >>> from agentos.core.knowledge.source_bridge import SourceBridge
        >>> from agentos.core.knowledge.source_repo import KnowledgeSourceRepo
        >>>
        >>> # Create test source
        >>> repo = KnowledgeSourceRepo()
        >>> source_id = repo.create({
        ...     "id": "test-001",
        ...     "name": "Test Docs",
        ...     "source_type": "local",
        ...     "uri": "file:///tmp/test_docs",
        ...     "status": "pending"
        ... })
        >>>
        >>> # Sync source
        >>> bridge = SourceBridge()
        >>> result = bridge.sync_source(source_id)
        >>>
        >>> # Verify
        >>> assert result.success == True
        >>> assert result.chunk_count > 0
        >>>
        >>> # Check updated source
        >>> updated = repo.get(source_id)
        >>> assert updated["status"] == "indexed"
        >>> assert updated["chunk_count"] == result.chunk_count
    """

    def __init__(
        self,
        source_repo: Optional[KnowledgeSourceRepo] = None,
        kb_service: Optional[ProjectKBService] = None
    ):
        """
        Initialize the bridge layer.

        Creates or uses existing instances of the required subsystems.
        If not provided, default instances are created.

        Args:
            source_repo: Knowledge source repository (default: create new instance)
            kb_service: ProjectKB service (default: create new instance)
        """
        self.source_repo = source_repo or KnowledgeSourceRepo()
        self.kb_service = kb_service or ProjectKBService()
        self.chunker = self.kb_service.chunker

        logger.info("SourceBridge initialized")

    def sync_source(self, source_id: str) -> SyncResult:
        """
        Synchronize a single knowledge source to the knowledge base.

        This is the main synchronization method that implements the 7-step workflow:

        Workflow Steps:
            1. Read source configuration from knowledge_sources table
            2. Create appropriate BaseSource instance based on source_type
            3. Validate source configuration (URI, auth, options)
            4. Update status to 'active' (source is now operational)
            5. Fetch documents from the source
            6. Write documents to kb_sources and kb_chunks
            7. Update status to 'indexed' (success) or 'error' (failure)

        Error Handling:
            All exceptions are caught and logged. The source status is updated
            to 'error' with the error message stored in metadata.last_error.
            Returns a SyncResult with success=False and error details.

        Args:
            source_id: Unique identifier of the knowledge source

        Returns:
            SyncResult: Object containing:
                - success: True if sync completed successfully
                - chunk_count: Number of chunks indexed
                - error: Error message if failed
                - duration_ms: Time taken in milliseconds

        Example:
            >>> bridge = SourceBridge()
            >>> result = bridge.sync_source("local-docs-001")
            >>>
            >>> if result.success:
            ...     print(f"Synced {result.chunk_count} chunks in {result.duration_ms}ms")
            ... else:
            ...     print(f"Sync failed: {result.error}")
        """
        start_time = time.time()

        try:
            # Step 1: Read source configuration
            logger.info(f"Starting sync for source: {source_id}")
            source_config = self.source_repo.get(source_id)

            if not source_config:
                error_msg = f"Source not found: {source_id}"
                logger.error(error_msg)
                return SyncResult(success=False, error=error_msg)

            # Step 2: Create BaseSource instance
            source_instance = self._create_source_instance(source_config)

            if not source_instance:
                error_msg = f"Unsupported source type: {source_config.get('source_type')}"
                logger.error(error_msg)
                self._update_status(source_id, SourceStatus.FAILED, error=error_msg)
                return SyncResult(success=False, error=error_msg)

            # Step 3: Validate configuration
            logger.info(f"Validating source configuration: {source_id}")
            validation = source_instance.validate()

            if not validation.valid:
                error_msg = f"Validation failed: {validation.error}"
                logger.error(f"Source {source_id} validation failed: {validation.error}")
                self._update_status(source_id, SourceStatus.FAILED, error=validation.error)
                return SyncResult(success=False, error=error_msg)

            # Step 4: Update status to active
            logger.info(f"Source {source_id} validated, updating status to active")
            self._update_status(source_id, SourceStatus.ACTIVE)

            # Step 5: Fetch documents
            logger.info(f"Fetching documents from source: {source_id}")
            documents = source_instance.fetch()

            if not documents:
                error_msg = "No documents fetched from source"
                logger.warning(f"Source {source_id} returned no documents")
                self._update_status(source_id, SourceStatus.ERROR, error=error_msg)
                return SyncResult(success=False, error=error_msg)

            logger.info(f"Fetched {len(documents)} documents from source {source_id}")

            # Step 6: Write to kb_sources and kb_chunks
            chunk_count = self._write_to_kb(source_id, source_config, documents)

            # Step 7: Update status to indexed
            duration_ms = int((time.time() - start_time) * 1000)
            self._update_status(
                source_id,
                SourceStatus.INDEXED,
                chunk_count=chunk_count,
                last_indexed_at=utc_now_ms()
            )

            logger.info(
                f"Successfully synced source {source_id}: "
                f"{chunk_count} chunks indexed in {duration_ms}ms"
            )

            return SyncResult(
                success=True,
                chunk_count=chunk_count,
                duration_ms=duration_ms
            )

        except Exception as e:
            # Catch all exceptions and update status to error
            logger.error(f"Failed to sync source {source_id}: {e}", exc_info=True)
            self._update_status(source_id, SourceStatus.ERROR, error=str(e))

            duration_ms = int((time.time() - start_time) * 1000)
            return SyncResult(success=False, error=str(e), duration_ms=duration_ms)

    def sync_all_sources(self) -> List[SyncResult]:
        """
        Batch synchronize all active knowledge sources.

        Iterates through all sources with status='active' and synchronizes
        each one using sync_source(). This is useful for:
        - Initial bulk indexing
        - Scheduled refresh operations
        - Manual re-indexing of all sources

        Process:
            1. Query all sources with status='active' from knowledge_sources
            2. For each source, call sync_source() and collect result
            3. Return list of all results for monitoring

        Error Handling:
            Individual source failures do not stop the batch process.
            Each result contains success/failure status and error details.

        Returns:
            List[SyncResult]: Results for each synchronized source

        Example:
            >>> bridge = SourceBridge()
            >>> results = bridge.sync_all_sources()
            >>>
            >>> # Check results
            >>> successes = [r for r in results if r.success]
            >>> failures = [r for r in results if not r.success]
            >>>
            >>> print(f"Synced {len(successes)} sources successfully")
            >>> print(f"Failed to sync {len(failures)} sources")
            >>>
            >>> # Show errors
            >>> for result in failures:
            ...     print(f"Error: {result.error}")
        """
        logger.info("Starting batch sync for all active sources")

        # Query all active sources
        sources = self.source_repo.list(status=SourceStatus.ACTIVE.value)
        logger.info(f"Found {len(sources)} active sources to sync")

        results = []

        for source in sources:
            source_id = source["id"]
            logger.info(f"Syncing source {source_id} (batch mode)")

            result = self.sync_source(source_id)
            results.append(result)

        # Log summary
        successes = sum(1 for r in results if r.success)
        failures = len(results) - successes
        total_chunks = sum(r.chunk_count for r in results if r.success)

        logger.info(
            f"Batch sync completed: {successes} succeeded, {failures} failed, "
            f"{total_chunks} total chunks indexed"
        )

        return results

    def check_source_health(self, source_id: str) -> Dict[str, Any]:
        """
        Check the health status of a knowledge source.

        Performs a health check on the underlying source to verify it is
        operational and accessible. This includes:
        - Connectivity checks
        - Permission verification
        - Resource availability
        - Performance metrics

        Process:
            1. Read source configuration from knowledge_sources
            2. Create appropriate BaseSource instance
            3. Call health_check() method on the source
            4. Return health status and metrics

        Args:
            source_id: Unique identifier of the knowledge source

        Returns:
            Dict[str, Any]: Health check result with keys:
                - healthy (bool): True if source is operational
                - metrics (dict): Performance and availability metrics
                - error (str): Error message if unhealthy

        Example:
            >>> bridge = SourceBridge()
            >>> health = bridge.check_source_health("local-docs-001")
            >>>
            >>> if health["healthy"]:
            ...     print(f"Source is healthy")
            ...     print(f"File count: {health['metrics']['file_count']}")
            ...     print(f"Disk usage: {health['metrics']['disk_usage_mb']} MB")
            ... else:
            ...     print(f"Source is unhealthy: {health['error']}")
        """
        logger.info(f"Checking health for source: {source_id}")

        # Read source configuration
        source_config = self.source_repo.get(source_id)

        if not source_config:
            logger.error(f"Source not found: {source_id}")
            return {
                "healthy": False,
                "error": f"Source not found: {source_id}"
            }

        # Create source instance
        source_instance = self._create_source_instance(source_config)

        if not source_instance:
            error_msg = f"Unsupported source type: {source_config.get('source_type')}"
            logger.error(error_msg)
            return {
                "healthy": False,
                "error": error_msg
            }

        # Perform health check
        try:
            health = source_instance.health_check()
            result = health.to_dict()

            if result["healthy"]:
                logger.info(f"Source {source_id} is healthy")
            else:
                logger.warning(f"Source {source_id} is unhealthy: {result.get('error')}")

            return result

        except Exception as e:
            logger.error(f"Health check failed for source {source_id}: {e}", exc_info=True)
            return {
                "healthy": False,
                "error": f"Health check exception: {str(e)}"
            }

    def _create_source_instance(self, source_config: Dict[str, Any]) -> Optional[BaseSource]:
        """
        Create a BaseSource instance based on source_type.

        Factory method that instantiates the appropriate Source implementation
        based on the source_type field in the configuration. Currently supports:
        - local/directory/file: LocalSource

        Future implementations can add:
        - web: WebSource
        - api: APISource
        - database: DatabaseSource

        Args:
            source_config: Source configuration dictionary with fields:
                - id: Source identifier
                - source_type: Type of source (local, web, api, database)
                - uri: Source location
                - options: Source-specific options
                - auth_config: Authentication configuration

        Returns:
            BaseSource instance if source_type is supported, None otherwise
        """
        source_id = source_config["id"]
        source_type = source_config.get("source_type", "").lower()

        logger.debug(f"Creating source instance for {source_id} (type: {source_type})")

        # Local file sources
        if source_type in ["local", "directory", "file"]:
            return LocalSource(source_id=source_id, config=source_config)

        # Future: Add more source types
        # elif source_type == "web":
        #     return WebSource(source_id=source_id, config=source_config)
        # elif source_type == "api":
        #     return APISource(source_id=source_id, config=source_config)
        # elif source_type == "database":
        #     return DatabaseSource(source_id=source_id, config=source_config)

        else:
            logger.error(f"Unsupported source type: {source_type}")
            return None

    def _write_to_kb(
        self,
        source_id: str,
        source_config: Dict[str, Any],
        documents: List[Document]
    ) -> int:
        """
        Write documents to kb_sources and kb_chunks.

        This method implements Step 6 of the synchronization workflow:
        1. Iterate through all fetched documents
        2. For each document, create a kb_source record
        3. Chunk the document content using MarkdownChunker
        4. Insert all chunks into kb_chunks
        5. Return total chunk count

        Data Mapping:
            Document -> kb_source:
                - source_id: "{knowledge_source_id}:{file_hash}"
                - repo_id: Extracted from metadata or default
                - path: From document metadata
                - file_hash: SHA256 hash (first 16 chars)
                - mtime: Last modification time (epoch ms)
                - doc_type: Document type (md, txt, py, etc.)
                - language: Content language

            Document content -> kb_chunks:
                - Chunked using MarkdownChunker
                - Each chunk linked to kb_source via source_id

        Args:
            source_id: Knowledge source identifier
            source_config: Source configuration dictionary
            documents: List of Document objects from source.fetch()

        Returns:
            int: Total number of chunks indexed
        """
        chunk_count = 0
        indexer = self.kb_service.indexer

        # Extract repo_id from metadata or use default
        metadata = source_config.get("metadata") or {}
        repo_id = metadata.get("project_id", "default") if isinstance(metadata, dict) else "default"

        logger.info(f"Writing {len(documents)} documents to kb for source {source_id}")

        for doc in documents:
            try:
                file_path = doc.metadata.get("file_path", "unknown")

                # Generate file hash from content
                content_bytes = doc.content.encode('utf-8')
                file_hash = hashlib.sha256(content_bytes).hexdigest()[:16]

                # Get modification time from metadata
                mtime = doc.metadata.get("mtime", utc_now_ms())

                # Create kb_source record
                kb_source = Source(
                    source_id=f"{source_id}:{file_hash}",
                    repo_id=repo_id,
                    path=file_path,
                    file_hash=file_hash,
                    mtime=mtime,
                    doc_type=doc.metadata.get("doc_type", "md"),
                    language=doc.metadata.get("language", "en"),
                    tags=[]
                )

                # Upsert source to kb_sources table
                indexer.upsert_source(kb_source)
                logger.debug(f"Upserted kb_source: {kb_source.source_id}")

                # Chunk the document content
                # MarkdownChunker.chunk_file() expects a file path, so we need to
                # write the content to a temporary file
                chunks_list = []
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.md') as tmp_file:
                    tmp_file.write(doc.content)
                    tmp_file_path = tmp_file.name

                try:
                    # Chunk the temporary file
                    for chunk in self.chunker.chunk_file(kb_source.source_id, Path(tmp_file_path)):
                        chunks_list.append(chunk)

                    # Insert all chunks into kb_chunks
                    for chunk in chunks_list:
                        indexer.insert_chunk(chunk)
                        chunk_count += 1

                    logger.debug(f"Indexed {len(chunks_list)} chunks from {file_path}")

                finally:
                    # Clean up temporary file
                    import os
                    try:
                        os.unlink(tmp_file_path)
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to clean up temporary file {tmp_file_path}: {cleanup_error}")

            except Exception as e:
                logger.error(f"Failed to write document to kb: {file_path}: {e}", exc_info=True)
                # Continue with next document even if one fails
                continue

        logger.info(f"Wrote {chunk_count} chunks to kb for source {source_id}")

        return chunk_count

    def _update_status(
        self,
        source_id: str,
        status: SourceStatus,
        error: Optional[str] = None,
        chunk_count: Optional[int] = None,
        last_indexed_at: Optional[int] = None
    ):
        """
        Update knowledge source status and metadata.

        This is a wrapper around source_repo.update_status() that provides
        type-safe status updates using the SourceStatus enum. It updates:
        - status: Current lifecycle state
        - error: Error message (stored in metadata.last_error)
        - chunk_count: Number of indexed chunks
        - last_indexed_at: Timestamp of last successful indexing

        Status Transitions:
            pending -> active: Configuration validated
            active -> indexed: Documents successfully indexed
            active -> error: Temporary failure (can retry)
            active -> failed: Permanent failure (needs manual fix)

        Args:
            source_id: Knowledge source identifier
            status: New status (SourceStatus enum)
            error: Optional error message
            chunk_count: Optional chunk count
            last_indexed_at: Optional last indexed timestamp (epoch ms)
        """
        logger.debug(
            f"Updating source {source_id} status to {status.value}"
            + (f" (error: {error})" if error else "")
        )

        try:
            self.source_repo.update_status(
                source_id=source_id,
                status=status.value,
                error=error,
                chunk_count=chunk_count,
                last_indexed_at=last_indexed_at
            )
        except Exception as e:
            logger.error(f"Failed to update source status: {source_id}: {e}", exc_info=True)
            # Don't raise - status update failure shouldn't break the workflow
