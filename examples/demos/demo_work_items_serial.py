"""Demo: Work Items Serial Execution (PR-C)

This demo shows the work_items framework in action:
1. Create a task: "Implement frontend + backend + tests"
2. Extract 3 work_items from plan
3. Execute serially (one by one)
4. Each work_item has independent audit trail
5. Create summary artifact
6. Integrate with DONE gates
"""

import json
import logging
from pathlib import Path

from agentos.core.task.work_items import (
    WorkItem,
    WorkItemOutput,
    create_work_items_summary,
)

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def main():
    """Demo work items serial execution"""

    logger.info("=" * 60)
    logger.info("Work Items Serial Execution Demo (PR-C)")
    logger.info("=" * 60)
    logger.info("")

    # Step 1: Define task with 3 work items
    logger.info("Step 1: Define Task")
    logger.info("-" * 60)
    task_title = "Implement frontend UI + backend API + integration tests"
    logger.info(f"Task: {task_title}")
    logger.info("")

    # Step 2: Create 3 work items (would be extracted from plan in production)
    logger.info("Step 2: Extract Work Items from Plan")
    logger.info("-" * 60)

    work_items = [
        WorkItem(
            item_id="wi_frontend",
            title="Implement frontend UI",
            description="""
            Create React components:
            - Landing page
            - Navigation bar
            - Contact form
            - Responsive styling
            """,
            dependencies=[],
        ),
        WorkItem(
            item_id="wi_backend",
            title="Implement backend API",
            description="""
            Create REST endpoints:
            - GET /api/health
            - POST /api/contact
            - Database models
            - Input validation
            """,
            dependencies=[],
        ),
        WorkItem(
            item_id="wi_tests",
            title="Implement integration tests",
            description="""
            Write end-to-end tests:
            - Frontend render tests
            - API endpoint tests
            - Full user flow tests
            """,
            dependencies=["wi_frontend", "wi_backend"],
        ),
    ]

    for idx, item in enumerate(work_items, 1):
        logger.info(f"  {idx}. {item.item_id}: {item.title}")
        if item.dependencies:
            logger.info(f"     Dependencies: {', '.join(item.dependencies)}")

    logger.info("")
    logger.info(f"✓ Extracted {len(work_items)} work items")
    logger.info("")

    # Step 3: Execute work items serially
    logger.info("Step 3: Execute Work Items Serially")
    logger.info("-" * 60)

    for idx, work_item in enumerate(work_items, 1):
        logger.info(f"\nExecuting work item {idx}/{len(work_items)}: {work_item.title}")

        # Mark as running
        work_item.mark_running()
        logger.info(f"  Status: RUNNING")
        logger.info(f"  Started at: {work_item.started_at}")

        # Simulate execution (in production, this calls sub-agent)
        logger.info(f"  → Sub-agent executing...")

        # Create mock output
        output = WorkItemOutput(
            files_changed=[
                f"src/{work_item.item_id}/module.py",
                f"src/{work_item.item_id}/utils.py",
                f"tests/test_{work_item.item_id}.py",
            ],
            commands_run=[
                "ruff check .",
                "pytest tests/",
                "mypy src/",
            ],
            tests_run=[
                {
                    "test_suite": f"test_{work_item.item_id}",
                    "passed": 8,
                    "failed": 0,
                    "skipped": 1,
                }
            ],
            evidence=f"✓ Successfully implemented {work_item.title}",
            handoff_notes=f"Work item {work_item.item_id} completed. All tests passing.",
        )

        # Mark as completed
        work_item.mark_completed(output)
        logger.info(f"  Status: COMPLETED")
        logger.info(f"  Completed at: {work_item.completed_at}")
        logger.info(f"  Files changed: {len(output.files_changed)}")
        logger.info(f"  Tests run: {len(output.tests_run)} suites")
        logger.info(f"  Evidence: {output.evidence}")

    logger.info("")
    logger.info(f"✓ All {len(work_items)} work items completed successfully")
    logger.info("")

    # Step 4: Create summary
    logger.info("Step 4: Create Work Items Summary")
    logger.info("-" * 60)

    summary = create_work_items_summary(work_items)

    logger.info(f"Total items: {summary.total_items}")
    logger.info(f"Completed: {summary.completed_count}")
    logger.info(f"Failed: {summary.failed_count}")
    logger.info(f"Overall status: {summary.overall_status.upper()}")

    if summary.all_succeeded:
        logger.info("")
        logger.info("✓ All work items succeeded!")

    logger.info("")

    # Step 5: Save summary artifact
    logger.info("Step 5: Save Summary Artifact")
    logger.info("-" * 60)

    artifact_dir = Path("demo_outputs")
    artifact_dir.mkdir(exist_ok=True)

    summary_path = artifact_dir / "work_items_summary.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary.to_dict(), f, indent=2, ensure_ascii=False)

    logger.info(f"✓ Saved summary to: {summary_path}")
    logger.info("")

    # Step 6: Show what happens next (DONE gates)
    logger.info("Step 6: Next Step - DONE Gates Verification")
    logger.info("-" * 60)
    logger.info("After work items complete, task transitions to 'verifying' state")
    logger.info("DONE gates will run:")
    logger.info("  1. doctor: Basic health check")
    logger.info("  2. smoke: Quick smoke tests")
    logger.info("  3. tests: Full test suite")
    logger.info("")
    logger.info("If all gates pass → task status = SUCCEEDED")
    logger.info("If any gate fails → return to PLANNING with failure context")
    logger.info("")

    # Summary
    logger.info("=" * 60)
    logger.info("Demo Complete!")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Key Features Demonstrated:")
    logger.info("  ✓ Work items extracted from plan")
    logger.info("  ✓ Serial execution (one by one)")
    logger.info("  ✓ Structured output from each work item")
    logger.info("  ✓ Aggregated summary artifact")
    logger.info("  ✓ Ready for DONE gates integration")
    logger.info("")
    logger.info(f"View full summary: {summary_path}")
    logger.info("")


if __name__ == "__main__":
    main()
