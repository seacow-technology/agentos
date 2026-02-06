"""
Chat to Task Workflow

Defines the workflow for creating tasks from chat interactions.
This module enforces the chat → draft → approve pattern.

Key Principles:
1. Chat can ONLY create DRAFT tasks (never directly executable)
2. Tasks must be explicitly approved before execution
3. Clear guidance is provided to users on approval workflow
4. State machine transitions are enforced through TaskService

Workflow:
    Chat Input → Create DRAFT Task → (User Approval) → Execute Task

State Flow:
    DRAFT → APPROVED → QUEUED → RUNNING → VERIFYING → VERIFIED → DONE
"""

from typing import Dict, Any, Optional
import logging

from agentos.core.task.service import TaskService
from agentos.core.task.states import TaskState

logger = logging.getLogger(__name__)


class ChatTaskWorkflow:
    """
    Chat Task Workflow Manager

    Manages the workflow from chat to task creation and approval.
    Enforces that chat can only create DRAFT tasks.
    """

    def __init__(self, task_service: Optional[TaskService] = None):
        """
        Initialize workflow manager

        Args:
            task_service: TaskService instance (creates new if not provided)
        """
        self.task_service = task_service or TaskService()

    def create_draft_from_chat(
        self,
        title: str,
        session_id: str,
        created_by: str = "chat_mode",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a DRAFT task from chat interaction

        This is the ONLY way chat should create tasks. It enforces:
        1. Task starts in DRAFT state
        2. Cannot be executed without approval
        3. Provides clear approval instructions

        Args:
            title: Task title
            session_id: Chat session ID
            created_by: Creator identifier
            metadata: Optional task metadata

        Returns:
            Dict containing task and workflow guidance
        """
        # Ensure metadata includes chat context
        if metadata is None:
            metadata = {}

        metadata.update({
            "source": "chat",
            "chat_session_id": session_id,
            "workflow": "chat_to_task",
        })

        # Create DRAFT task (enforced by TaskService)
        task = self.task_service.create_draft_task(
            title=title,
            session_id=session_id,
            created_by=created_by,
            metadata=metadata
        )

        logger.info(
            f"Created DRAFT task {task.task_id} from chat session {session_id}"
        )

        # Return task with workflow guidance
        return {
            "task": task,
            "status": task.status,
            "workflow_stage": "draft_created",
            "next_action": "approve",
            "approval_guidance": self._get_approval_guidance(task.task_id),
        }

    def approve_task(
        self,
        task_id: str,
        actor: str,
        reason: str = "Approved from chat workflow"
    ) -> Dict[str, Any]:
        """
        Approve a DRAFT task

        Args:
            task_id: Task ID
            actor: Who is approving
            reason: Reason for approval

        Returns:
            Dict containing approved task and next steps
        """
        task = self.task_service.approve_task(
            task_id=task_id,
            actor=actor,
            reason=reason
        )

        logger.info(f"Approved task {task_id} by {actor}")

        return {
            "task": task,
            "status": task.status,
            "workflow_stage": "approved",
            "next_action": "queue_for_execution",
            "message": f"Task {task_id} approved. Ready to be queued for execution.",
        }

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get task status and workflow position

        Args:
            task_id: Task ID

        Returns:
            Dict containing task status and workflow info
        """
        task = self.task_service.get_task(task_id)

        if not task:
            return {
                "error": "Task not found",
                "task_id": task_id,
            }

        # Determine workflow stage
        workflow_stage = self._get_workflow_stage(task.status)
        next_action = self._get_next_action(task.status)

        return {
            "task_id": task.task_id,
            "title": task.title,
            "status": task.status,
            "workflow_stage": workflow_stage,
            "next_action": next_action,
            "can_execute": task.status not in [TaskState.DRAFT.value],
        }

    def _get_workflow_stage(self, status: str) -> str:
        """Map task status to workflow stage"""
        workflow_map = {
            TaskState.DRAFT.value: "draft_created",
            TaskState.APPROVED.value: "approved",
            TaskState.QUEUED.value: "queued",
            TaskState.RUNNING.value: "executing",
            TaskState.VERIFYING.value: "verifying",
            TaskState.VERIFIED.value: "verified",
            TaskState.DONE.value: "completed",
            TaskState.FAILED.value: "failed",
            TaskState.CANCELED.value: "canceled",
        }
        return workflow_map.get(status, "unknown")

    def _get_next_action(self, status: str) -> str:
        """Get next action based on current status"""
        action_map = {
            TaskState.DRAFT.value: "approve",
            TaskState.APPROVED.value: "queue_for_execution",
            TaskState.QUEUED.value: "wait_for_execution",
            TaskState.RUNNING.value: "wait_for_completion",
            TaskState.VERIFYING.value: "wait_for_verification",
            TaskState.VERIFIED.value: "mark_as_done",
            TaskState.DONE.value: "completed",
            TaskState.FAILED.value: "review_or_retry",
            TaskState.CANCELED.value: "none",
        }
        return action_map.get(status, "unknown")

    def _get_approval_guidance(self, task_id: str) -> Dict[str, str]:
        """Generate approval guidance for user"""
        return {
            "why_needed": (
                "Tasks created from chat must be approved to ensure "
                "they are reviewed before execution. This prevents "
                "accidental or unauthorized task execution."
            ),
            "python_api": f"""
from agentos.core.task.service import TaskService
ts = TaskService()
task = ts.approve_task(
    task_id='{task_id}',
    actor='user',
    reason='Approved for execution'
)
""".strip(),
            "cli_command": f"agentos task approve {task_id}",
            "web_ui": f"Navigate to task details and click 'Approve' button",
        }

    def format_draft_response(
        self,
        task_id: str,
        title: str,
        status: str,
        routing_result: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Format a user-friendly response for draft task creation

        Args:
            task_id: Task ID
            title: Task title
            status: Task status
            routing_result: Optional routing information

        Returns:
            Formatted message string
        """
        message = f"✓ Created DRAFT task: **{task_id[:12]}...** - {title}\n\n"
        message += f"**Status:** {status.upper()}\n"
        message += f"**Task ID:** `{task_id}`\n\n"

        # Routing information
        if routing_result and "error" not in routing_result:
            message += "**Routing:**\n"
            message += f"- Selected: `{routing_result['selected']}`\n"
            message += f"- Score: {routing_result['score']:.2f}\n"
            message += f"- Reasons: {', '.join(routing_result['reasons'])}\n"
            if routing_result.get('fallback'):
                message += f"- Fallback: {', '.join(routing_result['fallback'])}\n"
            message += "\n"
        elif routing_result and "error" in routing_result:
            message += f"⚠️  Routing failed: {routing_result['error']}\n\n"

        # Approval guidance
        guidance = self._get_approval_guidance(task_id)

        message += "---\n\n"
        message += "**⚠️  This task is in DRAFT state and cannot execute yet.**\n\n"
        message += "**Why approval is needed:**\n"
        message += f"{guidance['why_needed']}\n\n"
        message += "**How to approve this task:**\n\n"
        message += "**Option 1: Using Python API**\n"
        message += f"```python\n{guidance['python_api']}\n```\n\n"
        message += "**Option 2: Using CLI** (if available)\n"
        message += f"```bash\n{guidance['cli_command']}\n```\n\n"
        message += "After approval, the task will transition to APPROVED → QUEUED → RUNNING.\n"

        return message


# Singleton instance for convenience
_workflow_instance: Optional[ChatTaskWorkflow] = None


def get_workflow() -> ChatTaskWorkflow:
    """
    Get singleton workflow instance

    Returns:
        ChatTaskWorkflow instance
    """
    global _workflow_instance
    if _workflow_instance is None:
        _workflow_instance = ChatTaskWorkflow()
    return _workflow_instance
