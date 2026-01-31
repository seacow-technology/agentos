"""Demo: Web Fetch Connector with CommunicationService

This example demonstrates how to use the Web Fetch Connector
through the CommunicationService with security policies and auditing.
"""

import asyncio
from agentos.core.communication.service import CommunicationService
from agentos.core.communication.connectors.web_fetch import WebFetchConnector
from agentos.core.communication.models import ConnectorType


async def demo_basic_fetch():
    """Demo: Basic web fetch operation."""
    print("\n" + "=" * 60)
    print("Demo 1: Basic Web Fetch")
    print("=" * 60)

    # Initialize service and register connector
    service = CommunicationService()
    connector = WebFetchConnector(config={
        "timeout": 30,
        "max_size": 10 * 1024 * 1024,  # 10MB
        "user_agent": "AgentOS/1.0 Demo",
    })
    service.register_connector(ConnectorType.WEB_FETCH, connector)

    # Fetch a URL
    response = await service.execute(
        connector_type=ConnectorType.WEB_FETCH,
        operation="fetch",
        params={
            "url": "https://example.com",
            "extract_content": True,
        },
        context={
            "task_id": "demo-task-001",
            "session_id": "demo-session",
        }
    )

    print(f"Status: {response.status}")
    print(f"Request ID: {response.request_id}")
    print(f"Evidence ID: {response.evidence_id}")

    if response.data:
        print(f"HTTP Status: {response.data['status_code']}")
        print(f"Content Length: {response.data['content_length']} bytes")
        print(f"Content Type: {response.data['content_type']}")

        if response.data.get('extracted'):
            ext = response.data['extracted']
            print(f"\nExtracted Content:")
            print(f"  Title: {ext.get('title', 'N/A')}")
            print(f"  Description: {ext.get('description', 'N/A')}")
            print(f"  Text Preview: {ext.get('text', '')[:200]}...")
            print(f"  Links: {len(ext.get('links', []))}")
            print(f"  Images: {len(ext.get('images', []))}")


async def demo_download_file():
    """Demo: Download file operation."""
    print("\n" + "=" * 60)
    print("Demo 2: File Download")
    print("=" * 60)

    service = CommunicationService()
    connector = WebFetchConnector()
    service.register_connector(ConnectorType.WEB_FETCH, connector)

    # Download a small file
    response = await service.execute(
        connector_type=ConnectorType.WEB_FETCH,
        operation="download",
        params={
            "url": "https://www.google.com/favicon.ico",
        },
        context={"task_id": "demo-download-001"}
    )

    print(f"Status: {response.status}")

    if response.data:
        print(f"Downloaded to: {response.data['destination']}")
        print(f"File size: {response.data['size']} bytes")
        print(f"Content type: {response.data['content_type']}")

        # Clean up temp file
        import os
        if os.path.exists(response.data['destination']):
            os.remove(response.data['destination'])
            print(f"Cleaned up temporary file")


async def demo_error_handling():
    """Demo: Error handling and security policies."""
    print("\n" + "=" * 60)
    print("Demo 3: Error Handling & Security Policies")
    print("=" * 60)

    service = CommunicationService()
    connector = WebFetchConnector()
    service.register_connector(ConnectorType.WEB_FETCH, connector)

    # Test 1: SSRF protection - localhost blocked
    print("\nTest 1: Attempting to access localhost (should be blocked)...")
    response = await service.execute(
        connector_type=ConnectorType.WEB_FETCH,
        operation="fetch",
        params={"url": "http://localhost:8080"},
    )
    print(f"Status: {response.status}")
    print(f"Error: {response.error}")

    # Test 2: Invalid URL
    print("\nTest 2: Invalid URL (should fail)...")
    response = await service.execute(
        connector_type=ConnectorType.WEB_FETCH,
        operation="fetch",
        params={"url": "not-a-valid-url"},
    )
    print(f"Status: {response.status}")
    print(f"Error: {response.error}")

    # Test 3: Unsupported operation
    print("\nTest 3: Unsupported operation (should fail)...")
    response = await service.execute(
        connector_type=ConnectorType.WEB_FETCH,
        operation="unsupported_op",
        params={"url": "https://example.com"},
    )
    print(f"Status: {response.status}")
    print(f"Error: {response.error}")


async def demo_custom_headers():
    """Demo: Fetching with custom headers."""
    print("\n" + "=" * 60)
    print("Demo 4: Custom Headers and Methods")
    print("=" * 60)

    service = CommunicationService()
    connector = WebFetchConnector()
    service.register_connector(ConnectorType.WEB_FETCH, connector)

    # Fetch with custom headers
    response = await service.execute(
        connector_type=ConnectorType.WEB_FETCH,
        operation="fetch",
        params={
            "url": "https://httpbin.org/headers",
            "method": "GET",
            "headers": {
                "X-Custom-Header": "Demo-Value",
                "X-Request-ID": "demo-123",
            },
        },
    )

    print(f"Status: {response.status}")
    if response.data:
        print(f"HTTP Status: {response.data['status_code']}")
        print(f"Content Preview: {response.data['content'][:500]}...")


async def demo_rate_limiting():
    """Demo: Rate limiting enforcement."""
    print("\n" + "=" * 60)
    print("Demo 5: Rate Limiting")
    print("=" * 60)

    service = CommunicationService()
    connector = WebFetchConnector()
    service.register_connector(ConnectorType.WEB_FETCH, connector)

    # Get current policy
    policy = service.policy_engine.get_policy(ConnectorType.WEB_FETCH)
    print(f"Rate limit: {policy.rate_limit_per_minute} requests per minute")
    print(f"Max response size: {policy.max_response_size_mb}MB")
    print(f"Timeout: {policy.timeout_seconds}s")

    # Make multiple requests
    print("\nMaking multiple requests...")
    for i in range(3):
        response = await service.execute(
            connector_type=ConnectorType.WEB_FETCH,
            operation="fetch",
            params={"url": "https://example.com"},
        )
        print(f"Request {i+1}: {response.status}")


async def demo_html_extraction():
    """Demo: Advanced HTML content extraction."""
    print("\n" + "=" * 60)
    print("Demo 6: HTML Content Extraction")
    print("=" * 60)

    service = CommunicationService()
    connector = WebFetchConnector()
    service.register_connector(ConnectorType.WEB_FETCH, connector)

    # Fetch a page with rich content
    urls = [
        "https://example.com",
        "https://www.wikipedia.org",
    ]

    for url in urls:
        print(f"\nFetching: {url}")
        response = await service.execute(
            connector_type=ConnectorType.WEB_FETCH,
            operation="fetch",
            params={
                "url": url,
                "extract_content": True,
            },
        )

        if response.data and response.data.get('extracted'):
            ext = response.data['extracted']
            print(f"  Title: {ext.get('title', 'N/A')[:80]}")
            print(f"  Description: {ext.get('description', 'N/A')[:80]}")
            print(f"  Text length: {len(ext.get('text', ''))} chars")
            print(f"  Links found: {len(ext.get('links', []))}")
            print(f"  Images found: {len(ext.get('images', []))}")
        else:
            print(f"  Status: {response.status}")
            print(f"  Error: {response.error}")


async def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("Web Fetch Connector - Comprehensive Demo")
    print("=" * 60)

    try:
        await demo_basic_fetch()
        await demo_download_file()
        await demo_error_handling()
        await demo_custom_headers()
        await demo_rate_limiting()
        await demo_html_extraction()

        print("\n" + "=" * 60)
        print("All demos completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError during demo: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
