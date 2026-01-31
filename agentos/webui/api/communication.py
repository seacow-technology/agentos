"""Communication API - External communication management and audit endpoints.

This module provides REST API endpoints for managing and monitoring external
communication operations through CommunicationOS, including:
- Policy configuration retrieval
- Audit log querying and filtering
- Web search operations
- Web fetch operations
- Service status monitoring

All operations are secured with policy enforcement, rate limiting, and comprehensive
audit logging.

Part of CommunicationOS implementation
"""

import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from agentos.core.communication.service import CommunicationService
from agentos.core.communication.policy import PolicyEngine
from agentos.core.communication.evidence import EvidenceLogger
from agentos.core.communication.rate_limit import RateLimiter
from agentos.core.communication.sanitizers import InputSanitizer, OutputSanitizer
from agentos.core.time import utc_now
from agentos.core.communication.models import (
    ConnectorType,
    RequestStatus,
    RiskLevel,
)
from agentos.core.communication.connectors.web_fetch import WebFetchConnector
from agentos.core.communication.connectors.web_search import WebSearchConnector
from agentos.core.communication.network_mode import NetworkModeManager, NetworkMode
from agentos.webui.api.contracts import (
    success,
    error,
    not_found_error,
    validation_error,
    ReasonCode,
)
from agentos.webui.api.time_format import iso_z

logger = logging.getLogger(__name__)

router = APIRouter()

# Global service instance
_service: Optional[CommunicationService] = None


def get_service() -> CommunicationService:
    """Get or create the communication service instance.

    Returns:
        CommunicationService instance
    """
    global _service
    if _service is None:
        # Initialize service components
        policy_engine = PolicyEngine()
        evidence_logger = EvidenceLogger()
        rate_limiter = RateLimiter()
        input_sanitizer = InputSanitizer()
        output_sanitizer = OutputSanitizer()
        network_mode_manager = NetworkModeManager()

        # Create service
        _service = CommunicationService(
            policy_engine=policy_engine,
            evidence_logger=evidence_logger,
            rate_limiter=rate_limiter,
            input_sanitizer=input_sanitizer,
            output_sanitizer=output_sanitizer,
            network_mode_manager=network_mode_manager,
        )

        # Register connectors
        _service.register_connector(ConnectorType.WEB_FETCH, WebFetchConnector())
        _service.register_connector(ConnectorType.WEB_SEARCH, WebSearchConnector())

        logger.info("Initialized CommunicationService with connectors")

    return _service


# ============================================
# Request/Response Models
# ============================================

class PolicyResponse(BaseModel):
    """Response model for policy configuration"""
    connector_type: str
    name: str
    enabled: bool
    allowed_operations: List[str]
    blocked_domains: List[str]
    allowed_domains: List[str]
    require_approval: bool
    rate_limit_per_minute: int
    max_response_size_mb: int
    timeout_seconds: int
    sanitize_inputs: bool
    sanitize_outputs: bool


class AuditListItem(BaseModel):
    """Audit list item (summary)"""
    id: str
    request_id: str
    connector_type: str
    operation: str
    status: str
    risk_level: Optional[str] = None
    created_at: str


class AuditDetailResponse(BaseModel):
    """Audit detail response"""
    id: str
    request_id: str
    connector_type: str
    operation: str
    request_summary: Dict[str, Any]
    response_summary: Optional[Dict[str, Any]] = None
    status: str
    metadata: Dict[str, Any]
    created_at: str


class SearchRequest(BaseModel):
    """Request model for web search"""
    query: str = Field(..., description="Search query string")
    max_results: Optional[int] = Field(10, description="Maximum number of results", ge=1, le=100)
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context (task_id, session_id, etc.)")


class FetchRequest(BaseModel):
    """Request model for web fetch"""
    url: str = Field(..., description="URL to fetch")
    timeout: Optional[int] = Field(30, description="Request timeout in seconds", ge=1, le=120)
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context (task_id, session_id, etc.)")


class ServiceStatusResponse(BaseModel):
    """Response model for service status"""
    status: str
    connectors: Dict[str, Any]
    statistics: Dict[str, Any]
    timestamp: str


class NetworkModeRequest(BaseModel):
    """Request model for setting network mode"""
    mode: str = Field(..., description="Network mode: 'off', 'readonly', or 'on'")
    reason: Optional[str] = Field(None, description="Reason for mode change")
    updated_by: Optional[str] = Field(None, description="Who/what is changing the mode")


class NetworkModeResponse(BaseModel):
    """Response model for network mode"""
    mode: str
    updated_at: str
    updated_by: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ============================================
# Policy Endpoints
# ============================================

@router.get("/api/communication/policy", tags=["communication"])
async def get_policy() -> Dict[str, Any]:
    """Get current policy configuration for all connectors.

    Returns:
        Dictionary mapping connector types to their policy configurations

    Example response:
    ```json
    {
      "ok": true,
      "data": {
        "web_search": {
          "name": "default_web_search",
          "enabled": true,
          "allowed_operations": ["search"],
          "rate_limit_per_minute": 30,
          ...
        }
      }
    }
    ```
    """
    try:
        service = get_service()
        policies = {}

        for connector_type in ConnectorType:
            policy = service.policy_engine.get_policy(connector_type)
            if policy:
                policies[connector_type.value] = policy.to_dict()

        return success(policies)

    except Exception as e:
        logger.error(f"Failed to get policies: {str(e)}", exc_info=True)
        raise error(
            "Failed to retrieve policy configuration",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


@router.get("/api/communication/policy/{connector_type}", tags=["communication"])
async def get_connector_policy(connector_type: str) -> Dict[str, Any]:
    """Get policy configuration for a specific connector.

    Args:
        connector_type: Type of connector (web_search, web_fetch, etc.)

    Returns:
        Policy configuration for the specified connector
    """
    try:
        # Validate connector type
        try:
            conn_type = ConnectorType(connector_type)
        except ValueError:
            raise validation_error(
                f"Invalid connector type: {connector_type}",
                hint=f"Valid types: {', '.join([ct.value for ct in ConnectorType])}",
            )

        service = get_service()
        policy = service.policy_engine.get_policy(conn_type)

        if not policy:
            raise not_found_error("Policy", connector_type)

        return success(policy.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get policy for {connector_type}: {str(e)}", exc_info=True)
        raise error(
            f"Failed to retrieve policy for {connector_type}",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


# ============================================
# Audit Endpoints
# ============================================

@router.get("/api/communication/audits", tags=["communication"])
async def list_audits(
    connector_type: Optional[str] = Query(None, description="Filter by connector type"),
    operation: Optional[str] = Query(None, description="Filter by operation"),
    status: Optional[str] = Query(None, description="Filter by status"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    limit: int = Query(100, description="Maximum number of results", ge=1, le=1000),
) -> Dict[str, Any]:
    """List audit records with optional filtering.

    Args:
        connector_type: Filter by connector type
        operation: Filter by operation name
        status: Filter by request status
        start_date: Filter by start date (ISO format)
        end_date: Filter by end date (ISO format)
        limit: Maximum number of results

    Returns:
        List of audit records matching the filters

    Example response:
    ```json
    {
      "ok": true,
      "data": {
        "audits": [...],
        "total": 42,
        "filters_applied": {...}
      }
    }
    ```
    """
    try:
        service = get_service()

        # Parse date filters
        start_dt = None
        end_dt = None

        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                raise validation_error(
                    f"Invalid start_date format: {start_date}",
                    hint="Use ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ"
                )

        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                raise validation_error(
                    f"Invalid end_date format: {end_date}",
                    hint="Use ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ"
                )

        # Parse status filter
        status_enum = None
        if status:
            try:
                status_enum = RequestStatus(status)
            except ValueError:
                raise validation_error(
                    f"Invalid status: {status}",
                    hint=f"Valid statuses: {', '.join([s.value for s in RequestStatus])}"
                )

        # Search evidence
        evidence_records = await service.evidence_logger.search_evidence(
            connector_type=connector_type,
            operation=operation,
            status=status_enum,
            start_date=start_dt,
            end_date=end_dt,
            limit=limit,
        )

        # Convert to response format
        audits = []
        for record in evidence_records:
            audits.append({
                "id": record.id,
                "request_id": record.request_id,
                "connector_type": record.connector_type.value,
                "operation": record.operation,
                "status": record.status.value,
                "risk_level": record.metadata.get("risk_level"),
                "created_at": iso_z(record.created_at),
            })

        return success({
            "audits": audits,
            "total": len(audits),
            "filters_applied": {
                "connector_type": connector_type,
                "operation": operation,
                "status": status,
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit,
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list audits: {str(e)}", exc_info=True)
        raise error(
            "Failed to retrieve audit records",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


@router.get("/api/communication/audits/{audit_id}", tags=["communication"])
async def get_audit_detail(audit_id: str) -> Dict[str, Any]:
    """Get detailed information for a specific audit record.

    Args:
        audit_id: Audit record ID

    Returns:
        Detailed audit record including request and response summaries
    """
    try:
        service = get_service()

        # Get evidence record
        evidence = await service.evidence_logger.get_evidence(audit_id)

        if not evidence:
            raise not_found_error("Audit record", audit_id)

        # Convert to response format
        audit_detail = {
            "id": evidence.id,
            "request_id": evidence.request_id,
            "connector_type": evidence.connector_type.value,
            "operation": evidence.operation,
            "request_summary": evidence.request_summary,
            "response_summary": evidence.response_summary,
            "status": evidence.status.value,
            "metadata": evidence.metadata,
            "created_at": iso_z(evidence.created_at),
        }

        return success(audit_detail)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get audit {audit_id}: {str(e)}", exc_info=True)
        raise error(
            f"Failed to retrieve audit record {audit_id}",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


# ============================================
# Communication Operations
# ============================================

@router.post("/api/communication/search", tags=["communication"])
async def execute_search(request: SearchRequest) -> Dict[str, Any]:
    """Execute a web search operation.

    Args:
        request: Search request parameters

    Returns:
        Search results with metadata and evidence ID

    Example response:
    ```json
    {
      "ok": true,
      "data": {
        "request_id": "comm-abc123",
        "status": "success",
        "data": {
          "results": [...],
          "total_results": 10
        },
        "evidence_id": "ev-xyz789"
      }
    }
    ```
    """
    try:
        service = get_service()

        # Execute search
        response = await service.execute(
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            params={
                "query": request.query,
                "max_results": request.max_results or 10,
            },
            context=request.context or {},
        )

        # Check if request was denied or rate limited
        if response.status == RequestStatus.DENIED:
            raise error(
                response.error or "Search request denied by policy",
                reason_code=ReasonCode.AUTH_FORBIDDEN,
                hint="Check policy configuration and domain restrictions",
                http_status=403
            )

        if response.status == RequestStatus.RATE_LIMITED:
            raise error(
                response.error or "Rate limit exceeded",
                reason_code=ReasonCode.RATE_LIMITED,
                hint="Wait before making more requests",
                http_status=429
            )

        if response.status == RequestStatus.FAILED:
            raise error(
                response.error or "Search operation failed",
                reason_code=ReasonCode.INTERNAL_ERROR,
                hint="Check the query and try again",
                http_status=500
            )

        return success(response.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search execution failed: {str(e)}", exc_info=True)
        raise error(
            "Failed to execute search",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


@router.post("/api/communication/fetch", tags=["communication"])
async def execute_fetch(request: FetchRequest) -> Dict[str, Any]:
    """Fetch content from a URL.

    Args:
        request: Fetch request parameters

    Returns:
        Fetched content with metadata and evidence ID

    Example response:
    ```json
    {
      "ok": true,
      "data": {
        "request_id": "comm-abc123",
        "status": "success",
        "data": {
          "content": "...",
          "content_type": "text/html",
          "status_code": 200
        },
        "evidence_id": "ev-xyz789"
      }
    }
    ```
    """
    try:
        service = get_service()

        # Execute fetch
        response = await service.execute(
            connector_type=ConnectorType.WEB_FETCH,
            operation="fetch",
            params={
                "url": request.url,
                "timeout": request.timeout or 30,
            },
            context=request.context or {},
        )

        # Check if request was denied or rate limited
        if response.status == RequestStatus.DENIED:
            raise error(
                response.error or "Fetch request denied by policy",
                reason_code=ReasonCode.AUTH_FORBIDDEN,
                hint="Check policy configuration and domain restrictions",
                http_status=403
            )

        if response.status == RequestStatus.RATE_LIMITED:
            raise error(
                response.error or "Rate limit exceeded",
                reason_code=ReasonCode.RATE_LIMITED,
                hint="Wait before making more requests",
                http_status=429
            )

        if response.status == RequestStatus.FAILED:
            raise error(
                response.error or "Fetch operation failed",
                reason_code=ReasonCode.INTERNAL_ERROR,
                hint="Check the URL and try again",
                http_status=500
            )

        return success(response.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fetch execution failed: {str(e)}", exc_info=True)
        raise error(
            "Failed to execute fetch",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


# ============================================
# Network Mode Endpoints
# ============================================

@router.get("/api/communication/mode", tags=["communication"])
async def get_network_mode() -> Dict[str, Any]:
    """Get current network mode.

    Returns:
        Current network mode configuration and information

    Example response:
    ```json
    {
      "ok": true,
      "data": {
        "current_state": {
          "mode": "on",
          "updated_at": "2024-01-15T10:30:00Z",
          "updated_by": "admin"
        },
        "recent_history": [...],
        "available_modes": ["off", "readonly", "on"]
      }
    }
    ```
    """
    try:
        service = get_service()
        mode_info = service.network_mode_manager.get_mode_info()
        return success(mode_info)

    except Exception as e:
        logger.error(f"Failed to get network mode: {str(e)}", exc_info=True)
        raise error(
            "Failed to retrieve network mode",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


@router.put("/api/communication/mode", tags=["communication"])
async def set_network_mode(request: NetworkModeRequest) -> Dict[str, Any]:
    """Set network mode.

    Args:
        request: Network mode change request

    Returns:
        Mode change result and metadata

    Example request:
    ```json
    {
      "mode": "readonly",
      "reason": "Maintenance window",
      "updated_by": "admin"
    }
    ```

    Example response:
    ```json
    {
      "ok": true,
      "data": {
        "previous_mode": "on",
        "new_mode": "readonly",
        "changed": true,
        "timestamp": "2024-01-15T10:30:00Z",
        "updated_by": "admin",
        "reason": "Maintenance window"
      }
    }
    ```
    """
    try:
        # Validate mode
        try:
            mode = NetworkMode(request.mode.lower())
        except ValueError:
            raise validation_error(
                f"Invalid network mode: {request.mode}",
                hint=f"Valid modes: {', '.join([m.value for m in NetworkMode])}"
            )

        service = get_service()

        # Set mode
        change_info = service.network_mode_manager.set_mode(
            mode=mode,
            updated_by=request.updated_by,
            reason=request.reason,
        )

        return success(change_info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set network mode: {str(e)}", exc_info=True)
        raise error(
            "Failed to set network mode",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


@router.get("/api/communication/mode/history", tags=["communication"])
async def get_network_mode_history(
    limit: int = Query(100, description="Maximum number of history records", ge=1, le=1000),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
) -> Dict[str, Any]:
    """Get network mode change history.

    Args:
        limit: Maximum number of history records to return
        start_date: Filter by start date (ISO format)
        end_date: Filter by end date (ISO format)

    Returns:
        List of network mode changes

    Example response:
    ```json
    {
      "ok": true,
      "data": {
        "history": [
          {
            "previous_mode": "on",
            "new_mode": "readonly",
            "changed_at": "2024-01-15T10:30:00Z",
            "changed_by": "admin",
            "reason": "Maintenance window"
          }
        ],
        "total": 1
      }
    }
    ```
    """
    try:
        service = get_service()

        # Parse date filters
        start_dt = None
        end_dt = None

        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                raise validation_error(
                    f"Invalid start_date format: {start_date}",
                    hint="Use ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ"
                )

        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                raise validation_error(
                    f"Invalid end_date format: {end_date}",
                    hint="Use ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ"
                )

        # Get history
        history = service.network_mode_manager.get_history(
            limit=limit,
            start_date=start_dt,
            end_date=end_dt,
        )

        return success({
            "history": history,
            "total": len(history),
            "filters_applied": {
                "limit": limit,
                "start_date": start_date,
                "end_date": end_date,
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get network mode history: {str(e)}", exc_info=True)
        raise error(
            "Failed to retrieve network mode history",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


# ============================================
# Status Endpoint
# ============================================

@router.get("/api/communication/status", tags=["communication"])
async def get_status() -> Dict[str, Any]:
    """Get communication service status and statistics.

    Returns:
        Service status including connector info, statistics, and network mode

    Example response:
    ```json
    {
      "ok": true,
      "data": {
        "status": "operational",
        "network_mode": "on",
        "connectors": {
          "web_search": {
            "enabled": true,
            "operations": ["search"],
            "rate_limit": 30
          }
        },
        "statistics": {
          "total_requests": 1234,
          "success_rate": 95.6,
          "by_connector": {...}
        }
      }
    }
    ```
    """
    try:
        service = get_service()

        # Get connector information
        connectors = await service.list_connectors()

        # Get statistics
        statistics = await service.get_statistics()

        # Get network mode
        network_mode = service.network_mode_manager.get_mode().value

        status_response = {
            "status": "operational",
            "network_mode": network_mode,
            "connectors": connectors,
            "statistics": statistics,
            "timestamp": iso_z(utc_now()),
        }

        return success(status_response)

    except Exception as e:
        logger.error(f"Failed to get status: {str(e)}", exc_info=True)
        raise error(
            "Failed to retrieve service status",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )
