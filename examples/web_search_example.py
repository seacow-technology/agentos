"""Example usage of Web Search Connector.

This example demonstrates how to use the Web Search Connector
to perform searches and process results.
"""

import asyncio
import json
from agentos.core.communication.connectors.web_search import (
    WebSearchConnector,
    WebSearchError,
    RateLimitError,
    NetworkError,
)


async def basic_search():
    """Basic search example."""
    print("\n=== Basic Search Example ===\n")

    connector = WebSearchConnector({
        "engine": "duckduckgo",
        "max_results": 5,
    })

    result = await connector.execute("search", {
        "query": "Python asyncio tutorial",
        "max_results": 3,
    })

    print(f"Query: {result['query']}")
    print(f"Found {result['total_results']} results\n")

    for idx, item in enumerate(result['results'], 1):
        print(f"{idx}. {item['title']}")
        print(f"   {item['url']}")
        print(f"   {item['snippet'][:80]}...\n")


async def search_with_language():
    """Search with language parameter."""
    print("\n=== Search with Language Parameter ===\n")

    connector = WebSearchConnector({
        "engine": "duckduckgo",
    })

    # Search in Chinese
    result = await connector.execute("search", {
        "query": "人工智能",
        "language": "zh",
        "max_results": 3,
    })

    print(f"Query: {result['query']}")
    print(f"Language: zh (Chinese)")
    print(f"Found {result['total_results']} results\n")

    for idx, item in enumerate(result['results'], 1):
        print(f"{idx}. {item['title']}")
        print(f"   {item['url']}\n")


async def error_handling_example():
    """Error handling example."""
    print("\n=== Error Handling Example ===\n")

    connector = WebSearchConnector({
        "engine": "duckduckgo",
    })

    # Example 1: Empty query
    try:
        await connector.execute("search", {"query": ""})
    except ValueError as e:
        print(f"✓ Caught ValueError: {e}\n")

    # Example 2: Unsupported operation
    try:
        await connector.execute("invalid_op", {"query": "test"})
    except ValueError as e:
        print(f"✓ Caught ValueError: {e}\n")

    # Example 3: General error handling
    try:
        result = await connector.execute("search", {
            "query": "test query"
        })
    except RateLimitError as e:
        print(f"Rate limited: {e}")
    except NetworkError as e:
        print(f"Network error: {e}")
    except WebSearchError as e:
        print(f"Search error: {e}")


async def multiple_queries():
    """Search multiple queries in parallel."""
    print("\n=== Multiple Queries in Parallel ===\n")

    connector = WebSearchConnector({
        "engine": "duckduckgo",
        "max_results": 3,
    })

    queries = [
        "machine learning",
        "natural language processing",
        "computer vision",
    ]

    # Execute all searches in parallel
    tasks = [
        connector.execute("search", {"query": q, "max_results": 2})
        for q in queries
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for query, result in zip(queries, results):
        if isinstance(result, Exception):
            print(f"✗ {query}: {result}")
        else:
            print(f"✓ {query}: {result['total_results']} results")


async def search_and_filter():
    """Search and filter results."""
    print("\n=== Search and Filter Results ===\n")

    connector = WebSearchConnector({
        "engine": "duckduckgo",
        "max_results": 10,
    })

    result = await connector.execute("search", {
        "query": "Python programming",
        "max_results": 10,
    })

    print(f"Total results: {result['total_results']}\n")

    # Filter results by domain
    official_results = [
        r for r in result['results']
        if 'python.org' in r['url']
    ]

    print(f"Official Python.org results: {len(official_results)}")
    for item in official_results:
        print(f"  - {item['title']}")
        print(f"    {item['url']}\n")


async def connector_status():
    """Check connector status and configuration."""
    print("\n=== Connector Status ===\n")

    connector = WebSearchConnector({
        "engine": "duckduckgo",
        "max_results": 10,
        "timeout": 30,
        "deduplicate": True,
    })

    status = connector.get_status()
    print(f"Connector: {status['name']}")
    print(f"Enabled: {status['enabled']}")
    print(f"Config Valid: {status['config_valid']}")
    print(f"Operations: {', '.join(status['supported_operations'])}\n")

    # Health check
    healthy = await connector.health_check()
    print(f"Health Check: {'✓ Passed' if healthy else '✗ Failed'}\n")


async def search_json_export():
    """Search and export results as JSON."""
    print("\n=== Search and Export as JSON ===\n")

    connector = WebSearchConnector({
        "engine": "duckduckgo",
    })

    result = await connector.execute("search", {
        "query": "climate change",
        "max_results": 3,
    })

    # Export as formatted JSON
    json_output = json.dumps(result, indent=2, ensure_ascii=False)
    print("JSON Output:")
    print(json_output[:500] + "...\n")


async def main():
    """Run all examples."""
    examples = [
        ("Basic Search", basic_search),
        ("Search with Language", search_with_language),
        ("Error Handling", error_handling_example),
        ("Multiple Queries", multiple_queries),
        ("Search and Filter", search_and_filter),
        ("Connector Status", connector_status),
        ("JSON Export", search_json_export),
    ]

    for name, func in examples:
        print(f"\n{'='*60}")
        print(f"Running: {name}")
        print('='*60)
        try:
            await func()
        except Exception as e:
            print(f"Error in {name}: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print("All examples completed!")
    print('='*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
