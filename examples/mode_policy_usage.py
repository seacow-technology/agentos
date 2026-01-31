#!/usr/bin/env python3
"""
Mode Policy Engine 使用示例

演示 mode_policy.py 的各种使用场景
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentos.core.mode.mode_policy import (
    ModePolicy,
    ModePermissions,
    get_global_policy,
    check_mode_permission,
    get_mode_permissions,
)


def example_1_basic_usage():
    """示例 1: 基本使用"""
    print("=" * 60)
    print("示例 1: 基本使用")
    print("=" * 60)

    # 创建策略实例
    policy = ModePolicy()

    # 检查各个 mode 的权限
    modes = ["implementation", "design", "chat", "planning"]

    for mode in modes:
        can_commit = policy.check_permission(mode, "commit")
        can_diff = policy.check_permission(mode, "diff")
        print(f"{mode:15} -> commit: {can_commit:5}, diff: {can_diff:5}")

    print()


def example_2_get_permissions():
    """示例 2: 获取完整权限配置"""
    print("=" * 60)
    print("示例 2: 获取完整权限配置")
    print("=" * 60)

    policy = ModePolicy()

    # 获取 implementation mode 的权限
    perms = policy.get_permissions("implementation")

    print(f"Mode ID: {perms.mode_id}")
    print(f"Allows Commit: {perms.allows_commit}")
    print(f"Allows Diff: {perms.allows_diff}")
    print(f"Allowed Operations: {perms.allowed_operations}")
    print(f"Risk Level: {perms.risk_level}")

    print()


def example_3_unknown_mode_safety():
    """示例 3: 未知 mode 的安全默认值"""
    print("=" * 60)
    print("示例 3: 未知 mode 的安全默认值")
    print("=" * 60)

    policy = ModePolicy()

    # 查询一个不存在的 mode
    perms = policy.get_permissions("unknown_custom_mode")

    print(f"Unknown mode: {perms.mode_id}")
    print(f"Allows Commit: {perms.allows_commit} (安全默认: False)")
    print(f"Allows Diff: {perms.allows_diff} (安全默认: False)")
    print(f"Risk Level: {perms.risk_level} (安全默认: low)")

    print()


def example_4_global_policy():
    """示例 4: 使用全局策略"""
    print("=" * 60)
    print("示例 4: 使用全局策略")
    print("=" * 60)

    # 获取全局策略（自动初始化）
    policy = get_global_policy()

    print(f"Global policy version: {policy.get_policy_version()}")
    print(f"All modes: {sorted(policy.get_all_modes())}")

    # 使用便捷函数检查权限
    print(f"\nUsing convenience function:")
    print(f"  check_mode_permission('implementation', 'commit'): "
          f"{check_mode_permission('implementation', 'commit')}")

    print()


def example_5_risk_levels():
    """示例 5: 风险等级分析"""
    print("=" * 60)
    print("示例 5: 风险等级分析")
    print("=" * 60)

    policy = ModePolicy()

    # 按风险等级分类 modes
    risk_groups = {"high": [], "medium": [], "low": []}

    for mode_id in policy.get_all_modes():
        perms = policy.get_permissions(mode_id)
        risk_groups[perms.risk_level].append(mode_id)

    for risk_level in ["high", "medium", "low"]:
        modes = risk_groups[risk_level]
        print(f"{risk_level.upper()} risk modes: {', '.join(sorted(modes))}")

    print()


def example_6_permission_matrix():
    """示例 6: 权限矩阵"""
    print("=" * 60)
    print("示例 6: 权限矩阵")
    print("=" * 60)

    policy = ModePolicy()

    # 打印权限矩阵
    print(f"{'Mode':<15} {'Commit':<8} {'Diff':<8} {'Risk':<10}")
    print("-" * 50)

    for mode_id in sorted(policy.get_all_modes()):
        perms = policy.get_permissions(mode_id)
        commit = "✓" if perms.allows_commit else "✗"
        diff = "✓" if perms.allows_diff else "✗"
        print(f"{mode_id:<15} {commit:<8} {diff:<8} {perms.risk_level:<10}")

    print()


def example_7_create_custom_permissions():
    """示例 7: 创建自定义权限"""
    print("=" * 60)
    print("示例 7: 创建自定义权限")
    print("=" * 60)

    # 手动创建一个权限配置
    custom_perms = ModePermissions(
        mode_id="custom_mode",
        allows_commit=False,
        allows_diff=False,
        allowed_operations={"read", "analyze"},
        risk_level="medium"
    )

    print(f"Custom Mode: {custom_perms.mode_id}")
    print(f"  Commit: {custom_perms.allows_commit}")
    print(f"  Diff: {custom_perms.allows_diff}")
    print(f"  Operations: {custom_perms.allowed_operations}")
    print(f"  Risk: {custom_perms.risk_level}")

    print()


def example_8_validation_workflow():
    """示例 8: 权限验证工作流"""
    print("=" * 60)
    print("示例 8: 权限验证工作流")
    print("=" * 60)

    def execute_operation(mode_id: str, operation: str):
        """模拟执行操作前的权限检查"""
        if check_mode_permission(mode_id, operation):
            print(f"✓ {mode_id} 允许执行 {operation} 操作")
            return True
        else:
            print(f"✗ {mode_id} 禁止执行 {operation} 操作")
            return False

    # 测试各种操作
    execute_operation("implementation", "commit")
    execute_operation("implementation", "diff")
    execute_operation("design", "commit")
    execute_operation("design", "read")
    execute_operation("unknown_mode", "commit")

    print()


def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("MODE POLICY ENGINE 使用示例")
    print("=" * 60)
    print()

    try:
        example_1_basic_usage()
        example_2_get_permissions()
        example_3_unknown_mode_safety()
        example_4_global_policy()
        example_5_risk_levels()
        example_6_permission_matrix()
        example_7_create_custom_permissions()
        example_8_validation_workflow()

        print("=" * 60)
        print("所有示例执行完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
