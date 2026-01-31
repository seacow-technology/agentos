"""
Provenance System Demo

演示 AgentOS Provenance（溯源）系统的基本使用。
"""

import asyncio
from datetime import datetime

from agentos.core.capabilities.governance_models.provenance import (
    ProvenanceStamp,
    ExecutionEnv,
    get_current_env,
    TrustTier,
)
from agentos.core.capabilities.capability_models import ToolResult
from agentos.core.capabilities.provenance_validator import ProvenanceValidator
from agentos.core.capabilities.provenance_utils import (
    filter_results_by_trust_tier,
    verify_result_origin,
    compare_results_by_env,
)


def demo_get_current_env():
    """演示：获取当前执行环境"""
    print("=" * 60)
    print("Demo 1: 获取当前执行环境")
    print("=" * 60)

    env = get_current_env()

    print(f"主机名: {env.host}")
    print(f"进程 ID: {env.pid}")
    print(f"容器 ID: {env.container_id or 'N/A'}")
    print(f"Python 版本: {env.python_version}")
    print(f"AgentOS 版本: {env.agentos_version}")
    print(f"平台: {env.platform}")
    print(f"工作目录: {env.cwd}")
    print()


def demo_create_provenance():
    """演示：创建溯源戳"""
    print("=" * 60)
    print("Demo 2: 创建溯源戳")
    print("=" * 60)

    env = get_current_env()

    # 模拟一个来自 MCP 服务器的工具调用
    provenance = ProvenanceStamp(
        capability_id="mcp:filesystem:read_file",
        tool_id="read_file",
        capability_type="mcp",
        source_id="filesystem",
        source_version="1.0.0",
        execution_env=env,
        trust_tier=TrustTier.T1.value,
        timestamp=datetime.now(),
        invocation_id="inv_demo_001",
        task_id="task_demo_001",
        project_id="proj_demo",
    )

    print(f"能力 ID: {provenance.capability_id}")
    print(f"工具名称: {provenance.tool_id}")
    print(f"来源类型: {provenance.capability_type}")
    print(f"来源 ID: {provenance.source_id}")
    print(f"来源版本: {provenance.source_version}")
    print(f"信任层级: {provenance.trust_tier}")
    print(f"调用 ID: {provenance.invocation_id}")
    print(f"时间戳: {provenance.timestamp}")
    print()

    return provenance


def demo_validate_provenance(provenance: ProvenanceStamp):
    """演示：验证溯源信息"""
    print("=" * 60)
    print("Demo 3: 验证溯源信息")
    print("=" * 60)

    validator = ProvenanceValidator()

    # 验证完整性
    valid, error = validator.validate_completeness(provenance)
    print(f"完整性验证: {'✓ 通过' if valid else f'✗ 失败 - {error}'}")

    # 创建一个结果并验证一致性
    result = ToolResult(
        invocation_id=provenance.invocation_id,
        success=True,
        payload={"content": "Hello, World!"},
        declared_side_effects=["fs.read"],
        duration_ms=100,
        provenance=provenance
    )

    valid, error = validator.validate_consistency(provenance, result)
    print(f"一致性验证: {'✓ 通过' if valid else f'✗ 失败 - {error}'}")

    # 验证是否可以回放
    current_env = get_current_env()
    can_replay, reason = validator.can_replay(provenance, current_env)
    print(f"回放验证: {'✓ 可以回放' if can_replay else f'✗ 无法回放 - {reason}'}")
    print()

    return result


def demo_filter_by_trust_tier():
    """演示：按信任层级过滤结果"""
    print("=" * 60)
    print("Demo 4: 按信任层级过滤结果")
    print("=" * 60)

    # 创建不同信任层级的结果
    results = []

    for tier in [TrustTier.T0, TrustTier.T1, TrustTier.T2, TrustTier.T3]:
        provenance = ProvenanceStamp(
            capability_id=f"test:tool:{tier.value}",
            tool_id="test_tool",
            capability_type="extension" if tier == TrustTier.T0 else "mcp",
            source_id=f"source_{tier.value}",
            execution_env=get_current_env(),
            trust_tier=tier.value,
            timestamp=datetime.now(),
            invocation_id=f"inv_{tier.value}"
        )

        result = ToolResult(
            invocation_id=provenance.invocation_id,
            success=True,
            payload={"tier": tier.value},
            declared_side_effects=[],
            duration_ms=100,
            provenance=provenance
        )

        results.append(result)

    print(f"总结果数: {len(results)}")
    print(f"信任层级分布: T0={sum(1 for r in results if r.provenance.trust_tier == TrustTier.T0.value)}, "
          f"T1={sum(1 for r in results if r.provenance.trust_tier == TrustTier.T1.value)}, "
          f"T2={sum(1 for r in results if r.provenance.trust_tier == TrustTier.T2.value)}, "
          f"T3={sum(1 for r in results if r.provenance.trust_tier == TrustTier.T3.value)}")

    # 只保留 T1 及以上信任级别
    high_trust_results = filter_results_by_trust_tier(results, TrustTier.T1)
    print(f"\n过滤后（T1 及以上）: {len(high_trust_results)} 个结果")
    for result in high_trust_results:
        print(f"  - {result.provenance.source_id} (信任层级: {result.provenance.trust_tier})")
    print()


def demo_verify_origin(result: ToolResult):
    """演示：验证结果来源"""
    print("=" * 60)
    print("Demo 5: 验证结果来源")
    print("=" * 60)

    # 正确的来源验证
    is_valid = verify_result_origin(
        result,
        expected_source_id="filesystem",
        expected_trust_tier=TrustTier.T1
    )
    print(f"验证来源 'filesystem' (T1): {'✓ 通过' if is_valid else '✗ 失败'}")

    # 错误的来源验证
    is_valid = verify_result_origin(
        result,
        expected_source_id="other_source",
        expected_trust_tier=TrustTier.T1
    )
    print(f"验证来源 'other_source' (T1): {'✓ 通过' if is_valid else '✗ 失败（预期）'}")

    # 错误的信任层级验证
    is_valid = verify_result_origin(
        result,
        expected_source_id="filesystem",
        expected_trust_tier=TrustTier.T0
    )
    print(f"验证来源 'filesystem' (T0): {'✓ 通过' if is_valid else '✗ 失败（预期）'}")
    print()


def demo_compare_environments():
    """演示：比较不同环境的结果"""
    print("=" * 60)
    print("Demo 6: 比较不同环境的结果")
    print("=" * 60)

    # 当前环境
    env1 = get_current_env()

    # 模拟不同的环境
    env2 = ExecutionEnv(
        host="production-server",
        pid=54321,
        python_version="3.11.0",
        agentos_version="0.3.0",
        platform="Linux-5.15.0-x86_64",
        cwd="/opt/agentos"
    )

    results = []

    # 在环境1的结果
    for i in range(3):
        provenance = ProvenanceStamp(
            capability_id="test:tool",
            tool_id="test_tool",
            capability_type="mcp",
            source_id="test_server",
            execution_env=env1,
            trust_tier=TrustTier.T1.value,
            timestamp=datetime.now(),
            invocation_id=f"inv_env1_{i}"
        )

        result = ToolResult(
            invocation_id=provenance.invocation_id,
            success=True,
            payload={},
            declared_side_effects=[],
            duration_ms=100,
            provenance=provenance
        )

        results.append(result)

    # 在环境2的结果
    for i in range(2):
        provenance = ProvenanceStamp(
            capability_id="test:tool",
            tool_id="test_tool",
            capability_type="mcp",
            source_id="test_server",
            execution_env=env2,
            trust_tier=TrustTier.T1.value,
            timestamp=datetime.now(),
            invocation_id=f"inv_env2_{i}"
        )

        result = ToolResult(
            invocation_id=provenance.invocation_id,
            success=True,
            payload={},
            declared_side_effects=[],
            duration_ms=100,
            provenance=provenance
        )

        results.append(result)

    # 生成环境对比报告
    report = compare_results_by_env(results)

    print(f"总环境数: {report['total_environments']}")
    print("\n各环境结果统计:")
    for env_key, env_results in report['environments'].items():
        host, platform = env_key
        print(f"  - {host} ({platform}): {len(env_results)} 个结果")
    print()


def main():
    """运行所有演示"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "AgentOS Provenance System Demo" + " " * 17 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    # Demo 1: 获取环境
    demo_get_current_env()

    # Demo 2: 创建溯源
    provenance = demo_create_provenance()

    # Demo 3: 验证溯源
    result = demo_validate_provenance(provenance)

    # Demo 4: 按信任层级过滤
    demo_filter_by_trust_tier()

    # Demo 5: 验证来源
    demo_verify_origin(result)

    # Demo 6: 比较环境
    demo_compare_environments()

    print("=" * 60)
    print("所有演示完成！")
    print("=" * 60)
    print()
    print("提示：")
    print("- 查看 docs/governance/PROVENANCE_GUIDE.md 了解更多")
    print("- 运行测试: pytest tests/core/capabilities/test_provenance.py")
    print()


if __name__ == "__main__":
    main()
