"""
Example: Using TaskService for State-Machine-Enforced Task Operations

This example demonstrates how to use the new TaskService layer to create
and manage tasks with proper state machine validation.

Created for Task #3: S3 - Enforce State Machine at core/task API
"""

from pathlib import Path
from agentos.core.task.service import TaskService
from agentos.core.task.errors import InvalidTransitionError


def example_successful_task_lifecycle():
    """Example: Complete task lifecycle from creation to completion"""
    print("\n" + "="*60)
    print("Example 1: Successful Task Lifecycle")
    print("="*60)

    service = TaskService()

    # 1. Create a draft task
    print("\n1. Creating draft task...")
    task = service.create_draft_task(
        title="Implement feature X",
        created_by="developer",
        metadata={
            "priority": "high",
            "component": "backend"
        }
    )
    print(f"   ✅ Task created: {task.task_id[:12]}... (status: {task.status})")

    # 2. Approve the task
    print("\n2. Approving task...")
    task = service.approve_task(
        task_id=task.task_id,
        actor="tech_lead",
        reason="Feature approved after review",
        metadata={"approved_by": "tech_lead", "review_id": "REV-123"}
    )
    print(f"   ✅ Task approved (status: {task.status})")

    # 3. Queue for execution
    print("\n3. Queuing task for execution...")
    task = service.queue_task(
        task_id=task.task_id,
        actor="scheduler",
        reason="Added to execution queue"
    )
    print(f"   ✅ Task queued (status: {task.status})")

    # 4. Start execution
    print("\n4. Starting task execution...")
    task = service.start_task(
        task_id=task.task_id,
        actor="runner_01",
        reason="Picked up by runner"
    )
    print(f"   ✅ Task started (status: {task.status})")

    # 5. Complete execution
    print("\n5. Completing task execution...")
    task = service.complete_task_execution(
        task_id=task.task_id,
        actor="runner_01",
        reason="All steps completed successfully"
    )
    print(f"   ✅ Task completed, entering verification (status: {task.status})")

    # 6. Verify task
    print("\n6. Verifying task...")
    task = service.verify_task(
        task_id=task.task_id,
        actor="qa_system",
        reason="All checks passed"
    )
    print(f"   ✅ Task verified (status: {task.status})")

    # 7. Mark as done
    print("\n7. Marking task as done...")
    task = service.mark_task_done(
        task_id=task.task_id,
        actor="developer",
        reason="Feature deployed to production"
    )
    print(f"   ✅ Task done (status: {task.status})")

    # 8. View transition history
    print("\n8. Viewing transition history...")
    history = service.get_transition_history(task.task_id)
    print(f"   📜 Total transitions: {len(history)}")
    for i, transition in enumerate(history, 1):
        print(f"      {i}. {transition['from_state']} → {transition['to_state']} "
              f"by {transition['actor']} ({transition['reason'][:50]}...)")


def example_task_failure_and_retry():
    """Example: Task fails and is retried"""
    print("\n" + "="*60)
    print("Example 2: Task Failure and Retry")
    print("="*60)

    service = TaskService()

    # Create and start task
    print("\n1. Creating and starting task...")
    task = service.create_draft_task(
        title="Deploy service Y",
        created_by="developer"
    )
    task = service.approve_task(task.task_id, "tech_lead", "Approved")
    task = service.queue_task(task.task_id, "scheduler", "Queued")
    task = service.start_task(task.task_id, "runner_02", "Running")
    print(f"   ✅ Task running: {task.task_id[:12]}... (status: {task.status})")

    # Task fails
    print("\n2. Task execution fails...")
    task = service.fail_task(
        task_id=task.task_id,
        actor="runner_02",
        reason="Connection timeout to database",
        metadata={"error_code": "TIMEOUT", "error_details": "DB connection failed"}
    )
    print(f"   ❌ Task failed (status: {task.status})")

    # Retry the task
    print("\n3. Retrying failed task...")
    task = service.retry_failed_task(
        task_id=task.task_id,
        actor="developer",
        reason="Fixed database connection issue, retrying",
        metadata={"fix": "Updated DB credentials"}
    )
    print(f"   🔄 Task queued for retry (status: {task.status})")

    # Continue to success
    print("\n4. Completing retry attempt...")
    task = service.start_task(task.task_id, "runner_03", "Retrying")
    task = service.complete_task_execution(task.task_id, "runner_03", "Completed")
    task = service.verify_task(task.task_id, "qa_system", "Verified")
    task = service.mark_task_done(task.task_id, "developer", "Done")
    print(f"   ✅ Task completed after retry (status: {task.status})")


def example_invalid_transition():
    """Example: Attempting invalid transitions raises errors"""
    print("\n" + "="*60)
    print("Example 3: Invalid Transition Handling")
    print("="*60)

    service = TaskService()

    # Create draft task
    print("\n1. Creating draft task...")
    task = service.create_draft_task(
        title="Test invalid transitions",
        created_by="developer"
    )
    print(f"   ✅ Task created: {task.task_id[:12]}... (status: {task.status})")

    # Try to skip approval (invalid)
    print("\n2. Attempting to queue task without approval...")
    try:
        service.queue_task(
            task_id=task.task_id,
            actor="scheduler",
            reason="Trying to skip approval"
        )
        print("   ❌ This should not happen!")
    except InvalidTransitionError as e:
        print(f"   ✅ Caught invalid transition: {e}")
        print(f"      - From: {e.from_state}")
        print(f"      - To: {e.to_state}")

    # Check valid transitions
    print("\n3. Getting valid transitions from draft state...")
    valid = service.get_valid_transitions(task.task_id)
    print(f"   ℹ️  Valid transitions: {', '.join(valid)}")


def example_task_cancellation():
    """Example: Canceling a task at different stages"""
    print("\n" + "="*60)
    print("Example 4: Task Cancellation")
    print("="*60)

    service = TaskService()

    # Cancel from draft
    print("\n1. Canceling task from draft state...")
    task1 = service.create_draft_task(title="Task to cancel 1", created_by="dev")
    task1 = service.cancel_task(
        task_id=task1.task_id,
        actor="developer",
        reason="Requirements changed, task no longer needed"
    )
    print(f"   ✅ Task canceled from draft (status: {task1.status})")

    # Cancel from running
    print("\n2. Canceling task from running state...")
    task2 = service.create_draft_task(title="Task to cancel 2", created_by="dev")
    task2 = service.approve_task(task2.task_id, "lead", "Approved")
    task2 = service.queue_task(task2.task_id, "scheduler", "Queued")
    task2 = service.start_task(task2.task_id, "runner", "Running")
    task2 = service.cancel_task(
        task_id=task2.task_id,
        actor="developer",
        reason="Critical bug found, stopping execution"
    )
    print(f"   ✅ Task canceled from running (status: {task2.status})")


def example_viewing_task_info():
    """Example: Viewing task information and history"""
    print("\n" + "="*60)
    print("Example 5: Viewing Task Information")
    print("="*60)

    service = TaskService()

    # Create and transition a task
    task = service.create_draft_task(
        title="Example task for viewing",
        created_by="developer",
        metadata={"project": "demo"}
    )
    task = service.approve_task(task.task_id, "lead", "Approved")
    task = service.queue_task(task.task_id, "scheduler", "Queued")

    # Get task details
    print("\n1. Getting task details...")
    task_info = service.get_task(task.task_id)
    print(f"   Task ID: {task_info.task_id}")
    print(f"   Title: {task_info.title}")
    print(f"   Status: {task_info.status}")
    print(f"   Created by: {task_info.created_by}")
    print(f"   Metadata: {task_info.metadata}")

    # Get valid transitions
    print("\n2. Getting valid transitions...")
    valid = service.get_valid_transitions(task.task_id)
    print(f"   From '{task_info.status}' can go to: {', '.join(valid)}")

    # Get transition history
    print("\n3. Getting transition history...")
    history = service.get_transition_history(task.task_id)
    for transition in history:
        print(f"   {transition['from_state']} → {transition['to_state']} "
              f"by {transition['actor']} at {transition['created_at'][:19]}")


def main():
    """Run all examples"""
    print("\n" + "🎯 " + "="*58)
    print("TaskService Usage Examples")
    print("Task #3: S3 - State Machine Enforcement")
    print("="*60)

    try:
        example_successful_task_lifecycle()
        example_task_failure_and_retry()
        example_invalid_transition()
        example_task_cancellation()
        example_viewing_task_info()

        print("\n" + "="*60)
        print("✅ All examples completed successfully!")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
