"""Evidence logging for audit and compliance.

This module provides comprehensive audit logging for all communication
operations, enabling traceability, compliance, and security analysis.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

from agentos.core.storage.paths import component_db_path
from agentos.core.time import utc_now
from agentos.core.communication.models import (
    CommunicationRequest,
    CommunicationResponse,
    ConnectorType,
    EvidenceRecord,
    RequestStatus,
    TrustTier,
)
from agentos.core.communication.storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


class EvidenceLogger:
    """Logger for communication audit evidence.

    The EvidenceLogger records all communication operations with
    sufficient detail for audit, compliance, and security analysis.
    """

    # Authoritative domains (government, academia, certified organizations)
    AUTHORITATIVE_DOMAINS: Set[str] = {
        # Government
        "whitehouse.gov", "state.gov", "defense.gov", "nih.gov", "cdc.gov",
        "fda.gov", "sec.gov", "ftc.gov", "dhs.gov", "justice.gov",
        # International government
        "europa.eu", "who.int", "un.org",
        # Academia
        "mit.edu", "stanford.edu", "harvard.edu", "berkeley.edu",
        "oxford.ac.uk", "cambridge.ac.uk",
        # Standards bodies
        "w3.org", "ietf.org", "ieee.org", "iso.org",
        # Scientific publishers
        "nature.com", "science.org", "sciencedirect.com",
    }

    # Primary source domains (official company sites, original publishers)
    PRIMARY_SOURCE_DOMAINS: Set[str] = {
        # Tech companies (official docs)
        "docs.python.org", "docs.microsoft.com", "developer.apple.com",
        "developer.mozilla.org", "docs.github.com", "cloud.google.com",
        "docs.aws.amazon.com", "kubernetes.io", "docker.com",
        # News organizations (original reporting)
        "reuters.com", "apnews.com", "bbc.com", "npr.org",
        # Open source projects (official sites)
        "github.com", "gitlab.com", "sourceforge.net",
    }

    def __init__(self, storage: Optional[SQLiteStore] = None):
        """Initialize evidence logger.

        Args:
            storage: Storage backend for evidence records
        """
        if storage is None:
            # Use environment variable with CommunicationOS-specific fallback
            comm_db_path = os.getenv("AGENTOS_COMMUNICATION_DB",
                                      str(component_db_path("communicationos")))
            storage = SQLiteStore(Path(comm_db_path))
        self.storage = storage

        # Allow runtime configuration of domain lists
        self.authoritative_domains = self.AUTHORITATIVE_DOMAINS.copy()
        self.primary_source_domains = self.PRIMARY_SOURCE_DOMAINS.copy()

    def determine_trust_tier(
        self,
        url: str,
        connector_type: ConnectorType,
    ) -> TrustTier:
        """Determine trust tier based on URL and connector type.

        CRITICAL PRINCIPLE: Search results are NOT truth sources.
        They are candidate source generators.

        Args:
            url: The URL being accessed
            connector_type: Type of connector used

        Returns:
            TrustTier: The determined trust level

        Trust hierarchy:
        1. SEARCH_RESULT: Search engine results (candidates only)
        2. EXTERNAL_SOURCE: Fetched content (default, needs verification)
        3. PRIMARY_SOURCE: Official sites, original documents
        4. AUTHORITATIVE_SOURCE: Government, academia, certified orgs
        """
        # Search results are ALWAYS lowest tier - they are candidates, not truth
        if connector_type == ConnectorType.WEB_SEARCH:
            return TrustTier.SEARCH_RESULT

        # Parse domain from URL
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Remove port if present
            if ":" in domain:
                domain = domain.split(":")[0]

            # Remove www. prefix for matching
            if domain.startswith("www."):
                domain = domain[4:]

        except Exception as e:
            logger.warning(f"Failed to parse URL {url}: {e}")
            return TrustTier.EXTERNAL_SOURCE

        # Check for government domains (.gov, gov.cn, .edu)
        if domain.endswith(".gov") or domain == "gov.cn" or domain.endswith(".gov.cn"):
            return TrustTier.AUTHORITATIVE_SOURCE

        # Academic institutions
        if domain.endswith(".edu") or domain.endswith(".ac.uk"):
            return TrustTier.AUTHORITATIVE_SOURCE

        # International organization domains
        if domain.endswith(".int") or domain.endswith(".org") and domain in self.authoritative_domains:
            return TrustTier.AUTHORITATIVE_SOURCE

        # Check authoritative domains (configured allowlist)
        if domain in self.authoritative_domains or any(domain.endswith(f".{d}") for d in self.authoritative_domains):
            return TrustTier.AUTHORITATIVE_SOURCE

        # Check primary source domains
        if domain in self.primary_source_domains or any(domain.endswith(f".{d}") for d in self.primary_source_domains):
            return TrustTier.PRIMARY_SOURCE

        # Default: external source (needs verification)
        return TrustTier.EXTERNAL_SOURCE

    async def log_operation(
        self,
        request: CommunicationRequest,
        response: CommunicationResponse,
    ) -> str:
        """Log a communication operation.

        Args:
            request: Communication request
            response: Communication response

        Returns:
            Evidence record ID
        """
        # Create evidence record
        evidence_id = f"ev-{uuid.uuid4().hex[:12]}"

        # Create sanitized summaries
        request_summary = self._create_request_summary(request)
        response_summary = self._create_response_summary(response)

        # Determine trust tier based on URL and connector type
        url = request.params.get("url", "") or request.params.get("query", "")
        trust_tier = self.determine_trust_tier(url, request.connector_type)

        evidence = EvidenceRecord(
            id=evidence_id,
            request_id=request.id,
            connector_type=request.connector_type,
            operation=request.operation,
            request_summary=request_summary,
            response_summary=response_summary,
            status=response.status,
            trust_tier=trust_tier,
            metadata={
                "risk_level": request.risk_level.value,
                "context": request.context,
            },
        )

        # Store evidence
        await self.storage.save_evidence(evidence)

        logger.info(
            f"Logged evidence: {evidence_id} for request {request.id} "
            f"with trust_tier={trust_tier.value}"
        )
        return evidence_id

    def _create_request_summary(self, request: CommunicationRequest) -> Dict[str, Any]:
        """Create sanitized request summary.

        Args:
            request: Communication request

        Returns:
            Request summary dictionary
        """
        summary = {
            "connector_type": request.connector_type.value,
            "operation": request.operation,
            "timestamp": request.created_at.isoformat(),
        }

        # Include safe parameters
        safe_params = {}
        for key, value in request.params.items():
            if key in ["url", "query", "feed_url", "to", "channel"]:
                safe_params[key] = value
            elif key in ["body", "content", "message"]:
                # Truncate long content
                safe_params[key] = str(value)[:200] + "..." if len(str(value)) > 200 else value

        summary["params"] = safe_params
        return summary

    def _create_response_summary(self, response: CommunicationResponse) -> Dict[str, Any]:
        """Create sanitized response summary.

        Args:
            response: Communication response

        Returns:
            Response summary dictionary
        """
        summary = {
            "status": response.status.value,
            "timestamp": response.created_at.isoformat(),
        }

        if response.error:
            summary["error"] = response.error

        if response.metadata:
            summary["metadata"] = {
                k: v for k, v in response.metadata.items()
                if k in ["content_type", "content_length", "status_code"]
            }

        # Don't include full response data in summary for security
        if response.data:
            summary["has_data"] = True
            summary["data_type"] = type(response.data).__name__

        return summary

    async def get_evidence(self, evidence_id: str) -> Optional[EvidenceRecord]:
        """Get evidence record by ID.

        Args:
            evidence_id: Evidence record ID

        Returns:
            Evidence record if found, None otherwise
        """
        return await self.storage.get_evidence(evidence_id)

    async def get_request_evidence(self, request_id: str) -> Optional[EvidenceRecord]:
        """Get evidence for a specific request.

        Args:
            request_id: Request ID

        Returns:
            Evidence record if found, None otherwise
        """
        return await self.storage.get_evidence_by_request(request_id)

    async def search_evidence(
        self,
        connector_type: Optional[str] = None,
        operation: Optional[str] = None,
        status: Optional[RequestStatus] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[EvidenceRecord]:
        """Search evidence records.

        Args:
            connector_type: Filter by connector type
            operation: Filter by operation
            status: Filter by status
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum number of records to return

        Returns:
            List of evidence records
        """
        return await self.storage.search_evidence(
            connector_type=connector_type,
            operation=operation,
            status=status,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    async def get_total_requests(self) -> int:
        """Get total number of requests.

        Returns:
            Total request count
        """
        return await self.storage.get_total_count()

    async def get_success_rate(self) -> float:
        """Get success rate of requests.

        Returns:
            Success rate as a percentage (0-100)
        """
        total = await self.storage.get_total_count()
        if total == 0:
            return 0.0

        successful = await self.storage.get_count_by_status(RequestStatus.SUCCESS)
        return (successful / total) * 100

    async def get_stats_by_connector(self) -> Dict[str, int]:
        """Get statistics by connector type.

        Returns:
            Dictionary mapping connector types to request counts
        """
        return await self.storage.get_stats_by_connector()

    async def export_evidence(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        output_path: Optional[Path] = None,
    ) -> Path:
        """Export evidence records to JSON file.

        Args:
            start_date: Start date for export
            end_date: End date for export
            output_path: Output file path

        Returns:
            Path to exported file
        """
        if output_path is None:
            timestamp = utc_now().strftime("%Y%m%d_%H%M%S")
            output_path = Path.home() / ".agentos" / f"evidence_export_{timestamp}.json"

        records = await self.search_evidence(
            start_date=start_date,
            end_date=end_date,
            limit=10000,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(
                [record.to_dict() for record in records],
                f,
                indent=2,
                default=str,
            )

        logger.info(f"Exported {len(records)} evidence records to {output_path}")
        return output_path
