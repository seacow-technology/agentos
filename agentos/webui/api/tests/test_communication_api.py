"""Tests for Communication API endpoints.

This test suite validates the Communication API module structure,
endpoints, and integration without requiring external dependencies.
"""

import sys
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

# Mock external dependencies before importing
sys.modules['bs4'] = Mock()
sys.modules['httpx'] = Mock()

import pytest

from agentos.core.communication.models import (
    ConnectorType,
    RequestStatus,
    RiskLevel,
    CommunicationResponse,
    EvidenceRecord,
)


class TestCommunicationAPIStructure:
    """Test the basic structure and configuration of the Communication API."""

    def test_module_import(self):
        """Test that the communication API module can be imported."""
        from agentos.webui.api import communication
        assert communication is not None

    def test_router_exists(self):
        """Test that the router is properly configured."""
        from agentos.webui.api import communication
        assert hasattr(communication, 'router')
        assert communication.router is not None

    def test_endpoints_defined(self):
        """Test that all required endpoints are defined."""
        from agentos.webui.api import communication

        expected_endpoints = [
            'get_policy',
            'get_connector_policy',
            'list_audits',
            'get_audit_detail',
            'execute_search',
            'execute_fetch',
            'get_status',
        ]

        for endpoint_name in expected_endpoints:
            assert hasattr(communication, endpoint_name), \
                f"Endpoint {endpoint_name} not found"


class TestRequestModels:
    """Test Pydantic request models."""

    def test_search_request_valid(self):
        """Test valid SearchRequest creation."""
        from agentos.webui.api.communication import SearchRequest

        request = SearchRequest(query="test query", max_results=10)
        assert request.query == "test query"
        assert request.max_results == 10

    def test_search_request_requires_query(self):
        """Test that SearchRequest requires a query."""
        from agentos.webui.api.communication import SearchRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SearchRequest(max_results=10)  # Missing query

    def test_fetch_request_valid(self):
        """Test valid FetchRequest creation."""
        from agentos.webui.api.communication import FetchRequest

        request = FetchRequest(url="https://example.com", timeout=30)
        assert request.url == "https://example.com"
        assert request.timeout == 30

    def test_fetch_request_requires_url(self):
        """Test that FetchRequest requires a URL."""
        from agentos.webui.api.communication import FetchRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            FetchRequest(timeout=30)  # Missing url


class TestResponseModels:
    """Test Pydantic response models."""

    def test_response_models_exist(self):
        """Test that all response models are defined."""
        from agentos.webui.api import communication

        response_models = [
            'PolicyResponse',
            'AuditListItem',
            'AuditDetailResponse',
            'ServiceStatusResponse',
        ]

        for model_name in response_models:
            assert hasattr(communication, model_name), \
                f"Response model {model_name} not found"


class TestEndpointSignatures:
    """Test that endpoint functions have correct signatures."""

    def test_endpoints_are_async(self):
        """Test that all endpoints are async functions."""
        import inspect
        from agentos.webui.api.communication import (
            get_policy,
            get_connector_policy,
            list_audits,
            get_audit_detail,
            execute_search,
            execute_fetch,
            get_status,
        )

        endpoints = [
            get_policy,
            get_connector_policy,
            list_audits,
            get_audit_detail,
            execute_search,
            execute_fetch,
            get_status,
        ]

        for endpoint in endpoints:
            assert inspect.iscoroutinefunction(endpoint), \
                f"{endpoint.__name__} should be async"


class TestServiceInitialization:
    """Test service initialization and singleton pattern."""

    @patch('agentos.webui.api.communication.WebFetchConnector')
    @patch('agentos.webui.api.communication.WebSearchConnector')
    def test_service_initialization(self, mock_web_search, mock_web_fetch):
        """Test that the service can be initialized."""
        from agentos.webui.api.communication import get_service

        service = get_service()
        assert service is not None

    @patch('agentos.webui.api.communication.WebFetchConnector')
    @patch('agentos.webui.api.communication.WebSearchConnector')
    def test_service_singleton(self, mock_web_search, mock_web_fetch):
        """Test that get_service returns the same instance."""
        from agentos.webui.api.communication import get_service

        service1 = get_service()
        service2 = get_service()
        assert service1 is service2


class TestAPIContractIntegration:
    """Test integration with AgentOS API contract."""

    def test_contract_imports(self):
        """Test that API contract utilities are imported."""
        from agentos.webui.api.communication import (
            success,
            error,
            not_found_error,
            validation_error,
            ReasonCode,
        )

        assert success is not None
        assert error is not None
        assert not_found_error is not None
        assert validation_error is not None
        assert ReasonCode is not None


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
