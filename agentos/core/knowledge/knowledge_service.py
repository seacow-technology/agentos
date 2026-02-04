"""
Knowledge Service - RAG health checks and diagnostics

This module provides health check functionality for knowledge base sources,
implementing Contract 4 (Health Check Real Health Status).

Features:
- Single source health checks with real metrics
- Batch health checks for all sources
- Real health indicators: last_indexed_at, chunk_count, error_count, status
"""

import logging
import sqlite3
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from agentos.store import get_db
from agentos.core.time import utc_now_ms

logger = logging.getLogger(__name__)


class KnowledgeService:
    """Service for knowledge base management and health checks"""

    def __init__(self):
        """Initialize knowledge service"""
        pass

    def check_connection(self, source_id: str) -> Dict[str, Any]:
        """
        Check health status of a single knowledge source

        Queries the database for real source information and metrics:
        - Source status and indexing timestamp
        - Number of chunks associated with source
        - Error tracking if applicable

        Args:
            source_id: Source ID to check

        Returns:
            Dict with health status:
            - If healthy:
                {
                    "ok": True,
                    "source_id": "src-001",
                    "status": "indexed",
                    "last_indexed_at": 1738416000000,
                    "chunk_count": 250,
                    "error_count": 0,
                    "message": "Source is healthy"
                }
            - If source not found:
                {"ok": False, "error": "Source not found"}
            - If database error:
                {"ok": False, "error": "Database error: ..."}

        Example:
            >>> service = KnowledgeService()
            >>> health = service.check_connection("src-001")
            >>> assert health["ok"] == True
            >>> assert "chunk_count" in health
            >>> assert "last_indexed_at" in health
        """
        try:
            conn = get_db()
            cursor = conn.cursor()

            # Query knowledge_sources table for source info
            try:
                source_row = cursor.execute(
                    "SELECT id, status, last_indexed_at, chunk_count FROM knowledge_sources WHERE id = ?",
                    (source_id,)
                ).fetchone()

                if not source_row:
                    return {
                        "ok": False,
                        "error": "Source not found"
                    }

                source_dict = dict(source_row) if hasattr(source_row, 'keys') else {
                    'id': source_row[0],
                    'status': source_row[1],
                    'last_indexed_at': source_row[2],
                    'chunk_count': source_row[3]
                }

            except sqlite3.OperationalError:
                # Table might not exist yet
                return {
                    "ok": False,
                    "error": "Source not found"
                }

            # Get chunk count from kb_chunks table for this source
            # Note: kb_chunks.source_id is in format "{knowledge_source_id}:{file_hash}"
            try:
                chunk_count_row = cursor.execute(
                    "SELECT COUNT(*) FROM kb_chunks WHERE source_id LIKE ?",
                    (f"{source_id}:%",)
                ).fetchone()

                actual_chunk_count = chunk_count_row[0] if chunk_count_row else 0
            except sqlite3.OperationalError:
                # Table might not exist yet, use stored chunk_count
                actual_chunk_count = source_dict.get('chunk_count', 0)

            # Try to get error count from audit table or error tracking
            try:
                error_count_row = cursor.execute(
                    "SELECT COUNT(*) FROM knowledge_source_audit "
                    "WHERE source_id = ? AND action = 'update' AND new_values LIKE '%error%'",
                    (source_id,)
                ).fetchone()

                error_count = error_count_row[0] if error_count_row else 0
            except sqlite3.OperationalError:
                error_count = 0

            # Determine health message
            status = source_dict.get('status', 'unknown')
            if status == 'indexed':
                message = "Source is healthy"
            elif status == 'pending':
                message = "Source pending indexing"
            elif status == 'error' or status == 'failed':
                message = f"Source has error status: {status}"
            else:
                message = f"Source status: {status}"

            return {
                "ok": True,
                "source_id": source_id,
                "status": status,
                "last_indexed_at": source_dict.get('last_indexed_at'),
                "chunk_count": actual_chunk_count,
                "error_count": error_count,
                "message": message
            }

        except sqlite3.Error as e:
            logger.error(f"Database error checking source {source_id}: {e}")
            return {
                "ok": False,
                "error": f"Database error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error checking source {source_id}: {e}")
            return {
                "ok": False,
                "error": f"Unexpected error: {str(e)}"
            }

    def check_all_sources_health(self) -> List[Dict[str, Any]]:
        """
        Check health status of all knowledge sources

        Returns a list of health status for all sources in the knowledge_sources table.
        Each entry contains the same information as check_connection() but for all sources.

        Returns:
            List of health status dictionaries:
            [
                {
                    "ok": True,
                    "source_id": "src-001",
                    "status": "indexed",
                    "last_indexed_at": 1738416000000,
                    "chunk_count": 250,
                    "error_count": 0,
                    "message": "Source is healthy"
                },
                ...
            ]

        Example:
            >>> service = KnowledgeService()
            >>> healths = service.check_all_sources_health()
            >>> for health in healths:
            ...     print(f"{health['source_id']}: {health['message']}")
        """
        try:
            conn = get_db()
            cursor = conn.cursor()

            # Query all sources
            try:
                sources_rows = cursor.execute(
                    "SELECT id, status, last_indexed_at, chunk_count FROM knowledge_sources"
                ).fetchall()
            except sqlite3.OperationalError:
                # Table doesn't exist yet
                logger.warning("knowledge_sources table does not exist yet")
                return []

            health_results = []

            for source_row in sources_rows:
                # Convert row to dict
                source_dict = dict(source_row) if hasattr(source_row, 'keys') else {
                    'id': source_row[0],
                    'status': source_row[1],
                    'last_indexed_at': source_row[2],
                    'chunk_count': source_row[3]
                }

                source_id = source_dict['id']

                # Get actual chunk count from kb_chunks table
                # Note: kb_chunks.source_id is in format "{knowledge_source_id}:{file_hash}"
                try:
                    chunk_count_row = cursor.execute(
                        "SELECT COUNT(*) FROM kb_chunks WHERE source_id LIKE ?",
                        (f"{source_id}:%",)
                    ).fetchone()

                    actual_chunk_count = chunk_count_row[0] if chunk_count_row else 0
                except sqlite3.OperationalError:
                    actual_chunk_count = source_dict.get('chunk_count', 0)

                # Get error count from audit table
                try:
                    error_count_row = cursor.execute(
                        "SELECT COUNT(*) FROM knowledge_source_audit "
                        "WHERE source_id = ? AND action = 'update' AND new_values LIKE '%error%'",
                        (source_id,)
                    ).fetchone()

                    error_count = error_count_row[0] if error_count_row else 0
                except sqlite3.OperationalError:
                    error_count = 0

                # Determine message
                status = source_dict.get('status', 'unknown')
                if status == 'indexed':
                    message = "Source is healthy"
                elif status == 'pending':
                    message = "Source pending indexing"
                elif status == 'error' or status == 'failed':
                    message = f"Source has error status: {status}"
                else:
                    message = f"Source status: {status}"

                health_results.append({
                    "ok": True,
                    "source_id": source_id,
                    "status": status,
                    "last_indexed_at": source_dict.get('last_indexed_at'),
                    "chunk_count": actual_chunk_count,
                    "error_count": error_count,
                    "message": message
                })

            return health_results

        except sqlite3.Error as e:
            logger.error(f"Database error checking all sources: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error checking all sources: {e}")
            return []
