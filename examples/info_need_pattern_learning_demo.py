"""
InfoNeed Pattern Learning Demo

This script demonstrates the complete pattern learning workflow:
1. Simulate classification judgments
2. Extract patterns from judgments
3. Write patterns to BrainOS
4. Query and analyze patterns
5. Demonstrate pattern evolution

Run:
    python examples/info_need_pattern_learning_demo.py
"""

import asyncio
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agentos.core.brain.info_need_pattern_extractor import InfoNeedPatternExtractor
from agentos.core.brain.info_need_pattern_writer import InfoNeedPatternWriter
from agentos.core.brain.info_need_pattern_models import (
    InfoNeedPatternNode,
    PatternType,
)
from agentos.core.memory.schema import (
    InfoNeedJudgment,
    InfoNeedType,
    ConfidenceLevel,
    DecisionAction,
    JudgmentOutcome,
)
from agentos.jobs.info_need_pattern_extraction import PatternExtractionJob


def create_sample_judgment(
    question: str,
    classification: InfoNeedType,
    outcome: JudgmentOutcome = JudgmentOutcome.USER_PROCEEDED,
    timestamp: datetime = None
) -> InfoNeedJudgment:
    """Create a sample judgment for demonstration."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    return InfoNeedJudgment(
        judgment_id=f"demo-{hash(question)}",
        timestamp=timestamp,
        session_id="demo-session",
        message_id=f"msg-{hash(question)}",
        question_text=question,
        question_hash=InfoNeedJudgment.create_question_hash(question),
        classified_type=classification,
        confidence_level=ConfidenceLevel.HIGH,
        decision_action=DecisionAction.DIRECT_ANSWER,
        rule_signals={
            "has_time_sensitive_keywords": "latest" in question.lower(),
            "signal_strength": 0.7,
        },
        llm_confidence_score=0.85,
        decision_latency_ms=45.0,
        outcome=outcome,
        phase="planning",
        mode="conversation",
    )


async def demo_feature_extraction():
    """Demo 1: Feature Extraction"""
    print("\n" + "="*60)
    print("Demo 1: Question Feature Extraction")
    print("="*60)

    from agentos.core.brain.info_need_pattern_extractor import QuestionFeatureExtractor

    extractor = QuestionFeatureExtractor()

    questions = [
        "What is the latest Python version?",
        "How do I implement the API?",
        "What is the current system status?",
        "Would you recommend using Django or Flask?",
    ]

    for question in questions:
        features = extractor.extract_features(question)
        print(f"\nQuestion: {question}")
        print(f"  Signature: {features['signature']}")
        print(f"  Time keywords: {features['has_time_keywords']}")
        print(f"  Tech keywords: {features['has_tech_keywords']}")
        print(f"  Opinion keywords: {features['has_opinion_keywords']}")
        print(f"  Length: {features['length']} chars")


async def demo_pattern_extraction():
    """Demo 2: Pattern Extraction from Judgments"""
    print("\n" + "="*60)
    print("Demo 2: Pattern Extraction")
    print("="*60)

    # Create sample judgments with patterns
    judgments = [
        # Pattern 1: Time-sensitive questions (6 instances)
        create_sample_judgment(
            "What is the latest Python version?",
            InfoNeedType.EXTERNAL_FACT_UNCERTAIN
        ),
        create_sample_judgment(
            "What is the latest Node.js release?",
            InfoNeedType.EXTERNAL_FACT_UNCERTAIN
        ),
        create_sample_judgment(
            "Tell me the latest React version.",
            InfoNeedType.EXTERNAL_FACT_UNCERTAIN
        ),
        create_sample_judgment(
            "What is the latest Django version?",
            InfoNeedType.EXTERNAL_FACT_UNCERTAIN
        ),
        create_sample_judgment(
            "Latest Flask release?",
            InfoNeedType.EXTERNAL_FACT_UNCERTAIN
        ),
        create_sample_judgment(
            "Current Vue.js version?",
            InfoNeedType.EXTERNAL_FACT_UNCERTAIN
        ),

        # Pattern 2: Tech/API questions (5 instances)
        create_sample_judgment(
            "How do I use the API?",
            InfoNeedType.LOCAL_DETERMINISTIC
        ),
        create_sample_judgment(
            "Where is the function defined?",
            InfoNeedType.LOCAL_DETERMINISTIC
        ),
        create_sample_judgment(
            "Show me the class implementation.",
            InfoNeedType.LOCAL_DETERMINISTIC
        ),
        create_sample_judgment(
            "Find the API documentation.",
            InfoNeedType.LOCAL_DETERMINISTIC
        ),
        create_sample_judgment(
            "Where is file.py located?",
            InfoNeedType.LOCAL_DETERMINISTIC
        ),
    ]

    # Extract patterns
    extractor = InfoNeedPatternExtractor()

    # Mock the memory query (in production, this queries MemoryOS)
    from unittest.mock import patch

    with patch.object(
        extractor.memory_writer,
        'query_recent_judgments',
        return_value=judgments
    ):
        patterns = await extractor.extract_patterns(min_occurrences=5)

        print(f"\nExtracted {len(patterns)} patterns from {len(judgments)} judgments:")

        for i, pattern in enumerate(patterns, 1):
            print(f"\n  Pattern {i}:")
            print(f"    Classification: {pattern.classification_type}")
            print(f"    Occurrences: {pattern.occurrence_count}")
            print(f"    Success rate: {pattern.success_rate:.1%}")
            print(f"    Avg confidence: {pattern.avg_confidence_score:.2f}")
            print(f"    Features: {pattern.question_features.get('signature', 'N/A')}")


async def demo_pattern_storage_and_query():
    """Demo 3: Pattern Storage and Query"""
    print("\n" + "="*60)
    print("Demo 3: Pattern Storage and Query")
    print("="*60)

    # Create temporary database
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    try:
        # Initialize schema (simplified for demo)
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE info_need_patterns (
                pattern_id TEXT PRIMARY KEY,
                pattern_type TEXT NOT NULL,
                question_features TEXT NOT NULL,
                classification_type TEXT NOT NULL,
                confidence_level TEXT NOT NULL,
                occurrence_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                avg_confidence_score REAL DEFAULT 0.0,
                avg_latency_ms REAL DEFAULT 0.0,
                success_rate REAL DEFAULT 0.0,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                pattern_version INTEGER DEFAULT 1
            )
        """)
        conn.commit()
        conn.close()

        # Create writer
        writer = InfoNeedPatternWriter(brain_db_path=db_path)

        # Create sample patterns
        pattern1 = InfoNeedPatternNode(
            pattern_type=PatternType.QUESTION_KEYWORD_PATTERN,
            question_features={"has_time_keywords": True, "signature": "TIME|MEDIUM"},
            classification_type="external_fact_uncertain",
            confidence_level="low",
            occurrence_count=50,
            success_count=40,
            failure_count=10,
        )
        pattern1.success_rate = pattern1.calculate_success_rate()

        pattern2 = InfoNeedPatternNode(
            pattern_type=PatternType.QUESTION_KEYWORD_PATTERN,
            question_features={"has_tech_keywords": True, "signature": "TECH|SHORT"},
            classification_type="local_deterministic",
            confidence_level="high",
            occurrence_count=30,
            success_count=28,
            failure_count=2,
        )
        pattern2.success_rate = pattern2.calculate_success_rate()

        # Write patterns
        print("\nWriting patterns to BrainOS...")
        await writer.write_pattern(pattern1)
        await writer.write_pattern(pattern2)
        print("✓ Patterns written")

        # Query all patterns
        print("\nQuerying all patterns:")
        all_patterns = await writer.query_patterns()
        for pattern in all_patterns:
            print(f"  - {pattern.classification_type}: "
                  f"{pattern.occurrence_count} occurrences, "
                  f"{pattern.success_rate:.1%} success")

        # Query with filters
        print("\nQuerying high-success patterns (>90%):")
        high_success = await writer.query_patterns(min_success_rate=0.9)
        for pattern in high_success:
            print(f"  - {pattern.classification_type}: "
                  f"{pattern.success_rate:.1%} success")

    finally:
        # Cleanup
        Path(db_path).unlink()


async def demo_pattern_evolution():
    """Demo 4: Pattern Evolution"""
    print("\n" + "="*60)
    print("Demo 4: Pattern Evolution")
    print("="*60)

    # Create temporary database
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    try:
        # Initialize schema
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE info_need_patterns (
                pattern_id TEXT PRIMARY KEY,
                pattern_type TEXT NOT NULL,
                question_features TEXT NOT NULL,
                classification_type TEXT NOT NULL,
                confidence_level TEXT NOT NULL,
                occurrence_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                avg_confidence_score REAL DEFAULT 0.0,
                avg_latency_ms REAL DEFAULT 0.0,
                success_rate REAL DEFAULT 0.0,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                pattern_version INTEGER DEFAULT 1
            )
        """)

        cursor.execute("""
            CREATE TABLE pattern_evolution (
                evolution_id TEXT PRIMARY KEY,
                from_pattern_id TEXT NOT NULL,
                to_pattern_id TEXT NOT NULL,
                evolution_type TEXT NOT NULL,
                reason TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                triggered_by TEXT
            )
        """)

        conn.commit()
        conn.close()

        writer = InfoNeedPatternWriter(brain_db_path=db_path)

        # Create original pattern
        old_pattern = InfoNeedPatternNode(
            pattern_type=PatternType.QUESTION_KEYWORD_PATTERN,
            question_features={"has_time_keywords": True},
            classification_type="external_fact_uncertain",
            confidence_level="low",
            occurrence_count=100,
            success_count=60,
            failure_count=40,
        )
        old_pattern.success_rate = old_pattern.calculate_success_rate()

        print(f"\nOriginal pattern:")
        print(f"  Success rate: {old_pattern.success_rate:.1%}")
        print(f"  Occurrences: {old_pattern.occurrence_count}")

        old_id = await writer.write_pattern(old_pattern)

        # Create refined pattern
        refined_pattern = InfoNeedPatternNode(
            pattern_type=PatternType.QUESTION_KEYWORD_PATTERN,
            question_features={
                "has_time_keywords": True,
                "has_policy_keywords": True,  # Added refinement
            },
            classification_type="external_fact_uncertain",
            confidence_level="low",
            occurrence_count=150,
            success_count=120,
            failure_count=30,
        )
        refined_pattern.success_rate = refined_pattern.calculate_success_rate()

        print(f"\nRefined pattern:")
        print(f"  Success rate: {refined_pattern.success_rate:.1%}")
        print(f"  Occurrences: {refined_pattern.occurrence_count}")
        print(f"  Improvement: +{(refined_pattern.success_rate - old_pattern.success_rate)*100:.1f}%")

        # Record evolution
        new_id = await writer.evolve_pattern(
            old_pattern_id=old_id,
            new_pattern=refined_pattern,
            evolution_type="refined",
            reason="Added policy keyword filter to reduce false positives",
            triggered_by="demo"
        )

        print(f"\n✓ Pattern evolution recorded")
        print(f"  Old ID: {old_id[:8]}...")
        print(f"  New ID: {new_id[:8]}...")

    finally:
        Path(db_path).unlink()


async def demo_pattern_extraction_job():
    """Demo 5: Complete Pattern Extraction Job"""
    print("\n" + "="*60)
    print("Demo 5: Pattern Extraction Job")
    print("="*60)

    # Create temporary database
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    try:
        # Initialize schema
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE info_need_patterns (
                pattern_id TEXT PRIMARY KEY,
                pattern_type TEXT NOT NULL,
                question_features TEXT NOT NULL,
                classification_type TEXT NOT NULL,
                confidence_level TEXT NOT NULL,
                occurrence_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                avg_confidence_score REAL DEFAULT 0.0,
                avg_latency_ms REAL DEFAULT 0.0,
                success_rate REAL DEFAULT 0.0,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                pattern_version INTEGER DEFAULT 1
            )
        """)
        conn.commit()
        conn.close()

        # Create sample judgments
        judgments = [
            create_sample_judgment(f"What is the latest version {i}?",
                                   InfoNeedType.EXTERNAL_FACT_UNCERTAIN)
            for i in range(10)
        ]

        # Create job
        job = PatternExtractionJob(
            brain_db_path=db_path,
            time_window_days=7,
            min_occurrences=5,
            min_success_rate=0.3,
            dry_run=False,
        )

        # Mock MemoryOS query
        from unittest.mock import patch

        with patch.object(
            job.extractor.memory_writer,
            'query_recent_judgments',
            return_value=judgments
        ):
            print("\nRunning pattern extraction job...")
            stats = await job.run()

            print(f"\n✓ Job completed!")
            print(f"  Status: {stats['status']}")
            print(f"  Patterns extracted: {stats['patterns_extracted']}")
            print(f"  Patterns written: {stats['patterns_written']}")
            print(f"  Patterns updated: {stats['patterns_updated']}")
            print(f"  Patterns cleaned: {stats['patterns_cleaned']}")

    finally:
        Path(db_path).unlink()


async def main():
    """Run all demos."""
    print("\n" + "="*60)
    print("InfoNeed Pattern Learning Demo")
    print("="*60)

    await demo_feature_extraction()
    await demo_pattern_extraction()
    await demo_pattern_storage_and_query()
    await demo_pattern_evolution()
    await demo_pattern_extraction_job()

    print("\n" + "="*60)
    print("Demo Complete!")
    print("="*60)
    print("\nKey Takeaways:")
    print("  1. Features are extracted using rule-based methods (no LLM)")
    print("  2. Patterns are clustered by feature similarity")
    print("  3. Patterns track success rates and evolve over time")
    print("  4. BrainOS stores patterns permanently for long-term learning")
    print("  5. Daily jobs extract patterns from MemoryOS automatically")
    print("\nFor more info, see: docs/brain/INFO_NEED_PATTERN_LEARNING.md")


if __name__ == "__main__":
    asyncio.run(main())
