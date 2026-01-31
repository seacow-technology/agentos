"""
Demo: Chat Auto-trigger Runner (Task #1: PR-A)

This script demonstrates the event-driven flow:
    Chat /task command → Task creation → Auto-approve → Auto-queue → Immediate runner launch

Usage:
    python demo_chat_auto_trigger.py

Features demonstrated:
1. Intent recognition: Detects /task commands
2. Task creation: Creates task in DRAFT state
3. Auto-approval: Transitions DRAFT → APPROVED
4. Auto-queue: Transitions APPROVED → QUEUED
5. Immediate launch: Starts runner in background thread
6. State monitoring: Tracks task status changes

Expected output:
- Task created in <1s
- State transitions complete in <5s
- Task reaches RUNNING state quickly
"""

import time
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Import core modules
from agentos.core.task.service import TaskService
from agentos.core.runner.launcher import TaskLauncher


def simulate_chat_task_command(title: str) -> str:
    """
    Simulate /task command from chat

    This mimics what happens when a user types:
        /task <title>

    Returns:
        task_id of created task
    """
    logger.info(f"📩 Received chat command: /task {title}")

    # Step 1: Create task (DRAFT state)
    task_service = TaskService()
    task = task_service.create_draft_task(
        title=title,
        created_by="chat_demo",
        metadata={
            "source": "chat",
            "demo": True,
            "command": f"/task {title}"
        }
    )

    logger.info(f"✓ Created task {task.task_id} in {task.status} state")
    return task.task_id


def launch_task_immediately(task_id: str) -> bool:
    """
    Launch task immediately (auto-approve, queue, and start runner)

    This performs the full event-driven flow:
    1. Approve task (DRAFT → APPROVED)
    2. Queue task (APPROVED → QUEUED)
    3. Launch runner in background

    Returns:
        True if launch successful, False otherwise
    """
    logger.info(f"🚀 Launching task {task_id} immediately...")

    launcher = TaskLauncher(use_real_pipeline=False)  # Use simulation mode
    success = launcher.launch_task(task_id, actor="chat_launcher")

    if success:
        logger.info(f"✓ Task {task_id} launched successfully")
    else:
        logger.error(f"✗ Failed to launch task {task_id}")

    return success


def monitor_task_status(task_id: str, max_wait: float = 10.0):
    """
    Monitor task status changes

    Tracks state transitions and measures timing.

    Args:
        task_id: Task to monitor
        max_wait: Maximum seconds to wait for RUNNING state
    """
    logger.info(f"👀 Monitoring task {task_id} status...")

    task_service = TaskService()
    start_time = time.time()
    previous_status = None
    transitions = []

    while True:
        elapsed = time.time() - start_time

        if elapsed > max_wait:
            logger.warning(f"⏱️  Timeout after {elapsed:.1f}s")
            break

        # Get current task status
        task = task_service.get_task(task_id)
        if not task:
            logger.error(f"Task {task_id} not found!")
            break

        current_status = task.status

        # Log status change
        if current_status != previous_status:
            transitions.append((current_status, elapsed))
            logger.info(
                f"  [{elapsed:5.1f}s] Status: {current_status}"
            )
            previous_status = current_status

        # Check if reached RUNNING state
        if current_status.upper() == "RUNNING":
            logger.info(f"✓ Task reached RUNNING state in {elapsed:.1f}s")
            break

        # Check if task failed
        if current_status.upper() in ["FAILED", "CANCELED"]:
            logger.error(f"✗ Task ended in {current_status} state")
            break

        # Small delay between checks
        time.sleep(0.2)

    # Print transition summary
    logger.info(f"\n📊 Transition Summary:")
    logger.info(f"   Total time: {elapsed:.1f}s")
    logger.info(f"   Transitions: {len(transitions)}")
    for status, t in transitions:
        logger.info(f"     {status:12s} at {t:5.1f}s")


def main():
    """Main demo function"""
    print("\n" + "=" * 70)
    print("🤖 Chat Auto-trigger Runner Demo (Task #1: PR-A)")
    print("=" * 70 + "\n")

    # Step 1: Simulate /task command
    print("📝 Step 1: Simulate chat /task command")
    print("-" * 70)
    task_title = f"Demo task created at {datetime.now().strftime('%H:%M:%S')}"
    task_id = simulate_chat_task_command(task_title)
    print()

    # Step 2: Launch task immediately
    print("🚀 Step 2: Launch task immediately")
    print("-" * 70)
    success = launch_task_immediately(task_id)
    print()

    if not success:
        print("❌ Launch failed. Check logs above for details.\n")
        return

    # Step 3: Monitor status
    print("👀 Step 3: Monitor task status transitions")
    print("-" * 70)
    monitor_task_status(task_id, max_wait=10.0)
    print()

    # Step 4: Show final result
    print("✅ Step 4: Final result")
    print("-" * 70)
    task_service = TaskService()
    task = task_service.get_task(task_id)

    if task:
        print(f"Task ID: {task.task_id}")
        print(f"Title: {task.title}")
        print(f"Status: {task.status}")
        print(f"Created by: {task.created_by}")

        # Get transition history
        history = task_service.get_transition_history(task_id)
        print(f"\nTransition history ({len(history)} transitions):")
        for h in history:
            print(f"  {h['from_state']:12s} → {h['to_state']:12s}  ({h['actor']})")
    else:
        print("❌ Task not found!")

    print("\n" + "=" * 70)
    print("Demo complete!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user\n")
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        print(f"\n❌ Demo failed: {e}\n")
