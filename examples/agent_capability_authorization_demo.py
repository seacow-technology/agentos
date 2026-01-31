"""
Agent Capability Authorization System Demo - AgentOS v3
Task #27: 重构Agent定义为Capability授权模型

这个示例演示如何使用新的Agent Capability Authorization系统：
1. 创建Agent Profile
2. 授权检查
3. Tier升级
4. Escalation请求处理

核心理念：Agent ≠ Capability，Agent是Capability的使用者
"""

import tempfile
import sqlite3
from unittest.mock import Mock

from agentos.core.agent import (
    AgentCapabilityProfile,
    CapabilityAuthorizer,
    AgentTierSystem,
    EscalationEngine,
    AgentTier,
    EscalationPolicy,
)


def setup_demo_environment():
    """Setup temporary database for demo"""
    temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = temp_db.name
    temp_db.close()

    # Create schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE agent_profiles (
            agent_id TEXT PRIMARY KEY,
            agent_type TEXT,
            tier INTEGER,
            allowed_capabilities_json TEXT,
            forbidden_capabilities_json TEXT,
            default_capability_level TEXT,
            escalation_policy TEXT,
            created_at_ms INTEGER,
            updated_at_ms INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE agent_tier_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT,
            from_tier INTEGER,
            to_tier INTEGER,
            changed_by TEXT,
            reason TEXT,
            changed_at_ms INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE escalation_requests (
            request_id TEXT PRIMARY KEY,
            agent_id TEXT,
            requested_capability TEXT,
            reason TEXT,
            status TEXT,
            requested_at_ms INTEGER,
            reviewed_by TEXT,
            reviewed_at_ms INTEGER,
            deny_reason TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE capability_invocations (
            invocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT,
            capability_id TEXT,
            operation TEXT,
            allowed INTEGER,
            reason TEXT,
            context_json TEXT,
            timestamp_ms INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE capability_grants (
            grant_id TEXT PRIMARY KEY,
            agent_id TEXT,
            capability_id TEXT,
            granted_by TEXT,
            granted_at_ms INTEGER,
            expires_at_ms INTEGER,
            reason TEXT,
            metadata TEXT
        )
    """)

    conn.commit()
    conn.close()

    return db_path


def demo_agent_profiles():
    """Demo 1: 创建和使用Agent Profiles"""
    print("\n" + "=" * 70)
    print("Demo 1: Agent Capability Profiles")
    print("=" * 70)

    # 创建不同tier的Agent profiles
    print("\n1. Creating Agent Profiles with different tiers...")

    # Tier 2: Chat Agent (Propose)
    chat_profile = AgentCapabilityProfile(
        agent_id="chat_agent",
        tier=AgentTier.T2_PROPOSE,
        agent_type="decision_maker",
        allowed_capabilities=[
            "state.read",
            "state.memory.propose",
            "decision.infoneed.classify",
            "evidence.query",
        ],
        forbidden_capabilities=[
            "action.execute.*",
            "state.memory.write",
            "governance.override.*",
        ],
        escalation_policy=EscalationPolicy.REQUEST_APPROVAL,
    )

    print(f"\n   Chat Agent Profile:")
    print(f"   - Tier: {chat_profile.tier.name_str} ({chat_profile.tier.value})")
    print(f"   - Type: {chat_profile.agent_type}")
    print(f"   - Allowed: {len(chat_profile.allowed_capabilities)} capabilities")
    print(f"   - Forbidden: {len(chat_profile.forbidden_capabilities)} patterns")

    # 测试权限检查
    print("\n2. Testing capability checks...")

    test_capabilities = [
        ("state.read", "Should allow"),
        ("state.memory.propose", "Should allow"),
        ("state.memory.write", "Should deny (forbidden)"),
        ("action.execute.local", "Should deny (forbidden pattern)"),
        ("unknown.capability", "Should deny (not in allowed)"),
    ]

    for cap_id, expected in test_capabilities:
        result = chat_profile.can_use(cap_id)
        status = "✓ ALLOWED" if result else "✗ DENIED"
        print(f"   {cap_id:30s} → {status:12s} ({expected})")

    # Tier capabilities
    print("\n3. Tier-based auto-grant capabilities:")
    tier_caps = chat_profile.get_tier_capabilities()
    for cap in tier_caps:
        print(f"   - {cap}")

    print("\n4. Profile serialization:")
    profile_dict = chat_profile.to_dict()
    print(f"   Within tier limit: {profile_dict['within_tier_limit']}")
    print(f"   Max capabilities for tier: {chat_profile.tier.max_capabilities}")


def demo_capability_authorizer(db_path):
    """Demo 2: Capability授权检查"""
    print("\n" + "=" * 70)
    print("Demo 2: Capability Authorization")
    print("=" * 70)

    # Mock dependencies
    mock_registry = Mock()
    mock_governance = Mock()

    # Setup mock responses
    perm_result = Mock()
    perm_result.allowed = True
    perm_result.reason = "All checks passed"
    perm_result.risk_score = 0.2
    mock_governance.check_permission = Mock(return_value=perm_result)

    risk_score = Mock()
    risk_score.score = 0.2
    risk_score.mitigation_required = False
    risk_score.level = Mock(value="LOW")
    mock_governance.calculate_risk_score = Mock(return_value=risk_score)

    # Create authorizer
    authorizer = CapabilityAuthorizer(mock_registry, mock_governance, db_path)

    # Register profile
    print("\n1. Registering agent profile...")
    profile = AgentCapabilityProfile(
        agent_id="test_agent",
        tier=AgentTier.T2_PROPOSE,
        allowed_capabilities=["state.read", "decision.*"],
        forbidden_capabilities=["action.execute.*"],
    )
    authorizer.register_profile(profile)
    print(f"   ✓ Profile registered for: {profile.agent_id}")

    # Test authorization scenarios
    print("\n2. Testing authorization scenarios...")

    # Scenario 1: Grant exists, profile allows
    print("\n   Scenario 1: Valid grant + allowed by profile")
    mock_registry.has_capability = Mock(return_value=True)

    result = authorizer.authorize(
        agent_id="test_agent",
        capability_id="state.read",
        context={"operation": "read"},
    )
    print(f"   Result: {'✓ ALLOWED' if result.allowed else '✗ DENIED'}")
    print(f"   Reason: {result.reason}")

    # Scenario 2: No grant, deny policy
    print("\n   Scenario 2: No grant + deny policy")
    mock_registry.has_capability = Mock(return_value=False)

    result = authorizer.authorize(
        agent_id="test_agent",
        capability_id="state.read",
    )
    print(f"   Result: {'✓ ALLOWED' if result.allowed else '✗ DENIED'}")
    print(f"   Reason: {result.reason}")

    # Scenario 3: Profile forbids
    print("\n   Scenario 3: Forbidden by profile")
    result = authorizer.authorize(
        agent_id="test_agent",
        capability_id="action.execute.local",
    )
    print(f"   Result: {'✓ ALLOWED' if result.allowed else '✗ DENIED'}")
    print(f"   Reason: {result.reason}")


def demo_tier_system(db_path):
    """Demo 3: Agent Tier系统"""
    print("\n" + "=" * 70)
    print("Demo 3: Agent Tier System")
    print("=" * 70)

    tier_system = AgentTierSystem(db_path=db_path)

    # Show all tiers
    print("\n1. Available Agent Tiers:")
    for tier_info in tier_system.get_all_tiers_info():
        print(f"\n   Tier {tier_info['tier']}: {tier_info['name']}")
        print(f"   - Description: {tier_info['description']}")
        print(f"   - Max capabilities: {tier_info['max_capabilities']}")
        print(f"   - Auto-grant: {', '.join(tier_info['auto_grant_capabilities'][:3])}...")

    # Upgrade tier
    print("\n2. Upgrading agent tier...")
    transition = tier_system.upgrade_tier(
        agent_id="new_agent",
        from_tier=AgentTier.T1_READ_ONLY,
        to_tier=AgentTier.T2_PROPOSE,
        changed_by="admin:alice",
        reason="Agent demonstrated reliable behavior over 30 days",
    )

    print(f"   ✓ Tier upgraded:")
    print(f"     Agent: {transition.agent_id}")
    print(f"     From: {transition.from_tier.name_str}")
    print(f"     To: {transition.to_tier.name_str}")
    print(f"     By: {transition.changed_by}")
    print(f"     Reason: {transition.reason}")

    # Get tier history
    print("\n3. Tier history:")
    history = tier_system.get_tier_history("new_agent")
    for i, trans in enumerate(history, 1):
        print(
            f"   {i}. {trans.from_tier.name_str} → {trans.to_tier.name_str} "
            f"(by {trans.changed_by})"
        )

    # Current tier
    current_tier = tier_system.get_current_tier("new_agent")
    print(f"\n   Current tier: {current_tier.name_str}")


def demo_escalation_engine(db_path):
    """Demo 4: Escalation请求处理"""
    print("\n" + "=" * 70)
    print("Demo 4: Escalation Request Handling")
    print("=" * 70)

    engine = EscalationEngine(db_path=db_path)

    # Create escalation request
    print("\n1. Creating escalation request...")
    request_id = engine.create_request(
        agent_id="chat_agent",
        capability_id="action.execute.local",
        reason="Need to execute validation script for user-requested file analysis",
        context={"user_id": "user123", "task_id": "task456"},
    )

    print(f"   ✓ Escalation request created:")
    print(f"     Request ID: {request_id}")

    request = engine.get_request(request_id)
    print(f"     Agent: {request.agent_id}")
    print(f"     Capability: {request.requested_capability}")
    print(f"     Status: {request.status.value}")

    # List pending requests
    print("\n2. Pending escalation requests:")
    pending = engine.list_pending_requests()
    print(f"   Total pending: {len(pending)}")
    for req in pending:
        print(f"   - {req.request_id}: {req.agent_id} → {req.requested_capability}")

    # Approve request (with mock)
    print("\n3. Approving escalation request...")

    # Mock the grant capability call
    from unittest.mock import patch

    with patch("agentos.core.capability.registry.get_capability_registry") as mock_get:
        mock_registry = Mock()
        mock_registry.grant_capability = Mock()
        mock_get.return_value = mock_registry

        result = engine.approve_request(
            request_id=request_id,
            reviewer_id="admin:alice",
            grant_duration_ms=3600000,  # 1 hour
        )

        print(f"   ✓ Request approved by admin:alice")
        print(f"   Grant duration: 1 hour (temporary)")

    # Verify status
    request = engine.get_request(request_id)
    print(f"   New status: {request.status.value}")
    print(f"   Reviewed by: {request.reviewed_by}")

    # Statistics
    print("\n4. Escalation statistics:")
    stats = engine.get_stats()
    print(f"   Status counts: {stats['status_counts']}")
    if stats['top_agents_with_pending']:
        print(f"   Top agents with pending:")
        for agent_info in stats['top_agents_with_pending'][:3]:
            print(f"     - {agent_info['agent_id']}: {agent_info['pending_count']}")


def main():
    """Run all demos"""
    print("\n" + "=" * 70)
    print("AgentOS v3 - Agent Capability Authorization System Demo")
    print("Task #27: 重构Agent定义为Capability授权模型")
    print("=" * 70)

    # Setup
    db_path = setup_demo_environment()
    print(f"\n✓ Demo environment setup complete (DB: {db_path})")

    try:
        # Run demos
        demo_agent_profiles()
        demo_capability_authorizer(db_path)
        demo_tier_system(db_path)
        demo_escalation_engine(db_path)

        print("\n" + "=" * 70)
        print("✓ All demos completed successfully!")
        print("=" * 70)

    finally:
        # Cleanup
        import os
        os.unlink(db_path)
        print(f"\n✓ Cleanup complete")


if __name__ == "__main__":
    main()
