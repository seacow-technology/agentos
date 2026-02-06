"""Priority scoring for search results based on metadata only.

This module implements a scoring system that ranks search results
based on domain authority, source type, document type, and recency
WITHOUT using semantic analysis or page content.

CRITICAL CONSTRAINT: Only metadata is used - no page content, no NLP,
no semantic understanding of what the content says.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field


class PriorityReason(str, Enum):
    """Enumeration of priority scoring reasons.

    These describe WHY a result received its score,
    for transparency and auditability.
    """

    # Domain-based reasons
    GOV_DOMAIN = "gov_domain"                    # .gov or .gov.au domain
    EDU_DOMAIN = "edu_domain"                    # .edu domain
    ORG_DOMAIN = "org_domain"                    # .org domain
    OTHER_DOMAIN = "other_domain"                # Other domains

    # Source type reasons
    OFFICIAL_POLICY_SOURCE = "official_policy"   # On official policy whitelist
    RECOGNIZED_NGO = "recognized_ngo"            # On recognized NGO whitelist
    GENERAL_SOURCE = "general_source"            # Not on any whitelist

    # Document type reasons
    PDF_DOCUMENT = "pdf_document"                # URL points to PDF
    POLICY_PATH = "policy_path"                  # URL contains policy/legislation path
    BLOG_OPINION = "blog_opinion"                # URL contains blog/opinion path
    GENERAL_DOCUMENT = "general_document"        # Other document types

    # Recency reasons
    CURRENT_YEAR = "current_year"                # Published this year
    RECENT_YEAR = "recent_year"                  # Published last year
    NO_DATE_INFO = "no_date_info"                # No date information found


class PriorityScore(BaseModel):
    """Detailed breakdown of priority scoring for a search result.

    This model provides full transparency into how a score was calculated,
    showing the contribution from each scoring dimension.

    Attributes:
        total_score: Final priority score (sum of all components)
        domain_score: Score from domain authority (0-40)
        source_type_score: Score from source type classification (0-30)
        document_type_score: Score from document type classification (0-30, can stack)
        recency_score: Score from publication recency (0-10)
        reasons: List of reasons explaining the score
        metadata: Additional metadata used in scoring
    """

    total_score: int = Field(
        ...,
        description="Total priority score (sum of all components)",
        ge=0,
        le=110
    )
    domain_score: int = Field(
        ...,
        description="Score from domain authority",
        ge=0,
        le=40
    )
    source_type_score: int = Field(
        ...,
        description="Score from source type",
        ge=0,
        le=30
    )
    document_type_score: int = Field(
        ...,
        description="Score from document type (can stack up to 30)",
        ge=0,
        le=30
    )
    recency_score: int = Field(
        ...,
        description="Score from publication recency",
        ge=0,
        le=10
    )
    reasons: List[PriorityReason] = Field(
        default_factory=list,
        description="Reasons explaining the score"
    )
    metadata: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional metadata used in scoring"
    )


class SearchResultWithPriority(BaseModel):
    """Search result annotated with priority score.

    This extends a standard search result with priority scoring
    information for ranking and filtering.

    Attributes:
        title: Result title
        url: Result URL
        snippet: Result snippet/description
        priority_score: Detailed priority scoring breakdown
        rank: Original rank from search engine (optional)
    """

    title: str = Field(..., description="Result title")
    url: str = Field(..., description="Result URL")
    snippet: str = Field(default="", description="Result snippet")
    priority_score: PriorityScore = Field(
        ...,
        description="Priority scoring breakdown"
    )
    rank: Optional[int] = Field(
        None,
        description="Original rank from search engine"
    )


def calculate_priority_score(
    url: str,
    snippet: str,
    trusted_sources: Optional[Dict[str, List[str]]] = None
) -> PriorityScore:
    """Calculate priority score for a search result based on metadata only.

    This function implements the priority scoring algorithm WITHOUT
    any semantic analysis or content understanding. It only uses:
    - URL structure and domain
    - Document type indicators in URL
    - Date patterns in snippet (regex-based)
    - Whitelist matching

    CRITICAL: This function does NOT:
    - Fetch page content
    - Analyze what the content says
    - Use NLP or semantic understanding
    - Make judgments about content quality

    Args:
        url: The URL to score
        snippet: The search result snippet (for date extraction only)
        trusted_sources: Optional dict with 'official_policy' and 'recognized_ngo' lists

    Returns:
        PriorityScore with detailed scoring breakdown

    Examples:
        >>> score = calculate_priority_score(
        ...     url="https://example.gov.au/policy/climate.pdf",
        ...     snippet="Updated 2025. Climate policy framework..."
        ... )
        >>> score.total_score
        80  # 40 (gov) + 30 (policy) + 15 (pdf) + 10 (current year) = 95
    """
    # Initialize scores and reasons
    domain_score = 0
    source_type_score = 0
    document_type_score = 0
    recency_score = 0
    reasons: List[PriorityReason] = []
    metadata: Dict[str, str] = {}

    # Parse URL
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        path = parsed_url.path.lower()

        # Validate that URL has a scheme and domain
        if not parsed_url.scheme or not domain:
            # Invalid URL - return zero score
            return PriorityScore(
                total_score=0,
                domain_score=0,
                source_type_score=0,
                document_type_score=0,
                recency_score=0,
                reasons=[],
                metadata={"error": "invalid_url"}
            )

        metadata["domain"] = domain
        metadata["path"] = path
    except Exception:
        # Invalid URL - return zero score
        return PriorityScore(
            total_score=0,
            domain_score=0,
            source_type_score=0,
            document_type_score=0,
            recency_score=0,
            reasons=[],
            metadata={"error": "invalid_url"}
        )

    # Initialize trusted sources if not provided
    if trusted_sources is None:
        trusted_sources = {
            "official_policy": [],
            "recognized_ngo": []
        }

    # 1. DOMAIN SCORE (0-40 points)
    domain_score, domain_reason = _score_domain(domain)
    reasons.append(domain_reason)
    metadata["domain_type"] = domain_reason.value

    # 2. SOURCE TYPE SCORE (0-30 points)
    source_type_score, source_reason = _score_source_type(
        domain,
        trusted_sources.get("official_policy", []),
        trusted_sources.get("recognized_ngo", [])
    )
    reasons.append(source_reason)
    metadata["source_type"] = source_reason.value

    # 3. DOCUMENT TYPE SCORE (0-15 points)
    document_type_score, doc_reasons = _score_document_type(url, path)
    reasons.extend(doc_reasons)
    metadata["document_type"] = ",".join(r.value for r in doc_reasons)

    # 4. RECENCY SCORE (0-10 points)
    recency_score, recency_reason = _score_recency(snippet)
    reasons.append(recency_reason)
    metadata["recency"] = recency_reason.value

    # Calculate total score
    total_score = (
        domain_score +
        source_type_score +
        document_type_score +
        recency_score
    )

    return PriorityScore(
        total_score=total_score,
        domain_score=domain_score,
        source_type_score=source_type_score,
        document_type_score=document_type_score,
        recency_score=recency_score,
        reasons=reasons,
        metadata=metadata
    )


def _score_domain(domain: str) -> tuple[int, PriorityReason]:
    """Score based on domain authority.

    Scoring rules:
    - .gov / .gov.au → 40 points (GOV_DOMAIN)
    - .edu → 25 points (EDU_DOMAIN)
    - .org → 15 points (ORG_DOMAIN)
    - Other → 5 points (OTHER_DOMAIN)

    Args:
        domain: Domain name (e.g., "example.gov.au")

    Returns:
        Tuple of (score, reason)
    """
    # Check for government domains
    if domain.endswith(".gov") or domain.endswith(".gov.au"):
        return (40, PriorityReason.GOV_DOMAIN)

    # Check for educational domains
    if domain.endswith(".edu"):
        return (25, PriorityReason.EDU_DOMAIN)

    # Check for organization domains
    if domain.endswith(".org"):
        return (15, PriorityReason.ORG_DOMAIN)

    # All other domains
    return (5, PriorityReason.OTHER_DOMAIN)


def _score_source_type(
    domain: str,
    official_policy_sources: List[str],
    recognized_ngos: List[str]
) -> tuple[int, PriorityReason]:
    """Score based on source type classification.

    Scoring rules:
    - Official policy source (whitelist) → 30 points
    - Recognized NGO (whitelist) → 20 points
    - Other → 5 points

    Args:
        domain: Domain name
        official_policy_sources: List of official policy domains
        recognized_ngos: List of recognized NGO domains

    Returns:
        Tuple of (score, reason)
    """
    # Check if domain matches official policy sources
    for source in official_policy_sources:
        if domain == source or domain.endswith(f".{source}"):
            return (30, PriorityReason.OFFICIAL_POLICY_SOURCE)

    # Check if domain matches recognized NGOs
    for ngo in recognized_ngos:
        if domain == ngo or domain.endswith(f".{ngo}"):
            return (20, PriorityReason.RECOGNIZED_NGO)

    # Default score for other sources
    return (5, PriorityReason.GENERAL_SOURCE)


def _score_document_type(url: str, path: str) -> tuple[int, List[PriorityReason]]:
    """Score based on document type indicators in URL.

    Scoring rules:
    - URL contains .pdf → +15 points
    - URL path contains /policy/ or /legislation/ → +15 points
    - URL path contains /blog/ or /opinion/ → +0 points
    - Other → 0 points (neutral)

    Note: Multiple indicators can apply (e.g., PDF + policy path = 30 points)

    Args:
        url: Full URL
        path: URL path component

    Returns:
        Tuple of (score, list of reasons)
    """
    score = 0
    reasons: List[PriorityReason] = []

    # Check for PDF documents
    if url.lower().endswith(".pdf") or ".pdf?" in url.lower():
        score += 15
        reasons.append(PriorityReason.PDF_DOCUMENT)

    # Check for policy/legislation paths
    if "/policy/" in path or "/legislation/" in path:
        score += 15
        reasons.append(PriorityReason.POLICY_PATH)

    # Check for blog/opinion paths (negative indicator)
    if "/blog/" in path or "/opinion/" in path:
        score += 0  # Explicitly 0, not negative
        reasons.append(PriorityReason.BLOG_OPINION)

    # If no specific document type found, mark as general
    if not reasons:
        reasons.append(PriorityReason.GENERAL_DOCUMENT)

    return (score, reasons)


def _score_recency(snippet: str) -> tuple[int, PriorityReason]:
    """Score based on recency indicators in snippet.

    This function uses simple regex patterns to detect year mentions
    in the snippet text. It does NOT understand what the content says.

    Scoring rules:
    - Snippet contains current year (2025) → 10 points
    - Snippet contains last year (2024) → 10 points
    - No year information → 0 points

    Args:
        snippet: Search result snippet text

    Returns:
        Tuple of (score, reason)
    """
    current_year = datetime.now().year
    last_year = current_year - 1

    # Simple regex to find 4-digit years
    year_pattern = r'\b(20\d{2})\b'
    years_found = re.findall(year_pattern, snippet)

    # Check if current year or last year appears
    for year_str in years_found:
        year = int(year_str)
        if year == current_year:
            return (10, PriorityReason.CURRENT_YEAR)
        elif year == last_year:
            return (10, PriorityReason.RECENT_YEAR)

    # No recent year information found
    return (0, PriorityReason.NO_DATE_INFO)
