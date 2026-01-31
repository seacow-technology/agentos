"""Example: Using CommunicationAdapter in Chat Commands

This example demonstrates how to integrate CommunicationAdapter
into Chat slash commands for web search and fetch operations.
"""

import asyncio
from agentos.core.chat.communication_adapter import CommunicationAdapter


async def example_search_command():
    """Example: /comm search command implementation."""
    print("=" * 80)
    print("Example: /comm search command")
    print("=" * 80)
    print()

    # Initialize adapter (typically done once per session)
    adapter = CommunicationAdapter()

    # User command: /comm search "Python best practices"
    query = "Python best practices"
    session_id = "demo-session-001"
    task_id = "demo-task-001"

    print(f"User: /comm search \"{query}\"")
    print()

    # Execute search
    result = await adapter.search(
        query=query,
        session_id=session_id,
        task_id=task_id,
        max_results=5
    )

    # Display results
    if "results" in result:
        print(f"Found {result['metadata']['total_results']} results:")
        print()
        for i, item in enumerate(result["results"], 1):
            print(f"{i}. {item['title']}")
            print(f"   🔗 {item['url']}")
            print(f"   📝 {item['snippet'][:100]}...")
            print(f"   🏷️  Trust: {item['trust_tier']}")
            print()

        # Show metadata (for transparency)
        print("---")
        print(f"ℹ️  {result['metadata']['trust_tier_warning']}")
        print(f"📊 {result['metadata']['attribution']}")
        print(f"🔍 Audit ID: {result['metadata']['audit_id']}")
    else:
        print(f"❌ Error: {result.get('message', 'Unknown error')}")

    print()


async def example_fetch_command():
    """Example: /comm fetch command implementation."""
    print("=" * 80)
    print("Example: /comm fetch command")
    print("=" * 80)
    print()

    # Initialize adapter
    adapter = CommunicationAdapter()

    # User command: /comm fetch https://www.python.org
    url = "https://www.python.org"
    session_id = "demo-session-001"
    task_id = "demo-task-002"

    print(f"User: /comm fetch {url}")
    print()

    # Execute fetch
    result = await adapter.fetch(
        url=url,
        session_id=session_id,
        task_id=task_id
    )

    # Display results
    if result.get("status") == "success":
        content = result["content"]
        metadata = result["metadata"]

        print(f"📄 Title: {content['title']}")
        print(f"🔗 URL: {result['url']}")
        print(f"📏 Content: {len(content['text'])} characters")
        print(f"🔗 Links: {len(content['links'])} found")
        print(f"🖼️  Images: {len(content['images'])} found")
        print()

        # Show extracted text preview
        print("Content Preview:")
        print("-" * 80)
        print(content['text'][:300] + "...")
        print("-" * 80)
        print()

        # Show trust tier and citations
        print(f"🏷️  Trust Tier: {metadata['trust_tier']}")
        print()
        print("Citations:")
        citations = metadata['citations']
        print(f"  • URL: {citations['url']}")
        print(f"  • Title: {citations['title']}")
        print(f"  • Author: {citations['author']}")
        print(f"  • Retrieved: {citations['retrieved_at']}")
        print()

        # Show audit info
        print(f"📊 {metadata['attribution']}")
        print(f"🔍 Audit ID: {metadata['audit_id']}")
        print(f"🔐 Content Hash: {metadata['content_hash'][:16]}...")
    else:
        print(f"❌ Error: {result.get('message', 'Unknown error')}")
        if result.get('status') == 'blocked':
            print(f"💡 Hint: {result.get('hint', '')}")

    print()


async def example_ssrf_protection():
    """Example: SSRF protection demonstration."""
    print("=" * 80)
    print("Example: SSRF Protection")
    print("=" * 80)
    print()

    adapter = CommunicationAdapter()

    # Try to access localhost (should be blocked)
    print("User: /comm fetch http://localhost:8080/admin")
    print()

    result = await adapter.fetch(
        url="http://localhost:8080/admin",
        session_id="demo-session-001",
        task_id="demo-task-003"
    )

    # Display blocked result
    print(f"🚫 Status: {result.get('status', 'unknown')}")
    print(f"⚠️  Reason: {result.get('reason', 'N/A')}")
    print(f"💬 Message: {result.get('message', 'N/A')}")
    print(f"💡 Hint: {result.get('hint', 'N/A')}")
    print()

    # Show that attribution is still present
    print(f"📊 {result['metadata']['attribution']}")
    print()


async def example_error_handling():
    """Example: Error handling demonstration."""
    print("=" * 80)
    print("Example: Error Handling")
    print("=" * 80)
    print()

    adapter = CommunicationAdapter()

    # Try invalid URL
    print("User: /comm fetch invalid-url")
    print()

    result = await adapter.fetch(
        url="invalid-url",
        session_id="demo-session-001",
        task_id="demo-task-004"
    )

    print(f"❌ Status: {result.get('status', 'error')}")
    print(f"💬 Message: {result.get('message', 'Unknown error')}")
    print()

    # Show attribution even in errors
    print(f"📊 {result['metadata']['attribution']}")
    print()


async def example_statistics():
    """Example: View statistics."""
    print("=" * 80)
    print("Example: Communication Statistics")
    print("=" * 80)
    print()

    adapter = CommunicationAdapter()

    # Get statistics
    stats = await adapter.get_statistics()

    print("Communication Statistics:")
    print(f"  📊 Total requests: {stats.get('total_requests', 0)}")
    print(f"  ✅ Success rate: {stats.get('success_rate', 0):.2f}%")
    print()

    by_connector = stats.get('by_connector', {})
    if by_connector:
        print("  By Connector:")
        for connector, count in by_connector.items():
            print(f"    • {connector}: {count} requests")
    print()

    # List connectors
    connectors = await adapter.list_connectors()
    print("Available Connectors:")
    for connector_type, info in connectors.items():
        status = "✅ Enabled" if info['enabled'] else "❌ Disabled"
        print(f"  • {connector_type}: {status}")
        print(f"    Operations: {', '.join(info['operations'])}")
        print(f"    Rate limit: {info['rate_limit']}/min")
    print()


async def main():
    """Run all examples."""
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "CommunicationAdapter Examples" + " " * 29 + "║")
    print("╚" + "═" * 78 + "╝")
    print()

    # Run examples
    await example_search_command()
    await example_fetch_command()
    await example_ssrf_protection()
    await example_error_handling()
    await example_statistics()

    print("=" * 80)
    print("All examples completed!")
    print("=" * 80)
    print()


if __name__ == "__main__":
    asyncio.run(main())
