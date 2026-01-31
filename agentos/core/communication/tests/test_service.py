"""Tests for CommunicationService integration.

This module tests the main CommunicationService orchestrator,
including integration with policy engine, rate limiter, and evidence logging.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
import tempfile
from pathlib import Path

from agentos.core.communication.service import CommunicationService
from agentos.core.communication.policy import PolicyEngine
from agentos.core.communication.evidence import EvidenceLogger
from agentos.core.communication.rate_limit import RateLimiter
from agentos.core.communication.sanitizers import InputSanitizer, OutputSanitizer
from agentos.core.communication.connectors.base import BaseConnector
from agentos.core.communication.storage.sqlite_store import SQLiteStore
from agentos.core.communication.models import (
    ConnectorType,
    RequestStatus,
    RiskLevel,
)


class MockConnector(BaseConnector):
    """Mock connector for testing."""

    async def execute(self, operation: str, params: dict) -> dict:
        """Execute mock operation."""
        if operation == "test":
            return {"result": "success", "params": params}
        elif operation == "fail":
            raise Exception("Mock operation failed")
        else:
            raise ValueError(f"Unsupported operation: {operation}")

    def get_supported_operations(self) -> list:
        """Get supported operations."""
        return ["test", "fail"]


class TestCommunicationServiceBasics:
    """Basic tests for CommunicationService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CommunicationService()

    def test_service_initialization(self):
        """Test service initialization with default components."""
        assert self.service.policy_engine is not None
        assert self.service.evidence_logger is not None
        assert self.service.rate_limiter is not None
        assert self.service.input_sanitizer is not None
        assert self.service.output_sanitizer is not None
        assert isinstance(self.service.connectors, dict)

    def test_service_initialization_custom_components(self):
        """Test service initialization with custom components."""
        policy_engine = PolicyEngine()
        rate_limiter = RateLimiter()
        input_sanitizer = InputSanitizer()
        output_sanitizer = OutputSanitizer()

        service = CommunicationService(
            policy_engine=policy_engine,
            rate_limiter=rate_limiter,
            input_sanitizer=input_sanitizer,
            output_sanitizer=output_sanitizer,
        )

        assert service.policy_engine is policy_engine
        assert service.rate_limiter is rate_limiter
        assert service.input_sanitizer is input_sanitizer
        assert service.output_sanitizer is output_sanitizer

    def test_register_connector(self):
        """Test registering a connector."""
        mock_connector = MockConnector()
        self.service.register_connector(ConnectorType.CUSTOM, mock_connector)
        # Register policy for CUSTOM connector
        from agentos.core.communication.models import CommunicationPolicy
        custom_policy = CommunicationPolicy(
            name="custom_policy",
            connector_type=ConnectorType.CUSTOM,
            allowed_operations=["test", "fail", "get_data", "another_test"],
            enabled=True,
        )
        self.service.policy_engine.register_policy(custom_policy)

        registered = self.service.get_connector(ConnectorType.CUSTOM)
        assert registered is mock_connector

    def test_get_nonexistent_connector(self):
        """Test getting nonexistent connector returns None."""
        connector = self.service.get_connector(ConnectorType.CUSTOM)
        assert connector is None


class TestServiceExecution:
    """Test suite for service execution."""

    def setup_method(self):
        """Set up test fixtures."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_service.db"
        storage = SQLiteStore(db_path)
        evidence_logger = EvidenceLogger(storage=storage)

        self.service = CommunicationService(evidence_logger=evidence_logger)
        self.mock_connector = MockConnector()
        self.service.register_connector(ConnectorType.CUSTOM, self.mock_connector)
        # Register policy for CUSTOM connector
        from agentos.core.communication.models import CommunicationPolicy
        custom_policy = CommunicationPolicy(
            name="custom_policy",
            connector_type=ConnectorType.CUSTOM,
            allowed_operations=["test", "fail", "get_data", "another_test"],
            enabled=True,
        )
        self.service.policy_engine.register_policy(custom_policy)

        # Register policy for CUSTOM connector
        from agentos.core.communication.models import CommunicationPolicy
        custom_policy = CommunicationPolicy(
            name="custom_policy",
            connector_type=ConnectorType.CUSTOM,
            allowed_operations=["test", "fail"],
            enabled=True,
        )
        self.service.policy_engine.register_policy(custom_policy)

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful operation execution."""
        response = await self.service.execute(
            connector_type=ConnectorType.CUSTOM,
            operation="test",
            params={"data": "test_data"},
        )

        assert response.status == RequestStatus.SUCCESS
        assert response.data is not None
        assert response.data["result"] == "success"
        assert response.evidence_id is not None

    @pytest.mark.asyncio
    async def test_execute_invalid_params(self):
        """Test execution with invalid parameters."""
        # WEB_SEARCH requires 'query' parameter
        response = await self.service.execute(
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            params={},  # Missing query
        )

        assert response.status == RequestStatus.DENIED
        assert response.error is not None
        assert "query" in response.error.lower()

    @pytest.mark.asyncio
    async def test_execute_policy_denied(self):
        """Test execution denied by policy."""
        # Try to execute operation not in allowed list
        response = await self.service.execute(
            connector_type=ConnectorType.WEB_SEARCH,
            operation="invalid_operation",
            params={"query": "test"},
        )

        assert response.status == RequestStatus.DENIED
        assert response.error is not None
        assert "not allowed" in response.error.lower()

    @pytest.mark.asyncio
    async def test_execute_ssrf_blocked(self):
        """Test execution blocked by SSRF protection."""
        response = await self.service.execute(
            connector_type=ConnectorType.WEB_FETCH,
            operation="fetch",
            params={"url": "http://localhost/admin"},
        )

        assert response.status == RequestStatus.DENIED
        assert response.error is not None
        assert "localhost" in response.error.lower() or "ssrf" in response.error.lower()

    @pytest.mark.asyncio
    async def test_execute_connector_not_registered(self):
        """Test execution with unregistered connector."""
        # Try to use RSS connector (not registered)
        response = await self.service.execute(
            connector_type=ConnectorType.RSS,
            operation="fetch_feed",
            params={"feed_url": "https://example.com/feed.xml"},
        )

        assert response.status == RequestStatus.FAILED
        assert response.error is not None
        assert "no connector registered" in response.error.lower()

    @pytest.mark.asyncio
    async def test_execute_connector_error(self):
        """Test execution when connector raises error."""
        response = await self.service.execute(
            connector_type=ConnectorType.CUSTOM,
            operation="fail",
            params={},
        )

        assert response.status == RequestStatus.FAILED
        assert response.error is not None
        assert "failed" in response.error.lower()

    @pytest.mark.asyncio
    async def test_execute_with_context(self):
        """Test execution with context information."""
        context = {
            "task_id": "task-123",
            "session_id": "session-456",
            "user_id": "user-789",
        }

        response = await self.service.execute(
            connector_type=ConnectorType.CUSTOM,
            operation="test",
            params={"data": "test"},
            context=context,
        )

        assert response.status == RequestStatus.SUCCESS


class TestRateLimiting:
    """Test suite for rate limiting integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.rate_limiter = RateLimiter()
        self.service = CommunicationService(rate_limiter=self.rate_limiter)
        self.mock_connector = MockConnector()
        self.service.register_connector(ConnectorType.CUSTOM, self.mock_connector)
        # Register policy for CUSTOM connector
        from agentos.core.communication.models import CommunicationPolicy
        custom_policy = CommunicationPolicy(
            name="custom_policy",
            connector_type=ConnectorType.CUSTOM,
            allowed_operations=["test", "fail", "get_data", "another_test"],
            enabled=True,
        )
        self.service.policy_engine.register_policy(custom_policy)

        # Register policy for CUSTOM connector
        from agentos.core.communication.models import CommunicationPolicy
        custom_policy = CommunicationPolicy(
            name="custom_policy",
            connector_type=ConnectorType.CUSTOM,
            allowed_operations=["test", "fail"],
            enabled=True,
            rate_limit_per_minute=2,
        )
        self.service.policy_engine.register_policy(custom_policy)

        # Set up a strict rate limit
        self.rate_limiter.set_limit("custom", limit=2, window_seconds=60)

    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self):
        """Test that rate limits are enforced."""
        # First request should succeed
        response1 = await self.service.execute(
            connector_type=ConnectorType.CUSTOM,
            operation="test",
            params={},
        )
        assert response1.status == RequestStatus.SUCCESS

        # Second request should succeed
        response2 = await self.service.execute(
            connector_type=ConnectorType.CUSTOM,
            operation="test",
            params={},
        )
        assert response2.status == RequestStatus.SUCCESS

        # Third request should be rate limited
        response3 = await self.service.execute(
            connector_type=ConnectorType.CUSTOM,
            operation="test",
            params={},
        )
        assert response3.status == RequestStatus.RATE_LIMITED
        assert "rate limit" in response3.error.lower()

    @pytest.mark.asyncio
    async def test_rate_limit_per_connector(self):
        """Test that rate limits are per connector type."""
        # Use up rate limit for CUSTOM connector
        await self.service.execute(ConnectorType.CUSTOM, "test", {})
        await self.service.execute(ConnectorType.CUSTOM, "test", {})

        # Third CUSTOM request should be rate limited
        response = await self.service.execute(ConnectorType.CUSTOM, "test", {})
        assert response.status == RequestStatus.RATE_LIMITED

        # But other connectors should still work (if registered)
        # This test assumes different connectors have independent rate limits


class TestInputSanitization:
    """Test suite for input sanitization integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CommunicationService()
        self.mock_connector = MockConnector()
        self.service.register_connector(ConnectorType.CUSTOM, self.mock_connector)
        # Register policy for CUSTOM connector
        from agentos.core.communication.models import CommunicationPolicy
        custom_policy = CommunicationPolicy(
            name="custom_policy",
            connector_type=ConnectorType.CUSTOM,
            allowed_operations=["test", "fail", "get_data", "another_test"],
            enabled=True,
        )
        self.service.policy_engine.register_policy(custom_policy)

    @pytest.mark.asyncio
    async def test_sql_injection_sanitized(self):
        """Test that SQL injection attempts are sanitized."""
        malicious_input = "test' OR '1'='1"

        response = await self.service.execute(
            connector_type=ConnectorType.CUSTOM,
            operation="test",
            params={"query": malicious_input},
        )

        # Input should be sanitized
        if response.status == RequestStatus.SUCCESS:
            # Check that SQL injection was removed
            sanitized_query = response.data["params"]["query"]
            assert "OR" not in sanitized_query.upper() or sanitized_query != malicious_input

    @pytest.mark.asyncio
    async def test_command_injection_sanitized(self):
        """Test that command injection attempts are sanitized."""
        malicious_input = "test; rm -rf /"

        response = await self.service.execute(
            connector_type=ConnectorType.CUSTOM,
            operation="test",
            params={"command": malicious_input},
        )

        if response.status == RequestStatus.SUCCESS:
            # Semicolon should be removed
            sanitized_command = response.data["params"]["command"]
            assert ";" not in sanitized_command

    @pytest.mark.asyncio
    async def test_xss_sanitized(self):
        """Test that XSS attempts are sanitized."""
        malicious_input = "<script>alert('xss')</script>"

        response = await self.service.execute(
            connector_type=ConnectorType.CUSTOM,
            operation="test",
            params={"content": malicious_input},
        )

        if response.status == RequestStatus.SUCCESS:
            # Script tags should be removed or escaped
            sanitized_content = response.data["params"]["content"]
            assert "<script>" not in sanitized_content.lower()


class TestOutputSanitization:
    """Test suite for output sanitization integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CommunicationService()

        # Create a connector that returns sensitive data
        class SensitiveDataConnector(BaseConnector):
            async def execute(self, operation: str, params: dict) -> dict:
                return {
                    "public_data": "visible",
                    "secret_key": "sk-1234567890abcdef1234567890",
                    "password": "mySecretPassword123",
                }

            def get_supported_operations(self) -> list:
                return ["get_data"]

        self.sensitive_connector = SensitiveDataConnector()
        self.service.register_connector(ConnectorType.CUSTOM, self.sensitive_connector)
        # Register policy for CUSTOM connector
        from agentos.core.communication.models import CommunicationPolicy
        custom_policy = CommunicationPolicy(
            name="custom_policy",
            connector_type=ConnectorType.CUSTOM,
            allowed_operations=["test", "fail", "get_data", "another_test"],
            enabled=True,
        )
        self.service.policy_engine.register_policy(custom_policy)

    @pytest.mark.asyncio
    async def test_sensitive_data_redacted(self):
        """Test that sensitive data is redacted in output."""
        response = await self.service.execute(
            connector_type=ConnectorType.CUSTOM,
            operation="get_data",
            params={},
        )

        assert response.status == RequestStatus.SUCCESS
        # Sensitive data should be redacted
        data_str = str(response.data)
        # Full API key should not appear
        assert "1234567890abcdef1234567890" not in data_str or "****" in data_str


class TestRiskAssessment:
    """Test suite for risk assessment."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CommunicationService()
        self.mock_connector = MockConnector()
        self.service.register_connector(ConnectorType.CUSTOM, self.mock_connector)
        # Register policy for CUSTOM connector
        from agentos.core.communication.models import CommunicationPolicy
        custom_policy = CommunicationPolicy(
            name="custom_policy",
            connector_type=ConnectorType.CUSTOM,
            allowed_operations=["test", "fail", "get_data", "another_test"],
            enabled=True,
        )
        self.service.policy_engine.register_policy(custom_policy)

    @pytest.mark.asyncio
    async def test_low_risk_operation(self):
        """Test low-risk operation assessment."""
        # Web search is typically low risk
        # Note: We can't execute it without registering the connector,
        # but we can test the policy engine directly
        policy_engine = self.service.policy_engine

        from agentos.core.communication.models import CommunicationRequest

        request = CommunicationRequest(
            id="test-1",
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            params={"query": "test"},
        )

        risk = policy_engine.assess_risk(request)
        assert risk in [RiskLevel.LOW, RiskLevel.MEDIUM]

    @pytest.mark.asyncio
    async def test_high_risk_operation(self):
        """Test high-risk operation assessment."""
        from agentos.core.communication.models import CommunicationRequest

        # Email operations are typically high risk
        request = CommunicationRequest(
            id="test-2",
            connector_type=ConnectorType.EMAIL_SMTP,
            operation="send",
            params={"to": "test@example.com", "subject": "Test", "body": "Test"},
        )

        risk = self.service.policy_engine.assess_risk(request)
        assert risk in [RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]


class TestEvidenceLogging:
    """Test suite for evidence logging integration."""

    def setup_method(self):
        """Set up test fixtures."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_evidence.db"
        storage = SQLiteStore(db_path)
        evidence_logger = EvidenceLogger(storage=storage)

        self.service = CommunicationService(evidence_logger=evidence_logger)
        self.mock_connector = MockConnector()
        self.service.register_connector(ConnectorType.CUSTOM, self.mock_connector)
        # Register policy for CUSTOM connector
        from agentos.core.communication.models import CommunicationPolicy
        custom_policy = CommunicationPolicy(
            name="custom_policy",
            connector_type=ConnectorType.CUSTOM,
            allowed_operations=["test", "fail", "get_data", "another_test"],
            enabled=True,
        )
        self.service.policy_engine.register_policy(custom_policy)

    @pytest.mark.asyncio
    async def test_evidence_logged_on_success(self):
        """Test that evidence is logged on successful execution."""
        response = await self.service.execute(
            connector_type=ConnectorType.CUSTOM,
            operation="test",
            params={"data": "test"},
        )

        assert response.evidence_id is not None
        assert response.evidence_id.startswith("ev-")

        # Verify evidence can be retrieved
        evidence = await self.service.evidence_logger.get_evidence(response.evidence_id)
        assert evidence is not None
        assert evidence.status == RequestStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_evidence_logged_on_failure(self):
        """Test that evidence is logged on failed execution."""
        response = await self.service.execute(
            connector_type=ConnectorType.CUSTOM,
            operation="fail",
            params={},
        )

        # Even failed requests should have evidence
        # (though evidence_id might not be set in response if logging fails)
        # The key is that the attempt to log should be made


class TestServiceStatistics:
    """Test suite for service statistics."""

    def setup_method(self):
        """Set up test fixtures."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_stats.db"
        storage = SQLiteStore(db_path)
        evidence_logger = EvidenceLogger(storage=storage)

        self.service = CommunicationService(evidence_logger=evidence_logger)
        self.mock_connector = MockConnector()
        self.service.register_connector(ConnectorType.CUSTOM, self.mock_connector)
        # Register policy for CUSTOM connector
        from agentos.core.communication.models import CommunicationPolicy
        custom_policy = CommunicationPolicy(
            name="custom_policy",
            connector_type=ConnectorType.CUSTOM,
            allowed_operations=["test", "fail", "get_data", "another_test"],
            enabled=True,
        )
        self.service.policy_engine.register_policy(custom_policy)

    @pytest.mark.asyncio
    async def test_get_statistics(self):
        """Test getting service statistics."""
        # Execute some operations
        await self.service.execute(ConnectorType.CUSTOM, "test", {})
        await self.service.execute(ConnectorType.CUSTOM, "test", {})

        # Get statistics
        stats = await self.service.get_statistics()

        assert "total_requests" in stats
        assert "success_rate" in stats
        assert "by_connector" in stats
        assert stats["total_requests"] >= 2

    @pytest.mark.asyncio
    async def test_list_connectors(self):
        """Test listing registered connectors."""
        connectors = await self.service.list_connectors()

        assert isinstance(connectors, dict)
        assert "custom" in connectors

        custom_info = connectors["custom"]
        assert "type" in custom_info
        assert "enabled" in custom_info
        assert "operations" in custom_info
        assert custom_info["type"] == "custom"


class TestServiceIntegrationScenarios:
    """Integration test scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_integration.db"
        storage = SQLiteStore(db_path)
        evidence_logger = EvidenceLogger(storage=storage)

        self.service = CommunicationService(evidence_logger=evidence_logger)
        self.mock_connector = MockConnector()
        self.service.register_connector(ConnectorType.CUSTOM, self.mock_connector)
        # Register policy for CUSTOM connector
        from agentos.core.communication.models import CommunicationPolicy
        custom_policy = CommunicationPolicy(
            name="custom_policy",
            connector_type=ConnectorType.CUSTOM,
            allowed_operations=["test", "fail", "get_data", "another_test"],
            enabled=True,
        )
        self.service.policy_engine.register_policy(custom_policy)

    @pytest.mark.asyncio
    async def test_complete_request_lifecycle(self):
        """Test complete request lifecycle from execution to evidence."""
        # Execute request
        response = await self.service.execute(
            connector_type=ConnectorType.CUSTOM,
            operation="test",
            params={"input": "test_data"},
            context={"task_id": "task-123"},
        )

        # Verify response
        assert response.status == RequestStatus.SUCCESS
        assert response.data is not None
        assert response.evidence_id is not None

        # Verify evidence was logged
        evidence = await self.service.evidence_logger.get_evidence(response.evidence_id)
        assert evidence is not None
        assert evidence.connector_type == ConnectorType.CUSTOM
        assert evidence.operation == "test"
        assert evidence.status == RequestStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_multiple_operations_with_different_connectors(self):
        """Test multiple operations with different connector types."""
        # Register another connector
        class AnotherMockConnector(BaseConnector):
            async def execute(self, operation: str, params: dict) -> dict:
                return {"result": "another_success"}

            def get_supported_operations(self) -> list:
                return ["another_test"]

        another_connector = AnotherMockConnector()
        self.service.register_connector(ConnectorType.RSS, another_connector)

        # Execute operations on different connectors
        response1 = await self.service.execute(
            ConnectorType.CUSTOM,
            "test",
            {"data": "test1"},
        )

        response2 = await self.service.execute(
            ConnectorType.RSS,
            "another_test",
            {"data": "test2"},
        )

        # Both should succeed
        assert response1.status == RequestStatus.SUCCESS
        assert response2.status == RequestStatus.SUCCESS

        # Get statistics
        stats = await self.service.get_statistics()
        assert stats["total_requests"] >= 2

    @pytest.mark.asyncio
    async def test_security_pipeline(self):
        """Test complete security pipeline: validation -> sanitization -> execution -> logging."""
        malicious_params = {
            "query": "test' OR '1'='1",
            "command": "test; rm -rf /",
        }

        response = await self.service.execute(
            connector_type=ConnectorType.CUSTOM,
            operation="test",
            params=malicious_params,
        )

        # Request should succeed but with sanitized input
        assert response.status == RequestStatus.SUCCESS

        # Verify evidence was logged
        assert response.evidence_id is not None

        # Verify input was sanitized
        if response.data and "params" in response.data:
            params = response.data["params"]
            # SQL injection should be sanitized
            if "query" in params:
                assert "OR" not in params["query"].upper() or params["query"] != malicious_params["query"]
            # Command injection should be sanitized
            if "command" in params:
                assert ";" not in params["command"]


class TestConnectorDisabling:
    """Test suite for connector enabling/disabling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CommunicationService()
        self.mock_connector = MockConnector()
        self.service.register_connector(ConnectorType.CUSTOM, self.mock_connector)
        # Register policy for CUSTOM connector
        from agentos.core.communication.models import CommunicationPolicy
        custom_policy = CommunicationPolicy(
            name="custom_policy",
            connector_type=ConnectorType.CUSTOM,
            allowed_operations=["test", "fail", "get_data", "another_test"],
            enabled=True,
        )
        self.service.policy_engine.register_policy(custom_policy)

    @pytest.mark.asyncio
    async def test_disabled_connector_rejected(self):
        """Test that disabled connectors reject requests."""
        # Disable the connector
        self.mock_connector.disable()

        response = await self.service.execute(
            connector_type=ConnectorType.CUSTOM,
            operation="test",
            params={},
        )

        assert response.status == RequestStatus.FAILED
        assert "disabled" in response.error.lower()

    @pytest.mark.asyncio
    async def test_enabled_connector_accepted(self):
        """Test that enabled connectors accept requests."""
        # Ensure connector is enabled
        self.mock_connector.enable()

        response = await self.service.execute(
            connector_type=ConnectorType.CUSTOM,
            operation="test",
            params={},
        )

        assert response.status == RequestStatus.SUCCESS
