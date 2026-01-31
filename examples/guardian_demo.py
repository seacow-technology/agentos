#!/usr/bin/env python3
"""
Guardian Module Demo

演示 Guardian 验收系统的基本功能。

运行方式：
    python examples/guardian_demo.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentos.core.guardian import GuardianService, GuardianPolicy, get_policy_registry


def demo_basic_usage():
    """演示基本使用"""
    print("=" * 60)
    print("Guardian Module Demo - Basic Usage")
    print("=" * 60)

    # 创建 GuardianService
    service = GuardianService()
    print("\n✅ GuardianService initialized")

    # 创建自动验收记录
    print("\n1. Creating AUTO review...")
    review1 = service.create_review(
        target_type="task",
        target_id="task_demo_001",
        guardian_id="guardian.demo.v1",
        review_type="AUTO",
        verdict="PASS",
        confidence=0.92,
        evidence={
            "checks": ["state_machine_valid", "dependencies_ok"],
            "metrics": {"execution_time_ms": 1234, "coverage": 0.85}
        },
        rule_snapshot_id="demo:v1@sha256:abc123"
    )
    print(f"   ✅ Review created: {review1.review_id}")
    print(f"   - Target: {review1.target_type}/{review1.target_id}")
    print(f"   - Verdict: {review1.verdict}")
    print(f"   - Confidence: {review1.confidence}")

    # 创建人工验收记录
    print("\n2. Creating MANUAL review...")
    review2 = service.create_review(
        target_type="task",
        target_id="task_demo_002",
        guardian_id="human.alice",
        review_type="MANUAL",
        verdict="FAIL",
        confidence=1.0,
        evidence={
            "reason": "Policy violation detected",
            "details": "Task violates security policy POL-001"
        }
    )
    print(f"   ✅ Review created: {review2.review_id}")
    print(f"   - Guardian: {review2.guardian_id}")
    print(f"   - Verdict: {review2.verdict}")

    # 查询验收记录
    print("\n3. Querying reviews...")
    all_reviews = service.list_reviews()
    print(f"   ✅ Total reviews: {len(all_reviews)}")

    # 按 verdict 过滤
    pass_reviews = service.list_reviews(verdict="PASS")
    fail_reviews = service.list_reviews(verdict="FAIL")
    print(f"   - PASS reviews: {len(pass_reviews)}")
    print(f"   - FAIL reviews: {len(fail_reviews)}")

    # 获取统计数据
    print("\n4. Getting statistics...")
    stats = service.get_statistics()
    print(f"   ✅ Statistics:")
    print(f"   - Total reviews: {stats['total_reviews']}")
    print(f"   - Pass rate: {stats['pass_rate']:.2%}")
    print(f"   - Guardians: {list(stats['guardians'].keys())}")
    print(f"   - By verdict: {stats['by_verdict']}")

    # 获取目标的验收摘要
    print("\n5. Getting verdict summary...")
    summary = service.get_verdict_summary("task", "task_demo_001")
    print(f"   ✅ Verdict summary for task_demo_001:")
    print(f"   - Total reviews: {summary['total_reviews']}")
    print(f"   - Latest verdict: {summary['latest_verdict']}")
    print(f"   - Latest guardian: {summary['latest_guardian_id']}")


def demo_policy_management():
    """演示规则集管理"""
    print("\n" + "=" * 60)
    print("Guardian Module Demo - Policy Management")
    print("=" * 60)

    # 获取全局注册表
    registry = get_policy_registry()
    print("\n✅ PolicyRegistry initialized")

    # 注册规则集 v1.0.0
    print("\n1. Registering policy v1.0.0...")
    snapshot_id_v1 = registry.create_and_register(
        policy_id="guardian.demo.state_machine",
        name="Demo State Machine Validator",
        version="v1.0.0",
        rules={
            "check_transitions": True,
            "allow_skip": False,
            "required_states": ["DRAFT", "APPROVED", "QUEUED"]
        },
        metadata={"author": "demo"}
    )
    print(f"   ✅ Registered: {snapshot_id_v1}")

    # 注册规则集 v2.0.0
    print("\n2. Registering policy v2.0.0...")
    snapshot_id_v2 = registry.create_and_register(
        policy_id="guardian.demo.state_machine",
        name="Demo State Machine Validator",
        version="v2.0.0",
        rules={
            "check_transitions": True,
            "allow_skip": True,  # 变更：允许跳过
            "required_states": ["DRAFT", "APPROVED", "QUEUED", "RUNNING"]  # 新增：RUNNING
        },
        metadata={"author": "demo", "changes": "Allow skip transitions"}
    )
    print(f"   ✅ Registered: {snapshot_id_v2}")

    # 列出所有版本
    print("\n3. Listing all versions...")
    versions = registry.list_versions("guardian.demo.state_machine")
    print(f"   ✅ Found {len(versions)} versions:")
    for policy in versions:
        print(f"   - {policy.version}: {policy.snapshot_id}")

    # 获取最新版本
    print("\n4. Getting latest version...")
    latest = registry.get_latest("guardian.demo.state_machine")
    print(f"   ✅ Latest version: {latest.version}")
    print(f"   - Rules: {latest.rules}")

    # 获取规则集详情
    print("\n5. Getting policy details...")
    policy = registry.get(snapshot_id_v1)
    print(f"   ✅ Policy v1.0.0 details:")
    print(f"   - Name: {policy.name}")
    print(f"   - Version: {policy.version}")
    print(f"   - Checksum: {policy.checksum[:16]}...")
    print(f"   - Rules: {policy.rules}")

    # 对比两个版本
    print("\n6. Comparing v1.0.0 and v2.0.0...")
    policy_v1 = registry.get(snapshot_id_v1)
    policy_v2 = registry.get(snapshot_id_v2)
    print(f"   ✅ Differences:")
    print(f"   - v1.0.0 allow_skip: {policy_v1.rules.get('allow_skip')}")
    print(f"   - v2.0.0 allow_skip: {policy_v2.rules.get('allow_skip')}")
    print(f"   - v1.0.0 required_states: {len(policy_v1.rules.get('required_states', []))}")
    print(f"   - v2.0.0 required_states: {len(policy_v2.rules.get('required_states', []))}")


def demo_error_handling():
    """演示错误处理"""
    print("\n" + "=" * 60)
    print("Guardian Module Demo - Error Handling")
    print("=" * 60)

    service = GuardianService()

    # 测试无效的 target_type
    print("\n1. Testing invalid target_type...")
    try:
        service.create_review(
            target_type="invalid",  # 无效
            target_id="task_001",
            guardian_id="guardian.v1",
            review_type="AUTO",
            verdict="PASS",
            confidence=0.9,
            evidence={}
        )
        print("   ❌ Should have raised ValueError")
    except ValueError as e:
        print(f"   ✅ Caught ValueError: {e}")

    # 测试无效的 verdict
    print("\n2. Testing invalid verdict...")
    try:
        service.create_review(
            target_type="task",
            target_id="task_001",
            guardian_id="guardian.v1",
            review_type="AUTO",
            verdict="INVALID",  # 无效
            confidence=0.9,
            evidence={}
        )
        print("   ❌ Should have raised ValueError")
    except ValueError as e:
        print(f"   ✅ Caught ValueError: {e}")

    # 测试无效的 confidence
    print("\n3. Testing invalid confidence...")
    try:
        service.create_review(
            target_type="task",
            target_id="task_001",
            guardian_id="guardian.v1",
            review_type="AUTO",
            verdict="PASS",
            confidence=1.5,  # 无效（> 1.0）
            evidence={}
        )
        print("   ❌ Should have raised ValueError")
    except ValueError as e:
        print(f"   ✅ Caught ValueError: {e}")

    # 测试查询不存在的记录
    print("\n4. Testing query for non-existent review...")
    review = service.get_review("nonexistent_id")
    if review is None:
        print("   ✅ Correctly returned None for non-existent review")
    else:
        print("   ❌ Should have returned None")


def initialize_database():
    """初始化数据库（确保 guardian_reviews 表存在）"""
    from agentos.store import get_db_path
    import sqlite3

    db_path = get_db_path()

    # 检查表是否存在
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='guardian_reviews'
    """)

    if cursor.fetchone() is None:
        print("📦 Creating guardian_reviews table...")
        # 创建表
        cursor.execute("""
            CREATE TABLE guardian_reviews (
                review_id TEXT PRIMARY KEY,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                guardian_id TEXT NOT NULL,
                review_type TEXT NOT NULL,
                verdict TEXT NOT NULL,
                confidence REAL NOT NULL,
                rule_snapshot_id TEXT,
                evidence TEXT NOT NULL,
                created_at TEXT NOT NULL,
                CHECK(target_type IN ('task', 'decision', 'finding')),
                CHECK(review_type IN ('AUTO', 'MANUAL')),
                CHECK(verdict IN ('PASS', 'FAIL', 'NEEDS_REVIEW')),
                CHECK(confidence >= 0.0 AND confidence <= 1.0)
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX idx_guardian_reviews_target
            ON guardian_reviews(target_type, target_id, created_at DESC)
        """)

        conn.commit()
        print("   ✅ Table and indexes created")
    else:
        print("✅ Database already initialized")

    conn.close()


def main():
    """主函数"""
    print("\n🛡️  Guardian Module Demonstration\n")

    try:
        # 初始化数据库
        initialize_database()

        # 演示基本使用
        demo_basic_usage()

        # 演示规则集管理
        demo_policy_management()

        # 演示错误处理
        demo_error_handling()

        print("\n" + "=" * 60)
        print("✅ All demos completed successfully!")
        print("=" * 60)
        print("\nNext steps:")
        print("  - Read full documentation: agentos/core/guardian/README.md")
        print("  - Read quick start guide: agentos/core/guardian/QUICKSTART.md")
        print("  - Explore API endpoints: agentos/webui/api/guardian.py")
        print("  - Run tests: pytest tests/unit/guardian/ -v")
        print()

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
