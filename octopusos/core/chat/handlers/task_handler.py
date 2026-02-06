"""/task command handler - Create task from conversation

This handler implements the chat → draft → approve workflow.
Chat can ONLY create tasks in DRAFT state. Tasks must be explicitly
approved before they can be executed.
"""

from typing import List, Dict, Any
import logging
import asyncio

from agentos.core.chat.commands import CommandResult, get_registry
from agentos.core.chat.service import ChatService
from agentos.core.chat.workflow import get_workflow
from agentos.core.task.routing_service import TaskRoutingService

logger = logging.getLogger(__name__)


def task_handler(command: str, args: List[str], context: Dict[str, Any]) -> CommandResult:
    """Handler for /task command

    Usage: /task [title]

    Creates a new DRAFT task and associates it with the current chat session.

    IMPORTANT: Chat can ONLY create DRAFT tasks. Tasks must be approved
    before execution using the approve workflow.
    """
    session_id = context.get("session_id")
    if not session_id:
        return CommandResult.error_result("No session context")

    # Get title from args or generate default
    if args:
        title = " ".join(args)
    else:
        # Get session title as default
        try:
            chat_service = context.get("chat_service") or ChatService()
            session = chat_service.get_session(session_id)
            title = f"Task from: {session.title}"
        except Exception:
            title = "Task from chat session"

    try:
        # Use workflow to create draft task (enforces chat → draft → approve pattern)
        workflow = get_workflow()

        # Create task in DRAFT state (ENFORCED by workflow)
        result = workflow.create_draft_from_chat(
            title=title,
            session_id=session_id,
            created_by="chat_mode",
            metadata={"chat_command": "/task"}
        )

        task = result["task"]

        # Add lineage entry
        workflow.task_service.add_lineage(
            task_id=task.task_id,
            kind="chat_session",
            ref_id=session_id,
            phase="intent_analysis",
            metadata={"command": "/task"}
        )

        # Update chat session to link to task
        chat_service = context.get("chat_service") or ChatService()
        session = chat_service.get_session(session_id)
        chat_service.update_session_metadata(
            session_id,
            {"task_id": task.task_id}
        )

        logger.info(f"Created DRAFT task {task.task_id} from chat session {session_id}")

        # PR-2: Route the task
        routing_result = None
        try:
            routing_service = TaskRoutingService()

            # Build task spec from available context
            task_spec = {
                "title": title,
                "metadata": {
                    "source": "chat",
                    "session_id": session_id,
                }
            }

            # Try to get recent chat history for better routing context
            try:
                messages = chat_service.get_messages(session_id, limit=5)
                if messages:
                    recent_messages = "\n".join([f"{m.role}: {m.content[:200]}" for m in messages[-5:]])
                    task_spec["description"] = recent_messages
            except Exception as msg_err:
                logger.debug(f"Could not fetch messages for routing context: {msg_err}")

            # Route the task (async)
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create a new thread to run async operation
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, routing_service.route_new_task(task.task_id, task_spec))
                    route_plan = future.result(timeout=5.0)  # 5 second timeout
            else:
                route_plan = asyncio.run(routing_service.route_new_task(task.task_id, task_spec))

            routing_result = {
                "selected": route_plan.selected,
                "fallback": route_plan.fallback[:2] if len(route_plan.fallback) > 2 else route_plan.fallback,
                "reasons": route_plan.reasons[:3],  # Top 3 reasons
                "score": route_plan.scores.get(route_plan.selected, 0.0),
            }

            logger.info(f"Task {task.task_id} routed to {route_plan.selected}")

        except Exception as route_err:
            logger.warning(f"Task routing failed, task created without routing: {route_err}")
            routing_result = {"error": str(route_err)}

        # Build response message with clear draft → approve workflow guidance
        message = f"✓ Created DRAFT task: **{task.task_id[:12]}...** - {title}\n\n"
        message += f"**Status:** {task.status.upper()}\n"
        message += f"**Task ID:** `{task.task_id}`\n\n"

        # Routing information
        if routing_result and "error" not in routing_result:
            message += f"**Routing:**\n"
            message += f"- Selected: `{routing_result['selected']}`\n"
            message += f"- Score: {routing_result['score']:.2f}\n"
            message += f"- Reasons: {', '.join(routing_result['reasons'])}\n"
            if routing_result['fallback']:
                message += f"- Fallback: {', '.join(routing_result['fallback'])}\n"
            message += "\n"
        elif routing_result and "error" in routing_result:
            message += f"⚠️  Routing failed: {routing_result['error']}\n\n"

        # Clear approval workflow guidance
        message += "---\n\n"
        message += "**⚠️  This task is in DRAFT state and cannot execute yet.**\n\n"
        message += "**Why approval is needed:**\n"
        message += "- Ensures task is reviewed before execution\n"
        message += "- Validates task requirements and routing\n"
        message += "- Prevents accidental or unauthorized execution\n\n"
        message += "**How to approve this task:**\n\n"
        message += "**Option 1: Using Python API**\n"
        message += "```python\n"
        message += "from agentos.core.task.service import TaskService\n"
        message += "ts = TaskService()\n"
        message += f"task = ts.approve_task(\n"
        message += f"    task_id='{task.task_id}',\n"
        message += f"    actor='user',\n"
        message += f"    reason='Approved for execution'\n"
        message += f")\n"
        message += "```\n\n"
        message += "**Option 2: Using CLI** (if available)\n"
        message += f"```bash\n"
        message += f"agentos task approve {task.task_id}\n"
        message += "```\n\n"
        message += "After approval, the task will transition to APPROVED → QUEUED → RUNNING.\n"

        return CommandResult.success_result(
            message=message,
            data={
                "task_id": task.task_id,
                "title": title,
                "status": task.status,
                "session_id": session_id,
                "routing": routing_result,
                "next_action": "approve",
            }
        )
    
    except Exception as e:
        logger.error(f"Task command failed: {e}", exc_info=True)
        return CommandResult.error_result(f"Failed to create task: {str(e)}")


def register_task_command():
    """Register /task command"""
    registry = get_registry()
    registry.register(
        "task",
        task_handler,
        "Create a task from the conversation"
    )
