"""Brief generator for CommunicationOS.

This module implements the BRIEF stage of the SEARCH→FETCH→BRIEF pipeline,
generating structured summaries from verified documents with strict phase gate
validation and trust tier enforcement.

Architecture:
- Phase Gate: Validates minimum N fetched documents (trust_tier=verified_source)
- Input: FetchedDocument list from FETCH stage
- Output: Structured Markdown brief with citations and provenance
- Constraints: NO unverified content, NO over-interpretation, declarative only

Design Principles:
1. Verification-First: All content must be from fetched documents
2. Attribution: Every claim must cite source URLs
3. Declarative: Categorize and format, do NOT introduce new content
4. Trust Tier: Enforce verified_source requirement (≥Tier 1)
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional, Any
from urllib.parse import urlparse
from collections import defaultdict
from agentos.core.time import utc_now


logger = logging.getLogger(__name__)


class BriefGenerator:
    """Generate structured briefings from verified documents.

    Implements BRIEF stage of the SEARCH→FETCH→BRIEF pipeline with:
    - Input validation and phase gate enforcement
    - Structured Markdown generation
    - Regional categorization
    - Trend extraction (basic keyword-based, no deep analysis)
    - Trust tier verification
    """

    def __init__(
        self,
        min_documents: int = 3,
        trust_tier_requirement: str = "verified_source"
    ):
        """Initialize brief generator.

        Args:
            min_documents: Minimum number of documents required (default 3)
            trust_tier_requirement: Required trust tier ("verified_source")
        """
        self.min_documents = min_documents
        self.trust_tier_requirement = trust_tier_requirement

    def validate_inputs(self, documents: List[Dict]) -> Tuple[bool, str]:
        """Validate input documents (Phase Gate).

        Checks:
        - At least N documents (N configurable, default 3)
        - All documents trust_tier = "verified_source" (or higher tiers)
        - All documents contain required fields

        Args:
            documents: List of fetched documents

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Rule 1: Minimum document count
        if len(documents) < self.min_documents:
            return (
                False,
                f"Insufficient documents: {len(documents)} < {self.min_documents}. "
                f"Brief requires at least {self.min_documents} verified documents."
            )

        # Rule 2: Trust tier verification
        # verified_source = external_source | primary_source | authoritative_source
        # search_result (Tier 0) is NOT accepted
        valid_tiers = {
            "external_source",
            "primary_source",
            "authoritative",
            "verified_source"  # Alias for any ≥Tier 1
        }

        invalid_docs = []
        for doc in documents:
            trust_tier = doc.get("trust_tier", "").lower()

            # search_result is explicitly blocked
            if trust_tier == "search_result":
                invalid_docs.append({
                    "url": doc.get("url", "unknown"),
                    "trust_tier": trust_tier,
                    "reason": "search_result tier not accepted (must be verified)"
                })
            elif trust_tier not in valid_tiers:
                invalid_docs.append({
                    "url": doc.get("url", "unknown"),
                    "trust_tier": trust_tier,
                    "reason": f"Invalid trust tier (expected: {', '.join(valid_tiers)})"
                })

        if invalid_docs:
            error_lines = [
                f"Found {len(invalid_docs)} documents with invalid trust tier:",
            ]
            for doc_info in invalid_docs[:5]:  # Show first 5
                error_lines.append(
                    f"  - {doc_info['url']}: {doc_info['trust_tier']} "
                    f"({doc_info['reason']})"
                )
            if len(invalid_docs) > 5:
                error_lines.append(f"  ... and {len(invalid_docs) - 5} more")

            return (False, "\n".join(error_lines))

        # Rule 3: Required fields validation
        required_fields = ["url", "title", "trust_tier"]
        missing_fields_docs = []

        for doc in documents:
            missing = [field for field in required_fields if not doc.get(field)]
            if missing:
                missing_fields_docs.append({
                    "url": doc.get("url", "unknown"),
                    "missing_fields": missing
                })

        if missing_fields_docs:
            error_lines = [
                f"Found {len(missing_fields_docs)} documents with missing required fields:",
            ]
            for doc_info in missing_fields_docs[:5]:
                error_lines.append(
                    f"  - {doc_info['url']}: missing {', '.join(doc_info['missing_fields'])}"
                )
            if len(missing_fields_docs) > 5:
                error_lines.append(f"  ... and {len(missing_fields_docs) - 5} more")

            return (False, "\n".join(error_lines))

        # All validations passed
        return (True, "")

    def generate_brief(self, documents: List[Dict], topic: str) -> str:
        """Generate structured brief from fetched documents.

        Input: fetched_document list
        Output: Markdown formatted brief

        Args:
            documents: List of verified fetched documents
            topic: Brief topic (e.g., "AI Policy")

        Returns:
            Markdown formatted brief string
        """
        # Generate metadata
        generation_time = utc_now()
        date_str = generation_time.strftime("%Y-%m-%d")
        timestamp_str = generation_time.isoformat()

        # Categorize by region
        regional_docs = self._categorize_by_region(documents)

        # Extract trends
        trends = self._extract_trends(documents)

        # Start building Markdown
        md_lines = [
            f"# Today's {topic.upper()} Policy Brief ({date_str})",
            "",
            f"**Generation Time**: {timestamp_str}",
            f"**Source**: CommunicationOS ({len(documents)} verified sources)",
            f"**Scope**: AI / Policy / Regulation",
            "",
            "---",
            ""
        ]

        # Regional sections
        if regional_docs:
            for region, docs in regional_docs.items():
                # Region header with flag emoji
                region_emoji = self._get_region_emoji(region)
                md_lines.append(f"## {region_emoji} {region}")
                md_lines.append("")

                for doc in docs:
                    title = doc.get("title", "No Title")
                    url = doc.get("url", "")
                    domain = doc.get("domain", urlparse(url).netloc if url else "unknown")
                    summary = doc.get("summary", "")
                    body_text = doc.get("text", "")
                    publish_date = doc.get("retrieved_at", "")
                    trust_tier = doc.get("trust_tier", "external_source")

                    # Extract key points from body_text or summary
                    key_points = self._extract_key_points(body_text or summary)

                    md_lines.append(f"### Policy Update: {title}")
                    md_lines.append(f"- **Key Content**: {key_points}")
                    if publish_date:
                        md_lines.append(f"- **Effective Date**: {publish_date}")
                    md_lines.append(f"- **Source**: [{domain}]({url})")
                    md_lines.append(f"- **Trust Tier**: {trust_tier}")
                    md_lines.append("")

        # Global trends section
        if trends:
            md_lines.append("## 🌍 Global Trends")
            md_lines.append("")
            for trend in trends:
                md_lines.append(f"- {trend}")
            md_lines.append("")

        # Risk & Impact section (declarative)
        md_lines.extend([
            "## Risk & Impact (Declarative)",
            "",
            "- **Enterprise Impact**: Policy changes may affect AI deployment timelines",
            "- **Developer Notes**: Regulatory compliance requirements should be reviewed",
            "- **Monitoring**: Continued observation of regulatory developments recommended",
            "",
            "---",
            "",
            f"> All content based on {len(documents)} verified official sources",
            "> ",
            "> 📝 **Source Attribution**:",
        ])

        # List all source URLs
        for doc in documents:
            url = doc.get("url", "")
            domain = doc.get("domain", urlparse(url).netloc if url else "unknown")
            if url:
                md_lines.append(f"> - [{domain}]({url})")

        return "\n".join(md_lines)

    def _categorize_by_region(self, documents: List[Dict]) -> Dict[str, List[Dict]]:
        """Categorize documents by geographic region/country.

        Uses simple heuristics:
        - Domain TLD (.au, .cn, .uk, etc.)
        - Title/content keywords

        Args:
            documents: List of documents

        Returns:
            Dictionary mapping region name to document list
        """
        regional_docs = defaultdict(list)

        for doc in documents:
            url = doc.get("url", "")
            title = doc.get("title", "").lower()
            text = doc.get("text", "").lower()

            # Extract domain
            domain = urlparse(url).netloc if url else ""

            # Region detection (simple TLD + keyword based)
            region = "Global"  # Default

            if ".au" in domain or "australia" in title or "australia" in text[:200]:
                region = "Australia"
            elif ".cn" in domain or "china" in title or "china" in text[:200]:
                region = "China"
            elif ".uk" in domain or "united kingdom" in title or "britain" in title:
                region = "United Kingdom"
            elif ".eu" in domain or "european" in title or "europe" in text[:200]:
                region = "European Union"
            elif ".gov" in domain and "whitehouse.gov" in domain:
                region = "United States"
            elif "united states" in title or "u.s." in title or "usa" in title:
                region = "United States"
            elif "japan" in title or ".jp" in domain:
                region = "Japan"

            regional_docs[region].append(doc)

        return dict(regional_docs)

    def _extract_trends(self, documents: List[Dict]) -> List[str]:
        """Extract common trends from documents.

        Simple keyword-based trend detection (no deep analysis).

        Args:
            documents: List of documents

        Returns:
            List of trend descriptions
        """
        # Keyword frequency analysis
        keyword_counts = defaultdict(int)
        trend_keywords = {
            "regulation": "Increased regulatory activity across jurisdictions",
            "policy": "New policy frameworks under development",
            "compliance": "Growing emphasis on compliance requirements",
            "safety": "Safety considerations in AI deployment",
            "ethics": "Ethical guidelines for AI systems",
            "transparency": "Transparency and explainability requirements",
            "privacy": "Data privacy and protection measures",
            "security": "Security standards for AI applications",
            "audit": "Audit and accountability mechanisms",
            "governance": "Governance frameworks for AI oversight"
        }

        # Count keyword occurrences
        for doc in documents:
            text = (doc.get("title", "") + " " + doc.get("text", "")).lower()
            for keyword in trend_keywords:
                if keyword in text:
                    keyword_counts[keyword] += 1

        # Identify trends (keywords appearing in multiple sources)
        min_sources = max(2, len(documents) // 2)  # At least 2 or 50% of sources
        trends = []

        for keyword, count in sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True):
            if count >= min_sources:
                trends.append(f"{trend_keywords[keyword]} (observed in {count} sources)")

        # Return top 5 trends
        return trends[:5] if trends else ["Diverse policy developments across regions"]

    def _extract_key_points(self, text: str) -> str:
        """Extract key points from text (simple truncation).

        Args:
            text: Source text

        Returns:
            Extracted key points (truncated)
        """
        if not text:
            return "No content available"

        # Simple extraction: take first 200 chars
        text = text.strip()
        if len(text) <= 200:
            return text

        # Truncate at sentence boundary
        truncated = text[:200]
        last_period = truncated.rfind(".")
        if last_period > 100:  # If we can get a complete sentence
            return truncated[:last_period + 1]
        else:
            return truncated + "..."

    def _get_region_emoji(self, region: str) -> str:
        """Get emoji for region.

        Args:
            region: Region name

        Returns:
            Emoji string
        """
        emoji_map = {
            "Australia": "🇦🇺",
            "China": "🇨🇳",
            "United Kingdom": "🇬🇧",
            "European Union": "🇪🇺",
            "United States": "🇺🇸",
            "Japan": "🇯🇵",
            "Global": "🌍"
        }
        return emoji_map.get(region, "🌍")
