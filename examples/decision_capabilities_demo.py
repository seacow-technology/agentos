"""
Decision Capabilities Demo - AgentOS v3

This example demonstrates the complete Decision workflow:
1. Create an execution plan
2. Freeze the plan (make immutable)
3. Evaluate multiple options
4. Select best option with rationale
5. Record additional rationale with evidence

Run this demo:
    python examples/decision_capabilities_demo.py
"""

import tempfile
import os

from agentos.core.capability.domains.decision import (
    get_plan_service,
    get_option_evaluator,
    get_decision_judge,
    PlanStep,
    Alternative,
    Option,
)


def demo_plan_lifecycle():
    """Demo: Create and freeze a plan"""
    print("=" * 70)
    print("DEMO 1: Plan Lifecycle (DC-001, DC-002)")
    print("=" * 70)

    # Use temporary database for demo
    fd, db_path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)

    # Initialize service
    plan_service = get_plan_service(db_path=db_path)

    # Initialize schema (for demo only)
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE decision_plans (
            plan_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            steps_json TEXT NOT NULL,
            alternatives_json TEXT,
            rationale TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            frozen_at_ms INTEGER,
            plan_hash TEXT,
            created_by TEXT NOT NULL,
            created_at_ms INTEGER NOT NULL,
            updated_at_ms INTEGER,
            context_snapshot_id TEXT,
            metadata TEXT
        )
    """)
    conn.commit()
    conn.close()

    # 1. Create execution plan
    print("\n1. Creating execution plan...")

    steps = [
        PlanStep(
            step_id="step-1",
            description="Analyze user request",
            action_type="decision.analyze",
            requires_capabilities=["state.memory.read", "decision.plan.create"],
            depends_on=[],
            estimated_time_ms=200,
            estimated_cost=0.01,
        ),
        PlanStep(
            step_id="step-2",
            description="Generate response",
            action_type="action.llm.call",
            requires_capabilities=["action.llm.call"],
            depends_on=["step-1"],
            estimated_time_ms=1000,
            estimated_cost=0.05,
        ),
        PlanStep(
            step_id="step-3",
            description="Record result",
            action_type="evidence.record",
            requires_capabilities=["evidence.record"],
            depends_on=["step-2"],
            estimated_time_ms=50,
            estimated_cost=0.001,
        ),
    ]

    alternatives = [
        Alternative(
            alternative_id="alt-1",
            description="Skip analysis step (faster but less accurate)",
            pros=["Faster", "Lower cost"],
            cons=["Less accurate", "Might miss context"],
            rejection_reason="Accuracy is more important than speed for this task",
            estimated_cost=0.03,
        ),
    ]

    plan = plan_service.create_plan(
        task_id="task-demo-123",
        steps=steps,
        rationale="This approach balances accuracy with reasonable performance",
        created_by="demo-agent",
        alternatives=alternatives,
    )

    print(f"   Created plan: {plan.plan_id}")
    print(f"   Status: {plan.status.value}")
    print(f"   Steps: {len(plan.steps)}")
    print(f"   Alternatives considered: {len(plan.alternatives)}")

    # 2. Freeze plan
    print("\n2. Freezing plan (making immutable)...")

    frozen_plan = plan_service.freeze_plan(plan.plan_id, frozen_by="demo-agent")

    print(f"   Plan frozen at: {frozen_plan.frozen_at_ms}")
    print(f"   Plan hash: {frozen_plan.plan_hash[:16]}...")
    print(f"   Status: {frozen_plan.status.value}")

    # 3. Verify hash
    print("\n3. Verifying plan hash...")

    is_valid = plan_service.verify_plan(plan.plan_id, frozen_plan.plan_hash)
    print(f"   Hash verification: {'✅ PASSED' if is_valid else '❌ FAILED'}")

    # 4. Attempt to modify frozen plan (should fail)
    print("\n4. Attempting to modify frozen plan...")

    try:
        plan_service.update_plan(plan.plan_id, rationale="Try to modify")
        print("   ❌ FAILED - Modification was allowed (should be blocked)")
    except Exception as e:
        print(f"   ✅ PASSED - Modification blocked: {type(e).__name__}")

    # Cleanup
    os.unlink(db_path)

    print("\n" + "=" * 70)


def demo_option_evaluation():
    """Demo: Evaluate multiple options"""
    print("=" * 70)
    print("DEMO 2: Option Evaluation (DC-003)")
    print("=" * 70)

    # Use temporary database
    fd, db_path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)

    # Initialize service
    evaluator = get_option_evaluator(db_path=db_path)

    # Initialize schema
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE decision_evaluations (
            evaluation_id TEXT PRIMARY KEY,
            decision_context_id TEXT NOT NULL,
            options_json TEXT NOT NULL,
            scores_json TEXT NOT NULL,
            ranked_options_json TEXT NOT NULL,
            recommendation TEXT NOT NULL,
            recommendation_rationale TEXT,
            confidence REAL NOT NULL,
            evaluated_by TEXT NOT NULL,
            evaluated_at_ms INTEGER NOT NULL,
            metadata TEXT
        )
    """)
    conn.commit()
    conn.close()

    # 1. Define options
    print("\n1. Defining options to evaluate...")

    options = [
        Option(
            option_id="opt-gpt4",
            description="Use GPT-4 (high quality)",
            estimated_cost=10.0,
            estimated_time_ms=2000,
            risks=["Expensive", "Slower"],
            benefits=["Highest quality", "Best reasoning", "Most reliable"],
        ),
        Option(
            option_id="opt-gpt35",
            description="Use GPT-3.5 (balanced)",
            estimated_cost=2.0,
            estimated_time_ms=800,
            risks=["Lower quality"],
            benefits=["Fast", "Cost effective", "Good enough for most tasks"],
        ),
        Option(
            option_id="opt-claude",
            description="Use Claude (alternative)",
            estimated_cost=5.0,
            estimated_time_ms=1200,
            risks=["Less familiar", "Different API"],
            benefits=["Good quality", "Fast", "Strong reasoning"],
        ),
    ]

    for opt in options:
        print(f"   - {opt.description}")
        print(f"     Cost: ${opt.estimated_cost:.2f}, Time: {opt.estimated_time_ms}ms")

    # 2. Evaluate options
    print("\n2. Evaluating options...")

    result = evaluator.evaluate_options(
        decision_context_id="ctx-llm-selection",
        options=options,
        evaluated_by="demo-evaluator",
    )

    print(f"   Evaluated {len(result.options)} options")

    # 3. Show results
    print("\n3. Evaluation results:")

    for i, option_id in enumerate(result.ranked_options, 1):
        score = result.scores[option_id]
        opt = result.get_option_by_id(option_id)
        print(f"   #{i}. {opt.description}")
        print(f"       Score: {score:.1f}/100")

    print(f"\n   Recommendation: {result.get_option_by_id(result.recommendation).description}")
    print(f"   Confidence: {result.confidence:.1f}%")

    # Cleanup
    os.unlink(db_path)

    print("\n" + "=" * 70)


def demo_decision_selection():
    """Demo: Select best option and record rationale"""
    print("=" * 70)
    print("DEMO 3: Decision Selection (DC-004, DC-005)")
    print("=" * 70)

    # Use temporary database
    fd, db_path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)

    # Note: This is a demo workaround - in production, use singleton instances
    # that share the same database connection
    from agentos.core.capability.domains.decision.option_evaluator import OptionEvaluator
    from agentos.core.capability.domains.decision.judge import DecisionJudge

    # Initialize services with same database
    evaluator = OptionEvaluator(db_path=db_path)
    judge = DecisionJudge(db_path=db_path)

    # Initialize schema
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE decision_evaluations (
            evaluation_id TEXT PRIMARY KEY,
            decision_context_id TEXT NOT NULL,
            options_json TEXT NOT NULL,
            scores_json TEXT NOT NULL,
            ranked_options_json TEXT NOT NULL,
            recommendation TEXT NOT NULL,
            recommendation_rationale TEXT,
            confidence REAL NOT NULL,
            evaluated_by TEXT NOT NULL,
            evaluated_at_ms INTEGER NOT NULL,
            metadata TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE decision_selections (
            decision_id TEXT PRIMARY KEY,
            evaluation_id TEXT NOT NULL,
            selected_option_id TEXT NOT NULL,
            selected_option_json TEXT NOT NULL,
            rationale TEXT NOT NULL,
            alternatives_rejected_json TEXT,
            rejection_reasons_json TEXT,
            confidence_level TEXT NOT NULL,
            decided_by TEXT NOT NULL,
            decided_at_ms INTEGER NOT NULL,
            evidence_id TEXT,
            metadata TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE decision_rationales (
            rationale_id TEXT PRIMARY KEY,
            decision_id TEXT NOT NULL,
            rationale TEXT NOT NULL,
            evidence_refs_json TEXT,
            created_by TEXT NOT NULL,
            created_at_ms INTEGER NOT NULL,
            metadata TEXT
        )
    """)
    conn.commit()
    conn.close()

    # 1. Evaluate options
    print("\n1. Evaluating options...")

    options = [
        Option(
            option_id="opt-approach-a",
            description="Use machine learning approach",
            estimated_cost=15.0,
            estimated_time_ms=5000,
            risks=["Requires training data", "Complex setup"],
            benefits=["Highly accurate", "Scalable", "Learns from data"],
        ),
        Option(
            option_id="opt-approach-b",
            description="Use rule-based approach",
            estimated_cost=3.0,
            estimated_time_ms=500,
            risks=["Limited flexibility", "Maintenance overhead"],
            benefits=["Fast", "Predictable", "Easy to debug"],
        ),
    ]

    evaluation = evaluator.evaluate_options(
        decision_context_id="ctx-approach-selection",
        options=options,
        evaluated_by="demo-evaluator",
    )

    print(f"   Recommendation: {evaluation.get_option_by_id(evaluation.recommendation).description}")

    # 2. Make decision
    print("\n2. Making final decision...")

    decision = judge.select_option(
        evaluation_result=evaluation,
        decided_by="senior-engineer",
    )

    print(f"   Decision ID: {decision.decision_id}")
    print(f"   Selected: {decision.selected_option.description}")
    print(f"   Confidence: {decision.confidence_level.value}")
    print(f"   Evidence ID: {decision.evidence_id}")

    # 3. Record additional rationale
    print("\n3. Recording additional rationale...")

    rationale = judge.record_rationale(
        decision_id=decision.decision_id,
        rationale=(
            "After consulting with the team, we confirmed that the selected approach "
            "aligns with our technical capabilities and project timeline. "
            "The alternative approaches were thoroughly evaluated but ultimately "
            "did not meet our specific requirements."
        ),
        created_by="tech-lead",
        evidence_refs=["evidence-001", "evidence-002", "meeting-notes-2026-02-01"],
    )

    print(f"   Rationale ID: {rationale.rationale_id}")
    print(f"   Evidence references: {len(rationale.evidence_refs)}")

    # 4. Show final decision summary
    print("\n4. Decision summary:")
    print(f"   Selected option: {decision.selected_option.description}")
    print(f"   Rationale: {decision.rationale[:100]}...")
    print(f"   Alternatives rejected: {len(decision.alternatives_rejected)}")
    for alt in decision.alternatives_rejected:
        reason = decision.rejection_reasons.get(alt.option_id, "N/A")
        print(f"   - {alt.description}: {reason}")

    # Cleanup
    os.unlink(db_path)

    print("\n" + "=" * 70)


def main():
    """Run all demos"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  AgentOS v3 Decision Capabilities - Demo".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    demo_plan_lifecycle()
    print()
    demo_option_evaluation()
    print()
    demo_decision_selection()

    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  All demos completed successfully!".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "═" * 68 + "╝")
    print()


if __name__ == "__main__":
    main()
