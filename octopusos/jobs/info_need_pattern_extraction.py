"""
InfoNeed Pattern Extraction Job - Daily job to extract patterns from MemoryOS

This job runs periodically (recommended: daily) to:
1. Extract patterns from MemoryOS judgment history
2. Write/update patterns in BrainOS
3. Calculate signal effectiveness
4. Clean up low-quality patterns
5. Generate job statistics

Recommended schedule: Daily at 2 AM (low traffic time)
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from agentos.core.brain.info_need_pattern_extractor import InfoNeedPatternExtractor
from agentos.core.brain.info_need_pattern_writer import InfoNeedPatternWriter

logger = logging.getLogger(__name__)


class PatternExtractionJob:
    """
    Pattern extraction job for InfoNeed decision patterns.

    Extracts patterns from MemoryOS (short-term) and promotes them
    to BrainOS (long-term) for improved classification over time.
    """

    def __init__(
        self,
        brain_db_path: Optional[str] = None,
        time_window_days: int = 7,
        min_occurrences: int = 5,
        min_success_rate: float = 0.3,
        dry_run: bool = False,
    ):
        """
        Initialize pattern extraction job.

        Args:
            brain_db_path: Path to BrainOS database (None for default)
            time_window_days: Time window for extracting patterns (days)
            min_occurrences: Minimum occurrences for a pattern
            min_success_rate: Minimum success rate for keeping patterns
            dry_run: If True, no changes are made to BrainOS
        """
        self.brain_db_path = brain_db_path
        self.time_window_days = time_window_days
        self.min_occurrences = min_occurrences
        self.min_success_rate = min_success_rate
        self.dry_run = dry_run

        # Initialize components
        self.extractor = InfoNeedPatternExtractor()
        self.writer = InfoNeedPatternWriter(brain_db_path=brain_db_path)

        # Track statistics
        self.stats = {
            "started_at": None,
            "completed_at": None,
            "status": "pending",
            "patterns_extracted": 0,
            "patterns_written": 0,
            "patterns_updated": 0,
            "patterns_cleaned": 0,
            "error": None,
        }

    async def run(self) -> Dict[str, Any]:
        """
        Run pattern extraction job.

        Returns:
            Statistics dictionary
        """
        self.stats["started_at"] = datetime.now(timezone.utc).isoformat()
        self.stats["status"] = "running"

        logger.info("=" * 60)
        logger.info("Starting InfoNeed Pattern Extraction Job")
        logger.info("=" * 60)
        logger.info(f"Time window: {self.time_window_days} days")
        logger.info(f"Min occurrences: {self.min_occurrences}")
        logger.info(f"Min success rate: {self.min_success_rate}")
        if self.dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
        logger.info("=" * 60)

        try:
            # Step 1: Extract patterns from MemoryOS
            logger.info("Step 1: Extracting patterns from MemoryOS...")
            time_window = timedelta(days=self.time_window_days)
            patterns = await self.extractor.extract_patterns(
                time_window=time_window,
                min_occurrences=self.min_occurrences,
            )
            self.stats["patterns_extracted"] = len(patterns)
            logger.info(f"✓ Extracted {len(patterns)} patterns")

            if not patterns:
                logger.warning("No patterns extracted, job complete")
                self.stats["status"] = "completed"
                self.stats["completed_at"] = datetime.now(timezone.utc).isoformat()
                return self.stats

            # Step 2: Write/update patterns in BrainOS
            if not self.dry_run:
                logger.info("Step 2: Writing patterns to BrainOS...")
                written, updated = await self._write_patterns(patterns)
                self.stats["patterns_written"] = written
                self.stats["patterns_updated"] = updated
                logger.info(f"✓ Written: {written}, Updated: {updated}")
            else:
                logger.info("Step 2: SKIPPED (dry run)")

            # Step 3: Clean up low-quality patterns
            if not self.dry_run:
                logger.info("Step 3: Cleaning up low-quality patterns...")
                cleaned = await self.writer.cleanup_low_quality_patterns(
                    min_occurrences=self.min_occurrences,
                    min_success_rate=self.min_success_rate,
                )
                self.stats["patterns_cleaned"] = cleaned
                logger.info(f"✓ Cleaned up {cleaned} low-quality patterns")
            else:
                logger.info("Step 3: SKIPPED (dry run)")

            # Job complete
            self.stats["status"] = "completed"
            self.stats["completed_at"] = datetime.now(timezone.utc).isoformat()

            logger.info("=" * 60)
            logger.info("Pattern Extraction Job Complete")
            logger.info(f"  Extracted: {self.stats['patterns_extracted']}")
            logger.info(f"  Written: {self.stats['patterns_written']}")
            logger.info(f"  Updated: {self.stats['patterns_updated']}")
            logger.info(f"  Cleaned: {self.stats['patterns_cleaned']}")
            logger.info("=" * 60)

            return self.stats

        except Exception as e:
            self.stats["status"] = "failed"
            self.stats["error"] = str(e)
            self.stats["completed_at"] = datetime.now(timezone.utc).isoformat()
            logger.error(f"Pattern extraction job failed: {e}", exc_info=True)
            return self.stats

    async def _write_patterns(self, patterns) -> tuple[int, int]:
        """
        Write patterns to BrainOS, updating existing ones if found.

        Args:
            patterns: List of InfoNeedPatternNode instances

        Returns:
            Tuple of (written_count, updated_count)
        """
        written = 0
        updated = 0

        for pattern in patterns:
            # Check if pattern already exists (by feature signature)
            existing_patterns = await self.writer.query_patterns(
                classification_type=pattern.classification_type,
                min_occurrences=0,
                limit=1000,
            )

            # Find matching pattern by feature similarity
            matched = False
            for existing in existing_patterns:
                if self._patterns_match(pattern, existing):
                    # Update existing pattern statistics
                    # For simplicity, we'll just update the occurrence counts
                    # In production, you might want more sophisticated merging
                    await self.writer.update_pattern_statistics(
                        pattern_id=existing.pattern_id,
                        success=True,  # Placeholder
                        confidence_score=pattern.avg_confidence_score,
                        latency_ms=pattern.avg_latency_ms,
                    )
                    updated += 1
                    matched = True
                    logger.debug(f"Updated existing pattern: {existing.pattern_id}")
                    break

            if not matched:
                # Write new pattern
                await self.writer.write_pattern(pattern)
                written += 1
                logger.debug(f"Wrote new pattern: {pattern.pattern_id}")

        return written, updated

    def _patterns_match(self, pattern1, pattern2) -> bool:
        """
        Check if two patterns represent the same underlying pattern.

        Args:
            pattern1: First pattern
            pattern2: Second pattern

        Returns:
            True if patterns match
        """
        # Simple matching: same classification type and similar features
        if pattern1.classification_type != pattern2.classification_type:
            return False

        # Check feature signature similarity
        sig1 = pattern1.question_features.get("signature", "")
        sig2 = pattern2.question_features.get("signature", "")

        return sig1 == sig2


async def run_pattern_extraction_job(
    brain_db_path: Optional[str] = None,
    time_window_days: int = 7,
    min_occurrences: int = 5,
    min_success_rate: float = 0.3,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Convenience function to run pattern extraction job.

    Args:
        brain_db_path: Path to BrainOS database (None for default)
        time_window_days: Time window for extracting patterns (days)
        min_occurrences: Minimum occurrences for a pattern
        min_success_rate: Minimum success rate for keeping patterns
        dry_run: If True, no changes are made

    Returns:
        Statistics dictionary
    """
    job = PatternExtractionJob(
        brain_db_path=brain_db_path,
        time_window_days=time_window_days,
        min_occurrences=min_occurrences,
        min_success_rate=min_success_rate,
        dry_run=dry_run,
    )

    return await job.run()


def main():
    """CLI entry point for running the job."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract InfoNeed patterns from MemoryOS to BrainOS"
    )
    parser.add_argument(
        "--brain-db",
        type=str,
        default=None,
        help="Path to BrainOS database (default: ~/.brainos/patterns.db)",
    )
    parser.add_argument(
        "--time-window",
        type=int,
        default=7,
        help="Time window in days (default: 7)",
    )
    parser.add_argument(
        "--min-occurrences",
        type=int,
        default=5,
        help="Minimum occurrences for a pattern (default: 5)",
    )
    parser.add_argument(
        "--min-success-rate",
        type=float,
        default=0.3,
        help="Minimum success rate for keeping patterns (default: 0.3)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (no changes made)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run job
    stats = asyncio.run(
        run_pattern_extraction_job(
            brain_db_path=args.brain_db,
            time_window_days=args.time_window,
            min_occurrences=args.min_occurrences,
            min_success_rate=args.min_success_rate,
            dry_run=args.dry_run,
        )
    )

    # Print summary
    print("\n" + "=" * 60)
    print("Job Summary")
    print("=" * 60)
    print(f"Status: {stats['status']}")
    print(f"Extracted: {stats['patterns_extracted']}")
    print(f"Written: {stats['patterns_written']}")
    print(f"Updated: {stats['patterns_updated']}")
    print(f"Cleaned: {stats['patterns_cleaned']}")
    if stats.get("error"):
        print(f"Error: {stats['error']}")
    print("=" * 60)

    # Exit with appropriate code
    exit(0 if stats["status"] == "completed" else 1)


if __name__ == "__main__":
    main()
