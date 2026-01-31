#!/usr/bin/env python3
"""TL Gate B - Adapters存在性检查"""
import sys
from pathlib import Path

EXIT_CODE, PROJECT_ROOT = 0, Path(__file__).parent.parent.parent

def main():
    global EXIT_CODE
    print("=" * 60 + "\nTL Gate B - Adapters Existence\n" + "=" * 60 + "\n")
    
    files = [
        "agentos/ext/tools/__init__.py",
        "agentos/ext/tools/base_adapter.py",
        "agentos/ext/tools/claude_cli_adapter.py",
        "agentos/ext/tools/opencode_adapter.py",
        "agentos/cli/tools.py",
    ]
    
    for f in files:
        if (PROJECT_ROOT / f).exists():
            print(f"✓ {f}")
        else:
            print(f"✗ {f} - NOT FOUND")
            EXIT_CODE = 1
    
    print("\n" + "=" * 60)
    print("✅ TL Gate B: PASSED" if EXIT_CODE == 0 else "❌ TL Gate B: FAILED")
    print("=" * 60)
    return EXIT_CODE

if __name__ == "__main__":
    sys.exit(main())
