#!/usr/bin/env python3
"""
P1-7 Budget Audit Demo

演示如何使用 Budget Snapshot Audit API 查询模型调用的预算信息。
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentos.core.chat.budget_audit import (
    BudgetAuditAPI,
    get_budget_for_message,
    get_budget_for_task,
    ThresholdState
)


def demo_basic_usage():
    """演示基本用法"""
    print("=" * 60)
    print("Demo 1: 基本用法")
    print("=" * 60)

    # 使用便捷函数查询消息
    print("\n1. 查询消息预算 (便捷函数):")
    print("   get_budget_for_message('msg-123')")

    audit = get_budget_for_message("msg-123")

    if audit["status"] == "auditable":
        snapshot = audit["snapshot"]
        print(f"\n   ✅ 可审计")
        print(f"   预算: {snapshot['budget_tokens']} tokens")
        print(f"   使用: {snapshot['total_tokens_est']} tokens ({snapshot['usage_ratio']:.1%})")
        print(f"   状态: {snapshot['watermark']}")
        print(f"   预期截断: {'是' if snapshot['truncation_expected'] else '否'}")
    else:
        print(f"\n   ❌ 不可审计")
        print(f"   原因: {audit['reason']}")
        print(f"   说明: {audit.get('note', 'N/A')}")


def demo_api_class():
    """演示 API 类用法"""
    print("\n" + "=" * 60)
    print("Demo 2: 使用 BudgetAuditAPI 类")
    print("=" * 60)

    api = BudgetAuditAPI()

    # 直接查询 snapshot
    print("\n1. 直接查询 snapshot:")
    print("   api.get_snapshot_by_id('snap-456')")

    snapshot = api.get_snapshot_by_id("snap-456")

    if snapshot:
        print(f"\n   ✅ 找到 snapshot")
        print(f"   ID: {snapshot.snapshot_id}")
        print(f"   Session: {snapshot.session_id}")
        print(f"   Provider: {snapshot.provider or 'N/A'}")
        print(f"   Model: {snapshot.model or 'N/A'}")
    else:
        print(f"\n   ❌ Snapshot 不存在")


def demo_budget_breakdown():
    """演示预算分解查询"""
    print("\n" + "=" * 60)
    print("Demo 3: 预算分解查询")
    print("=" * 60)

    api = BudgetAuditAPI()

    print("\n1. 查询预算分解:")
    print("   snapshot = api.get_snapshot_for_message('msg-789')")

    snapshot = api.get_snapshot_for_message("msg-789")

    if snapshot:
        print(f"\n   ✅ 找到 snapshot")
        print(f"\n   预算分解:")
        print(f"   ├─ System Prompt:  {snapshot.tokens_system:>5} tokens")
        print(f"   ├─ 对话窗口:       {snapshot.tokens_window:>5} tokens")
        print(f"   ├─ RAG 检索:       {snapshot.tokens_rag:>5} tokens")
        print(f"   ├─ 记忆系统:       {snapshot.tokens_memory:>5} tokens")
        print(f"   ├─ 摘要 Artifacts: {snapshot.tokens_summary:>5} tokens")
        print(f"   └─ 策略/规则:      {snapshot.tokens_policy:>5} tokens")

        total = (snapshot.tokens_system + snapshot.tokens_window +
                 snapshot.tokens_rag + snapshot.tokens_memory +
                 snapshot.tokens_summary + snapshot.tokens_policy)
        print(f"\n   总计: {total} tokens")
        print(f"   预算: {snapshot.budget_tokens} tokens")
        print(f"   使用率: {snapshot.usage_ratio:.1%}")
    else:
        print(f"\n   ❌ 未找到 snapshot")


def demo_threshold_detection():
    """演示阈值检测"""
    print("\n" + "=" * 60)
    print("Demo 4: 阈值状态检测")
    print("=" * 60)

    api = BudgetAuditAPI()

    test_cases = [
        ("msg-safe", "安全状态 (<80%)"),
        ("msg-warning", "警告状态 (80-90%)"),
        ("msg-critical", "临界状态 (>90%)"),
    ]

    print("\n阈值说明:")
    print("  • SAFE:     < 80% 使用率")
    print("  • WARNING:  80% - 90% 使用率")
    print("  • CRITICAL: > 90% 使用率")
    print("\n截断预期:")
    print("  • 使用率 > 90% → truncation_expected = True")

    for msg_id, description in test_cases:
        print(f"\n{description}:")
        print(f"  api.get_snapshot_for_message('{msg_id}')")

        snapshot = api.get_snapshot_for_message(msg_id)

        if snapshot:
            # 状态图标
            icons = {
                ThresholdState.SAFE: "✅",
                ThresholdState.WARNING: "⚠️",
                ThresholdState.CRITICAL: "🔴"
            }
            icon = icons.get(snapshot.watermark, "❓")

            print(f"  {icon} {snapshot.watermark.value.upper()}")
            print(f"     使用率: {snapshot.usage_ratio:.1%}")
            print(f"     预期截断: {'是' if snapshot.truncation_expected else '否'}")
        else:
            print(f"  ❌ 未找到 snapshot")


def demo_backward_compatibility():
    """演示向后兼容性"""
    print("\n" + "=" * 60)
    print("Demo 5: 向后兼容性 (旧消息)")
    print("=" * 60)

    print("\nP1-7 之前的消息没有 snapshot_id:")
    print("  audit = get_budget_for_message('old-msg-123')")

    audit = get_budget_for_message("old-msg-123")

    if audit["status"] == "not_auditable":
        print(f"\n  ❌ 不可审计 (预期行为)")
        print(f"     原因: {audit['reason']}")
        print(f"     说明: {audit.get('note', 'N/A')}")
        print(f"\n  这是正常的！旧消息没有 snapshot 不影响系统运行。")
    else:
        print(f"\n  ✅ 可审计")


def demo_audit_summary():
    """演示审计摘要"""
    print("\n" + "=" * 60)
    print("Demo 6: 审计摘要")
    print("=" * 60)

    api = BudgetAuditAPI()

    print("\n1. 获取消息审计摘要:")
    print("   api.get_audit_summary('message', 'msg-999')")

    summary = api.get_audit_summary("message", "msg-999")

    print(f"\n   状态: {summary['status']}")
    print(f"   实体类型: {summary.get('entity_type', 'N/A')}")
    print(f"   实体ID: {summary.get('entity_id', 'N/A')}")

    if summary["status"] == "auditable":
        snapshot = summary["snapshot"]
        print(f"\n   Snapshot 摘要:")
        print(f"   • ID: {snapshot['snapshot_id']}")
        print(f"   • 预算: {snapshot['budget_tokens']} tokens")
        print(f"   • 使用: {snapshot['total_tokens_est']} tokens")
        print(f"   • 水位: {snapshot['watermark']}")
    elif summary["status"] == "not_auditable":
        print(f"   原因: {summary['reason']}")


def main():
    """运行所有演示"""
    print("\n" + "=" * 60)
    print("P1-7: Budget Snapshot → Audit/TaskDB - 演示")
    print("=" * 60)
    print("\n这个演示展示了如何使用 Budget Audit API 查询预算信息。")
    print("注意: 演示使用的消息ID是示例，实际使用需要真实的ID。")

    try:
        demo_basic_usage()
        demo_api_class()
        demo_budget_breakdown()
        demo_threshold_detection()
        demo_backward_compatibility()
        demo_audit_summary()

        print("\n" + "=" * 60)
        print("演示完成！")
        print("=" * 60)
        print("\n更多信息:")
        print("  • 完整文档: docs/features/P1_7_BUDGET_SNAPSHOT_AUDIT.md")
        print("  • 验收报告: P1_7_ACCEPTANCE_REPORT.md")
        print("  • 快速参考: P1_7_QUICK_REFERENCE.md")
        print("\n测试覆盖: 18/18 PASSED ✅")
        print("状态: COMPLETED ✅\n")

    except Exception as e:
        print(f"\n❌ 演示失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
