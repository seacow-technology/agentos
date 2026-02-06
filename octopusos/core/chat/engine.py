"""Chat Engine - Orchestrates message sending, context building, and model invocation"""

from typing import Optional, Dict, Any
import logging
import json
import re

from agentos.core.chat.service import ChatService
from agentos.core.chat.context_builder import ContextBuilder, ContextBudget
from agentos.core.chat.commands import parse_command, get_registry
from agentos.core.chat.slash_command_router import (
    SlashCommandRouter,
    build_command_not_found_response,
    build_extension_disabled_response
)
from agentos.core.time import utc_now
from agentos.core.coordinator.model_router import ModelRouter
from agentos.core.task.manager import TaskManager
from agentos.core.memory.service import MemoryService
from agentos.core.extensions.registry import ExtensionRegistry
from agentos.core.chat.models.external_info import (
    ExternalInfoDeclaration,
    ExternalInfoAction
)
from agentos.core.chat.models_base import ChatMessage
from agentos.core.audit import log_audit_event
from agentos.core.chat.info_need_classifier import InfoNeedClassifier
from agentos.core.chat.models.info_need import DecisionAction
from agentos.core.chat.multi_intent_splitter import MultiIntentSplitter, SubQuestion
from agentos.core.chat.auto_comm_policy import AutoCommPolicy, AutoCommDecision
from agentos.core.chat.selfcheck import run_startup_checks
from agentos.core.chat.rate_limiter import rate_limiter, dedup_checker
from agentos.core.chat.response_guardian import check_response_with_guardian

# Import and register all slash commands
from agentos.core.chat.handlers import (
    register_help_command,
    register_summary_command,
    register_extract_command,
    register_task_command,
    register_model_command,
    register_context_command,
    register_stream_command,
    register_export_command,
    register_comm_command
)

logger = logging.getLogger(__name__)


class ChatEngine:
    """Main engine for Chat Mode"""
    
    def __init__(
        self,
        chat_service: Optional[ChatService] = None,
        context_builder: Optional[ContextBuilder] = None,
        model_router: Optional[ModelRouter] = None,
        task_manager: Optional[TaskManager] = None,
        memory_service: Optional[MemoryService] = None,
        extension_registry: Optional[ExtensionRegistry] = None,
        slash_command_router: Optional[SlashCommandRouter] = None
    ):
        """Initialize ChatEngine

        Args:
            chat_service: ChatService instance
            context_builder: ContextBuilder instance
            model_router: ModelRouter instance
            task_manager: TaskManager instance
            memory_service: MemoryService instance
            extension_registry: ExtensionRegistry instance
            slash_command_router: SlashCommandRouter instance
        """
        self.chat_service = chat_service or ChatService()
        self.context_builder = context_builder or ContextBuilder()
        self.model_router = model_router or ModelRouter(policy={})
        self.task_manager = task_manager or TaskManager()
        self.memory_service = memory_service or MemoryService()

        # Initialize extension support
        from pathlib import Path
        from agentos.store import get_store_path

        self.extension_registry = extension_registry or ExtensionRegistry()

        # Use project's store/extensions directory for slash command router
        if slash_command_router is None:
            extensions_dir = Path(get_store_path("extensions"))
            slash_command_router = SlashCommandRouter(
                self.extension_registry,
                extensions_dir=extensions_dir
            )

        self.slash_command_router = slash_command_router

        # Initialize InfoNeedClassifier
        self.info_need_classifier = InfoNeedClassifier(
            config={},
            llm_callable=self._create_llm_callable_for_classifier()
        )
        logger.info("ChatEngine initialized with InfoNeedClassifier")

        # Initialize AutoCommPolicy
        self.auto_comm_policy = AutoCommPolicy(config={})
        logger.info("ChatEngine initialized with AutoCommPolicy")

        # Initialize MultiIntentSplitter (Task #25)
        self.multi_intent_splitter = MultiIntentSplitter(
            config={
                "min_length": 5,
                "max_splits": 3,
                "enable_context": True,
            }
        )
        logger.info("ChatEngine initialized with MultiIntentSplitter")

        # Register built-in slash commands
        self._register_commands()

        # Startup self-check (fail-fast for broken modules)
        try:
            run_startup_checks()
        except RuntimeError as e:
            logger.critical(f"ChatEngine startup checks failed: {e}")
            raise
    
    def _register_commands(self):
        """Register all slash commands"""
        register_help_command()
        register_summary_command()
        register_extract_command()
        register_task_command()
        register_model_command()
        register_context_command()
        register_stream_command()
        register_export_command()
        register_comm_command()
        logger.info("Registered slash commands")
    
    def send_message(
        self,
        session_id: str,
        user_input: str,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Send a message and get response
        
        Args:
            session_id: Chat session ID
            user_input: User's input message
            stream: Whether to stream the response
        
        Returns:
            Response dictionary with message and metadata
        """
        logger.info(f"Processing message for session {session_id}")

        # 1. Save user message
        user_message = self.chat_service.add_message(
            session_id=session_id,
            role="user",
            content=user_input
        )

        # 2. Check if it's an extension slash command first
        if self.slash_command_router.is_slash_command(user_input):
            route = self.slash_command_router.route(user_input)

            if route is None:
                # Command not found - check if it's a built-in command
                command, args, remaining = parse_command(user_input)
                if command:
                    # It's a built-in command
                    return self._execute_command(session_id, command, args, remaining, stream)
                else:
                    # Unknown command - return helpful error
                    error_response = build_command_not_found_response(user_input.split()[0])
                    error_message = error_response['message']

                    # Save error message
                    self.chat_service.add_message(
                        session_id=session_id,
                        role="assistant",
                        content=error_message,
                        metadata={"error": "command_not_found", "response": error_response}
                    )

                    if stream:
                        # Return generator for streaming
                        def error_generator():
                            yield error_message
                        return error_generator()
                    else:
                        return {
                            "message_id": None,
                            "content": error_message,
                            "role": "assistant",
                            "metadata": error_response,
                            "context": {}
                        }

            elif not route.extension_enabled:
                # Extension is disabled
                error_response = build_extension_disabled_response(route)
                error_message = error_response['message']

                # Save error message
                self.chat_service.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=error_message,
                    metadata={"error": "extension_disabled", "response": error_response}
                )

                if stream:
                    # Return generator for streaming
                    def error_generator():
                        yield error_message
                    return error_generator()
                else:
                    return {
                        "message_id": None,
                        "content": error_message,
                        "role": "assistant",
                        "metadata": error_response,
                        "context": {}
                    }

            else:
                # Route to extension capability
                return self._execute_extension_command(session_id, route, stream)

        # 2b. Check if it's a built-in slash command
        command, args, remaining = parse_command(user_input)

        if command:
            return self._execute_command(session_id, command, args, remaining, stream)

        # 2c. Check for multi-intent splitting (Task #25)
        try:
            if self.multi_intent_splitter.should_split(user_input):
                logger.info("Multi-intent detected, processing with splitter")
                # Process as multi-intent
                import asyncio
                return asyncio.run(self._process_multi_intent(
                    message=user_input,
                    session_id=session_id,
                    stream=stream
                ))
        except Exception as e:
            # If multi-intent processing fails, fall back to single intent
            logger.warning(f"Multi-intent processing failed: {e}, falling back to single intent")

        # 3. Classify message to determine action (TASK 5 Integration)
        session = self.chat_service.get_session(session_id)
        classification_result = None

        # Build context dict for classification handlers
        classification_context = {
            "session_id": session_id,
            "execution_phase": session.metadata.get("execution_phase", "planning"),
            "conversation_mode": session.metadata.get("conversation_mode", "chat"),
            "task_id": session.task_id
        }

        try:
            import asyncio
            # Classify the message
            classification_result = asyncio.run(self.info_need_classifier.classify(user_input))

            logger.info(
                f"Message classified: type={classification_result.info_need_type.value}, "
                f"action={classification_result.decision_action.value}, "
                f"confidence={classification_result.confidence_level.value}"
            )

            # Route based on classification decision
            if classification_result.decision_action == DecisionAction.LOCAL_CAPABILITY:
                # Handle ambient state queries or local deterministic operations
                return self._handle_ambient_state(session_id, user_input, classification_result, classification_context, stream)

            elif classification_result.decision_action == DecisionAction.REQUIRE_COMM:
                # Requires external information
                return self._handle_external_info_need(session_id, user_input, classification_result, classification_context, stream)

            elif classification_result.decision_action == DecisionAction.SUGGEST_COMM:
                # Can answer but suggest verification
                return self._handle_with_comm_suggestion(session_id, user_input, classification_result, classification_context, stream)

            # DecisionAction.DIRECT_ANSWER - continue to normal flow
            logger.info("Direct answer mode - proceeding with normal message flow")

        except Exception as e:
            # Classification failed - fallback to normal flow
            logger.warning(f"Classification failed, falling back to direct answer: {e}", exc_info=True)

        # 5. Normal message - build context
        rag_enabled = session.metadata.get("rag_enabled", True)
        
        context_pack = self.context_builder.build(
            session_id=session_id,
            user_input=user_input,
            rag_enabled=rag_enabled,
            memory_enabled=True
        )

        # 6. Route to model
        model_route = session.metadata.get("model_route", "local")

        # 7. Get response from model
        if stream:
            # Return a stream generator
            return self._stream_response(session_id, context_pack, model_route)
        else:
            response_content, response_metadata = self._invoke_model(context_pack, model_route, session_id)

            # 8. Save assistant message
            message_metadata = {
                "model_route": model_route,
                "context_tokens": context_pack.metadata.get("total_tokens"),
                "rag_chunks": len(context_pack.audit.get("rag_chunk_ids", [])),
                "memory_facts": len(context_pack.audit.get("memory_ids", []))
            }

            # P1-7: Link budget snapshot for audit traceability
            if context_pack.snapshot_id:
                message_metadata["context_snapshot_id"] = context_pack.snapshot_id

            # Merge response metadata (truncation info)
            if response_metadata:
                message_metadata.update(response_metadata)

            assistant_message = self.chat_service.add_message(
                session_id=session_id,
                role="assistant",
                content=response_content,
                metadata=message_metadata
            )

            logger.info(f"Generated response for session {session_id}: {assistant_message.message_id}")

            # NEW (Task #5): Extract memories from conversation pair
            # This can capture implicit information and commitments
            try:
                import asyncio
                asyncio.create_task(self._extract_memories_from_conversation(
                    user_message=user_message,
                    assistant_message=assistant_message,
                    session_id=session_id
                ))
            except RuntimeError:
                # No event loop running, skip async extraction
                # (extraction already triggered by add_message)
                pass
            except Exception as e:
                logger.warning(f"Failed to schedule conversation memory extraction: {e}")

            return {
                "message_id": assistant_message.message_id,
                "content": response_content,
                "role": "assistant",
                "metadata": assistant_message.metadata,
                "context": context_pack.metadata
            }
    
    def _stream_response(
        self,
        session_id: str,
        context_pack: Any,
        model_route: str = "local"
    ):
        """Stream response from model

        Args:
            session_id: Session ID
            context_pack: ContextPack with assembled messages
            model_route: "local" or "cloud"

        Yields:
            Text chunks
        """
        logger.info(f"Streaming {model_route} model response")

        try:
            from agentos.core.chat.adapters import get_adapter

            # Get session to read provider/model preferences
            session = self.chat_service.get_session(session_id)

            logger.info(f"Session metadata: {session.metadata}")

            # Determine provider from session metadata (with fallback)
            provider = session.metadata.get("provider")
            if not provider:
                provider = "ollama" if model_route == "local" else "openai"
                logger.warning(f"No provider in metadata, using fallback: {provider}")

            # Get model name if specified
            model = session.metadata.get("model")

            logger.info(f"Using provider: {provider}, model: {model}")

            adapter = get_adapter(provider, model)
            
            # Check health
            is_healthy, status = adapter.health_check()
            if not is_healthy:
                yield f"⚠️ Model unavailable: {status}"
                return
            
            # Collect full response for saving
            full_response = []
            
            # Stream response
            for chunk in adapter.generate_stream(
                messages=context_pack.messages,
                temperature=0.7,
                max_tokens=2000
            ):
                full_response.append(chunk)
                yield chunk
            
            # Save complete message
            response_content = "".join(full_response)

            # Response Guardian: Check streamed response for capability denials
            session = self.chat_service.get_session(session_id)
            final_response, guardian_metadata = check_response_with_guardian(
                response_content=response_content,
                session_metadata=session.metadata,
                classification=None
            )

            message_metadata = {
                "model_route": model_route,
                "context_tokens": context_pack.metadata.get("total_tokens"),
                "streamed": True
            }

            # Add guardian metadata if response was modified
            if guardian_metadata:
                message_metadata['response_guardian'] = guardian_metadata

            # P1-7: Link budget snapshot for audit traceability
            if context_pack.snapshot_id:
                message_metadata["context_snapshot_id"] = context_pack.snapshot_id

            self.chat_service.add_message(
                session_id=session_id,
                role="assistant",
                content=final_response,  # Use guardian-checked response
                metadata=message_metadata
            )
        
        except Exception as e:
            logger.error(f"Streaming failed: {e}", exc_info=True)
            yield f"\n\n⚠️ Streaming error: {str(e)}"
    
    def _execute_extension_command(
        self,
        session_id: str,
        route,
        stream: bool = False
    ):
        """Execute an extension slash command

        Args:
            session_id: Session ID
            route: CommandRoute from slash_command_router
            stream: Whether to stream response

        Returns:
            Response dictionary or generator
        """
        logger.info(
            f"Executing extension command: {route.command_name} "
            f"-> {route.extension_id}.{route.action_id}"
        )

        try:
            # Import runner components
            from agentos.core.capabilities.runner_base import get_runner
            from agentos.core.capabilities.runner_base.base import Invocation

            # Get extension name from registry
            extension_record = self.extension_registry.get_extension(route.extension_id)
            extension_name = extension_record.name if extension_record else route.extension_id

            # Create invocation
            invocation = Invocation(
                extension_id=route.extension_id,
                action_id=route.action_id or "default",
                session_id=session_id,
                args=route.args,
                metadata={
                    "command_name": route.command_name
                }
            )

            # Get runner with correct extensions directory
            from pathlib import Path
            from agentos.store import get_store_path

            if route.runner in ("builtin", "exec.python_handler", "default"):
                # For builtin runner, use project's extensions directory
                extensions_dir = Path(get_store_path("extensions"))
                runner = get_runner(route.runner, extensions_dir=extensions_dir)
            else:
                runner = get_runner(route.runner)

            # Execute
            logger.debug(f"Executing with runner: {route.runner}")
            result = runner.run(invocation)

            # Build result message
            if result.success:
                result_message = result.output
            else:
                result_message = f"Execution failed: {result.error or 'Unknown error'}"

            # Save message with extension metadata for WebUI display
            self.chat_service.add_message(
                session_id=session_id,
                role="assistant",
                content=result_message,
                metadata={
                    "is_extension_output": True,
                    "extension_id": route.extension_id,
                    "extension_name": extension_name,
                    "action": route.action_id or "default",
                    "command": route.command_name,
                    "extension_command": route.command_name,
                    "action_id": route.action_id,
                    "args": route.args,
                    "status": "succeeded" if result.success else "failed"
                }
            )

            if stream:
                def result_generator():
                    yield result_message
                return result_generator()
            else:
                return {
                    "message_id": None,
                    "content": result_message,
                    "role": "assistant",
                    "metadata": {
                        "extension_command": route.command_name,
                        "success": result.success
                    },
                    "context": {}
                }

        except Exception as e:
            logger.error(f"Failed to execute extension command: {e}", exc_info=True)
            error_message = f"Failed to execute '{route.command_name}': {str(e)}"

            self.chat_service.add_message(
                session_id=session_id,
                role="assistant",
                content=error_message,
                metadata={
                    "extension_command": route.command_name,
                    "error": str(e)
                }
            )

            if stream:
                def error_generator():
                    yield error_message
                return error_generator()
            else:
                return {
                    "message_id": None,
                    "content": error_message,
                    "role": "assistant",
                    "metadata": {"error": str(e)},
                    "context": {}
                }

    def _execute_command(
        self,
        session_id: str,
        command: str,
        args: list,
        remaining: Optional[str],
        stream: bool = False
    ):
        """Execute a built-in slash command

        Args:
            session_id: Session ID
            command: Command name
            args: Command arguments
            remaining: Remaining text after command
            stream: Whether to return a generator for streaming

        Returns:
            Command result as dict (stream=False) or generator (stream=True)
        """
        logger.info(f"Executing built-in command /{command} in session {session_id}")

        # Get session for metadata
        session = self.chat_service.get_session(session_id)

        # Build command context
        context = {
            "session_id": session_id,
            "chat_service": self.chat_service,
            "task_manager": self.task_manager,
            "memory_service": self.memory_service,
            "router": self.slash_command_router,
            "execution_phase": session.metadata.get("execution_phase", "planning"),
            "task_id": session.task_id
        }

        # Execute command
        registry = get_registry()
        result = registry.execute(command, args, context)

        # Save command result as assistant message
        if result.should_display:
            self.chat_service.add_message(
                session_id=session_id,
                role="assistant",
                content=result.message,
                metadata={
                    "command": f"/{command}",
                    "command_success": result.success,
                    "command_data": result.data
                }
            )

        if stream:
            # Return generator for streaming
            def command_result_generator():
                yield result.message
            return command_result_generator()
        else:
            return {
                "message_id": None,
                "content": result.message,
                "role": "assistant",
                "metadata": {
                    "command": f"/{command}",
                    "success": result.success
                },
                "context": {}
            }
    
    def _create_llm_callable_for_classifier(self):
        """Create an LLM callable for InfoNeedClassifier

        This provides a simple async callable that the classifier can use
        to invoke the LLM for confidence evaluation.

        Returns:
            Async callable that takes a prompt and returns LLM response
        """
        async def llm_callable(prompt: str) -> str:
            """Invoke LLM with a simple prompt"""
            try:
                from agentos.core.chat.adapters import get_adapter

                # Use a fast local model for classification
                adapter = get_adapter("ollama", "qwen2.5:14b")

                # Format as messages
                messages = [{"role": "user", "content": prompt}]

                # Generate response
                response, _ = adapter.generate(
                    messages=messages,
                    temperature=0.3,  # Lower temperature for more deterministic classification
                    max_tokens=200,   # Small response for classification
                    stream=False
                )

                return response

            except Exception as e:
                logger.error(f"LLM callable for classifier failed: {e}")
                # Return default medium confidence
                import json
                return json.dumps({
                    "confidence": "medium",
                    "reason": "uncertain"
                })

        return llm_callable

    def _handle_ambient_state(
        self,
        session_id: str,
        message: str,
        classification: Any,
        context: Dict[str, Any],
        stream: bool = False
    ):
        """Handle ambient state queries using local capabilities

        This handles queries about system state, configuration, time, phase, etc.
        that can be answered without LLM generation.

        Args:
            session_id: Session ID
            message: User's message
            classification: ClassificationResult from classifier
            context: Context dict with session info
            stream: Whether to stream response

        Returns:
            Response dict or generator
        """
        logger.info("Using local capability for ambient state query")

        msg_lower = message.lower()

        # Time queries
        if any(word in msg_lower for word in ["time", "几点", "when"]):
            from datetime import datetime, timezone
            current_time = utc_now().strftime("%Y-%m-%d %H:%M:%S")
            response_content = f"Current time: {current_time}"

        # Phase queries
        elif any(word in msg_lower for word in ["phase", "阶段", "stage"]):
            phase = context.get("execution_phase", "unknown")
            response_content = f"Current execution phase: {phase}"

        # Session queries
        elif any(word in msg_lower for word in ["session"]):
            response_content = f"Current session ID: {session_id}"

        # Mode queries
        elif any(word in msg_lower for word in ["mode", "模式"]):
            mode = context.get("conversation_mode", "unknown")
            response_content = f"Current conversation mode: {mode}"

        # Status queries
        elif any(word in msg_lower for word in ["status", "state", "状态"]):
            response_content = (
                f"System status:\n"
                f"- Session: {session_id}\n"
                f"- Execution phase: {context.get('execution_phase', 'unknown')}\n"
                f"- Conversation mode: {context.get('conversation_mode', 'unknown')}\n"
                f"- Task ID: {context.get('task_id', 'none')}"
            )

        # Generic system info
        else:
            response_content = (
                f"System information:\n"
                f"- Session ID: {session_id}\n"
                f"- Execution phase: {context.get('execution_phase', 'unknown')}\n"
                f"- Conversation mode: {context.get('conversation_mode', 'unknown')}\n"
                f"- Task ID: {context.get('task_id', 'none')}"
            )

        # Save response
        assistant_message = self.chat_service.add_message(
            session_id=session_id,
            role="assistant",
            content=response_content,
            metadata={
                "classification": "local_capability",
                "info_need_type": classification.info_need_type.value,
                "confidence": classification.confidence_level.value
            }
        )

        if stream:
            def result_generator():
                yield response_content
            return result_generator()
        else:
            return {
                "message_id": assistant_message.message_id,
                "content": response_content,
                "role": "assistant",
                "metadata": assistant_message.metadata,
                "context": {}
            }

    def _handle_external_info_need(
        self,
        session_id: str,
        message: str,
        classification: Any,
        context: Dict[str, Any],
        stream: bool = False
    ):
        """Handle external information needs by triggering ExternalInfoDeclaration

        This does NOT execute the communication - it only informs the user that
        external info is needed and suggests how to get it.

        Args:
            session_id: Session ID
            message: User's message
            classification: ClassificationResult from classifier
            context: Context dict with session info
            stream: Whether to stream response

        Returns:
            Response dict or generator
        """
        logger.warning(
            f"External info needed: {classification.reasoning} "
            f"(type={classification.info_need_type.value})"
        )

        # Check execution phase - block if in planning phase
        if context.get("execution_phase") == "planning":
            response_content = (
                "⚠️ This question requires external information, but the current "
                "execution phase is 'planning'.\n\n"
                f"**Question type**: {classification.info_need_type.value}\n"
                f"**Reason**: {classification.reasoning}\n\n"
                "To get external information, you need to:\n"
                "1. Switch to execution phase: `/phase execution`\n"
                "2. Use the communication command: `/comm search <query>`\n\n"
                "Alternatively, I can provide an answer based on my existing knowledge, "
                "but it may not be up-to-date."
            )
        else:
            # execution phase: try auto-comm first if enabled
            auto_comm_enabled = self._is_auto_comm_enabled(session_id, context)

            if auto_comm_enabled:
                decision = self.auto_comm_policy.decide(message, classification)
                if decision.allowed:
                    # 1. Check rate limit
                    allowed, remaining = rate_limiter.check_rate_limit(session_id)
                    if not allowed:
                        logger.warning(
                            "AutoComm rate limited",
                            extra={
                                "event": "AUTOCOMM_RATE_LIMITED",
                                "session_id": session_id,
                                "quota_limit": rate_limiter.max_requests
                            }
                        )

                        # Return suggestion with rate limit metadata
                        suggested_command = self._suggest_comm_command(message)
                        response_content = (
                            "⚠️ **AutoComm Rate Limited**\n\n"
                            f"You've reached the rate limit ({rate_limiter.max_requests} requests/minute).\n\n"
                            f"**Suggested action**: {suggested_command}\n\n"
                            "_Please wait a moment or use the manual command._"
                        )

                        assistant_message = self.chat_service.add_message(
                            session_id=session_id,
                            role="assistant",
                            content=response_content,
                            metadata={
                                "classification": "require_comm",
                                "info_need_type": classification.info_need_type.value,
                                "confidence": classification.confidence_level.value,
                                "auto_comm_rate_limited": True,
                                "remaining_quota": 0
                            }
                        )

                        if stream:
                            def result_generator():
                                yield response_content
                            return result_generator()
                        else:
                            return {
                                "message_id": assistant_message.message_id,
                                "content": response_content,
                                "role": "assistant",
                                "metadata": assistant_message.metadata,
                                "context": {}
                            }

                    # 2. Check deduplication
                    is_duplicate, cached_result = dedup_checker.check_duplicate(session_id, message)
                    if is_duplicate:
                        logger.info(
                            "AutoComm duplicate query",
                            extra={
                                "event": "AUTOCOMM_DUPLICATE",
                                "session_id": session_id,
                                "query": message[:100]
                            }
                        )

                        # Return cached result
                        return cached_result

                    # Log AutoComm attempt (before execution)
                    logger.info(
                        "AutoComm execution started",
                        extra={
                            "event": "AUTOCOMM_ATTEMPT",
                            "session_id": session_id,
                            "query": message[:100],
                            "classification": classification.info_need_type.value,
                            "suggested_action": decision.suggested_action,
                            "decision_confidence": decision.confidence
                        }
                    )

                    # 3. Execute AutoComm
                    try:
                        result = self._execute_auto_comm_search(
                            session_id=session_id,
                            context=context,
                            decision=decision,
                        )

                        # Store result for deduplication
                        dedup_checker.store_result(session_id, message, result)

                        return result
                    except Exception as e:
                        # Log AutoComm failure (structured)
                        logger.error(
                            "AutoComm execution failed",
                            extra={
                                "event": "AUTOCOMM_FAILED",
                                "session_id": session_id,
                                "error_type": type(e).__name__,
                                "error_message": str(e),
                                "user_message": message[:100],
                                "classification": classification.to_dict() if classification else None,
                                "execution_phase": context.get("execution_phase"),
                            }
                        )

                        # Return observable failure message
                        suggested_command = self._suggest_comm_command(message)

                        # Add failure indicator to response
                        response_content = (
                            f"⚠️ **AutoComm Failed**: {type(e).__name__}\n\n"
                            f"{suggested_command}\n\n"
                            f"_Debug info: Auto-search attempted but failed. "
                            f"Check logs for details._"
                        )

                        # Save response with failure metadata
                        assistant_message = self.chat_service.add_message(
                            session_id=session_id,
                            role="assistant",
                            content=response_content,
                            metadata={
                                "classification": "require_comm",
                                "info_need_type": classification.info_need_type.value,
                                "confidence": classification.confidence_level.value,
                                "execution_phase": context.get("execution_phase"),
                                "auto_comm_attempted": True,
                                "auto_comm_failed": True,
                                "auto_comm_error": str(e),
                                "auto_comm_error_type": type(e).__name__,
                                "fallback_mode": "suggestion",
                            }
                        )

                        if stream:
                            def result_generator():
                                yield response_content
                            return result_generator()
                        else:
                            return {
                                "message_id": assistant_message.message_id,
                                "content": response_content,
                                "role": "assistant",
                                "metadata": assistant_message.metadata,
                                "context": {}
                            }

            # Suggest communication command
            suggested_command = self._suggest_comm_command(message)

            response_content = (
                "🔍 External information required\n\n"
                f"**Question**: {message}\n"
                f"**Type**: {classification.info_need_type.value}\n"
                f"**Reason**: {classification.reasoning}\n\n"
                f"**Suggested action**:\n"
                f"`{suggested_command}`\n\n"
                "If you prefer, I can answer based on my existing knowledge, "
                "but the information may not be current or authoritative."
            )

        # Save response
        assistant_message = self.chat_service.add_message(
            session_id=session_id,
            role="assistant",
            content=response_content,
            metadata={
                "classification": "require_comm",
                "info_need_type": classification.info_need_type.value,
                "confidence": classification.confidence_level.value,
                "execution_phase": context.get("execution_phase")
            }
        )

        if stream:
            def result_generator():
                yield response_content
            return result_generator()
        else:
            return {
                "message_id": assistant_message.message_id,
                "content": response_content,
                "role": "assistant",
                "metadata": assistant_message.metadata,
                "context": {}
            }

    def _truthy(self, value: Any) -> bool:
        """Check if a value is truthy in a flexible way

        Handles configuration values that might be string "true"/"false",
        boolean, or None.

        Args:
            value: Value to check

        Returns:
            True if value is truthy
        """
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'enabled')
        return bool(value)

    def _is_auto_comm_enabled(self, session_id: str, context: Dict[str, Any]) -> bool:
        """Check if auto-comm is enabled for this session

        Checks both global policy and session-specific settings.

        Args:
            session_id: Session ID
            context: Context dict with session info

        Returns:
            True if auto-comm is enabled
        """
        try:
            # Check if policy is enabled globally
            if not self._truthy(self.auto_comm_policy.enabled):
                logger.debug("Auto-comm disabled globally")
                return False

            # Check session metadata
            session = self.chat_service.get_session(session_id)
            session_auto_comm = session.metadata.get('auto_comm_enabled')

            # Session setting overrides global if explicitly set
            if session_auto_comm is not None:
                enabled = self._truthy(session_auto_comm)
                logger.debug(f"Auto-comm from session metadata: {enabled}")
                return enabled

            # Default to enabled if not explicitly disabled
            logger.debug("Auto-comm using default (enabled)")
            return True

        except Exception as e:
            logger.error(f"Error checking auto-comm enabled: {e}")
            return False

    def _execute_auto_comm_search(
        self,
        session_id: str,
        context: Dict[str, Any],
        decision: AutoCommDecision
    ) -> Dict[str, Any]:
        """Execute auto-comm search based on policy decision

        This executes the actual communication command (e.g., weather search)
        without user interaction, based on the policy decision.

        Args:
            session_id: Session ID
            context: Context dict with session info
            decision: AutoCommDecision from policy

        Returns:
            Response dict with search results

        Raises:
            Exception: If execution fails
        """
        try:
            logger.info(
                f"Executing auto-comm search: "
                f"action={decision.suggested_action}, "
                f"reason={decision.reason}"
            )

            # Parse the suggested action
            if not decision.suggested_action:
                raise ValueError("No suggested action in decision")

            # Format: "weather_search:query"
            action_parts = decision.suggested_action.split(":", 1)
            if len(action_parts) != 2:
                raise ValueError(f"Invalid action format: {decision.suggested_action}")

            action_type, query = action_parts

            if action_type == "weather_search":
                # Execute weather search via CommunicationAdapter
                import asyncio
                from agentos.core.chat.communication_adapter import CommunicationAdapter

                async def _execute_search():
                    adapter = CommunicationAdapter()
                    return await adapter.search(
                        query=query,
                        session_id=session_id,
                        task_id=context.get("task_id", "unknown"),
                        max_results=5
                    )

                # Run async search
                try:
                    search_result = asyncio.run(_execute_search())
                except RuntimeError:
                    # Event loop already running (e.g., in async context)
                    import concurrent.futures
                    import threading

                    result_holder = {}
                    exception_holder = {}

                    def run_in_thread():
                        try:
                            new_loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(new_loop)
                            try:
                                result = new_loop.run_until_complete(_execute_search())
                                result_holder['result'] = result
                            finally:
                                new_loop.close()
                        except Exception as e:
                            exception_holder['exception'] = e

                    thread = threading.Thread(target=run_in_thread)
                    thread.start()
                    thread.join()

                    if 'exception' in exception_holder:
                        raise exception_holder['exception']

                    search_result = result_holder.get('result')

                logger.info(f"Auto-comm search completed: {search_result}")

                # Log AutoComm success (structured)
                logger.info(
                    "AutoComm execution succeeded",
                    extra={
                        "event": "AUTOCOMM_SUCCESS",
                        "session_id": session_id,
                        "action_type": action_type,
                        "query": query,
                        "result_summary": str(search_result)[:200] if search_result else "empty"
                    }
                )

                # Format results
                from agentos.core.chat.comm_commands import CommCommandHandler

                result_message = CommCommandHandler._format_search_results(search_result)

                # Build response with search results
                response_content = (
                    f"🌤️ **Weather Information for {query}**\n\n"
                    f"{result_message}\n\n"
                    "---\n"
                    "*This information was automatically retrieved and may need verification.*"
                )

                # Save response with success metadata
                assistant_message = self.chat_service.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=response_content,
                    metadata={
                        "classification": "require_comm",
                        "auto_comm_attempted": True,  # Indicates attempt was made
                        "auto_comm_failed": False,     # Indicates success
                        "auto_comm_result": {          # Result details
                            "action_type": action_type,
                            "query": query,
                            "summary": str(search_result)[:200] if search_result else "empty"
                        },
                        "decision_confidence": decision.confidence
                    }
                )

                return {
                    "message_id": assistant_message.message_id,
                    "content": response_content,
                    "role": "assistant",
                    "metadata": assistant_message.metadata,
                    "context": {}
                }
            else:
                raise ValueError(f"Unsupported auto-comm action: {action_type}")

        except Exception as e:
            logger.error(
                f"Auto-comm search execution failed: {e}",
                exc_info=True,
                extra={
                    "session_id": session_id,
                    "decision": decision.to_dict() if decision else None,
                    "error_type": type(e).__name__,
                    "execution_phase": context.get("execution_phase"),
                }
            )
            raise

    def _handle_with_comm_suggestion(
        self,
        session_id: str,
        message: str,
        classification: Any,
        context: Dict[str, Any],
        stream: bool = False
    ):
        """Handle message with communication suggestion

        This provides a normal answer but adds a suggestion that the user
        can verify or get updated information using /comm.

        Args:
            session_id: Session ID
            message: User's message
            classification: ClassificationResult from classifier
            context: Context dict with session info
            stream: Whether to stream response

        Returns:
            Response dict or generator
        """
        logger.info("Answering with communication suggestion")

        # Build context and get normal answer
        session = self.chat_service.get_session(session_id)
        rag_enabled = session.metadata.get("rag_enabled", True)

        context_pack = self.context_builder.build(
            session_id=session_id,
            user_input=message,
            rag_enabled=rag_enabled,
            memory_enabled=True
        )

        model_route = session.metadata.get("model_route", "local")

        if stream:
            # For streaming, we need to append the suggestion at the end
            def result_generator():
                # Stream the main response
                for chunk in self._stream_response(session_id, context_pack, model_route):
                    yield chunk

                # Add suggestion disclaimer
                suggested_command = self._suggest_comm_command(message)
                disclaimer = (
                    "\n\n---\n"
                    "💡 **Note**: This answer is based on my existing knowledge and may not "
                    "reflect the latest information.\n"
                    f"To verify or get current information, use: `{suggested_command}`"
                )
                yield disclaimer

            return result_generator()
        else:
            # Non-streaming: get response and append disclaimer
            response_content, response_metadata = self._invoke_model(context_pack, model_route, session_id)

            suggested_command = self._suggest_comm_command(message)
            disclaimer = (
                "\n\n---\n"
                "💡 **Note**: This answer is based on my existing knowledge and may not "
                "reflect the latest information.\n"
                f"To verify or get current information, use: `{suggested_command}`"
            )

            full_response = response_content + disclaimer

            # Save message
            message_metadata = {
                "model_route": model_route,
                "context_tokens": context_pack.metadata.get("total_tokens"),
                "classification": "suggest_comm",
                "info_need_type": classification.info_need_type.value,
                "confidence": classification.confidence_level.value
            }

            if context_pack.snapshot_id:
                message_metadata["context_snapshot_id"] = context_pack.snapshot_id

            if response_metadata:
                message_metadata.update(response_metadata)

            assistant_message = self.chat_service.add_message(
                session_id=session_id,
                role="assistant",
                content=full_response,
                metadata=message_metadata
            )

            return {
                "message_id": assistant_message.message_id,
                "content": full_response,
                "role": "assistant",
                "metadata": assistant_message.metadata,
                "context": context_pack.metadata
            }

    def _suggest_comm_command(self, message: str) -> str:
        """Suggest appropriate /comm command based on message content

        Args:
            message: User's message

        Returns:
            Suggested /comm command string
        """
        msg_lower = message.lower()

        # Time-sensitive queries suggest search
        if any(word in msg_lower for word in ["latest", "today", "news", "current", "最新", "今天"]):
            # Extract key terms for search
            search_query = message[:60]  # Limit length
            return f"/comm search {search_query}"

        # Policy/regulation queries suggest targeted search
        elif any(word in msg_lower for word in ["policy", "regulation", "law", "政策", "法规"]):
            search_query = message[:60]
            return f"/comm search {search_query}"

        # URL-like content suggests fetch
        elif "http://" in message or "https://" in message:
            import re
            url_match = re.search(r'https?://[^\s]+', message)
            if url_match:
                url = url_match.group(0)
                return f"/comm fetch {url}"

        # Default to search
        search_query = message[:60]
        return f"/comm search {search_query}"

    def _invoke_model(
        self,
        context_pack: Any,
        model_route: str = "local",
        session_id: Optional[str] = None
    ) -> tuple[str, Dict[str, Any]]:
        """Invoke model to get response

        Args:
            context_pack: ContextPack with assembled messages
            model_route: "local" or "cloud"
            session_id: Optional session ID to get provider/model preferences

        Returns:
            Tuple of (response_text, metadata)
            Metadata includes truncation information
        """
        logger.info(f"Invoking {model_route} model")

        try:
            from agentos.core.chat.adapters import get_adapter

            messages = context_pack.messages

            # Determine provider and model from session metadata (with fallback)
            provider = None
            model = None

            if session_id:
                session = self.chat_service.get_session(session_id)
                logger.info(f"Session metadata: {session.metadata}")
                provider = session.metadata.get("provider")
                model = session.metadata.get("model")

            # Fallback to default providers
            if not provider:
                provider = "ollama" if model_route == "local" else "openai"
                logger.warning(f"No provider in metadata, using fallback: {provider}")

            logger.info(f"Using provider: {provider}, model: {model}")

            # Get adapter
            adapter = get_adapter(provider, model)

            # Check health
            is_healthy, status = adapter.health_check()
            if not is_healthy:
                return f"⚠️ Model unavailable: {status}\n\nPlease configure the model or try switching with `/model`", {}

            # Generate response
            response, metadata = adapter.generate(
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
                stream=False
            )

            # Task #4: Capture external info declarations from LLM response
            if session_id:
                self._capture_external_info_declarations(response, session_id, metadata)

            # Response Guardian: Check and enforce capability declarations in Execution Phase
            if session_id:
                session = self.chat_service.get_session(session_id)
                final_response, guardian_metadata = check_response_with_guardian(
                    response_content=response,
                    session_metadata=session.metadata,
                    classification=None  # Can pass classification if available in context
                )

                # Merge guardian metadata into response metadata
                if guardian_metadata:
                    metadata = metadata or {}
                    metadata['response_guardian'] = guardian_metadata

                return final_response, metadata
            else:
                return response, metadata

        except Exception as e:
            logger.error(f"Model invocation failed: {e}", exc_info=True)
            return f"⚠️ Model invocation failed: {str(e)}", {}
    
    def create_session(
        self,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new chat session

        Args:
            title: Session title
            metadata: Session metadata

        Returns:
            Session ID
        """
        session = self.chat_service.create_session(
            title=title,
            metadata=metadata
        )

        logger.info(f"Created new chat session: {session.session_id}")
        return session.session_id

    def _capture_external_info_declarations(
        self,
        response_content: str,
        session_id: str,
        response_metadata: Dict[str, Any]
    ) -> None:
        """Capture external information declarations from LLM response

        Task #4: Detects external_info declarations in LLM responses and:
        1. Logs them to audit trail
        2. Marks session metadata if external info is required
        3. Returns response as-is (NO external execution)

        CRITICAL CONSTRAINT: This method MUST NOT trigger /comm commands or
        call comm_adapter. It only captures declarations for later user review.

        Args:
            response_content: LLM response text
            session_id: Current chat session ID
            response_metadata: Response metadata from model adapter
        """
        try:
            # Detect external info declarations in response
            # Look for JSON blocks containing ExternalInfoDeclaration data
            declarations = self._parse_external_info_declarations(response_content)

            if not declarations:
                return

            # Filter for required declarations
            required_declarations = [d for d in declarations if d.get("required", False)]

            if not required_declarations:
                return

            logger.info(
                f"Captured {len(required_declarations)} required external info "
                f"declarations in session {session_id}"
            )

            # Log each declaration to audit trail
            for declaration in required_declarations:
                self._log_external_info_declaration(
                    declaration=declaration,
                    session_id=session_id
                )

            # Mark session metadata to indicate external info is required
            session = self.chat_service.get_session(session_id)
            session_metadata = session.metadata.copy()
            session_metadata["external_info_required"] = True
            session_metadata["external_info_count"] = len(required_declarations)

            # Update session with new metadata
            self.chat_service.update_session_metadata(
                session_id=session_id,
                metadata=session_metadata
            )

            logger.info(
                f"Marked session {session_id} with external_info_required=True"
            )

        except Exception as e:
            # Don't propagate - declaration capture should not break response flow
            logger.error(
                f"Failed to capture external info declarations: {e}",
                exc_info=True
            )

    def _parse_external_info_declarations(
        self,
        response_content: str
    ) -> list[Dict[str, Any]]:
        """Parse external info declarations from LLM response

        Looks for JSON blocks in the response that match ExternalInfoDeclaration
        structure. Supports multiple declaration formats:

        1. Structured JSON blocks:
           ```json
           {
             "external_info": {
               "required": true,
               "declarations": [...]
             }
           }
           ```

        2. Inline declaration objects:
           {"action": "web_search", "reason": "...", ...}

        Args:
            response_content: LLM response text

        Returns:
            List of parsed declaration dictionaries
        """
        declarations = []

        try:
            # Pattern 1: Look for external_info blocks
            external_info_pattern = r'"external_info"\s*:\s*\{[^}]+?"required"\s*:\s*true'
            if re.search(external_info_pattern, response_content, re.IGNORECASE):
                # Try to extract full JSON block
                json_blocks = re.findall(
                    r'\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}',
                    response_content
                )

                for block in json_blocks:
                    try:
                        data = json.loads(block)

                        # Check if this is an external_info declaration
                        if isinstance(data, dict) and "external_info" in data:
                            ext_info = data["external_info"]

                            if ext_info.get("required", False):
                                # Extract declaration list
                                decls = ext_info.get("declarations", [])

                                if not decls and "reason" in ext_info:
                                    # Single declaration embedded in external_info
                                    decls = [ext_info]

                                for decl in decls:
                                    declarations.append({
                                        "required": True,
                                        "declaration": decl
                                    })

                        # Pattern 2: Direct declaration object
                        elif isinstance(data, dict) and "action" in data and "reason" in data:
                            # Validate it looks like ExternalInfoDeclaration
                            try:
                                ExternalInfoDeclaration(**data)
                                declarations.append({
                                    "required": True,
                                    "declaration": data
                                })
                            except Exception:
                                # Not a valid declaration
                                pass

                    except json.JSONDecodeError:
                        continue

            return declarations

        except Exception as e:
            logger.warning(
                f"Failed to parse external info declarations: {e}",
                exc_info=True
            )
            return []

    def _log_external_info_declaration(
        self,
        declaration: Dict[str, Any],
        session_id: str
    ) -> None:
        """Log external info declaration to audit trail

        Args:
            declaration: Declaration dictionary with "required" and "declaration" keys
            session_id: Current chat session ID
        """
        try:
            decl_data = declaration.get("declaration", {})

            # Build audit metadata
            audit_metadata = {
                "session_id": session_id,
                "action": decl_data.get("action"),
                "reason": decl_data.get("reason"),
                "target": decl_data.get("target"),
                "priority": decl_data.get("priority", 2),
                "estimated_cost": decl_data.get("estimated_cost", "MED"),
                "params": decl_data.get("params"),
                "alternatives": decl_data.get("alternatives"),
            }

            # Remove None values
            audit_metadata = {
                k: v for k, v in audit_metadata.items() if v is not None
            }

            # Log to audit system
            from agentos.core.audit import EXTERNAL_INFO_DECLARED

            audit_id = log_audit_event(
                event_type=EXTERNAL_INFO_DECLARED,
                task_id=None,  # Not tied to a specific task
                level="info",
                metadata=audit_metadata
            )

            logger.info(
                f"Logged external info declaration to audit: "
                f"audit_id={audit_id}, action={audit_metadata.get('action')}"
            )

        except Exception as e:
            logger.error(
                f"Failed to log external info declaration: {e}",
                exc_info=True
            )

    # ============================================
    # Multi-Intent Processing (Task #25)
    # ============================================

    async def _process_multi_intent(
        self,
        message: str,
        session_id: str,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Process multi-intent question

        This method handles questions containing multiple intents by:
        1. Splitting into sub-questions
        2. Classifying each sub-question
        3. Processing each according to its classification
        4. Combining results into user-friendly format

        Args:
            message: User's composite question
            session_id: Session ID
            stream: Whether to stream response

        Returns:
            Response dict with type="multi_intent" or generator if streaming
        """
        logger.info(f"Processing multi-intent message: {message[:100]}...")

        # Generate unique message ID for correlation
        import uuid
        message_id = str(uuid.uuid4())

        # Split into sub-questions
        sub_questions = self.multi_intent_splitter.split(message)

        if not sub_questions:
            # Splitting failed, fall back to single intent
            logger.warning("Splitting returned empty list, falling back to single intent")
            raise ValueError("Split returned empty list")

        logger.info(f"Split into {len(sub_questions)} sub-questions")

        # Log multi-intent split event
        try:
            await self._log_multi_intent_split(
                message_id=message_id,
                session_id=session_id,
                original_question=message,
                sub_questions=[sq.to_dict() for sq in sub_questions]
            )
        except Exception as e:
            logger.warning(f"Failed to log multi-intent split: {e}")

        # Get session context
        session = self.chat_service.get_session(session_id)
        context = {
            "session_id": session_id,
            "execution_phase": session.metadata.get("execution_phase", "planning"),
            "conversation_mode": session.metadata.get("conversation_mode", "chat"),
            "task_id": session.task_id
        }

        # Process each sub-question
        results = []
        for i, sub_q in enumerate(sub_questions):
            logger.info(f"Processing sub-question {i+1}/{len(sub_questions)}: {sub_q.text}")

            try:
                # Resolve context if needed
                resolved_text = self._resolve_context_for_subquestion(
                    sub_q=sub_q,
                    previous_results=results
                )

                # Classify the sub-question
                classification = await self.info_need_classifier.classify(
                    resolved_text,
                    session_id=session_id
                )

                # Process based on classification
                sub_result = await self._process_subquestion(
                    text=resolved_text,
                    original_text=sub_q.text,
                    classification=classification,
                    session_id=session_id,
                    context=context,
                    index=i
                )

                results.append({
                    "text": sub_q.text,
                    "resolved_text": resolved_text if resolved_text != sub_q.text else None,
                    "index": i,
                    "needs_context": sub_q.needs_context,
                    "context_hint": sub_q.context_hint,
                    "classification": {
                        "type": classification.info_need_type.value,
                        "action": classification.decision_action.value,
                        "confidence": classification.confidence_level.value,
                        "reasoning": classification.reasoning
                    },
                    "response": sub_result,
                    "success": True
                })

            except Exception as e:
                logger.error(f"Failed to process sub-question {i}: {e}", exc_info=True)
                results.append({
                    "text": sub_q.text,
                    "index": i,
                    "needs_context": sub_q.needs_context,
                    "context_hint": sub_q.context_hint,
                    "success": False,
                    "error": str(e),
                    "response": f"Failed to process this question: {str(e)}"
                })

        # Combine results
        combined_response = self._combine_multi_intent_responses(results)

        # Build final response
        response_data = {
            "type": "multi_intent",
            "original_question": message,
            "sub_questions": results,
            "combined_response": combined_response,
            "message_id": message_id
        }

        # Save assistant message with multi-intent metadata
        assistant_message = self.chat_service.add_message(
            session_id=session_id,
            role="assistant",
            content=combined_response,
            metadata={
                "type": "multi_intent",
                "sub_count": len(sub_questions),
                "success_count": sum(1 for r in results if r.get("success", False)),
                "message_id": message_id
            }
        )

        if stream:
            # For streaming, yield the combined response
            def result_generator():
                yield combined_response
            return result_generator()
        else:
            return {
                "message_id": assistant_message.message_id,
                "content": combined_response,
                "role": "assistant",
                "metadata": response_data,
                "context": {}
            }

    async def _process_subquestion(
        self,
        text: str,
        original_text: str,
        classification: Any,
        session_id: str,
        context: Dict[str, Any],
        index: int
    ) -> str:
        """Process a single sub-question based on classification

        Args:
            text: Resolved sub-question text
            original_text: Original sub-question text
            classification: ClassificationResult
            session_id: Session ID
            context: Context dict
            index: Sub-question index

        Returns:
            Response text for this sub-question
        """
        # Route based on classification decision
        if classification.decision_action == DecisionAction.LOCAL_CAPABILITY:
            # Handle ambient state using local capabilities
            return self._handle_ambient_state_sync(
                message=text,
                classification=classification,
                context=context
            )

        elif classification.decision_action == DecisionAction.REQUIRE_COMM:
            # Requires external information
            return self._handle_external_info_need_sync(
                message=text,
                classification=classification,
                context=context
            )

        elif classification.decision_action == DecisionAction.SUGGEST_COMM:
            # Can answer but suggest verification
            return await self._handle_with_comm_suggestion_sync(
                message=text,
                session_id=session_id,
                classification=classification,
                context=context
            )

        else:  # DIRECT_ANSWER
            # Normal answer flow
            return await self._handle_direct_answer_sync(
                message=text,
                session_id=session_id,
                context=context
            )

    def _resolve_context_for_subquestion(
        self,
        sub_q: SubQuestion,
        previous_results: list[Dict[str, Any]]
    ) -> str:
        """Resolve context for sub-questions that need it

        For sub-questions marked with needs_context=True, this method
        attempts to resolve pronouns or add context from previous results.

        Args:
            sub_q: SubQuestion that may need context
            previous_results: Results from previously processed sub-questions

        Returns:
            Resolved question text (same as original if no context needed)
        """
        if not sub_q.needs_context or not previous_results:
            return sub_q.text

        # For now, return as-is
        # TODO: Implement pronoun resolution and context injection
        # This is a simplified version - can be enhanced later
        logger.debug(f"Sub-question needs context (hint: {sub_q.context_hint}), but resolution not yet implemented")
        return sub_q.text

    def _combine_multi_intent_responses(
        self,
        results: list[Dict[str, Any]]
    ) -> str:
        """Combine multiple sub-question responses into user-friendly format

        Args:
            results: List of sub-question result dicts

        Returns:
            Combined response text
        """
        parts = []

        # Header
        success_count = sum(1 for r in results if r.get("success", False))
        parts.append(f"You asked {len(results)} questions. Here are the answers:\n")

        # Individual responses
        for i, result in enumerate(results, 1):
            parts.append(f"\n**{i}. {result['text']}**\n")

            if result.get("success", False):
                parts.append(result["response"])
            else:
                parts.append(f"Error: {result.get('error', 'Unknown error')}")

        return "\n".join(parts)

    def _handle_ambient_state_sync(
        self,
        message: str,
        classification: Any,
        context: Dict[str, Any]
    ) -> str:
        """Synchronous version of _handle_ambient_state for sub-question processing"""
        msg_lower = message.lower()

        # Time queries
        if any(word in msg_lower for word in ["time", "几点", "when"]):
            from datetime import datetime, timezone
            current_time = utc_now().strftime("%Y-%m-%d %H:%M:%S")
            return f"Current time: {current_time}"

        # Phase queries
        elif any(word in msg_lower for word in ["phase", "阶段", "stage"]):
            phase = context.get("execution_phase", "unknown")
            return f"Current execution phase: {phase}"

        # Mode queries
        elif any(word in msg_lower for word in ["mode", "模式"]):
            mode = context.get("conversation_mode", "unknown")
            return f"Current conversation mode: {mode}"

        # Default
        return f"System information available in metadata: phase={context.get('execution_phase')}, mode={context.get('conversation_mode')}"

    def _handle_external_info_need_sync(
        self,
        message: str,
        classification: Any,
        context: Dict[str, Any]
    ) -> str:
        """Synchronous version of _handle_external_info_need for sub-question processing"""
        suggested_command = self._suggest_comm_command(message)

        return (
            f"External information required for this question. "
            f"Suggested action: `{suggested_command}`"
        )

    async def _handle_with_comm_suggestion_sync(
        self,
        message: str,
        session_id: str,
        classification: Any,
        context: Dict[str, Any]
    ) -> str:
        """Synchronous version of _handle_with_comm_suggestion for sub-question processing"""
        # For multi-intent, provide a brief answer without full context building
        # to avoid excessive token usage
        suggested_command = self._suggest_comm_command(message)

        return (
            f"[Based on existing knowledge] {message}\n"
            f"Note: To verify with current information, use: `{suggested_command}`"
        )

    async def _handle_direct_answer_sync(
        self,
        message: str,
        session_id: str,
        context: Dict[str, Any]
    ) -> str:
        """Synchronous version for direct answer in sub-question processing"""
        # For multi-intent, provide brief answer
        # Avoid full context building to keep responses concise
        return f"[Brief answer for: {message}] This question can be answered from existing knowledge."

    async def _log_multi_intent_split(
        self,
        message_id: str,
        session_id: str,
        original_question: str,
        sub_questions: list[Dict[str, Any]]
    ):
        """Log multi-intent split event to audit trail

        Args:
            message_id: Unique message ID
            session_id: Session ID
            original_question: Original composite question
            sub_questions: List of SubQuestion dicts
        """
        from agentos.core.audit import log_audit_event_async

        await log_audit_event_async(
            event_type="MULTI_INTENT_SPLIT",
            level="info",
            metadata={
                "message_id": message_id,
                "session_id": session_id,
                "original_question": original_question,
                "sub_count": len(sub_questions),
                "sub_questions": sub_questions
            }
        )

    async def _extract_memories_from_conversation(
        self,
        user_message: ChatMessage,
        assistant_message: ChatMessage,
        session_id: str
    ) -> int:
        """Extract memories from user-assistant conversation pair (Task #5)

        This can capture implicit information and commitments from the exchange.
        For example:
        - User: "I prefer Python for backend"
        - Assistant: "Got it, I'll use Python for the API"
        -> Extracts tech_preference: Python

        Args:
            user_message: User's message
            assistant_message: Assistant's response
            session_id: Session ID

        Returns:
            Number of memories extracted
        """
        try:
            from agentos.core.chat.memory_extractor import extract_and_store_async
            from agentos.core.memory.service import MemoryService

            memory_service = MemoryService()

            # Extract from both messages
            user_count = await extract_and_store_async(
                message=user_message,
                session_id=session_id,
                memory_service=memory_service,
                agent_id="webui_chat"
            )

            assistant_count = await extract_and_store_async(
                message=assistant_message,
                session_id=session_id,
                memory_service=memory_service,
                agent_id="webui_chat"
            )

            total = user_count + assistant_count

            if total > 0:
                logger.info(
                    f"Extracted {total} memories from conversation "
                    f"(user: {user_count}, assistant: {assistant_count})"
                )

                # Emit audit event for observability
                try:
                    from agentos.core.capabilities.audit import emit_audit_event

                    emit_audit_event(
                        event_type="conversation_memory_extracted",
                        details={
                            "session_id": session_id,
                            "user_message_id": user_message.message_id,
                            "assistant_message_id": assistant_message.message_id,
                            "total_count": total,
                            "user_count": user_count,
                            "assistant_count": assistant_count
                        },
                        level="info"
                    )
                except Exception as audit_err:
                    logger.warning(f"Failed to emit audit event: {audit_err}")

            return total

        except Exception as e:
            # Graceful degradation - log but don't fail
            logger.warning(
                f"Failed to extract memories from conversation: {e}",
                exc_info=True
            )
            return 0
