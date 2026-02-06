"""Communication service - main orchestrator for external communications.

This module provides the main service interface for executing external
communication operations with security, auditing, and policy enforcement.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from agentos.core.communication.models import (
    CommunicationRequest,
    CommunicationResponse,
    ConnectorType,
    RequestStatus,
)
from agentos.core.communication.policy import PolicyEngine
from agentos.core.communication.evidence import EvidenceLogger
from agentos.core.communication.rate_limit import RateLimiter
from agentos.core.communication.sanitizers import InputSanitizer, OutputSanitizer
from agentos.core.communication.connectors.base import BaseConnector
from agentos.core.communication.network_mode import NetworkModeManager, NetworkMode

logger = logging.getLogger(__name__)


class CommunicationService:
    """Main service for external communications.

    The CommunicationService orchestrates all external communication operations,
    enforcing security policies, rate limits, and audit logging.
    """

    def __init__(
        self,
        policy_engine: Optional[PolicyEngine] = None,
        evidence_logger: Optional[EvidenceLogger] = None,
        rate_limiter: Optional[RateLimiter] = None,
        input_sanitizer: Optional[InputSanitizer] = None,
        output_sanitizer: Optional[OutputSanitizer] = None,
        network_mode_manager: Optional[NetworkModeManager] = None,
    ):
        """Initialize the communication service.

        Args:
            policy_engine: Policy engine for security enforcement
            evidence_logger: Logger for audit evidence
            rate_limiter: Rate limiter for request throttling
            input_sanitizer: Sanitizer for input validation
            output_sanitizer: Sanitizer for output filtering
            network_mode_manager: Network mode manager for access control
        """
        self.policy_engine = policy_engine or PolicyEngine()
        self.evidence_logger = evidence_logger or EvidenceLogger()
        self.rate_limiter = rate_limiter or RateLimiter()
        self.input_sanitizer = input_sanitizer or InputSanitizer()
        self.output_sanitizer = output_sanitizer or OutputSanitizer()
        self.network_mode_manager = network_mode_manager or NetworkModeManager()

        # Registry of available connectors
        self.connectors: Dict[ConnectorType, BaseConnector] = {}

    def register_connector(self, connector_type: ConnectorType, connector: BaseConnector) -> None:
        """Register a connector.

        Args:
            connector_type: Type of connector
            connector: Connector instance
        """
        self.connectors[connector_type] = connector
        logger.info(f"Registered connector: {connector_type}")

    def get_connector(self, connector_type: ConnectorType) -> Optional[BaseConnector]:
        """Get a registered connector.

        Args:
            connector_type: Type of connector

        Returns:
            Connector instance if registered, None otherwise
        """
        return self.connectors.get(connector_type)

    async def execute(
        self,
        connector_type: ConnectorType,
        operation: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        execution_phase: str = "execution",
        approval_token: Optional[str] = None,
    ) -> CommunicationResponse:
        """Execute a communication operation.

        Args:
            connector_type: Type of connector to use
            operation: Operation to perform
            params: Operation parameters
            context: Additional context (task_id, session_id, etc.)
            execution_phase: Execution phase ("planning" or "execution")
            approval_token: Optional approval token for approved requests

        Returns:
            Communication response
        """
        # Create request
        request = CommunicationRequest(
            id=f"comm-{uuid.uuid4().hex[:12]}",
            connector_type=connector_type,
            operation=operation,
            params=params,
            context=context or {},
            execution_phase=execution_phase,
            approval_token=approval_token,
        )

        try:
            # Check network mode first (before any other checks)
            is_allowed, deny_reason = self.network_mode_manager.is_operation_allowed(operation)
            if not is_allowed:
                logger.warning(
                    f"Operation '{operation}' blocked by network mode "
                    f"({self.network_mode_manager.get_mode().value}): {deny_reason}"
                )
                return await self._create_error_response(
                    request,
                    f"NETWORK_MODE_BLOCKED: {deny_reason}",
                    RequestStatus.DENIED
                )

            # Validate parameters
            is_valid, reason = self.policy_engine.validate_params(request)
            if not is_valid:
                return await self._create_error_response(request, reason, RequestStatus.DENIED)

            # Assess risk
            request.risk_level = self.policy_engine.assess_risk(request)

            # Evaluate policy with execution phase
            verdict = self.policy_engine.evaluate_request(request, execution_phase)
            if verdict.status != RequestStatus.APPROVED:
                # Log all outbound attempts (allowed and blocked)
                await self.evidence_logger.log_operation(
                    request,
                    CommunicationResponse(
                        request_id=request.id,
                        status=verdict.status,
                        error=f"{verdict.reason_code}: {verdict.hint}",
                    )
                )
                return await self._create_error_response(
                    request,
                    f"{verdict.reason_code}: {verdict.hint}",
                    verdict.status
                )

            # Check rate limit
            policy = self.policy_engine.get_policy(connector_type)
            if policy:
                is_allowed, reason = self.rate_limiter.check_limit(
                    str(connector_type),
                    limit=policy.rate_limit_per_minute
                )
                if not is_allowed:
                    return await self._create_error_response(request, reason, RequestStatus.RATE_LIMITED)

            # Sanitize inputs
            if policy and policy.sanitize_inputs:
                request.params = self.input_sanitizer.sanitize(request.params)

            # Get connector
            connector = self.get_connector(connector_type)
            if not connector:
                return await self._create_error_response(
                    request,
                    f"No connector registered for {connector_type}",
                    RequestStatus.FAILED
                )

            # Execute operation
            request.status = RequestStatus.IN_PROGRESS
            result = await connector.execute(operation, request.params)

            # Sanitize outputs
            if policy and policy.sanitize_outputs:
                result = self.output_sanitizer.sanitize(result)

            # Create response
            response = CommunicationResponse(
                request_id=request.id,
                status=RequestStatus.SUCCESS,
                data=result,
            )

            # Log evidence
            evidence_id = await self.evidence_logger.log_operation(request, response)
            response.evidence_id = evidence_id

            return response

        except Exception as e:
            logger.error(f"Communication error: {str(e)}", exc_info=True)
            return await self._create_error_response(request, str(e), RequestStatus.FAILED)

    async def _create_error_response(
        self,
        request: CommunicationRequest,
        error: str,
        status: RequestStatus,
    ) -> CommunicationResponse:
        """Create an error response.

        Args:
            request: Original request
            error: Error message
            status: Response status

        Returns:
            Error response
        """
        response = CommunicationResponse(
            request_id=request.id,
            status=status,
            error=error,
        )

        # Log failed request
        try:
            await self.evidence_logger.log_operation(request, response)
        except Exception as e:
            logger.error(f"Failed to log evidence: {str(e)}")

        return response

    async def list_connectors(self) -> Dict[str, Any]:
        """List all registered connectors.

        Returns:
            Dictionary of connector information
        """
        connectors_info = {}
        for connector_type, connector in self.connectors.items():
            policy = self.policy_engine.get_policy(connector_type)
            connectors_info[connector_type.value] = {
                "type": connector_type.value,
                "enabled": policy.enabled if policy else False,
                "operations": policy.allowed_operations if policy else [],
                "rate_limit": policy.rate_limit_per_minute if policy else 0,
            }
        return connectors_info

    async def get_statistics(self) -> Dict[str, Any]:
        """Get communication statistics.

        Returns:
            Dictionary of statistics
        """
        return {
            "total_requests": await self.evidence_logger.get_total_requests(),
            "success_rate": await self.evidence_logger.get_success_rate(),
            "by_connector": await self.evidence_logger.get_stats_by_connector(),
        }
