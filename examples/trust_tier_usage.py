"""
Trust Tier Usage Examples

演示如何使用 Trust Tier 系统进行能力治理。
"""

from datetime import datetime

from agentos.core.capabilities.capability_models import (
    TrustTier,
    RiskLevel,
    ToolDescriptor,
    ToolInvocation,
    ExecutionMode,
    ToolSource,
)
from agentos.core.capabilities.trust_tier_defaults import (
    get_default_risk_level,
    get_default_quota,
    should_require_admin_token,
    get_side_effects_policy,
)
from agentos.core.capabilities.policy import ToolPolicyEngine
from agentos.core.mcp.adapter import MCPAdapter
from agentos.core.mcp.config import MCPServerConfig


def example_1_query_trust_tier_defaults():
    """示例 1: 查询信任层级的默认策略"""
    print("=" * 60)
    print("示例 1: 查询信任层级的默认策略")
    print("=" * 60)

    for tier in [TrustTier.T0, TrustTier.T1, TrustTier.T2, TrustTier.T3]:
        print(f"\n{tier.value}:")
        print(f"  默认风险级别: {get_default_risk_level(tier).value}")

        quota = get_default_quota(tier)
        print(f"  默认配额:")
        print(f"    - calls_per_minute: {quota['calls_per_minute']}")
        print(f"    - max_concurrent: {quota['max_concurrent']}")
        print(f"    - max_runtime_ms: {quota['max_runtime_ms']}")

        se_policy = get_side_effects_policy(tier)
        print(f"  副作用策略:")
        print(f"    - allow_side_effects: {se_policy['allow_side_effects']}")
        print(f"    - blacklisted_effects: {se_policy['blacklisted_effects']}")

        print(f"  Admin Token 需求:")
        print(f"    - 无副作用: {should_require_admin_token(tier, has_side_effects=False)}")
        print(f"    - 有副作用: {should_require_admin_token(tier, has_side_effects=True)}")


def example_2_mcp_trust_tier_inference():
    """示例 2: MCP 工具的信任层级推断"""
    print("\n" + "=" * 60)
    print("示例 2: MCP 工具的信任层级推断")
    print("=" * 60)

    adapter = MCPAdapter()

    # Local stdio MCP → T1
    local_config = MCPServerConfig(
        id="filesystem",
        transport="stdio",
        command=["node", "mcp-server-filesystem.js"]
    )
    print(f"\n本地 stdio MCP:")
    print(f"  配置: {local_config.transport} - {local_config.command[0]}")
    print(f"  推断的信任层级: {adapter._infer_trust_tier(local_config).value}")

    # Remote tcp MCP → T2
    remote_config = MCPServerConfig(
        id="remote_db",
        transport="tcp",
        command=["tcp://192.168.1.100:5432"]
    )
    print(f"\n远程 tcp MCP:")
    print(f"  配置: {remote_config.transport} - {remote_config.command[0]}")
    print(f"  推断的信任层级: {adapter._infer_trust_tier(remote_config).value}")

    # Cloud https MCP → T3
    cloud_config = MCPServerConfig(
        id="cloud_api",
        transport="https",
        command=["https://api.example.com"]
    )
    print(f"\n云端 https MCP:")
    print(f"  配置: {cloud_config.transport} - {cloud_config.command[0]}")
    print(f"  推断的信任层级: {adapter._infer_trust_tier(cloud_config).value}")


def example_3_extension_vs_mcp():
    """示例 3: Extension (T0) vs MCP (T1/T2/T3) 策略差异"""
    print("\n" + "=" * 60)
    print("示例 3: Extension (T0) vs MCP (T1/T2/T3) 策略差异")
    print("=" * 60)

    # Extension 工具 (T0)
    extension_tool = ToolDescriptor(
        tool_id="ext:tools.postman:get",
        name="postman_get",
        description="Send HTTP GET request",
        input_schema={},
        risk_level=RiskLevel.MED,
        side_effect_tags=["network.http"],
        trust_tier=TrustTier.T0,
        source_type=ToolSource.EXTENSION,
        source_id="tools.postman"
    )

    # Cloud MCP 工具 (T3)
    cloud_mcp_tool = ToolDescriptor(
        tool_id="mcp:cloud_api:get",
        name="cloud_get",
        description="Call cloud API",
        input_schema={},
        risk_level=RiskLevel.HIGH,
        side_effect_tags=["network.http"],
        trust_tier=TrustTier.T3,
        source_type=ToolSource.MCP,
        source_id="cloud_api"
    )

    print(f"\nExtension 工具 (T0):")
    print(f"  tool_id: {extension_tool.tool_id}")
    print(f"  trust_tier: {extension_tool.trust_tier.value}")
    print(f"  需要 admin token: {should_require_admin_token(extension_tool.trust_tier, has_side_effects=True)}")

    print(f"\nCloud MCP 工具 (T3):")
    print(f"  tool_id: {cloud_mcp_tool.tool_id}")
    print(f"  trust_tier: {cloud_mcp_tool.trust_tier.value}")
    print(f"  需要 admin token: {should_require_admin_token(cloud_mcp_tool.trust_tier, has_side_effects=True)}")


def example_4_policy_engine_integration():
    """示例 4: PolicyEngine 集成 Trust Tier"""
    print("\n" + "=" * 60)
    print("示例 4: PolicyEngine 集成 Trust Tier")
    print("=" * 60)

    policy = ToolPolicyEngine()

    # T3 工具带副作用 → 应该被拒绝
    t3_tool = ToolDescriptor(
        tool_id="mcp:cloud_api:write",
        name="cloud_write",
        description="Write to cloud storage",
        input_schema={},
        risk_level=RiskLevel.HIGH,
        side_effect_tags=["cloud.resource_create"],
        trust_tier=TrustTier.T3,
        source_type=ToolSource.MCP,
        source_id="cloud_api"
    )

    invocation = ToolInvocation(
        invocation_id="test-001",
        tool_id=t3_tool.tool_id,
        mode=ExecutionMode.EXECUTION,
        spec_frozen=True,
        spec_hash="abc123",
        project_id="proj-001",
        inputs={},
        actor="user@example.com",
        timestamp=datetime.now()
    )

    print(f"\n检查 T3 工具 (带副作用):")
    print(f"  tool_id: {t3_tool.tool_id}")
    print(f"  trust_tier: {t3_tool.trust_tier.value}")
    print(f"  side_effects: {t3_tool.side_effect_tags}")

    # 检查 policy gate
    allowed, reason = policy._check_policy_gate(t3_tool, invocation)
    print(f"\n  Policy Gate:")
    print(f"    允许: {allowed}")
    print(f"    原因: {reason if not allowed else 'N/A'}")

    # 检查 admin token gate
    allowed, reason = policy._check_admin_token_gate(t3_tool, admin_token=None)
    print(f"\n  Admin Token Gate (无 token):")
    print(f"    允许: {allowed}")
    print(f"    原因: {reason if not allowed else 'N/A'}")

    # 提供 admin token
    allowed, reason = policy._check_admin_token_gate(t3_tool, admin_token="valid-token")
    print(f"\n  Admin Token Gate (有 token):")
    print(f"    允许: {allowed}")
    print(f"    原因: {reason if not allowed else 'N/A'}")


def example_5_override_trust_tier_defaults():
    """示例 5: Override Trust Tier 默认值"""
    print("\n" + "=" * 60)
    print("示例 5: Override Trust Tier 默认值")
    print("=" * 60)

    # T3 工具，但 override 为不需要 admin token
    public_api_tool = ToolDescriptor(
        tool_id="mcp:public_api:get",
        name="get_public_data",
        description="Get public data from API",
        input_schema={},
        risk_level=RiskLevel.LOW,  # Override: 降低风险级别
        side_effect_tags=[],  # 无副作用
        requires_admin_token=False,  # Override: 不需要 admin token
        trust_tier=TrustTier.T3,  # 仍然是 T3
        source_type=ToolSource.MCP,
        source_id="public_api"
    )

    print(f"\nPublic API 工具 (T3 但 override):")
    print(f"  tool_id: {public_api_tool.tool_id}")
    print(f"  trust_tier: {public_api_tool.trust_tier.value}")
    print(f"  risk_level: {public_api_tool.risk_level.value} (override 为 LOW)")
    print(f"  requires_admin_token: {public_api_tool.requires_admin_token} (override 为 False)")
    print(f"  side_effect_tags: {public_api_tool.side_effect_tags}")

    policy = ToolPolicyEngine()
    invocation = ToolInvocation(
        invocation_id="test-002",
        tool_id=public_api_tool.tool_id,
        mode=ExecutionMode.EXECUTION,
        spec_frozen=True,
        spec_hash="def456",
        project_id="proj-001",
        inputs={},
        actor="user@example.com",
        timestamp=datetime.now()
    )

    allowed, reason, decision = policy.check_allowed(
        tool=public_api_tool,
        invocation=invocation,
        admin_token=None
    )

    print(f"\n策略检查结果:")
    print(f"  允许: {allowed}")
    print(f"  原因: {reason if not allowed else '所有 gates 通过'}")


def example_6_trust_tier_blacklist():
    """示例 6: Trust Tier 黑名单"""
    print("\n" + "=" * 60)
    print("示例 6: Trust Tier 黑名单")
    print("=" * 60)

    # T2 工具带 payments 副作用 → 应该被黑名单拒绝
    payment_tool = ToolDescriptor(
        tool_id="mcp:payment_gateway:charge",
        name="charge_payment",
        description="Charge customer payment",
        input_schema={},
        risk_level=RiskLevel.CRITICAL,
        side_effect_tags=["payments"],
        trust_tier=TrustTier.T2,
        source_type=ToolSource.MCP,
        source_id="payment_gateway"
    )

    print(f"\nPayment 工具 (T2):")
    print(f"  tool_id: {payment_tool.tool_id}")
    print(f"  trust_tier: {payment_tool.trust_tier.value}")
    print(f"  side_effects: {payment_tool.side_effect_tags}")

    se_policy = get_side_effects_policy(TrustTier.T2)
    print(f"\nT2 副作用策略:")
    print(f"  blacklisted_effects: {se_policy['blacklisted_effects']}")

    is_blacklisted = "payments" in se_policy["blacklisted_effects"]
    print(f"\n  'payments' 在黑名单中: {is_blacklisted}")

    policy = ToolPolicyEngine()
    invocation = ToolInvocation(
        invocation_id="test-003",
        tool_id=payment_tool.tool_id,
        mode=ExecutionMode.EXECUTION,
        spec_frozen=True,
        spec_hash="ghi789",
        project_id="proj-001",
        inputs={},
        actor="user@example.com",
        timestamp=datetime.now()
    )

    allowed, reason = policy._check_policy_gate(payment_tool, invocation)
    print(f"\n  Policy Gate 检查:")
    print(f"    允许: {allowed}")
    print(f"    原因: {reason}")


if __name__ == "__main__":
    # 运行所有示例
    example_1_query_trust_tier_defaults()
    example_2_mcp_trust_tier_inference()
    example_3_extension_vs_mcp()
    example_4_policy_engine_integration()
    example_5_override_trust_tier_defaults()
    example_6_trust_tier_blacklist()

    print("\n" + "=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)
