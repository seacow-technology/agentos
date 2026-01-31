#!/usr/bin/env python3
"""Demo script for priority scoring system.

This script demonstrates how to use the metadata-based priority scoring
system to rank search results without semantic analysis.
"""

from agentos.core.communication.priority import (
    calculate_priority_score,
    SearchResultWithPriority,
)
from agentos.core.communication.config import load_trusted_sources


def main():
    """Run priority scoring demo."""
    print("=" * 80)
    print("Priority Scoring System Demo")
    print("=" * 80)
    print()

    # Load trusted sources configuration
    try:
        trusted_sources = load_trusted_sources()
        print(f"Loaded {len(trusted_sources['official_policy'])} official policy sources")
        print(f"Loaded {len(trusted_sources['recognized_ngo'])} recognized NGOs")
        print()
    except FileNotFoundError:
        print("WARNING: Trusted sources config not found, using empty lists")
        trusted_sources = {"official_policy": [], "recognized_ngo": []}
        print()

    # Example search results to score
    example_results = [
        {
            "title": "Climate Policy Framework 2025",
            "url": "https://aph.gov.au/policy/climate-framework.pdf",
            "snippet": "Updated January 2025. Australia's comprehensive climate policy framework.",
        },
        {
            "title": "University Research on Climate Change",
            "url": "https://research.stanford.edu/climate-study",
            "snippet": "Published in 2024. Study on climate change impacts.",
        },
        {
            "title": "My Opinion on Climate Policy",
            "url": "https://example.com/blog/my-climate-opinion",
            "snippet": "I think we need better climate policies.",
        },
        {
            "title": "WHO Climate and Health Report",
            "url": "https://www.who.int/publications/climate-health-report.pdf",
            "snippet": "World Health Organization report on climate impacts on health, 2025.",
        },
        {
            "title": "Climate News Article",
            "url": "https://example.com/news/climate-article",
            "snippet": "Recent developments in climate policy.",
        },
    ]

    # Score each result
    print("Scoring search results...")
    print("-" * 80)
    print()

    scored_results = []
    for result in example_results:
        score = calculate_priority_score(
            url=result["url"],
            snippet=result["snippet"],
            trusted_sources=trusted_sources
        )

        scored_result = SearchResultWithPriority(
            title=result["title"],
            url=result["url"],
            snippet=result["snippet"],
            priority_score=score,
        )
        scored_results.append(scored_result)

    # Sort by priority score (descending)
    scored_results.sort(key=lambda x: x.priority_score.total_score, reverse=True)

    # Display results
    for i, result in enumerate(scored_results, 1):
        score = result.priority_score
        print(f"{i}. {result.title}")
        print(f"   URL: {result.url}")
        print(f"   Total Score: {score.total_score}")
        print(f"   Breakdown:")
        print(f"     - Domain: {score.domain_score} ({score.metadata.get('domain_type', 'N/A')})")
        print(f"     - Source Type: {score.source_type_score} ({score.metadata.get('source_type', 'N/A')})")
        print(f"     - Document Type: {score.document_type_score} ({score.metadata.get('document_type', 'N/A')})")
        print(f"     - Recency: {score.recency_score} ({score.metadata.get('recency', 'N/A')})")
        print()

    print("=" * 80)
    print("Scoring Rules Applied:")
    print("=" * 80)
    print()
    print("Domain Authority:")
    print("  - .gov / .gov.au: +40 points")
    print("  - .edu: +25 points")
    print("  - .org: +15 points")
    print("  - Other: +5 points")
    print()
    print("Source Type:")
    print("  - Official Policy Source (whitelist): +30 points")
    print("  - Recognized NGO (whitelist): +20 points")
    print("  - Other: +5 points")
    print()
    print("Document Type:")
    print("  - PDF document: +15 points")
    print("  - Policy/legislation path: +15 points")
    print("  - Blog/opinion path: +0 points")
    print("  - Other: +0 points")
    print("  (Note: Multiple indicators can stack)")
    print()
    print("Recency:")
    print("  - Current year (2025): +10 points")
    print("  - Last year (2024): +10 points")
    print("  - No date info: +0 points")
    print()
    print("=" * 80)
    print("IMPORTANT: This scoring uses ONLY metadata, NOT content!")
    print("=" * 80)


if __name__ == "__main__":
    main()
