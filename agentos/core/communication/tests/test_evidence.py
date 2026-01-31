"""Tests for Evidence logging system.

This module tests the evidence logging functionality for audit trails,
compliance, and security analysis.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta

from agentos.core.communication.models import (
    CommunicationRequest,
    CommunicationResponse,
    ConnectorType,
    RequestStatus,
    RiskLevel,
    EvidenceRecord,
)
from agentos.core.communication.evidence import EvidenceLogger
from agentos.core.communication.storage.sqlite_store import SQLiteStore


class TestEvidenceLoggerBasics:
    """Basic tests for EvidenceLogger."""

    def setup_method(self):
        """Set up test fixtures with temporary database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_evidence.db"
        self.storage = SQLiteStore(self.db_path)
        self.logger = EvidenceLogger(storage=self.storage)

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.db_path.exists():
            self.db_path.unlink()

    @pytest.mark.asyncio
    async def test_log_operation_creates_evidence(self):
        """Test that logging an operation creates evidence record."""
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
        assert len(evidence_id) > 10

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
        assert evidence.operation == "fetch"
        assert evidence.status == RequestStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_get_nonexistent_evidence(self):
        """Test retrieving nonexistent evidence returns None."""
        evidence = await self.logger.get_evidence("ev-nonexistent")
        assert evidence is None

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


class TestEvidenceSearch:
    """Test suite for evidence search functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_search.db"
        self.storage = SQLiteStore(self.db_path)
        self.logger = EvidenceLogger(storage=self.storage)

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.db_path.exists():
            self.db_path.unlink()

    @pytest.mark.asyncio
    async def test_search_by_connector_type(self):
        """Test searching evidence by connector type."""
        # Create evidence for different connectors
        for i in range(3):
            request = CommunicationRequest(
                id=f"req-search-{i}",
                connector_type=ConnectorType.WEB_SEARCH,
                operation="search",
                params={"query": f"query {i}"},
            )
            response = CommunicationResponse(
                request_id=request.id,
                status=RequestStatus.SUCCESS,
            )
            await self.logger.log_operation(request, response)

        # Create evidence for different connector
        request2 = CommunicationRequest(
            id="req-other",
            connector_type=ConnectorType.WEB_FETCH,
            operation="fetch",
            params={"url": "https://example.com"},
        )
        response2 = CommunicationResponse(
            request_id=request2.id,
            status=RequestStatus.SUCCESS,
        )
        await self.logger.log_operation(request2, response2)

        # Search for web_search
        results = await self.logger.search_evidence(
            connector_type="web_search",
            limit=10,
        )

        assert len(results) >= 3
        assert all(r.connector_type == ConnectorType.WEB_SEARCH for r in results)

    @pytest.mark.asyncio
    async def test_search_by_operation(self):
        """Test searching evidence by operation."""
        # Create evidence with different operations
        request1 = CommunicationRequest(
            id="req-op-1",
            connector_type=ConnectorType.WEB_FETCH,
            operation="fetch",
            params={"url": "https://example.com"},
        )
        response1 = CommunicationResponse(
            request_id=request1.id,
            status=RequestStatus.SUCCESS,
        )
        await self.logger.log_operation(request1, response1)

        request2 = CommunicationRequest(
            id="req-op-2",
            connector_type=ConnectorType.WEB_FETCH,
            operation="download",
            params={"url": "https://example.com/file.pdf"},
        )
        response2 = CommunicationResponse(
            request_id=request2.id,
            status=RequestStatus.SUCCESS,
        )
        await self.logger.log_operation(request2, response2)

        # Search for fetch operation
        results = await self.logger.search_evidence(
            operation="fetch",
            limit=10,
        )

        assert len(results) >= 1
        assert all(r.operation == "fetch" for r in results)

    @pytest.mark.asyncio
    async def test_search_by_status(self):
        """Test searching evidence by status."""
        # Create successful evidence
        request1 = CommunicationRequest(
            id="req-success",
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            params={"query": "test"},
        )
        response1 = CommunicationResponse(
            request_id=request1.id,
            status=RequestStatus.SUCCESS,
        )
        await self.logger.log_operation(request1, response1)

        # Create failed evidence
        request2 = CommunicationRequest(
            id="req-failed",
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            params={"query": "test"},
        )
        response2 = CommunicationResponse(
            request_id=request2.id,
            status=RequestStatus.FAILED,
            error="Network timeout",
        )
        await self.logger.log_operation(request2, response2)

        # Search for failed requests
        results = await self.logger.search_evidence(
            status=RequestStatus.FAILED,
            limit=10,
        )

        assert len(results) >= 1
        assert all(r.status == RequestStatus.FAILED for r in results)

    @pytest.mark.asyncio
    async def test_search_with_date_range(self):
        """Test searching evidence with date range."""
        # Create evidence
        request = CommunicationRequest(
            id="req-date",
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            params={"query": "test"},
        )
        response = CommunicationResponse(
            request_id=request.id,
            status=RequestStatus.SUCCESS,
        )
        await self.logger.log_operation(request, response)

        # Search with date range
        now = datetime.now(timezone.utc)
        start_date = now - timedelta(hours=1)
        end_date = now + timedelta(hours=1)

        results = await self.logger.search_evidence(
            start_date=start_date,
            end_date=end_date,
            limit=10,
        )

        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_search_with_limit(self):
        """Test search respects limit parameter."""
        # Create many evidence records
        for i in range(10):
            request = CommunicationRequest(
                id=f"req-limit-{i}",
                connector_type=ConnectorType.WEB_SEARCH,
                operation="search",
                params={"query": f"query {i}"},
            )
            response = CommunicationResponse(
                request_id=request.id,
                status=RequestStatus.SUCCESS,
            )
            await self.logger.log_operation(request, response)

        # Search with limit
        results = await self.logger.search_evidence(limit=5)
        assert len(results) <= 5

    @pytest.mark.asyncio
    async def test_search_combined_filters(self):
        """Test searching with combined filters."""
        # Create evidence
        request = CommunicationRequest(
            id="req-combined",
            connector_type=ConnectorType.WEB_FETCH,
            operation="fetch",
            params={"url": "https://example.com"},
        )
        response = CommunicationResponse(
            request_id=request.id,
            status=RequestStatus.SUCCESS,
        )
        await self.logger.log_operation(request, response)

        # Search with multiple filters
        results = await self.logger.search_evidence(
            connector_type="web_fetch",
            operation="fetch",
            status=RequestStatus.SUCCESS,
            limit=10,
        )

        assert len(results) >= 1
        for r in results:
            assert r.connector_type == ConnectorType.WEB_FETCH
            assert r.operation == "fetch"
            assert r.status == RequestStatus.SUCCESS


class TestEvidenceStatistics:
    """Test suite for evidence statistics."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_stats.db"
        self.storage = SQLiteStore(self.db_path)
        self.logger = EvidenceLogger(storage=self.storage)

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.db_path.exists():
            self.db_path.unlink()

    @pytest.mark.asyncio
    async def test_get_total_requests(self):
        """Test getting total request count."""
        initial_count = await self.logger.get_total_requests()

        # Add requests
        for i in range(5):
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
        assert final_count >= initial_count + 5

    @pytest.mark.asyncio
    async def test_get_success_rate(self):
        """Test calculating success rate."""
        # Add successful requests
        for i in range(3):
            request = CommunicationRequest(
                id=f"req-success-{i}",
                connector_type=ConnectorType.WEB_SEARCH,
                operation="search",
                params={"query": "test"},
            )
            response = CommunicationResponse(
                request_id=request.id,
                status=RequestStatus.SUCCESS,
            )
            await self.logger.log_operation(request, response)

        # Add failed request
        request_failed = CommunicationRequest(
            id="req-failed-rate",
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            params={"query": "test"},
        )
        response_failed = CommunicationResponse(
            request_id=request_failed.id,
            status=RequestStatus.FAILED,
            error="Error",
        )
        await self.logger.log_operation(request_failed, response_failed)

        success_rate = await self.logger.get_success_rate()
        assert 0 <= success_rate <= 100
        # With 3 success and 1 failure, rate should be 75%
        assert success_rate >= 70  # Allow some tolerance

    @pytest.mark.asyncio
    async def test_get_success_rate_no_requests(self):
        """Test success rate with no requests."""
        # Fresh logger with no requests
        success_rate = await self.logger.get_success_rate()
        assert success_rate == 0.0

    @pytest.mark.asyncio
    async def test_get_stats_by_connector(self):
        """Test getting statistics by connector type."""
        # Add requests for different connectors
        for i in range(3):
            request = CommunicationRequest(
                id=f"req-web-search-{i}",
                connector_type=ConnectorType.WEB_SEARCH,
                operation="search",
                params={"query": "test"},
            )
            response = CommunicationResponse(
                request_id=request.id,
                status=RequestStatus.SUCCESS,
            )
            await self.logger.log_operation(request, response)

        for i in range(2):
            request = CommunicationRequest(
                id=f"req-web-fetch-{i}",
                connector_type=ConnectorType.WEB_FETCH,
                operation="fetch",
                params={"url": "https://example.com"},
            )
            response = CommunicationResponse(
                request_id=request.id,
                status=RequestStatus.SUCCESS,
            )
            await self.logger.log_operation(request, response)

        stats = await self.logger.get_stats_by_connector()
        assert isinstance(stats, dict)
        assert "web_search" in stats
        assert "web_fetch" in stats
        assert stats["web_search"] >= 3
        assert stats["web_fetch"] >= 2


class TestEvidenceExport:
    """Test suite for evidence export functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_export.db"
        self.storage = SQLiteStore(self.db_path)
        self.logger = EvidenceLogger(storage=self.storage)

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.db_path.exists():
            self.db_path.unlink()
        # Clean up exported files
        for file in Path(self.temp_dir).glob("*.json"):
            file.unlink()

    @pytest.mark.asyncio
    async def test_export_evidence_creates_file(self):
        """Test that exporting evidence creates a file."""
        # Create some evidence
        request = CommunicationRequest(
            id="req-export",
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            params={"query": "test"},
        )
        response = CommunicationResponse(
            request_id=request.id,
            status=RequestStatus.SUCCESS,
        )
        await self.logger.log_operation(request, response)

        # Export
        output_path = Path(self.temp_dir) / "export_test.json"
        result_path = await self.logger.export_evidence(output_path=output_path)

        assert result_path.exists()
        assert result_path == output_path
        assert result_path.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_export_evidence_with_date_range(self):
        """Test exporting evidence with date range."""
        # Create evidence
        request = CommunicationRequest(
            id="req-export-date",
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            params={"query": "test"},
        )
        response = CommunicationResponse(
            request_id=request.id,
            status=RequestStatus.SUCCESS,
        )
        await self.logger.log_operation(request, response)

        # Export with date range
        now = datetime.now(timezone.utc)
        start_date = now - timedelta(hours=1)
        end_date = now + timedelta(hours=1)

        output_path = Path(self.temp_dir) / "export_date.json"
        result_path = await self.logger.export_evidence(
            start_date=start_date,
            end_date=end_date,
            output_path=output_path,
        )

        assert result_path.exists()

    @pytest.mark.asyncio
    async def test_export_evidence_default_path(self):
        """Test exporting evidence with default path."""
        # Create evidence
        request = CommunicationRequest(
            id="req-export-default",
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            params={"query": "test"},
        )
        response = CommunicationResponse(
            request_id=request.id,
            status=RequestStatus.SUCCESS,
        )
        await self.logger.log_operation(request, response)

        # Export with default path
        result_path = await self.logger.export_evidence()

        assert result_path.exists()
        assert "evidence_export_" in result_path.name
        assert result_path.suffix == ".json"

        # Clean up
        result_path.unlink()


class TestEvidenceRecordModel:
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
        assert evidence.request_id == "req-test-1"
        assert evidence.connector_type == ConnectorType.WEB_SEARCH
        assert evidence.operation == "search"
        assert evidence.status == RequestStatus.SUCCESS
        assert evidence.request_summary["query"] == "test"
        assert evidence.response_summary["results"] == 5

    def test_evidence_with_metadata(self):
        """Test creating evidence with metadata."""
        evidence = EvidenceRecord(
            id="ev-test-2",
            request_id="req-test-2",
            connector_type=ConnectorType.WEB_FETCH,
            operation="fetch",
            request_summary={"url": "https://example.com"},
            metadata={"user_id": "user123", "session_id": "sess456"},
            status=RequestStatus.SUCCESS,
        )

        assert evidence.metadata["user_id"] == "user123"
        assert evidence.metadata["session_id"] == "sess456"

    def test_evidence_to_dict(self):
        """Test converting evidence to dictionary."""
        evidence = EvidenceRecord(
            id="ev-test-3",
            request_id="req-test-3",
            connector_type=ConnectorType.RSS,
            operation="fetch_feed",
            request_summary={"feed_url": "https://example.com/feed"},
            status=RequestStatus.SUCCESS,
        )

        evidence_dict = evidence.to_dict()
        assert evidence_dict["id"] == "ev-test-3"
        assert evidence_dict["request_id"] == "req-test-3"
        assert evidence_dict["connector_type"] == "rss"
        assert evidence_dict["operation"] == "fetch_feed"
        assert evidence_dict["status"] == "success"
        assert "created_at" in evidence_dict

    def test_evidence_timestamps(self):
        """Test that evidence has timestamps."""
        evidence = EvidenceRecord(
            id="ev-test-4",
            request_id="req-test-4",
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            request_summary={},
            status=RequestStatus.SUCCESS,
        )

        assert evidence.created_at is not None
        assert isinstance(evidence.created_at, datetime)
        # Should be recent (within last minute)
        now = datetime.now(timezone.utc)
        time_diff = (now - evidence.created_at).total_seconds()
        assert time_diff < 60


class TestEvidenceRequestSummary:
    """Test suite for request summary creation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_summary.db"
        self.storage = SQLiteStore(self.db_path)
        self.logger = EvidenceLogger(storage=self.storage)

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.db_path.exists():
            self.db_path.unlink()

    def test_create_request_summary_includes_safe_params(self):
        """Test that request summary includes safe parameters."""
        request = CommunicationRequest(
            id="req-summary-1",
            connector_type=ConnectorType.WEB_FETCH,
            operation="fetch",
            params={"url": "https://example.com", "method": "GET"},
        )

        summary = self.logger._create_request_summary(request)

        assert "connector_type" in summary
        assert "operation" in summary
        assert "params" in summary
        assert summary["params"]["url"] == "https://example.com"

    def test_create_request_summary_truncates_long_content(self):
        """Test that long content is truncated in summary."""
        long_content = "x" * 300
        request = CommunicationRequest(
            id="req-summary-2",
            connector_type=ConnectorType.EMAIL_SMTP,
            operation="send",
            params={"to": "test@example.com", "body": long_content},
        )

        summary = self.logger._create_request_summary(request)

        # Body should be truncated
        assert len(summary["params"]["body"]) <= 203  # 200 + "..."
        assert "..." in summary["params"]["body"]

    def test_create_response_summary(self):
        """Test creating response summary."""
        response = CommunicationResponse(
            request_id="req-test",
            status=RequestStatus.SUCCESS,
            data={"result": "data"},
            metadata={"content_type": "application/json", "status_code": 200},
        )

        summary = self.logger._create_response_summary(response)

        assert "status" in summary
        assert summary["status"] == "success"
        assert "metadata" in summary
        assert summary["metadata"]["content_type"] == "application/json"
        assert "has_data" in summary
        assert summary["has_data"] is True

    def test_create_response_summary_with_error(self):
        """Test creating response summary with error."""
        response = CommunicationResponse(
            request_id="req-test",
            status=RequestStatus.FAILED,
            error="Network timeout",
        )

        summary = self.logger._create_response_summary(response)

        assert summary["status"] == "failed"
        assert "error" in summary
        assert summary["error"] == "Network timeout"
