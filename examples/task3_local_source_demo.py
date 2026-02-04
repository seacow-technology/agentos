"""
LocalSource Demo Script
=======================

This script demonstrates the usage of the LocalSource implementation.
It shows how to:
1. Create and configure a LocalSource
2. Validate configuration
3. Fetch documents from files and directories
4. Perform health checks
5. Handle various configuration options

Usage:
    python examples/task3_local_source_demo.py
"""

import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentos.core.knowledge.sources.local import LocalSource


def create_sample_documents(base_dir: Path):
    """Create sample documents for demonstration"""
    print(f"Creating sample documents in {base_dir}")

    # Create directory structure
    (base_dir / "docs").mkdir(exist_ok=True)
    (base_dir / "docs" / "guides").mkdir(exist_ok=True)
    (base_dir / "code").mkdir(exist_ok=True)

    # Create markdown files
    (base_dir / "README.md").write_text("""
# Sample Project

This is a sample project for demonstrating LocalSource.

## Features
- Document scanning
- Metadata extraction
- Health monitoring
""")

    (base_dir / "docs" / "architecture.md").write_text("""
# Architecture Documentation

## System Overview
The system consists of multiple components...

## Key Components
1. Source Management
2. Document Processing
3. Health Monitoring
""")

    (base_dir / "docs" / "guides" / "quickstart.md").write_text("""
# Quick Start Guide

## Installation
1. Clone the repository
2. Install dependencies
3. Run the application

## Configuration
Configure your settings in config.yml
""")

    # Create text files
    (base_dir / "notes.txt").write_text("""
Project Notes
=============

- Remember to update documentation
- Run tests before committing
- Check code coverage
""")

    # Create Python files
    (base_dir / "code" / "main.py").write_text("""
#!/usr/bin/env python3
\"\"\"Main application entry point\"\"\"

def main():
    print("Hello, World!")

if __name__ == "__main__":
    main()
""")

    (base_dir / "code" / "config.py").write_text("""
\"\"\"Configuration module\"\"\"

DEFAULT_CONFIG = {
    "app_name": "Sample App",
    "version": "1.0.0"
}
""")

    # Create a hidden file (should be skipped by default)
    (base_dir / ".hidden.txt").write_text("This is a hidden file")

    # Create a large file (for testing size limits)
    (base_dir / "large_file.txt").write_text("x" * 1_000_000)  # 1MB

    print(f"Created {len(list(base_dir.rglob('*')))} files and directories")


def demo_single_file():
    """Demo 1: Fetching a single file"""
    print("\n" + "="*70)
    print("DEMO 1: Fetching a Single File")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        create_sample_documents(tmp_path)

        readme_path = tmp_path / "README.md"

        source = LocalSource(
            source_id="readme-source",
            config={
                "uri": f"file://{readme_path}",
                "options": {}
            }
        )

        # Validate
        print("\n1. Validating configuration...")
        validation = source.validate()
        print(f"   Valid: {validation.valid}")
        if not validation.valid:
            print(f"   Error: {validation.error}")
            return

        # Fetch documents
        print("\n2. Fetching documents...")
        docs = source.fetch()
        print(f"   Fetched {len(docs)} document(s)")

        for doc in docs:
            print(f"\n   Document Metadata:")
            for key, value in doc.metadata.items():
                if key == "file_path":
                    print(f"     {key}: {Path(value).name}")
                else:
                    print(f"     {key}: {value}")
            print(f"\n   Content Preview:")
            print(f"     {doc.content[:100]}...")

        # Health check
        print("\n3. Health check...")
        health = source.health_check()
        print(f"   Healthy: {health.healthy}")
        print(f"   Metrics: {health.metrics}")


def demo_directory_recursive():
    """Demo 2: Fetching from a directory recursively"""
    print("\n" + "="*70)
    print("DEMO 2: Fetching from Directory (Recursive)")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        create_sample_documents(tmp_path)

        source = LocalSource(
            source_id="docs-source",
            config={
                "uri": f"file://{tmp_path}",
                "options": {
                    "recursive": True,
                    "file_types": ["md", "txt", "py"]
                }
            }
        )

        # Validate
        print("\n1. Validating configuration...")
        validation = source.validate()
        print(f"   Valid: {validation.valid}")

        # Fetch documents
        print("\n2. Fetching documents...")
        docs = source.fetch()
        print(f"   Fetched {len(docs)} document(s)")

        # Group by file type
        by_type = {}
        for doc in docs:
            doc_type = doc.metadata["doc_type"]
            by_type.setdefault(doc_type, []).append(doc)

        print("\n   Documents by type:")
        for doc_type, type_docs in sorted(by_type.items()):
            print(f"     {doc_type}: {len(type_docs)} files")
            for doc in type_docs:
                file_name = Path(doc.metadata["file_path"]).name
                size = doc.metadata["size_bytes"]
                print(f"       - {file_name} ({size} bytes)")


def demo_file_type_filter():
    """Demo 3: Filtering by file types"""
    print("\n" + "="*70)
    print("DEMO 3: Filtering by File Types")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        create_sample_documents(tmp_path)

        # Fetch only markdown files
        source = LocalSource(
            source_id="markdown-only",
            config={
                "uri": f"file://{tmp_path}",
                "options": {
                    "recursive": True,
                    "file_types": ["md"]
                }
            }
        )

        print("\n1. Fetching only Markdown files...")
        docs = source.fetch()
        print(f"   Found {len(docs)} Markdown document(s)")
        for doc in docs:
            file_name = Path(doc.metadata["file_path"]).name
            print(f"     - {file_name}")


def demo_size_limit():
    """Demo 4: File size limits"""
    print("\n" + "="*70)
    print("DEMO 4: File Size Limits")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        create_sample_documents(tmp_path)

        # Set a small size limit (0.5 MB)
        source = LocalSource(
            source_id="size-limited",
            config={
                "uri": f"file://{tmp_path}",
                "options": {
                    "recursive": True,
                    "max_file_size_mb": 0.5  # 500 KB
                }
            }
        )

        print("\n1. Fetching with 0.5 MB size limit...")
        docs = source.fetch()
        print(f"   Found {len(docs)} document(s) under size limit")
        for doc in docs:
            file_name = Path(doc.metadata["file_path"]).name
            size_kb = doc.metadata["size_bytes"] / 1024
            print(f"     - {file_name} ({size_kb:.1f} KB)")


def demo_non_recursive():
    """Demo 5: Non-recursive directory scan"""
    print("\n" + "="*70)
    print("DEMO 5: Non-Recursive Directory Scan")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        create_sample_documents(tmp_path)

        source = LocalSource(
            source_id="non-recursive",
            config={
                "uri": f"file://{tmp_path}",
                "options": {
                    "recursive": False
                }
            }
        )

        print("\n1. Fetching from root directory only (non-recursive)...")
        docs = source.fetch()
        print(f"   Found {len(docs)} document(s) in root directory")
        for doc in docs:
            file_name = Path(doc.metadata["file_path"]).name
            print(f"     - {file_name}")


def demo_hidden_files():
    """Demo 6: Hidden files handling"""
    print("\n" + "="*70)
    print("DEMO 6: Hidden Files Handling")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        create_sample_documents(tmp_path)

        # Skip hidden files (default)
        source1 = LocalSource(
            source_id="skip-hidden",
            config={
                "uri": f"file://{tmp_path}",
                "options": {
                    "skip_hidden": True,
                    "recursive": False
                }
            }
        )

        print("\n1. Fetching with skip_hidden=True...")
        docs1 = source1.fetch()
        print(f"   Found {len(docs1)} visible files")

        # Include hidden files
        source2 = LocalSource(
            source_id="include-hidden",
            config={
                "uri": f"file://{tmp_path}",
                "options": {
                    "skip_hidden": False,
                    "recursive": False
                }
            }
        )

        print("\n2. Fetching with skip_hidden=False...")
        docs2 = source2.fetch()
        print(f"   Found {len(docs2)} files (including hidden)")


def demo_health_check():
    """Demo 7: Health check capabilities"""
    print("\n" + "="*70)
    print("DEMO 7: Health Check Capabilities")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        create_sample_documents(tmp_path)

        source = LocalSource(
            source_id="health-demo",
            config={
                "uri": f"file://{tmp_path}",
                "options": {"recursive": True}
            }
        )

        print("\n1. Performing health check...")
        health = source.health_check()

        print(f"   Status: {'HEALTHY' if health.healthy else 'UNHEALTHY'}")
        if health.error:
            print(f"   Error: {health.error}")

        print(f"\n   Metrics:")
        for key, value in sorted(health.metrics.items()):
            print(f"     {key}: {value}")


def demo_error_handling():
    """Demo 8: Error handling"""
    print("\n" + "="*70)
    print("DEMO 8: Error Handling")
    print("="*70)

    # Test 1: Invalid URI scheme
    print("\n1. Testing invalid URI scheme...")
    source1 = LocalSource(
        source_id="invalid-scheme",
        config={
            "uri": "http://example.com/docs",
            "options": {}
        }
    )
    validation1 = source1.validate()
    print(f"   Valid: {validation1.valid}")
    print(f"   Error: {validation1.error}")

    # Test 2: Nonexistent path
    print("\n2. Testing nonexistent path...")
    source2 = LocalSource(
        source_id="nonexistent",
        config={
            "uri": "file:///nonexistent/path/to/docs",
            "options": {}
        }
    )
    validation2 = source2.validate()
    print(f"   Valid: {validation2.valid}")
    print(f"   Error: {validation2.error}")

    # Test 3: Fetch from invalid source
    print("\n3. Attempting to fetch from invalid source...")
    docs = source2.fetch()
    print(f"   Returned: {len(docs)} documents (graceful handling)")

    # Test 4: Health check on invalid source
    print("\n4. Health check on invalid source...")
    health = source2.health_check()
    print(f"   Healthy: {health.healthy}")
    print(f"   Error: {health.error}")


def main():
    """Run all demos"""
    print("\n")
    print("*" * 70)
    print("*" + " " * 68 + "*")
    print("*" + "  LocalSource Implementation Demo".center(68) + "*")
    print("*" + " " * 68 + "*")
    print("*" * 70)

    demos = [
        ("Single File", demo_single_file),
        ("Directory Recursive", demo_directory_recursive),
        ("File Type Filter", demo_file_type_filter),
        ("Size Limit", demo_size_limit),
        ("Non-Recursive", demo_non_recursive),
        ("Hidden Files", demo_hidden_files),
        ("Health Check", demo_health_check),
        ("Error Handling", demo_error_handling),
    ]

    for i, (name, demo_func) in enumerate(demos, 1):
        try:
            demo_func()
        except Exception as e:
            print(f"\n   ERROR in demo: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*70)
    print("All demos completed!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
