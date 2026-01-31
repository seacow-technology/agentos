#!/usr/bin/env python3
"""Demo script to show priority scoring integration in web search connector.

This script demonstrates how search results are automatically scored and
sorted based on domain authority, source type, document type, and recency.
"""

import asyncio
import json
from agentos.core.communication.connectors.web_search import WebSearchConnector


async def demo_priority_scoring():
    """Demonstrate priority scoring with mock results."""

    print("=" * 80)
    print("Web Search Connector - Priority Scoring Demo")
    print("=" * 80)
    print()

    # Create connector
    connector = WebSearchConnector({"engine": "duckduckgo"})

    # Create mock search results with varying priority levels
    mock_results = [
        {
            "title": "Climate Change Blog Post",
            "href": "https://myblog.com/climate-post",
            "body": "Personal thoughts on climate change",
        },
        {
            "title": "Australian Government Climate Policy",
            "href": "https://environment.gov.au/climate-change/policy/emissions.pdf",
            "body": "Updated 2025. National emissions reduction framework...",
        },
        {
            "title": "University Research on Climate",
            "href": "https://research.edu.au/climate/study",
            "body": "Climate research findings from 2024",
        },
        {
            "title": "NGO Climate Report",
            "href": "https://climatecouncil.org.au/resources/climate-report-2025",
            "body": "Latest climate report published in 2025",
        },
        {
            "title": "News Article on Climate",
            "href": "https://news.com.au/climate-story",
            "body": "Recent news about climate policy",
        },
    ]

    # Standardize and score results
    print("Processing search results with priority scoring...")
    print()

    standardized = connector._standardize_results(mock_results)

    # Display results
    print("Results (sorted by priority score):")
    print("-" * 80)
    print()

    for i, result in enumerate(standardized, 1):
        print(f"{i}. {result['title']}")
        print(f"   URL: {result['url']}")
        print(f"   Domain: {result['domain']}")
        print(f"   Priority Score: {result['priority_score']}")
        print(f"   Reasons: {', '.join(result['priority_reasons'])}")
        print(f"   Snippet: {result['snippet'][:80]}...")
        print()

    print("=" * 80)
    print("Key Observations:")
    print("=" * 80)
    print()
    print("1. Government policy PDF with recent year scored highest")
    print("2. NGO from trusted sources scored second")
    print("3. Educational institution scored third")
    print("4. General news article scored lower")
    print("5. Personal blog scored lowest")
    print()
    print("This demonstrates metadata-based priority scoring WITHOUT semantic analysis!")
    print()


if __name__ == "__main__":
    asyncio.run(demo_priority_scoring())
