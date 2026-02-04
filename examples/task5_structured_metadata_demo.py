#!/usr/bin/env python3
"""
Demo: Task #5 Structured Return Interface

This demo shows how the structured metadata can be used for future WebUI
card rendering while maintaining backward compatibility with CLI Markdown output.
"""

from agentos.core.chat.comm_commands import CommCommandHandler


def demo_weather_query():
    """Demo weather query with structured metadata extraction."""
    print("=" * 70)
    print("DEMO 1: Weather Query - 'weather in Sydney'")
    print("=" * 70)

    # Simulate a search result for weather query
    result = {
        "status": "success",
        "results": [
            {
                "title": "Sydney Weather Forecast - 7 Days",
                "url": "https://weather.example.com/sydney",
                "snippet": "Sunny, 25°C. UV Index: High. Wind: 15 km/h NE",
                "trust_tier": "search_result"
            },
            {
                "title": "Sydney, Australia Weather Conditions",
                "url": "https://weather.service.com/sydney-au",
                "snippet": "Current conditions: Clear sky, 24°C, Humidity 65%",
                "trust_tier": "search_result"
            }
        ],
        "metadata": {
            "query": "weather in Sydney",
            "total_results": 2,
            "attribution": "CommunicationOS",
            "audit_id": "demo-001",
            "engine": "duckduckgo",
            "retrieved_at": "2026-02-01T12:00:00Z"
        }
    }

    # Get both Markdown and structured metadata
    markdown, metadata = CommCommandHandler._format_search_results(result)

    print("\n📊 STRUCTURED METADATA (for WebUI card rendering):")
    print("-" * 70)
    print(f"  Search Type: {metadata['search_type']}")
    print(f"  Location: {metadata['location']}")
    print(f"  Total Results: {metadata['total_results']}")
    print(f"  Raw Results: {len(metadata['raw_results'])} items")
    print(f"  Error: {metadata['error']}")

    print("\n🎨 HOW WEBUI CAN USE THIS:")
    print("-" * 70)
    if metadata['search_type'] == 'weather' and metadata['location']:
        print(f"  ✅ Render WeatherCard for '{metadata['location']}'")
        print(f"  ✅ Show {len(metadata['raw_results'])} weather sources")
        print(f"  ✅ Enable location-specific features (map, radar, etc.)")
    else:
        print("  ⚪ Render generic search results")

    print("\n📝 CLI MARKDOWN OUTPUT (backward compatible):")
    print("-" * 70)
    print(markdown[:300] + "..." if len(markdown) > 300 else markdown)

    print("\n")


def demo_news_query():
    """Demo news query with structured metadata extraction."""
    print("=" * 70)
    print("DEMO 2: News Query - 'latest AI news'")
    print("=" * 70)

    result = {
        "status": "success",
        "results": [
            {
                "title": "Latest AI Breakthroughs in 2026",
                "url": "https://news.example.com/ai-2026",
                "snippet": "Major advances in language models and robotics...",
                "trust_tier": "search_result"
            }
        ],
        "metadata": {
            "query": "latest AI news",
            "total_results": 1,
            "attribution": "CommunicationOS",
            "audit_id": "demo-002"
        }
    }

    markdown, metadata = CommCommandHandler._format_search_results(result)

    print("\n📊 STRUCTURED METADATA:")
    print("-" * 70)
    print(f"  Search Type: {metadata['search_type']}")
    print(f"  Location: {metadata['location']}")

    print("\n🎨 HOW WEBUI CAN USE THIS:")
    print("-" * 70)
    if metadata['search_type'] == 'news':
        print("  ✅ Render NewsCard with article highlights")
        print("  ✅ Show publication dates and sources")
        print("  ✅ Enable news-specific filters (date, category)")
    else:
        print("  ⚪ Render generic search results")

    print("\n")


def demo_general_query():
    """Demo general query with structured metadata extraction."""
    print("=" * 70)
    print("DEMO 3: General Query - 'Python tutorial'")
    print("=" * 70)

    result = {
        "status": "success",
        "results": [
            {
                "title": "Python Tutorial - Learn Python",
                "url": "https://tutorial.example.com/python",
                "snippet": "Complete Python tutorial for beginners...",
                "trust_tier": "search_result"
            }
        ],
        "metadata": {
            "query": "Python tutorial",
            "total_results": 1,
            "attribution": "CommunicationOS",
            "audit_id": "demo-003"
        }
    }

    markdown, metadata = CommCommandHandler._format_search_results(result)

    print("\n📊 STRUCTURED METADATA:")
    print("-" * 70)
    print(f"  Search Type: {metadata['search_type']}")
    print(f"  Location: {metadata['location']}")

    print("\n🎨 HOW WEBUI CAN USE THIS:")
    print("-" * 70)
    if metadata['search_type'] == 'general':
        print("  ✅ Render standard search results list")
        print("  ✅ Show titles, URLs, and snippets")
        print("  ✅ No specialized card needed")

    print("\n")


def demo_error_handling():
    """Demo error handling with structured metadata."""
    print("=" * 70)
    print("DEMO 4: Error Handling - Blocked Request")
    print("=" * 70)

    result = {
        "status": "blocked",
        "reason": "SSRF_PROTECTION",
        "message": "内网地址被阻止",
        "hint": "请使用公开的 HTTPS URL"
    }

    markdown, metadata = CommCommandHandler._format_search_results(result)

    print("\n📊 STRUCTURED METADATA:")
    print("-" * 70)
    print(f"  Search Type: {metadata['search_type']}")
    print(f"  Error: {metadata['error']}")

    print("\n🎨 HOW WEBUI CAN USE THIS:")
    print("-" * 70)
    if metadata['error']:
        print(f"  ⚠️  Show error message: {metadata['error']['type']}")
        print(f"  ⚠️  Display hint to user")
        print(f"  ⚠️  Render error card with retry option")

    print("\n📝 CLI MARKDOWN OUTPUT:")
    print("-" * 70)
    print(markdown)

    print("\n")


def demo_location_extraction():
    """Demo various location extraction patterns."""
    print("=" * 70)
    print("DEMO 5: Location Extraction Patterns")
    print("=" * 70)

    test_queries = [
        "weather in Sydney",
        "Sydney weather",
        "what's the weather in New York",
        "天气 北京",
        "temperature in Tokyo",
        "San Francisco weather forecast",
        "weather London UK",
    ]

    print("\nLocation Extraction Results:")
    print("-" * 70)

    for query in test_queries:
        search_type, location = CommCommandHandler._detect_query_type(query)
        status = "✓" if location else "○"
        print(f"  {status} '{query}'")
        print(f"     -> type={search_type}, location={location}")

    print("\n")


def demo_communication_adapter_integration():
    """Demo CommunicationAdapter result_type integration."""
    print("=" * 70)
    print("DEMO 6: CommunicationAdapter result_type Detection")
    print("=" * 70)

    from agentos.core.chat.communication_adapter import CommunicationAdapter

    adapter = CommunicationAdapter()

    queries = [
        "weather in Sydney",
        "latest AI news",
        "Python tutorial",
        "temperature forecast",
        "今天新闻",
    ]

    print("\nResult Type Detection (for WebUI card selection):")
    print("-" * 70)

    for query in queries:
        result_type = adapter._detect_result_type(query)
        icon = {"weather": "🌤️", "news": "📰", "general": "🔍"}.get(result_type, "❓")
        print(f"  {icon} '{query}' -> result_type='{result_type}'")

    print("\n🎨 WebUI Card Mapping:")
    print("-" * 70)
    print("  🌤️  weather  -> WeatherCard (location, forecast, radar)")
    print("  📰 news     -> NewsCard (headlines, dates, sources)")
    print("  🔍 general  -> SearchResults (standard list view)")

    print("\n")


def main():
    """Run all demos."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  Task #5: Structured Return Interface Demo".center(68) + "║")
    print("║" + "  (Future WebUI Card Rendering)".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    print("\n")

    demo_weather_query()
    demo_news_query()
    demo_general_query()
    demo_error_handling()
    demo_location_extraction()
    demo_communication_adapter_integration()

    print("=" * 70)
    print("KEY TAKEAWAYS:")
    print("=" * 70)
    print("1. ✅ Backward compatible - Markdown output unchanged")
    print("2. ✅ Structured metadata enables specialized WebUI cards")
    print("3. ✅ Query type detection (weather/news/general)")
    print("4. ✅ Location extraction for weather queries")
    print("5. ✅ Graceful fallback when uncertain")
    print("6. ✅ Error information in metadata")
    print("7. ✅ Clear interface for future WebUI integration")
    print("=" * 70)
    print("\n")


if __name__ == "__main__":
    main()
