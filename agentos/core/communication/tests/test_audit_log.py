"""Tests for audit logging and evidence tracking.

This module tests the evidence logging system to ensure
proper audit trails for all communication operations.
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from agentos.core.communication.models import (
    CommunicationRequest,
    CommunicationResponse,
    ConnectorType,
    RequestStatus,
    EvidenceRecord,
)
from agentos.core.communication.evidence import EvidenceLogger
from agentos.core.communication.storage.sqlite_store import SQLiteStore


class TestEvidenceLogger:
    """Test suite for EvidenceLogger."""

    def setup_method(self):
        """Set up test fixtures with temporary database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_communication.db"
        self.storage = SQLiteStore(self.db_path)
        self.logger = EvidenceLogger(storage=self.storage)

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.db_path.exists():
            self.db_path.unlink()

    @pytest.mark.asyncio
    async def test_log_operation(self):
        """Test logging a communication operation."""
        request = CommunicationRequest(
            id="req-test-1",
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            params={"query": "test query"},
        )
        response = CommunicationResponse(
            request_id=request.id,
            status=RequestStatus.SUCCESS,
            data={"results": []},
        )

        evidence_id = await self.logger.log_operation(request, response)
        assert evidence_id is not None
        assert evidence_id.startswith("ev-")

    @pytest.mark.asyncio
    async def test_get_evidence_by_id(self):
        """Test retrieving evidence by ID."""
        request = CommunicationRequest(
            id="req-test-2",
            connector_type=ConnectorType.WEB_FETCH,
            operation="fetch",
            params={"url": "https://example.com"},
        )
        response = CommunicationResponse(
            request_id=request.id,
            status=RequestStatus.SUCCESS,
        )

        evidence_id = await self.logger.log_operation(request, response)
        evidence = await self.logger.get_evidence(evidence_id)

        assert evidence is not None
        assert evidence.id == evidence_id
        assert evidence.request_id == request.id
        assert evidence.connector_type == ConnectorType.WEB_FETCH

    @pytest.mark.asyncio
    async def test_get_evidence_by_request_id(self):
        """Test retrieving evidence by request ID."""
        request = CommunicationRequest(
            id="req-test-3",
            connector_type=ConnectorType.RSS,
            operation="fetch_feed",
            params={"feed_url": "https://example.com/feed.xml"},
        )
        response = CommunicationResponse(
            request_id=request.id,
            status=RequestStatus.SUCCESS,
        )

        await self.logger.log_operation(request, response)
        evidence = await self.logger.get_request_evidence(request.id)

        assert evidence is not None
        assert evidence.request_id == request.id

    @pytest.mark.asyncio
    async def test_search_evidence_by_connector(self):
        """Test searching evidence by connector type."""
        # Create multiple evidence records
        for i in range(3):
            request = CommunicationRequest(
                id=f"req-test-search-{i}",
                connector_type=ConnectorType.WEB_SEARCH,
                operation="search",
                params={"query": f"test query {i}"},
            )
            response = CommunicationResponse(
                request_id=request.id,
                status=RequestStatus.SUCCESS,
            )
            await self.logger.log_operation(request, response)

        results = await self.logger.search_evidence(
            connector_type="web_search",
            limit=10,
        )

        assert len(results) >= 3
        assert all(r.connector_type == ConnectorType.WEB_SEARCH for r in results)

    @pytest.mark.asyncio
    async def test_search_evidence_by_status(self):
        """Test searching evidence by status."""
        # Create success record
        request1 = CommunicationRequest(
            id="req-success",
            connector_type=ConnectorType.WEB_FETCH,
            operation="fetch",
            params={"url": "https://example.com"},
        )
        response1 = CommunicationResponse(
            request_id=request1.id,
            status=RequestStatus.SUCCESS,
        )
        await self.logger.log_operation(request1, response1)

        # Create failed record
        request2 = CommunicationRequest(
            id="req-failed",
            connector_type=ConnectorType.WEB_FETCH,
            operation="fetch",
            params={"url": "https://example.com"},
        )
        response2 = CommunicationResponse(
            request_id=request2.id,
            status=RequestStatus.FAILED,
            error="Connection timeout",
        )
        await self.logger.log_operation(request2, response2)

        # Search for failed records
        results = await self.logger.search_evidence(
            status=RequestStatus.FAILED,
            limit=10,
        )

        assert len(results) >= 1
        assert all(r.status == RequestStatus.FAILED for r in results)

    @pytest.mark.asyncio
    async def test_get_total_requests(self):
        """Test getting total request count."""
        initial_count = await self.logger.get_total_requests()

        # Add some requests
        for i in range(3):
            request = CommunicationRequest(
                id=f"req-count-{i}",
                connector_type=ConnectorType.WEB_SEARCH,
                operation="search",
                params={"query": "test"},
            )
            response = CommunicationResponse(
                request_id=request.id,
                status=RequestStatus.SUCCESS,
            )
            await self.logger.log_operation(request, response)

        final_count = await self.logger.get_total_requests()
        assert final_count >= initial_count + 3

    @pytest.mark.asyncio
    async def test_get_success_rate(self):
        """Test calculating success rate."""
        # Add successful request
        request1 = CommunicationRequest(
            id="req-rate-success",
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            params={"query": "test"},
        )
        response1 = CommunicationResponse(
            request_id=request1.id,
            status=RequestStatus.SUCCESS,
        )
        await self.logger.log_operation(request1, response1)

        # Add failed request
        request2 = CommunicationRequest(
            id="req-rate-failed",
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            params={"query": "test"},
        )
        response2 = CommunicationResponse(
            request_id=request2.id,
            status=RequestStatus.FAILED,
        )
        await self.logger.log_operation(request2, response2)

        success_rate = await self.logger.get_success_rate()
        assert 0 <= success_rate <= 100

    @pytest.mark.asyncio
    async def test_export_evidence(self):
        """Test exporting evidence to JSON."""
        # Create some evidence
        request = CommunicationRequest(
            id="req-export",
            connector_type=ConnectorType.EMAIL_SMTP,
            operation="send",
            params={"to": "test@example.com", "subject": "Test", "body": "Test"},
        )
        response = CommunicationResponse(
            request_id=request.id,
            status=RequestStatus.SUCCESS,
        )
        await self.logger.log_operation(request, response)

        # Export
        output_path = Path(self.temp_dir) / "export.json"
        result_path = await self.logger.export_evidence(output_path=output_path)

        assert result_path.exists()
        assert result_path.stat().st_size > 0


class TestEvidenceRecord:
    """Test suite for EvidenceRecord model."""

    def test_evidence_creation(self):
        """Test creating an evidence record."""
        evidence = EvidenceRecord(
            id="ev-test-1",
            request_id="req-test-1",
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            request_summary={"query": "test"},
            response_summary={"results": 5},
            status=RequestStatus.SUCCESS,
        )

        assert evidence.id == "ev-test-1"
        assert evidence.connector_type == ConnectorType.WEB_SEARCH
        assert evidence.status == RequestStatus.SUCCESS

    def test_evidence_to_dict(self):
        """Test converting evidence to dictionary."""
        evidence = EvidenceRecord(
            id="ev-test-2",
            request_id="req-test-2",
            connector_type=ConnectorType.RSS,
            operation="fetch_feed",
            request_summary={"feed_url": "https://example.com/feed"},
            status=RequestStatus.SUCCESS,
        )

        evidence_dict = evidence.to_dict()
        assert evidence_dict["id"] == "ev-test-2"
        assert evidence_dict["connector_type"] == "rss"
        assert "created_at" in evidence_dict
