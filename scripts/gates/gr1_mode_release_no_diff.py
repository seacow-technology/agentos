#!/usr/bin/env python3
"""
Gate GR1: Release Mode No Diff（最小可签版本）

测试：release mode 不能 apply diff
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.core.mode import get_mode


def main():
    print("=" * 60)
    print("Gate GR1: Release Mode No Diff")
    print("=" * 60)
    
    # 测试 1: release mode 存在
    print("\n[Test 1] release mode 存在")
    try:
        release_mode = get_mode("release")
        print("✅ PASS: release mode 已注册")
    except ValueError:
        print("❌ FAIL: release mode 未注册")
        return 1
    
    # 测试 2: release mode 不允许 commit
    print("\n[Test 2] release mode 不允许 commit")
    release_mode = get_mode("release")
    if not release_mode.allows_commit():
        print("✅ PASS: release.allows_commit() == False")
    else:
        print("❌ FAIL: release should not allow commit")
        return 1
    
    # 测试 3: release mode 不允许 diff
    print("\n[Test 3] release mode 不允许 diff")
    release_mode = get_mode("release")
    if not release_mode.allows_diff():
        print("✅ PASS: release.allows_diff() == False")
    else:
        print("❌ FAIL: release should not allow diff")
        return 1
    
    # 测试 4: release mode 的 required_output_kind 不是 "diff"
    print("\n[Test 4] release mode 禁止产生 diff")
    release_mode = get_mode("release")
    required = release_mode.get_required_output_kind()
    if required != "diff":
        print(f"✅ PASS: release.get_required_output_kind() != 'diff' (actual: '{required}')")
    else:
        print(f"❌ FAIL: release should not require diff output")
        return 1
    
    print("\n" + "=" * 60)
    print("✅ Gate GR1 PASSED")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
