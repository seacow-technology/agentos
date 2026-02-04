#!/usr/bin/env python3
"""
Golden Path Demo Example

This example demonstrates how to use the Golden Path demo system
in AgentOS WebUI.

Usage:
    1. Enable demo mode:
       python examples/golden_path_demo.py enable

    2. Start the WebUI server:
       agentos ui

    3. Open browser to http://localhost:8000

    4. Click the demo card on any supported page
"""

import sys
import requests
import json


def enable_demo_mode():
    """Enable demo mode via API."""
    try:
        response = requests.post(
            'http://localhost:8000/api/demo-mode/enable',
            json={'load_seed_modules': None},
            headers={'Content-Type': 'application/json'}
        )
        data = response.json()

        if data.get('ok'):
            print("✅ Demo mode enabled")
            print(f"   Loaded modules: {len(data.get('loaded_modules', []))}")
            return True
        else:
            print(f"❌ Failed to enable demo mode: {data.get('message')}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def disable_demo_mode():
    """Disable demo mode via API."""
    try:
        response = requests.post(
            'http://localhost:8000/api/demo-mode/disable',
            headers={'Content-Type': 'application/json'}
        )
        data = response.json()

        if data.get('ok'):
            print("✅ Demo mode disabled")
            return True
        else:
            print(f"❌ Failed to disable demo mode: {data.get('message')}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def check_status():
    """Check demo mode status."""
    try:
        response = requests.get('http://localhost:8000/api/demo-mode/status')
        data = response.json()

        print("\n📊 Demo Mode Status")
        print("=" * 50)
        print(f"Enabled: {data.get('enabled')}")
        print(f"Demo State Loaded: {data.get('demo_state_loaded')}")
        print(f"Seed Modules: {len(data.get('seed_modules', []))}")

        if data.get('seed_modules'):
            print("\nLoaded Modules:")
            for module in data['seed_modules']:
                print(f"  - {module}")

        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def list_golden_paths():
    """List all available golden paths."""
    try:
        response = requests.get('http://localhost:8000/static/golden_paths/index.json')
        data = response.json()

        print("\n📋 Available Golden Paths")
        print("=" * 50)
        print(f"Total: {data.get('count', 0)}\n")

        for path in data.get('golden_paths', []):
            print(f"📄 {path['page']}")
            print(f"   Title: {path['title']}")
            print(f"   Description: {path['description']}")
            print(f"   Time: {path['estimated_time']}")
            print()

        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_golden_path(page_id):
    """Test loading a specific golden path."""
    try:
        response = requests.get(f'http://localhost:8000/static/golden_paths/{page_id}.json')
        data = response.json()

        print(f"\n🎯 Golden Path: {page_id}")
        print("=" * 50)
        print(f"Title: {data.get('title')}")
        print(f"Description: {data.get('description')}")
        print(f"Estimated Time: {data.get('estimated_time')}")
        print(f"\nSteps: {len(data.get('steps', []))}")

        for i, step in enumerate(data.get('steps', []), 1):
            print(f"\n  Step {i}: {step.get('action')}")
            print(f"    Selector: {step.get('selector')}")
            print(f"    Expected: {step.get('expected')}")
            print(f"    Duration: {step.get('duration')}ms")

        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python golden_path_demo.py [enable|disable|status|list|test PAGE_ID]")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == 'enable':
        enable_demo_mode()
    elif command == 'disable':
        disable_demo_mode()
    elif command == 'status':
        check_status()
    elif command == 'list':
        list_golden_paths()
    elif command == 'test':
        if len(sys.argv) < 3:
            print("Usage: python golden_path_demo.py test PAGE_ID")
            sys.exit(1)
        test_golden_path(sys.argv[2])
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == '__main__':
    main()
