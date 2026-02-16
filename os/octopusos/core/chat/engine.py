"""Chat Engine - Orchestrates message sending, context building, and model invocation"""

from typing import Optional, Dict, Any, List, Set
import logging
import json
import re
import os
import threading
from types import SimpleNamespace
from pathlib import Path
import asyncio

from octopusos.core.chat.service import ChatService
from octopusos.core.chat.context_builder import ContextBuilder, ContextBudget
from octopusos.core.chat.commands import parse_command, get_registry
from octopusos.core.chat.slash_command_router import (
    SlashCommandRouter,
    build_command_not_found_response,
    build_extension_disabled_response
)
from octopusos.core.time import utc_now
from octopusos.core.coordinator.model_router import ModelRouter
from octopusos.core.task.manager import TaskManager
from octopusos.core.memory.service import MemoryService
from octopusos.core.extensions.registry import ExtensionRegistry
from octopusos.core.chat.models.external_info import (
    ExternalInfoDeclaration,
    ExternalInfoAction
)
from octopusos.core.chat.models_base import ChatMessage
from octopusos.core.audit import log_audit_event
from octopusos.core.chat.info_need_classifier import InfoNeedClassifier
from octopusos.core.chat.models.info_need import DecisionAction
from octopusos.core.chat.multi_intent_splitter import MultiIntentSplitter, SubQuestion
from octopusos.core.chat.auto_comm_policy import AutoCommPolicy, AutoCommDecision
from octopusos.core.chat.selfcheck import run_startup_checks
from octopusos.core.chat.rate_limiter import rate_limiter, dedup_checker
from octopusos.core.chat.response_guardian import check_response_with_guardian
from octopusos.core.chat.stream_gate import StreamGateDecision
from octopusos.core.chat.hold_controller import HoldController
from octopusos.core.chat.tool_dispatch import (
    try_handle_aws_via_mcp,
    try_handle_azure_via_mcp,
    try_handle_dbops_via_skillos,
)
from octopusos.core.chat.router_priority_contract import (
    validate_router_priority_contract_runtime,
)
from octopusos.core.chat.stock_analysis import (
    STOCK_DISCLAIMER,
    STOCK_REFUSAL_TEMPLATE,
    YahooOHLCVProvider,
    StockDataError,
    analysis_lint,
    build_numeric_summary_mode,
    build_stock_response_text,
    describe_price_action,
    is_trade_advice_request,
    infer_price_unit,
    parse_stock_query,
    sanitize_analysis_text,
)
from octopusos.core.chat.context_integrity import (
    ContextRecoveryService,
    ContextIntegrityGate,
)
from octopusos.core.chat.company_research import (
    apply_mature_company_fallback,
    COMPANY_RESEARCH_INTENT,
    COMPANY_RESEARCH_RESULT_TYPE,
    compute_stable_fill_rate,
    DEFAULT_COMPANY_RESEARCH_PROVIDERS,
    bootstrap_core_items_from_wikipedia,
    build_company_research_payload,
    build_company_research_report,
    company_research_boundary_response,
    extract_company_sections,
    filter_company_research_items,
    filter_items_by_recency,
    is_company_research_judgment_request,
    normalize_company_research_items,
    parse_company_research_request,
    validate_company_research_report_quality,
)
from octopusos.core.capabilities.permissions import PermissionChecker
from octopusos.core.capabilities.external_facts import (
    ExternalFactsCapability,
    ExternalFactsPolicyStore,
    ExternalFactsPlanExecutor,
    IntentPlan,
    SourcePolicy,
    SUPPORTED_FACT_KINDS,
)
from octopusos.core.capabilities.external_facts.provider_store import ExternalFactsProviderStore
from octopusos.core.evidence import enforce_evidence, normalize_evidence_refs
from octopusos.core.executor.audit_logger import AuditLogger
from octopusos.core.mcp.client import MCPClient
from octopusos.core.mcp.config import MCPConfigManager, MCPServerConfig

# Import and register all slash commands
from octopusos.core.chat.handlers import (
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
        self.memory_service = memory_service or MemoryService()
        self.context_builder = context_builder or ContextBuilder(
            chat_service=self.chat_service,
            memory_service=self.memory_service,
        )
        self.model_router = model_router or ModelRouter(policy={})
        self.task_manager = task_manager or TaskManager()

        # Initialize extension support
        from pathlib import Path
        from octopusos.store import get_store_path

        self.extension_registry = extension_registry or ExtensionRegistry()

        # Use project's store/extensions directory for slash command router
        if slash_command_router is None:
            extensions_dir = Path(get_store_path("extensions"))
            slash_command_router = SlashCommandRouter(
                self.extension_registry,
                extensions_dir=extensions_dir
            )

        self.slash_command_router = slash_command_router
        self.hold_controller = HoldController()
        self._hold_jobs_lock = threading.RLock()
        self._hold_jobs: Dict[str, Dict[str, Any]] = {}
        self._router_model_override = str(os.getenv("OCTOPUSOS_ROUTER_MODEL") or "").strip()
        self._cached_router_model: Optional[str] = None

        # Initialize InfoNeedClassifier
        self.info_need_classifier = InfoNeedClassifier(
            config={},
            llm_callable=self._create_llm_callable_for_classifier()
        )
        logger.info("ChatEngine initialized with InfoNeedClassifier")

        # Initialize AutoCommPolicy
        self.auto_comm_policy = AutoCommPolicy(config={})
        logger.info("ChatEngine initialized with AutoCommPolicy")
        self.external_facts = ExternalFactsCapability()
        self.external_facts_policy_store = ExternalFactsPolicyStore()
        self.external_facts_plan_executor = ExternalFactsPlanExecutor()
        self.stock_ohlcv_provider = YahooOHLCVProvider()
        self._external_facts_provider_store = ExternalFactsProviderStore()
        self._company_research_providers_bootstrapped = False
        logger.info("ChatEngine initialized with ExternalFactsCapability")
        self.context_recovery_service = ContextRecoveryService(
            chat_service=self.chat_service,
            memory_service=self.memory_service,
            kb_service=self.context_builder.kb_service,
        )
        self.context_integrity_gate = ContextIntegrityGate(
            recovery_service=self.context_recovery_service,
            chat_service=self.chat_service,
        )

        # Initialize MultiIntentSplitter (Task #25)
        self.multi_intent_splitter = MultiIntentSplitter(
            config={
                "min_length": 5,
                "max_splits": 3,
                "enable_context": True,
            }
        )
        logger.info("ChatEngine initialized with MultiIntentSplitter")

        # Router contract validation guards routing priority regressions.
        if self._truthy(os.getenv("OCTOPUSOS_VALIDATE_ROUTER_PRIORITY_CONTRACT", "1")):
            validate_router_priority_contract_runtime()
            logger.info("Router priority contract validated")

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
        stream: bool = False,
        idempotency_key: str | None = None,
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
            content=user_input,
            idempotency_key=idempotency_key,
            correlation_id=None,
            causation_id=None,
            source="chat_engine",
        )

        session = self.chat_service.get_session(session_id)
        capability_gate = self._resolve_bot_capability_gate(
            session_metadata=session.metadata or {},
            user_input=user_input,
        )
        slash_input = str(capability_gate.get("slash_input") or user_input)
        allow_mcp = bool(capability_gate.get("allow_mcp"))
        allow_skill = bool(capability_gate.get("allow_skill"))
        allow_ext = bool(capability_gate.get("allow_ext"))
        allow_web = bool(capability_gate.get("allow_web"))

        # 2. Check if it's an extension slash command first
        if self.slash_command_router.is_slash_command(slash_input):
            route = self.slash_command_router.route(slash_input)

            if route is None:
                # Command not found - check if it's a built-in command
                command, args, remaining = parse_command(slash_input)
                if command:
                    # It's a built-in command
                    return self._execute_command(session_id, command, args, remaining, stream)
                else:
                    # Unknown command - return helpful error
                    error_response = build_command_not_found_response(slash_input.split()[0])
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
                if capability_gate.get("strict_gate") and not allow_ext:
                    blocked_message = self._capability_gate_hint()
                    assistant_message = self.chat_service.add_message(
                        session_id=session_id,
                        role="assistant",
                        content=blocked_message,
                        metadata={
                            "capability_gate_blocked": True,
                            "required_prefix": "@ext",
                            "channel_id": capability_gate.get("channel_id") or "",
                        },
                    )
                    if stream:
                        def blocked_generator():
                            yield blocked_message
                        return blocked_generator()
                    return {
                        "message_id": assistant_message.message_id,
                        "content": blocked_message,
                        "role": "assistant",
                        "metadata": assistant_message.metadata,
                        "context": {},
                    }
                # Route to extension capability
                return self._execute_extension_command(session_id, route, stream)

        # 2b. Check if it's a built-in slash command
        command, args, remaining = parse_command(slash_input)

        if command:
            return self._execute_command(session_id, command, args, remaining, stream)

        low_latency_policy = self._resolve_low_latency_policy(
            session_metadata=session.metadata or {},
            user_input=str(capability_gate.get("input_for_policy") or slash_input),
        )
        effective_user_input = str(low_latency_policy.get("effective_user_input") or slash_input)
        can_use_mcp = allow_mcp
        can_use_skill = allow_skill
        can_use_ext = allow_ext
        can_use_external = allow_web and (not low_latency_policy.get("offline_only"))
        if capability_gate.get("strict_gate") and not effective_user_input.strip():
            hint = self._capability_gate_hint()
            assistant_message = self.chat_service.add_message(
                session_id=session_id,
                role="assistant",
                content=hint,
                metadata={"capability_gate_blocked": True, "reason": "empty_after_prefix"},
            )
            if stream:
                def hint_generator():
                    yield hint
                return hint_generator()
            return {
                "message_id": assistant_message.message_id,
                "content": hint,
                "role": "assistant",
                "metadata": assistant_message.metadata,
                "context": {},
            }

        if capability_gate.get("strict_gate") and not can_use_mcp and self._detect_tool_intent(effective_user_input):
            hint = self._capability_gate_hint()
            assistant_message = self.chat_service.add_message(
                session_id=session_id,
                role="assistant",
                content=hint,
                metadata={"capability_gate_blocked": True, "required_prefix": "@mcp"},
            )
            if stream:
                def mcp_hint_generator():
                    yield hint
                return mcp_hint_generator()
            return {
                "message_id": assistant_message.message_id,
                "content": hint,
                "role": "assistant",
                "metadata": assistant_message.metadata,
                "context": {},
            }
        if low_latency_policy.get("policy_applied"):
            log_audit_event(
                event_type="USER_BEHAVIOR_SIGNAL",
                task_id=session.task_id,
                level="info",
                metadata={
                    "signal_type": "channel_policy_applied",
                    "session_id": session_id,
                    "policy_applied": low_latency_policy.get("policy_applied"),
                    "blocked_capabilities": list(low_latency_policy.get("blocked_capabilities") or []),
                    "channel_id": session.metadata.get("channel_id"),
                },
            )
            logger.info(
                "Low-latency policy applied",
                extra={
                    "session_id": session_id,
                    "policy_applied": low_latency_policy.get("policy_applied"),
                    "blocked_capabilities": low_latency_policy.get("blocked_capabilities"),
                },
            )

        # 2c. MCP tool-intent route (explicitly enabled by @mcp in strict bot mode).
        if can_use_mcp:
            tool_intent_dispatch = self._try_handle_tool_intent(
                session_id=session_id,
                user_input=effective_user_input,
                stream=stream,
            )
            if tool_intent_dispatch is not None:
                return tool_intent_dispatch

        # 2c. Hard-route company research requests to stable fact-only brief.
        company_research_request = (
            None
            if not can_use_external
            else parse_company_research_request(effective_user_input)
        )
        if company_research_request is not None:
            classification = SimpleNamespace(
                info_need_type=SimpleNamespace(value="external_fact_uncertain"),
                confidence_level=SimpleNamespace(value="high"),
            )
            return self._handle_company_research_request(
                session_id=session_id,
                message=effective_user_input,
                classification=classification,
                context={
                    "session_id": session_id,
                    "execution_phase": session.metadata.get("execution_phase", "execution"),
                    "conversation_mode": session.metadata.get("conversation_mode", "chat"),
                    "task_id": session.task_id,
                    "timezone": session.metadata.get("timezone"),
                    "locale": session.metadata.get("locale"),
                    "external_fact_request": company_research_request,
                },
                fact_request=company_research_request,
                stream=stream,
            )

        # 2d. Fast path: DB ops dispatch via SkillOS -> DBOpsBridge.
        if can_use_skill:
            dbops_metadata = session.metadata or {}
            dbops_dispatch = try_handle_dbops_via_skillos(
                effective_user_input,
                session_context={
                    "session_id": session_id,
                    "task_id": session.task_id,
                    "actor": "chat",
                    "pending_action": dbops_metadata.get("dbops_pending_action"),
                },
            )
            if dbops_dispatch and dbops_dispatch.get("handled"):
                metadata_patch: Dict[str, Any] = {}
                if dbops_dispatch.get("pending_action_clear"):
                    metadata_patch["dbops_pending_action"] = None
                pending_set = dbops_dispatch.get("pending_action_set")
                if isinstance(pending_set, dict):
                    metadata_patch["dbops_pending_action"] = pending_set
                if metadata_patch:
                    self.chat_service.update_session_metadata(session_id, metadata_patch)

                response_content = str(dbops_dispatch.get("message") or "")
                assistant_message = self.chat_service.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=response_content,
                    metadata={
                        "dispatch": "db_ops",
                        "blocked": bool(dbops_dispatch.get("blocked")),
                        "dbops_result": dbops_dispatch.get("dbops_result"),
                        "ui": dbops_dispatch.get("ui"),
                        "missing": dbops_dispatch.get("missing"),
                    },
                )
                if stream:
                    def dbops_generator():
                        yield response_content
                    return dbops_generator()
                return {
                    "message_id": assistant_message.message_id,
                    "content": response_content,
                    "role": "assistant",
                    "metadata": assistant_message.metadata,
                    "context": {},
                }

        # 2e. Fast path: AWS read-only dispatch via enabled AWS MCP server.
        if can_use_mcp:
            session_metadata = session.metadata or {}
            aws_dispatch = try_handle_aws_via_mcp(
                effective_user_input,
                session_context={"pending_action": session_metadata.get("aws_pending_action")},
            )
            if aws_dispatch and aws_dispatch.get("handled"):
                metadata_patch: Dict[str, Any] = {}
                if aws_dispatch.get("pending_action_clear"):
                    metadata_patch["aws_pending_action"] = None
                pending_set = aws_dispatch.get("pending_action_set")
                if isinstance(pending_set, dict):
                    metadata_patch["aws_pending_action"] = pending_set
                if metadata_patch:
                    self.chat_service.update_session_metadata(session_id, metadata_patch)

                response_content = str(aws_dispatch.get("message") or "")
                assistant_message = self.chat_service.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=response_content,
                    metadata={
                        "dispatch": "aws_mcp",
                        "blocked": bool(aws_dispatch.get("blocked")),
                    },
                )
                if stream:
                    def aws_generator():
                        yield response_content
                    return aws_generator()
                return {
                    "message_id": assistant_message.message_id,
                    "content": response_content,
                    "role": "assistant",
                    "metadata": assistant_message.metadata,
                    "context": {},
                }

        # 2f. Fast path: Azure read-only dispatch via enabled Azure MCP server.
        if can_use_mcp:
            azure_dispatch = try_handle_azure_via_mcp(effective_user_input)
            if azure_dispatch and azure_dispatch.get("handled"):
                response_content = str(azure_dispatch.get("message") or "")
                assistant_message = self.chat_service.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=response_content,
                    metadata={
                        "dispatch": "azure_mcp",
                        "blocked": bool(azure_dispatch.get("blocked")),
                    },
                )
                if stream:
                    def azure_generator():
                        yield response_content
                    return azure_generator()
                return {
                    "message_id": assistant_message.message_id,
                    "content": response_content,
                    "role": "assistant",
                    "metadata": assistant_message.metadata,
                    "context": {},
                }

        # 2g. Check for multi-intent splitting (Task #25)
        try:
            if self.multi_intent_splitter.should_split(effective_user_input):
                logger.info("Multi-intent detected, processing with splitter")
                # Process as multi-intent
                import asyncio
                return asyncio.run(self._process_multi_intent(
                    message=effective_user_input,
                    session_id=session_id,
                    stream=stream
                ))
        except Exception as e:
            # If multi-intent processing fails, fall back to single intent
            logger.warning(f"Multi-intent processing failed: {e}, falling back to single intent")

        # 3. Classify message to determine action (TASK 5 Integration)
        classification_result = None

        # Build context dict for classification handlers
        classification_context = {
            "session_id": session_id,
            "execution_phase": session.metadata.get("execution_phase", "planning"),
            "conversation_mode": session.metadata.get("conversation_mode", "chat"),
            "task_id": session.task_id
        }

        if can_use_external:
            try:
                import asyncio
                # Classify the message
                classification_result = asyncio.run(self.info_need_classifier.classify(effective_user_input))

                logger.info(
                    f"Message classified: type={classification_result.info_need_type.value}, "
                    f"action={classification_result.decision_action.value}, "
                    f"confidence={classification_result.confidence_level.value}"
                )

                # Route based on classification decision
                if classification_result.decision_action == DecisionAction.LOCAL_CAPABILITY:
                    llm_fact_request = self._resolve_external_fact_request(
                        effective_user_input,
                        classification_context,
                    )
                    if llm_fact_request:
                        rerouted_context = dict(classification_context)
                        rerouted_context["external_fact_request"] = llm_fact_request
                        logger.info(
                            "Re-routing LOCAL_CAPABILITY to external facts via LLM intent resolution",
                            extra={"session_id": session_id, "kind": llm_fact_request.get("kind")},
                        )
                        return self._handle_external_info_need(
                            session_id,
                            effective_user_input,
                            classification_result,
                            rerouted_context,
                            stream,
                        )
                    # Handle ambient state queries or local deterministic operations
                    return self._handle_ambient_state(session_id, effective_user_input, classification_result, classification_context, stream)

                elif classification_result.decision_action == DecisionAction.REQUIRE_COMM:
                    # Requires external information
                    return self._handle_external_info_need(session_id, effective_user_input, classification_result, classification_context, stream)

                elif classification_result.decision_action == DecisionAction.SUGGEST_COMM:
                    # Can answer but suggest verification
                    return self._handle_with_comm_suggestion(session_id, effective_user_input, classification_result, classification_context, stream)

                # DecisionAction.DIRECT_ANSWER - continue to normal flow
                logger.info("Direct answer mode - proceeding with normal message flow")

            except Exception as e:
                # Classification failed - fallback to normal flow
                logger.warning(f"Classification failed, falling back to direct answer: {e}", exc_info=True)

        # 5. Normal message - build context
        rag_enabled = session.metadata.get("rag_enabled", True)
        
        context_pack = self.context_builder.build(
            session_id=session_id,
            user_input=effective_user_input,
            rag_enabled=rag_enabled,
            memory_enabled=True
        )
        context_pack = self._apply_context_integrity_gate(
            context_pack=context_pack,
            session=session,
            user_input=effective_user_input,
        )

        # 6. Route to model
        model_route = session.metadata.get("model_route", "local")

        # 7. Get response from model
        unlock_degraded_reason = ""
        if stream:
            # Return a stream generator
            return self._stream_response(session_id, context_pack, model_route)
        else:
            session_mode = str(session.metadata.get("conversation_mode") or "chat").lower()
            model_tools: List[Dict[str, Any]] = []
            if can_use_mcp:
                explicit_unlock = low_latency_policy.get("policy_applied") == "LOW_LATENCY_EXPLICIT_WEB_UNLOCK"
                if explicit_unlock:
                    model_tools, unlock_degraded_reason = self._build_mcp_model_tools_best_effort(
                        conversation_mode=session_mode,
                        probe_timeout_s=float(os.getenv("OCTOPUSOS_IMESSAGE_WEB_UNLOCK_TIMEOUT_S", "5") or "5"),
                    )
                else:
                    model_tools = self._build_mcp_model_tools(conversation_mode=session_mode)
            generate_kwargs: Dict[str, Any] = {}
            if model_tools:
                generate_kwargs["tools"] = model_tools
                generate_kwargs["tool_choice"] = "auto"
            response_content, response_metadata = self._invoke_model(
                context_pack,
                model_route,
                session_id,
                extra_generate_kwargs=generate_kwargs or None,
            )
            tool_loop_result = None
            if can_use_mcp:
                tool_loop_result = self._run_native_tool_loop(
                    session_id=session_id,
                    user_input=effective_user_input,
                    context_pack=context_pack,
                    model_route=model_route,
                    response_content=response_content,
                    response_metadata=response_metadata or {},
            )
            if tool_loop_result is not None:
                response_content, response_metadata = tool_loop_result
            if can_use_mcp:
                maybe_tool_call = self._intercept_tool_call_payload_for_chat(
                    session_id=session_id,
                    user_input=effective_user_input,
                    response_content=response_content,
                    context={
                        "conversation_mode": session_mode,
                        "execution_phase": session.metadata.get("execution_phase"),
                        "task_id": session.task_id,
                        "locale": session.metadata.get("locale"),
                        "timezone": session.metadata.get("timezone"),
                    },
                )
                if maybe_tool_call is not None:
                    return maybe_tool_call
            if can_use_ext:
                maybe_intercepted = self._intercept_raw_action_payload_for_chat(
                    session_id=session_id,
                    user_input=effective_user_input,
                    response_content=response_content,
                    context={
                        "conversation_mode": session_mode,
                        "execution_phase": session.metadata.get("execution_phase"),
                        "task_id": session.task_id,
                        "locale": session.metadata.get("locale"),
                        "timezone": session.metadata.get("timezone"),
                    },
                )
                if maybe_intercepted is not None:
                    return maybe_intercepted
            response_content, sanitize_metadata = self._sanitize_chat_tool_plan_output(
                response_content=response_content,
                context={
                    "conversation_mode": session_mode,
                    "execution_phase": session.metadata.get("execution_phase"),
                },
            )
            if unlock_degraded_reason:
                response_content = (
                    "联网暂时不可用，我先基于本地知识回答；你也可以稍后再试 @web。\n\n"
                    f"{response_content}".strip()
                )
            response_content, evidence_metadata = self._apply_evidence_requirement(
                session_id=session_id,
                response_content=response_content,
                context_metadata=context_pack.metadata,
            )

            # 8. Save assistant message
            message_metadata = {
                "model_route": model_route,
                "context_tokens": context_pack.metadata.get("total_tokens"),
                "rag_chunks": len(context_pack.audit.get("rag_chunk_ids", [])),
                "memory_facts": len(context_pack.audit.get("memory_ids", [])),
            }

            # P1-7: Link budget snapshot for audit traceability
            if context_pack.snapshot_id:
                message_metadata["context_snapshot_id"] = context_pack.snapshot_id
            self._attach_context_integrity_metadata(message_metadata=message_metadata, context_pack=context_pack)

            # Merge response metadata (truncation info)
            if response_metadata:
                message_metadata.update(response_metadata)
            if sanitize_metadata:
                message_metadata.update(sanitize_metadata)
            message_metadata.update(evidence_metadata)
            if low_latency_policy.get("policy_applied"):
                message_metadata["policy_applied"] = low_latency_policy["policy_applied"]
                message_metadata["blocked_capabilities"] = list(low_latency_policy.get("blocked_capabilities") or [])
            if capability_gate.get("strict_gate"):
                message_metadata["capability_gate"] = {
                    "strict": True,
                    "allow_mcp": bool(can_use_mcp),
                    "allow_skill": bool(can_use_skill),
                    "allow_ext": bool(allow_ext),
                    "allow_web": bool(allow_web),
                }
            if unlock_degraded_reason:
                message_metadata["unlock_fallback_reason"] = unlock_degraded_reason
                message_metadata["unlock_fallback_offline"] = True

            assistant_message = self.chat_service.add_message(
                session_id=session_id,
                role="assistant",
                content=response_content,
                metadata=message_metadata
            )

            logger.info(f"Generated response for session {session_id}: {assistant_message.message_id}")

            # Record LLM usage event (best-effort).
            try:
                from octopusos.core.llm.usage_events import LLMUsageEvent, record_llm_usage_event_best_effort

                provider = str(message_metadata.get("provider") or session.metadata.get("provider") or "").strip() or "unknown"
                model = str(message_metadata.get("model") or session.metadata.get("model") or "").strip() or None
                record_llm_usage_event_best_effort(
                    LLMUsageEvent(
                        provider=provider,
                        model=model,
                        operation="chat.generate",
                        session_id=session_id,
                        task_id=session.task_id,
                        message_id=assistant_message.message_id,
                        context_snapshot_id=message_metadata.get("context_snapshot_id"),
                        prompt_tokens=message_metadata.get("prompt_tokens"),
                        completion_tokens=message_metadata.get("completion_tokens") or message_metadata.get("tokens_used"),
                        total_tokens=message_metadata.get("total_tokens"),
                        confidence=str(message_metadata.get("tokens_confidence") or "HIGH"),
                        usage_raw={
                            "finish_reason": message_metadata.get("finish_reason"),
                            "truncated": message_metadata.get("truncated"),
                            "tool_calls": message_metadata.get("tool_calls"),
                        },
                        metadata={
                            "model_route": message_metadata.get("model_route"),
                            "context_tokens_est": message_metadata.get("context_tokens"),
                        },
                    )
                )
            except Exception:
                pass

            # NEW (Task #5): Extract memories from conversation pair
            # This can capture implicit information and commitments
            try:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    loop.create_task(self._extract_memories_from_conversation(
                        user_message=user_message,
                        assistant_message=assistant_message,
                        session_id=session_id
                    ))
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
            from octopusos.core.chat.adapters import get_adapter

            # Get session to read provider/model preferences
            session = self.chat_service.get_session(session_id)
            ok, detail = self._ensure_context_integrity_checked(
                context_pack=context_pack,
                session_id=session_id,
                reason="_stream_response",
            )
            if not ok:
                response_content = f"⚠️ Context integrity validation failed: {detail}"
                try:
                    from octopusos.core.chat.event_ledger import append_observed_event

                    append_observed_event(
                        session_id=session_id,
                        event_type="context_integrity_blocked",
                        source="engine",
                        payload={
                            "scope_type": "session",
                            "scope_id": session_id,
                            "card_type": "context_integrity_blocked",
                            "severity": "high",
                            "title": "Context check blocked",
                            "summary": str(detail)[:500],
                            "metadata": {"reason_code": "CONTEXT_GATE_BYPASS_BLOCKED"},
                        },
                    )
                except Exception:
                    pass
                message_metadata = {
                    "model_route": model_route,
                    "context_tokens": context_pack.metadata.get("total_tokens"),
                    "streamed": True,
                    "context_integrity_blocked": True,
                }
                self.chat_service.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=response_content,
                    metadata=message_metadata,
                )
                yield response_content
                return
            gate_decision = self._decide_stream_gate(
                context_metadata=context_pack.metadata,
                mode=PermissionChecker().mode.value,
            )
            self._log_stream_gate_decision(session_id=session_id, task_id=session.task_id, decision=gate_decision)

            if gate_decision.decision == "reject":
                response_content = gate_decision.output_text or "Response blocked by stream gate."
                message_metadata = {
                    "model_route": model_route,
                    "context_tokens": context_pack.metadata.get("total_tokens"),
                    "streamed": True,
                    "stream_gate_decision": gate_decision.decision,
                    "stream_gate_reason_code": gate_decision.reason_code,
                    "stream_gate_action_taken": gate_decision.action_taken,
                    "used_kb": gate_decision.used_kb,
                    "retrieval_run_id": gate_decision.retrieval_run_id,
                    "policy_snapshot_hash": gate_decision.policy_snapshot_hash,
                    "evidence_used": context_pack.metadata.get("evidence_refs") or [],
                }
                if context_pack.snapshot_id:
                    message_metadata["context_snapshot_id"] = context_pack.snapshot_id
                self._attach_context_integrity_metadata(message_metadata=message_metadata, context_pack=context_pack)
                self.chat_service.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=response_content,
                    metadata=message_metadata,
                )
                yield response_content
                return

            if gate_decision.decision == "hold":
                hold_id = self.hold_controller.begin_hold(
                    session_id=session_id,
                    run_id=gate_decision.retrieval_run_id,
                    gate_decision=gate_decision.__dict__,
                )
                timeout_ms = self._stream_hold_timeout_ms(gate_decision.mode)
                self._log_stream_hold_event(
                    session_id=session_id,
                    task_id=session.task_id,
                    event_name="STREAM_GATE_HOLD_START",
                    hold_id=hold_id,
                    timeout_ms=timeout_ms,
                    gate_decision=gate_decision,
                )
                self._start_evidence_preparation_job(
                    session_id=session_id,
                    hold_id=hold_id,
                    context_pack=context_pack,
                )
                hold_result = self.hold_controller.wait_ready(hold_id=hold_id, timeout_ms=timeout_ms)

                if hold_result.state == "ready":
                    payload = hold_result.evidence_payload or {}
                    evidence_refs = payload.get("evidence_refs") or []
                    evidence_count = int(payload.get("evidence_count", len(evidence_refs)))
                    context_pack.metadata["evidence_refs"] = evidence_refs
                    context_pack.metadata["retrieval_run_id"] = payload.get("retrieval_run_id")
                    context_pack.metadata["policy_snapshot_hash"] = payload.get("policy_snapshot_hash")

                    self._log_stream_hold_event(
                        session_id=session_id,
                        task_id=session.task_id,
                        event_name="STREAM_GATE_HOLD_READY",
                        hold_id=hold_id,
                        timeout_ms=timeout_ms,
                        gate_decision=gate_decision,
                        evidence_count=evidence_count,
                    )

                    if evidence_count <= 0:
                        response_content, evidence_metadata = self._apply_evidence_requirement(
                            session_id=session_id,
                            response_content=(
                                "I cannot stream this response because evidence requirements were not satisfied."
                            ),
                            context_metadata=context_pack.metadata,
                        )
                        evidence_metadata["evidence_enforcement_reason_code"] = "STREAM_GATE_HOLD_READY_NO_EVIDENCE"
                        self.hold_controller.release(hold_id, reason_code="STREAM_GATE_HOLD_READY_NO_EVIDENCE")
                        self._log_stream_hold_event(
                            session_id=session_id,
                            task_id=session.task_id,
                            event_name="STREAM_GATE_HOLD_RELEASED",
                            hold_id=hold_id,
                            timeout_ms=timeout_ms,
                            gate_decision=gate_decision,
                            reason_code="STREAM_GATE_HOLD_READY_NO_EVIDENCE",
                            evidence_count=evidence_count,
                        )
                        message_metadata = {
                            "model_route": model_route,
                            "context_tokens": context_pack.metadata.get("total_tokens"),
                            "streamed": True,
                            "stream_gate_decision": "reject",
                            "stream_gate_reason_code": "STREAM_GATE_HOLD_READY_NO_EVIDENCE",
                            "stream_gate_action_taken": "reject",
                        }
                        message_metadata.update(evidence_metadata)
                        if context_pack.snapshot_id:
                            message_metadata["context_snapshot_id"] = context_pack.snapshot_id
                        self._attach_context_integrity_metadata(message_metadata=message_metadata, context_pack=context_pack)
                        self.chat_service.add_message(
                            session_id=session_id,
                            role="assistant",
                            content=response_content,
                            metadata=message_metadata,
                        )
                        yield response_content
                        return

                    release_result = self.hold_controller.release(hold_id, reason_code="STREAM_GATE_HOLD_RELEASED")
                    self._log_stream_hold_event(
                        session_id=session_id,
                        task_id=session.task_id,
                        event_name="STREAM_GATE_HOLD_RELEASED",
                        hold_id=hold_id,
                        timeout_ms=timeout_ms,
                        gate_decision=gate_decision,
                        reason_code=release_result.reason_code,
                        evidence_count=evidence_count,
                    )
                    gate_decision = StreamGateDecision.build(
                        decision="allow",
                        reason_code="STREAM_GATE_HOLD_READY",
                        used_kb=gate_decision.used_kb,
                        retrieval_run_id=payload.get("retrieval_run_id"),
                        policy_snapshot_hash=payload.get("policy_snapshot_hash"),
                        evidence_count=evidence_count,
                        mode=gate_decision.mode,
                        action_taken="none",
                    )
                else:
                    reason_code = hold_result.reason_code or "STREAM_GATE_HOLD_TIMEOUT"
                    if hold_result.state == "timeout":
                        self._log_stream_hold_event(
                            session_id=session_id,
                            task_id=session.task_id,
                            event_name="STREAM_GATE_HOLD_TIMEOUT",
                            hold_id=hold_id,
                            timeout_ms=timeout_ms,
                            gate_decision=gate_decision,
                            reason_code=reason_code,
                        )
                    else:
                        self._log_stream_hold_event(
                            session_id=session_id,
                            task_id=session.task_id,
                            event_name="STREAM_GATE_HOLD_RELEASED",
                            hold_id=hold_id,
                            timeout_ms=timeout_ms,
                            gate_decision=gate_decision,
                            reason_code=reason_code,
                        )

                    response_content, evidence_metadata = self._apply_evidence_requirement(
                        session_id=session_id,
                        response_content=(
                            "I cannot stream this response because evidence requirements were not satisfied."
                        ),
                        context_metadata=context_pack.metadata,
                    )
                    evidence_metadata["evidence_enforcement_reason_code"] = reason_code
                    message_metadata = {
                        "model_route": model_route,
                        "context_tokens": context_pack.metadata.get("total_tokens"),
                        "streamed": True,
                        "stream_gate_decision": "reject",
                        "stream_gate_reason_code": reason_code,
                        "stream_gate_action_taken": "reject",
                    }
                    message_metadata.update(evidence_metadata)
                    if context_pack.snapshot_id:
                        message_metadata["context_snapshot_id"] = context_pack.snapshot_id
                    self._attach_context_integrity_metadata(message_metadata=message_metadata, context_pack=context_pack)
                    self.chat_service.add_message(
                        session_id=session_id,
                        role="assistant",
                        content=response_content,
                        metadata=message_metadata,
                    )
                    yield response_content
                    return

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
            full_response: list[str] = []
            user_input = str((context_pack.messages or [{}])[-1].get("content") or "")

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
            maybe_intercepted = self._intercept_raw_action_payload_for_chat(
                session_id=session_id,
                user_input=user_input,
                response_content=final_response,
                context={
                    "conversation_mode": session.metadata.get("conversation_mode"),
                    "execution_phase": session.metadata.get("execution_phase"),
                    "task_id": session.task_id,
                    "locale": session.metadata.get("locale"),
                    "timezone": session.metadata.get("timezone"),
                },
            )
            if maybe_intercepted is not None:
                yield str(maybe_intercepted.get("content") or "")
                return
            final_response, sanitize_metadata = self._sanitize_chat_tool_plan_output(
                response_content=final_response,
                context={
                    "conversation_mode": session.metadata.get("conversation_mode"),
                    "execution_phase": session.metadata.get("execution_phase"),
                },
            )
            final_response, evidence_metadata = self._apply_evidence_requirement(
                session_id=session_id,
                response_content=final_response,
                context_metadata=context_pack.metadata,
            )

            message_metadata = {
                "model_route": model_route,
                "context_tokens": context_pack.metadata.get("total_tokens"),
                "streamed": True
            }

            # Add guardian metadata if response was modified
            if guardian_metadata:
                message_metadata['response_guardian'] = guardian_metadata
            if sanitize_metadata:
                message_metadata.update(sanitize_metadata)
            message_metadata.update(evidence_metadata)
            message_metadata["stream_gate_decision"] = gate_decision.decision
            message_metadata["stream_gate_reason_code"] = gate_decision.reason_code
            message_metadata["stream_gate_action_taken"] = gate_decision.action_taken

            # P1-7: Link budget snapshot for audit traceability
            if context_pack.snapshot_id:
                message_metadata["context_snapshot_id"] = context_pack.snapshot_id
            self._attach_context_integrity_metadata(message_metadata=message_metadata, context_pack=context_pack)

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
            from octopusos.core.capabilities.runner_base import get_runner
            from octopusos.core.capabilities.runner_base.base import Invocation

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
            from octopusos.store import get_store_path

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
                from octopusos.core.chat.adapters import get_adapter

                # Use a fast local model for classification
                adapter = get_adapter("ollama", self._resolve_router_model())

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

    def _resolve_router_model(self) -> str:
        if self._router_model_override:
            return self._router_model_override
        if self._cached_router_model:
            return self._cached_router_model
        try:
            import requests
            from octopusos.providers.registry import ProviderRegistry

            registry = ProviderRegistry.get_instance()
            endpoint = None
            for provider in registry.list_all():
                if provider.id.startswith("ollama:") or provider.id == "ollama":
                    endpoint = str(getattr(provider, "endpoint", "") or "").strip()
                    if endpoint:
                        break
            endpoint = endpoint or "http://127.0.0.1:11434"
            resp = requests.get(f"{endpoint.rstrip('/')}/api/tags", timeout=5)
            resp.raise_for_status()
            models = resp.json().get("models", [])
            if isinstance(models, list) and models:
                first = models[0]
                if isinstance(first, dict):
                    model_name = str(first.get("name") or first.get("model") or "").strip()
                    if model_name:
                        self._cached_router_model = model_name
                        return model_name
        except Exception:
            pass
        self._cached_router_model = "qwen2.5:14b"
        return self._cached_router_model

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
        conversation_mode = str(context.get("conversation_mode") or "chat").lower()
        if conversation_mode in {"chat", "discussion"}:
            if self._chat_autoread_enabled(context):
                return self._handle_chat_mode_external_autoread(
                    session_id=session_id,
                    message=message,
                    classification=classification,
                    context=context,
                    stream=stream,
                )
            return self._handle_chat_mode_external_fallback(
                session_id=session_id,
                message=message,
                classification=classification,
                context=context,
                stream=stream,
            )

        capability_unavailable = False

        # Check execution phase - block if in planning phase
        if context.get("execution_phase") == "planning":
            capability_unavailable = True
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

                        failure_metadata = {
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

                        if decision.suggested_action and decision.suggested_action.startswith("weather_search:"):
                            failure_metadata.update({
                                "result_type": "weather_error",
                                "location": decision.suggested_action.split(":", 1)[1] or message,
                                "payload": {
                                    "status": "error",
                                    "error_type": type(e).__name__,
                                    "message": str(e),
                                    "updated_at": utc_now().isoformat(),
                                },
                            })

                        # Save response with failure metadata
                        assistant_message = self.chat_service.add_message(
                            session_id=session_id,
                            role="assistant",
                            content=response_content,
                            metadata=failure_metadata
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
                "execution_phase": context.get("execution_phase"),
                **({"capability_unavailable": "external_lookup"} if capability_unavailable else {})
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

    def _chat_autoread_enabled(self, session_metadata: Dict[str, Any]) -> bool:
        """Enable read-only external lookups by default in chat/discussion."""
        mode = str(session_metadata.get("conversation_mode") or "chat").lower()
        return mode in {"chat", "discussion"}

    def _handle_chat_mode_external_autoread(
        self,
        session_id: str,
        message: str,
        classification: Any,
        context: Dict[str, Any],
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Chat-safe external lookup path for chat/discussion mode.

        This path allows read-only external retrieval but never leaks runtime
        governance hints, command instructions, or raw search result lists.
        """
        try:
            fact_request = (
                context.get("external_fact_request")
                if isinstance(context.get("external_fact_request"), dict)
                else self._resolve_external_fact_request(message, context)
            )
            if fact_request:
                if (
                    str(fact_request.get("intent_type") or "") == COMPANY_RESEARCH_INTENT
                    or str(fact_request.get("kind") or "") == "company_research"
                ):
                    return self._handle_company_research_request(
                        session_id=session_id,
                        message=message,
                        classification=classification,
                        context=context,
                        fact_request=fact_request,
                        stream=stream,
                    )
                if str(fact_request.get("intent_type") or "") == "stock.query":
                    return self._handle_stock_query_request(
                        session_id=session_id,
                        message=message,
                        classification=classification,
                        context=context,
                        fact_request=fact_request,
                        stream=stream,
                    )
                intent = str(fact_request.get("intent") or "snapshot").lower()
                if intent == "analysis":
                    plan = self._resolve_intent_plan(message=message, fact_request=fact_request)
                    fact_result_dict = self._execute_intent_plan(plan=plan, context=context)
                    fact_result_dict = self._build_generic_analysis_fact_result(
                        request=fact_request,
                        snapshot_fact=fact_result_dict,
                    )
                    plan_meta = fact_result_dict.get("plan") if isinstance(fact_result_dict.get("plan"), dict) else {}
                    if isinstance(fact_result_dict.get("data"), dict):
                        fact_result_dict["data"] = {
                            **fact_result_dict["data"],
                            "plan": plan_meta,
                        }
                else:
                    fact_result = self._run_async_in_sync(
                        self.external_facts.resolve(
                            kind=fact_request["kind"],
                            query=fact_request["query"],
                            context={
                                "conversation_mode": context.get("conversation_mode"),
                                "execution_phase": context.get("execution_phase"),
                                "timezone": context.get("timezone"),
                                "locale": context.get("locale"),
                                "units": "C",
                                "now_iso": utc_now().isoformat(),
                            },
                            policy=self._resolve_external_facts_policy(
                                mode=str(context.get("conversation_mode") or "chat"),
                                kind=str(fact_request["kind"]),
                            ),
                        )
                    )
                    fact_result_dict = fact_result.to_dict()
                return self._build_chat_response_from_fact_result(
                    session_id=session_id,
                    classification=classification,
                    context=context,
                    fact_result=fact_result_dict,
                    stream=stream,
                )

            decision = self.auto_comm_policy.decide(message, classification)
            if not decision.allowed:
                return self._handle_chat_mode_external_fallback(
                    session_id=session_id,
                    message=message,
                    classification=classification,
                    context=context,
                    stream=stream,
                )

            result = self._execute_auto_comm_search(
                session_id=session_id,
                context=context,
                decision=decision,
            )

            content = str(result.get("content") or "")
            blocked_tokens = ("/phase", "/comm", "External lookup is disabled", "Trust Tier", "候选来源")
            if any(token in content for token in blocked_tokens):
                logger.warning(
                    "ChatAutoRead produced forbidden intermediate output; degrading to fallback",
                    extra={"session_id": session_id, "content_preview": content[:120]},
                )
                return self._handle_chat_mode_external_fallback(
                    session_id=session_id,
                    message=message,
                    classification=classification,
                    context=context,
                    stream=stream,
                )
            result_metadata = result.get("metadata") or {}
            if result_metadata.get("result_type") == "weather_error":
                logger.warning(
                    "ChatAutoRead produced weather_error metadata; degrading to fallback",
                    extra={"session_id": session_id, "content_preview": content[:120]},
                )
                return self._handle_chat_mode_external_fallback(
                    session_id=session_id,
                    message=message,
                    classification=classification,
                    context=context,
                    stream=stream,
                )

            return result
        except Exception as exc:
            logger.warning(
                "ChatAutoRead failed; using fallback",
                extra={"session_id": session_id, "error_type": type(exc).__name__, "error": str(exc)},
            )
            return self._handle_chat_mode_external_fallback(
                session_id=session_id,
                message=message,
                classification=classification,
                context=context,
                stream=stream,
            )

    def _handle_stock_query_request(
        self,
        *,
        session_id: str,
        message: str,
        classification: Any,
        context: Dict[str, Any],
        fact_request: Dict[str, Any],
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Handle stock.query intent with strictly descriptive K-line analysis."""
        symbol = str(fact_request.get("symbol") or fact_request.get("query") or "").strip().upper()
        market = str(fact_request.get("market") or "US").upper()
        timeframe = str(fact_request.get("timeframe") or "1D").upper()
        lookback = int(fact_request.get("lookback") or 60)
        parse_note = str(fact_request.get("parse_note") or "")
        price_unit = infer_price_unit(market)

        if is_trade_advice_request(message):
            content = STOCK_REFUSAL_TEMPLATE
            assistant_message = self.chat_service.add_message(
                session_id=session_id,
                role="assistant",
                content=content,
                metadata={
                    "classification": "require_comm",
                    "info_need_type": classification.info_need_type.value,
                    "confidence": classification.confidence_level.value,
                    "conversation_mode": context.get("conversation_mode"),
                    "execution_phase": context.get("execution_phase"),
                    "result_type": "stock_query_refusal",
                    "intent_type": "stock.query",
                    "why_stock_route": "stock_query_parser_match",
                    "payload": {
                        "symbol": symbol,
                        "market": market,
                        "timeframe": timeframe,
                        "lookback": lookback,
                    },
                },
            )
            if stream:
                def result_generator():
                    yield content
                return result_generator()
            return {
                "message_id": assistant_message.message_id,
                "content": assistant_message.content,
                "role": "assistant",
                "metadata": assistant_message.metadata,
                "context": {},
            }

        candles: List[Dict[str, Any]] = []
        data_as_of = utc_now().isoformat()
        data_status = "ok"
        try:
            dataset = self.stock_ohlcv_provider.fetch(
                parse_stock_query(
                    f"{symbol} {timeframe} {lookback}"
                ) or SimpleNamespace(symbol=symbol, market=market, timeframe=timeframe, lookback=lookback)
            )
            candles = dataset.get("candles") if isinstance(dataset.get("candles"), list) else []
            if candles:
                data_as_of = str(candles[-1].get("ts") or data_as_of)
        except StockDataError as exc:
            logger.warning(
                "Stock data fetch failed",
                extra={"symbol": symbol, "market": market, "timeframe": timeframe, "lookback": lookback, "error": str(exc)},
            )
            data_status = "unavailable"

        if not candles:
            content = build_numeric_summary_mode(
                candles=[],
                timeframe=timeframe,
                symbol=symbol or "UNKNOWN",
                price_unit=price_unit,
                parse_note=parse_note or "行情数据暂不可用，未生成走势段落。",
            )
            metadata = {
                "classification": "require_comm",
                "info_need_type": classification.info_need_type.value,
                "confidence": classification.confidence_level.value,
                "conversation_mode": context.get("conversation_mode"),
                "execution_phase": context.get("execution_phase"),
                "result_type": "query_fact",
                "intent_type": "stock.query",
                "why_stock_route": "stock_query_parser_match",
                "fact_kind": "stock",
                "fact_status": data_status,
                "fact_as_of": data_as_of,
                "payload": {
                    "kind": "stock",
                    "title": f"Stock · {symbol or 'UNKNOWN'}",
                    "query": symbol or "UNKNOWN",
                    "summary": content,
                    "value": None,
                    "unit": None,
                    "price_unit": price_unit,
                    "metrics": [],
                    "trend": [],
                    "source": "none",
                    "updated_at": data_as_of,
                    "symbol": symbol,
                    "market": market,
                    "timeframe": timeframe,
                    "lookback": lookback,
                    "data_cutoff": data_as_of,
                    "sections": {},
                    "candles_count": 0,
                    "safe_summary": True,
                },
            }
            assistant_message = self.chat_service.add_message(
                session_id=session_id,
                role="assistant",
                content=content,
                metadata=metadata,
            )
            if stream:
                def result_generator():
                    yield content
                return result_generator()
            return {
                "message_id": assistant_message.message_id,
                "content": assistant_message.content,
                "role": "assistant",
                "metadata": assistant_message.metadata,
                "context": {},
            }

        sections = describe_price_action(candles, options={"timeframe": timeframe, "price_unit": price_unit})
        response_text = build_stock_response_text(
            sections=sections,
            include_followup=True,
            parse_note=parse_note,
        )
        response_text = sanitize_analysis_text(response_text)
        violations = analysis_lint(response_text)
        if violations:
            response_text = build_numeric_summary_mode(
                candles=candles,
                timeframe=timeframe,
                symbol=symbol or "UNKNOWN",
                price_unit=price_unit,
                parse_note=parse_note or "检测到越界表述，已降级为数据摘要模式。",
            )
            response_text = sanitize_analysis_text(response_text)
            violations = analysis_lint(response_text)
        if violations:
            # Last-resort guard: return strict numeric summary without free text.
            first_close = float(candles[0].get("close") or 0.0)
            last_close = float(candles[-1].get("close") or 0.0)
            period_high = max(float(c.get("high") or 0.0) for c in candles)
            period_low = min(float(c.get("low") or 0.0) for c in candles)
            pct_delta = ((last_close - first_close) / first_close * 100.0) if first_close else 0.0
            response_text = (
                f"{STOCK_DISCLAIMER}\n\n"
                f"{symbol} 过去 {len(candles)} 根 {timeframe}：高点 {period_high:.2f} {price_unit}，低点 {period_low:.2f} {price_unit}，"
                f"首收 {first_close:.2f} {price_unit}，末收 {last_close:.2f} {price_unit}，区间涨跌幅 {pct_delta:.2f}%。\n\n"
                "你想看：近 20 / 60 / 120 根？日线 or 1 小时线？"
            )

        metadata = {
            "classification": "require_comm",
            "info_need_type": classification.info_need_type.value,
            "confidence": classification.confidence_level.value,
            "conversation_mode": context.get("conversation_mode"),
            "execution_phase": context.get("execution_phase"),
            "result_type": "query_fact",
            "intent_type": "stock.query",
            "why_stock_route": "stock_query_parser_match",
            "fact_kind": "stock",
            "fact_status": "ok",
            "fact_as_of": data_as_of,
            "payload": {
                "kind": "stock",
                "title": f"Stock · {symbol}",
                "query": symbol,
                "summary": response_text,
                "value": f"{float(candles[-1].get('close') or 0.0):.2f}",
                "unit": price_unit,
                "metrics": [
                    {"label": "Timeframe", "value": timeframe},
                    {"label": "Lookback", "value": str(lookback)},
                    {"label": "Samples", "value": str(len(candles))},
                ],
                "trend": [
                    {
                        "time": str(c.get("ts") or ""),
                        "value": float(c.get("close") or 0.0),
                    }
                    for c in candles
                    if c.get("ts") is not None and c.get("close") is not None
                ],
                "source": "structured-provider",
                "updated_at": data_as_of,
                "symbol": symbol,
                "market": market,
                "timeframe": timeframe,
                "lookback": lookback,
                "data_cutoff": data_as_of,
                "sections": sections,
                "candles_count": len(candles),
                "safe_summary": False,
            },
        }

        assistant_message = self.chat_service.add_message(
            session_id=session_id,
            role="assistant",
            content=response_text,
            metadata=metadata,
        )
        if stream:
            def result_generator():
                yield response_text
            return result_generator()
        return {
            "message_id": assistant_message.message_id,
            "content": assistant_message.content,
            "role": "assistant",
            "metadata": assistant_message.metadata,
            "context": {},
        }

    def _resolve_external_facts_policy(self, mode: str, kind: str) -> SourcePolicy:
        try:
            return self.external_facts_policy_store.get(mode=mode, kind=kind)  # type: ignore[arg-type]
        except Exception as exc:
            logger.warning(
                "External facts policy read failed; using default policy",
                extra={"mode": mode, "kind": kind, "error": str(exc)},
            )
            return SourcePolicy(
                prefer_structured=True,
                allow_search_fallback=True,
                max_sources=3,
                require_freshness_seconds=3600,
            )

    def _extract_analysis_window_minutes(self, message: str) -> int:
        text = (message or "").lower()
        minute_match = re.search(r"(\d+)\s*(分钟|min|mins|minute|minutes)", text)
        if minute_match:
            try:
                return max(1, min(240, int(minute_match.group(1))))
            except Exception:
                return 5
        hour_match = re.search(r"(\d+)\s*(小时|hour|hours|hr|hrs)", text)
        if hour_match:
            try:
                return max(1, min(240, int(hour_match.group(1)) * 60))
            except Exception:
                return 60
        return 5

    def _ensure_company_research_provider_defaults(self) -> None:
        if self._company_research_providers_bootstrapped:
            return
        try:
            existing = self._external_facts_provider_store.list(kind="company_research", include_disabled=True)
            existing_ids = {str(item.get("provider_id") or "") for item in existing}
            for preset in DEFAULT_COMPANY_RESEARCH_PROVIDERS:
                provider_id = str(preset.get("provider_id") or "")
                if not provider_id or provider_id in existing_ids:
                    continue
                self._external_facts_provider_store.upsert(dict(preset))
            self._company_research_providers_bootstrapped = True
        except Exception as exc:
            logger.warning("Company research provider bootstrap failed", extra={"error": str(exc)})

    def _build_company_research_queries(self, company_name: str, region: str) -> Dict[str, List[str]]:
        region_hint = f" {region}" if region else ""
        core_queries = [
            f"{company_name}{region_hint} company profile",
            f"{company_name}{region_hint} 公司 简介",
            f"{company_name} site:wikipedia.org",
            f"{company_name} site:baike.baidu.com",
        ]
        news_queries = [
            f"{company_name}{region_hint} latest news",
            f"{company_name} site:news.baidu.com",
        ]
        return {"core": core_queries, "news": news_queries}

    def _run_company_research_searches(
        self,
        *,
        session_id: str,
        task_id: str,
        company_name: str,
        region: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        self._ensure_company_research_provider_defaults()
        queries = self._build_company_research_queries(company_name=company_name, region=region)

        async def _search_all() -> Dict[str, List[Dict[str, Any]]]:
            from octopusos.core.chat.communication_adapter import CommunicationAdapter

            core_adapters = [
                CommunicationAdapter(web_search_engine="duckduckgo"),
                CommunicationAdapter(web_search_engine="bing"),
            ]
            news_adapter = CommunicationAdapter(web_search_engine="google", google_mode="auto")
            bucket: Dict[str, List[Dict[str, Any]]] = {"core": [], "news": []}
            seen_urls: set[str] = set()
            for key in ("core", "news"):
                for query in queries[key]:
                    adapters = core_adapters if key == "core" else [news_adapter]
                    collected = False
                    for adapter in adapters:
                        try:
                            response = await adapter.search(
                                query=query,
                                session_id=session_id,
                                task_id=task_id,
                                max_results=6 if key == "core" else 5,
                            )
                        except Exception:
                            continue
                        rows = response.get("results") if isinstance(response, dict) else []
                        if not isinstance(rows, list):
                            continue
                        local_count = 0
                        for row in rows:
                            if not isinstance(row, dict):
                                continue
                            url = str(row.get("url") or "").strip()
                            if url and url in seen_urls:
                                continue
                            if url:
                                seen_urls.add(url)
                            bucket[key].append(row)
                            local_count += 1
                        if local_count > 0:
                            collected = True
                        if collected:
                            break
            return bucket

        return self._run_async_in_sync(_search_all())

    def _handle_company_research_request(
        self,
        *,
        session_id: str,
        message: str,
        classification: Any,
        context: Dict[str, Any],
        fact_request: Dict[str, Any],
        stream: bool = False,
    ) -> Dict[str, Any]:
        company_name = str(fact_request.get("company_name") or "").strip()
        region = str(fact_request.get("region") or "").strip().upper()
        if not company_name:
            company_name = str(fact_request.get("query") or message).strip()

        if is_company_research_judgment_request(message):
            content = company_research_boundary_response()
            assistant_message = self.chat_service.add_message(
                session_id=session_id,
                role="assistant",
                content=content,
                metadata={
                    "classification": "require_comm",
                    "info_need_type": classification.info_need_type.value,
                    "confidence": classification.confidence_level.value,
                    "conversation_mode": context.get("conversation_mode"),
                    "execution_phase": context.get("execution_phase"),
                    "result_type": "company_research_boundary",
                    "intent_type": COMPANY_RESEARCH_INTENT,
                    "fact_kind": "company_research",
                    "payload": {"company_name": company_name, "depth": "mvp"},
                },
            )
            if stream:
                return {
                    "message_id": assistant_message.message_id,
                    "content": assistant_message.content,
                    "role": "assistant",
                    "metadata": assistant_message.metadata,
                    "context": {},
                }
            return {
                "message_id": assistant_message.message_id,
                "content": assistant_message.content,
                "role": "assistant",
                "metadata": assistant_message.metadata,
                "context": {},
            }

        search_data = self._run_company_research_searches(
            session_id=session_id,
            task_id=str(context.get("task_id") or "company_research"),
            company_name=company_name,
            region=region,
        )
        core_items = normalize_company_research_items(search_data.get("core") or [])
        news_items = normalize_company_research_items(search_data.get("news") or [])
        core_items, news_items = filter_company_research_items(core_items, news_items)
        if not core_items:
            core_items = bootstrap_core_items_from_wikipedia(company_name)
        as_of_dt = utc_now()
        recency_days = 2
        recent_news_items = filter_items_by_recency(items=news_items, now=as_of_dt, max_age_days=recency_days)
        base_info, product_info, business_context, normalized_news = extract_company_sections(
            company_name=company_name,
            core_items=core_items,
            news_items=recent_news_items,
        )
        base_info, product_info = apply_mature_company_fallback(
            company_name=company_name,
            base_info=base_info,
            product_info=product_info,
        )
        stable_fill_rate = compute_stable_fill_rate(base_info, product_info)

        as_of = as_of_dt.date().isoformat()
        retrieved_at = as_of_dt.strftime("%Y-%m-%d %H:%M")
        stable_source_items = [
            {
                "source": str(item.get("source") or ""),
                "url": str(item.get("url") or ""),
                "published_at": str(item.get("published_at") or item.get("date") or ""),
            }
            for item in core_items
        ]
        recent_source_items = [
            {
                "source": str(item.get("source") or ""),
                "url": str(item.get("url") or ""),
                "published_at": str(item.get("published_at") or item.get("date") or ""),
            }
            for item in recent_news_items
        ]
        freshness_passed = bool(recent_news_items)
        report_text = build_company_research_report(
            locale=str(context.get("locale") or "zh-CN"),
            company_name=company_name,
            aliases=list(fact_request.get("alias") or []),
            base_info=base_info,
            product_info=product_info,
            business_context=business_context,
            news_items=normalized_news,
            stable_source_items=stable_source_items,
            recent_source_items=recent_source_items,
            retrieved_at=retrieved_at,
            freshness_days=recency_days,
            freshness_passed=freshness_passed,
        )
        quality_issues = validate_company_research_report_quality(report_text)
        if stable_fill_rate < 0.7:
            quality_issues.append("stable-fill-rate-low")
        if quality_issues:
            logger.warning("company research quality gate triggered", extra={"issues": quality_issues})
        payload = build_company_research_payload(
            company_name=company_name,
            report_text=report_text,
            as_of=as_of,
            sources=core_items + recent_news_items,
            news_items=normalized_news,
        )
        metadata = {
            "classification": "require_comm",
            "info_need_type": classification.info_need_type.value,
            "confidence": classification.confidence_level.value,
            "conversation_mode": context.get("conversation_mode"),
            "execution_phase": context.get("execution_phase"),
            "result_type": COMPANY_RESEARCH_RESULT_TYPE,
            "intent_type": COMPANY_RESEARCH_INTENT,
            "fact_kind": "company_research",
            "fact_status": "ok",
            "fact_as_of": as_of,
            "company_research": {
                "company_name": company_name,
                "as_of": as_of,
                "sources": (payload.get("fact") or {}).get("sources", []),
                "news_count": len(normalized_news),
                "stable_fill_rate": stable_fill_rate,
                "quality_issues": quality_issues,
            },
        }
        assistant_message = self.chat_service.add_message(
            session_id=session_id,
            role="assistant",
            content=report_text,
            metadata=metadata,
        )
        if stream:
            return {
                "message_id": assistant_message.message_id,
                "content": assistant_message.content,
                "role": "assistant",
                "metadata": assistant_message.metadata,
                "context": {},
            }
        return {
            "message_id": assistant_message.message_id,
            "content": assistant_message.content,
            "role": "assistant",
            "metadata": assistant_message.metadata,
            "context": {},
        }

    def _detect_external_fact_request(self, message: str) -> Optional[Dict[str, Any]]:
        """Detect query-like external fact intents (20+ kinds) for ExternalFactsCapability."""
        text = (message or "").strip()
        lower = text.lower()
        company_research_request = parse_company_research_request(text)
        if company_research_request is not None:
            return company_research_request
        analysis_tokens = ("波动", "走势", "趋势", "变化", "analysis", "trend", "volatility", "波幅")
        is_analysis = any(token in lower for token in analysis_tokens)
        if any(token in lower for token in ("weather", "天气", "温度", "forecast", "气温")):
            query = re.sub(r"(?i)\b(weather|forecast)\b", "", text).strip()
            query = re.sub(r"(天气|温度|气温)", "", query).strip()
            query = re.sub(r"(怎么样|如何|多少度|几度|现在|当前)\??$", "", query).strip()
            return {
                "kind": "weather",
                "query": query or text,
                "intent": "analysis" if is_analysis else "snapshot",
                "window_minutes": self._extract_analysis_window_minutes(text) if is_analysis else None,
            }
        if any(token in lower for token in ("汇率", "exchange rate", "兑", " to ", " fx ", "currency")):
            return {
                "kind": "fx",
                "query": text,
                "intent": "analysis" if is_analysis else "snapshot",
                "window_minutes": self._extract_analysis_window_minutes(text) if is_analysis else None,
            }
        if re.search(r"(?<![A-Za-z])[A-Za-z]{3}\s*(?:/|to|->|兑|对|-)\s*[A-Za-z]{3}(?![A-Za-z])", text):
            return {
                "kind": "fx",
                "query": text,
                "intent": "analysis" if is_analysis else "snapshot",
                "window_minutes": self._extract_analysis_window_minutes(text) if is_analysis else None,
            }
        patterns = [
            ("stock", ("stock", "price", "股价", "股票", "美股", "港股")),
            ("crypto", ("crypto", "btc", "eth", "加密", "比特币", "以太坊")),
            ("index", ("index", "指数", "标普", "纳指", "道琼斯", "s&p")),
            ("etf", ("etf", "基金行情", "交易型基金")),
            ("bond_yield", ("bond yield", "收益率", "国债收益率", "10y", "10年期")),
            ("commodity", ("commodity", "gold", "oil", "大宗", "黄金", "原油")),
            ("news", ("news", "新闻", "headline", "头条")),
            ("flight", ("flight", "航班", "机票", "登机", "延误")),
            ("train", ("train", "高铁", "火车", "列车")),
            ("hotel", ("hotel", "酒店", "住宿")),
            ("traffic", ("traffic", "路况", "堵车", "通勤")),
            ("air_quality", ("air quality", "aqi", "空气质量", "pm2.5")),
            ("sports", ("score", "sports", "比分", "赛程", "比赛", "球队")),
            ("calendar", ("calendar", "日历", "本周安排", "行程", "会议安排", "日程")),
            ("package", ("package", "物流", "快递", "包裹", "运单")),
            ("shipping", ("shipping", "海运", "集运", "集装箱", "货轮")),
            ("fuel_price", ("fuel", "gas price", "油价", "汽油")),
            ("earthquake", ("earthquake", "地震")),
            ("power_outage", ("power outage", "停电", "断电", "电网故障")),
        ]
        for kind, keys in patterns:
            if any(k in lower for k in keys):
                return {
                    "kind": kind,
                    "query": text,
                    "intent": "analysis" if is_analysis else "snapshot",
                    "window_minutes": self._extract_analysis_window_minutes(text) if is_analysis else None,
                }
        return None

    def _detect_stock_query_request(self, message: str) -> Optional[Dict[str, Any]]:
        parsed = parse_stock_query(message)
        if not parsed:
            return None
        return {
            "intent_type": "stock.query",
            "kind": "stock",
            "query": parsed.symbol,
            "intent": "analysis",
            "symbol": parsed.symbol,
            "market": parsed.market,
            "timeframe": parsed.timeframe,
            "lookback": parsed.lookback,
            "window_minutes": None,
            "parse_note": parsed.parse_note,
        }

    def _detect_external_fact_request_llm(
        self,
        message: str,
    ) -> Optional[Dict[str, Any]]:
        """LLM-based external fact intent detection (preferred over keyword fallback)."""
        text = (message or "").strip()
        if not text:
            return None
        try:
            from octopusos.core.chat.adapters import get_adapter

            adapter = get_adapter("ollama", self._resolve_router_model())
            prompt = (
                "You are an intent router for external facts.\n"
                f"Supported kinds: {', '.join(SUPPORTED_FACT_KINDS)}.\n"
                "Given the user message, decide whether it asks for current/real-world factual lookup.\n"
                "Return STRICT JSON only: "
                '{"is_external_fact": boolean, "kind": string|null, "query": string, '
                '"intent": "snapshot"|"analysis", "window_minutes": number|null}.\n'
                "Use intent='analysis' only when user asks for trend/volatility/change over time.\n"
                "If not external fact, return is_external_fact=false.\n"
                f"User message: {text}"
            )
            response, _ = adapter.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=160,
                stream=False,
            )
            content = str(response or "").strip()
            if not content:
                return None
            json_match = re.search(r"\{[\s\S]*\}", content)
            payload = json.loads(json_match.group(0) if json_match else content)
            if not isinstance(payload, dict):
                return None
            if payload.get("is_external_fact") is not True:
                return None
            kind = str(payload.get("kind") or "").strip().lower()
            if kind not in SUPPORTED_FACT_KINDS:
                return None
            query = str(payload.get("query") or text).strip() or text
            intent = str(payload.get("intent") or "snapshot").strip().lower()
            if intent not in {"snapshot", "analysis"}:
                intent = "snapshot"
            window_minutes = payload.get("window_minutes")
            if intent == "analysis":
                try:
                    window_minutes = int(window_minutes) if window_minutes is not None else self._extract_analysis_window_minutes(text)
                except Exception:
                    window_minutes = self._extract_analysis_window_minutes(text)
                window_minutes = max(1, min(240, int(window_minutes)))
            else:
                window_minutes = None
            return {
                "kind": kind,
                "query": query,
                "intent": intent,
                "window_minutes": window_minutes,
            }
        except Exception as exc:
            logger.debug("LLM external fact detection failed", extra={"error": str(exc)})
            return None

    def _resolve_external_fact_request(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Resolve external fact request using LLM first, then deterministic fallback."""
        mode = str((context or {}).get("conversation_mode") or "chat").lower()
        if mode not in {"chat", "discussion", "plan", "planning"}:
            return None
        company_research = parse_company_research_request(message)
        if company_research is not None:
            return company_research
        if self._detect_tool_intent(message) is not None:
            # Explicit tool intent must never be hijacked by stock/fact parsers.
            return None
        stock_query = self._detect_stock_query_request(message)
        if stock_query is not None:
            return stock_query
        llm_result = self._detect_external_fact_request_llm(message)
        if llm_result:
            return llm_result
        return self._detect_external_fact_request(message)

    def _detect_tool_intent(self, message: str) -> Optional[Dict[str, Any]]:
        text = str(message or "").strip()
        if not text:
            return None

        patterns = (
            "使用工具",
            "调用工具",
            "tool call",
            "tool_call",
            "必填参数",
            "请直接执行",
            "use tool",
        )
        lowered = text.lower()
        if not any(token in text or token in lowered for token in patterns):
            return None

        tool_name = ""
        params: Dict[str, Any] = {}
        reason = "explicit_tool_intent_keywords"

        # Structured payload style.
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                target = str(payload.get("target") or payload.get("tool") or "").strip()
                if target:
                    tool_name = target
                    reason = "structured_tool_intent_payload"
                raw_params = payload.get("params")
                if isinstance(raw_params, dict):
                    params = raw_params
        except Exception:
            pass

        if not tool_name:
            json_match = re.search(r'"target"\s*:\s*"([^"]+)"', text, re.IGNORECASE)
            if json_match:
                tool_name = json_match.group(1).strip()
                reason = "inline_target_field"

        if not tool_name:
            # e.g. 使用工具“echo” / use tool echo
            match = re.search(r"(?:使用工具|调用工具|use tool)\s*[“\"']?([a-zA-Z0-9_.-]+)[”\"']?", text, re.IGNORECASE)
            if match:
                tool_name = match.group(1).strip()

        if not tool_name and "echo" in lowered:
            tool_name = "echo"

        if not tool_name:
            return None

        if not params:
            params = {}
        return {
            "tool_name": tool_name,
            "params": params,
            "reason": reason,
        }

    def _collect_enabled_mcp_servers(self) -> List[MCPServerConfig]:
        manager = MCPConfigManager()
        servers = list(manager.get_enabled_servers())
        normalized: List[MCPServerConfig] = []
        repo_root = Path(__file__).resolve().parents[4]
        local_echo_server = repo_root / "servers" / "echo-math-mcp" / "index.js"
        for server in servers:
            command = list(server.command or [])
            package_id = str((server.env or {}).get("OCTOPUSOS_MCP_PACKAGE_ID") or "")
            if (
                package_id == "octopusos.official/echo-math"
                and any("@modelcontextprotocol/server-echo" in str(v) for v in command)
                and local_echo_server.exists()
            ):
                normalized.append(
                    MCPServerConfig(
                        **{
                            **server.model_dump(),
                            "command": ["node", str(local_echo_server)],
                        }
                    )
                )
                continue
            normalized.append(server)
        return normalized

    def _build_mcp_model_tools(self, *, conversation_mode: str) -> List[Dict[str, Any]]:
        mode = str(conversation_mode or "chat").lower()
        if mode not in {"chat", "discussion"}:
            return []
        servers = self._collect_enabled_mcp_servers()
        if not servers:
            return []
        tools_out: List[Dict[str, Any]] = []
        seen_names: set[str] = set()
        for server in servers:
            try:
                tools = asyncio.run(self._probe_server_tools(server))
            except Exception:
                continue
            for tool in tools:
                name = str(tool.get("name") or "").strip()
                if not name or name in seen_names:
                    continue
                seen_names.add(name)
                description = str(tool.get("description") or "")
                params_schema = tool.get("inputSchema") if isinstance(tool.get("inputSchema"), dict) else {}
                if not isinstance(params_schema, dict):
                    params_schema = {}
                # OpenAI-compatible function tool schema.
                tools_out.append(
                    {
                        "type": "function",
                        "function": {
                            "name": name,
                            "description": description,
                            "parameters": params_schema or {"type": "object", "properties": {}},
                        },
                    }
                )
        return tools_out

    def _build_mcp_model_tools_best_effort(
        self,
        *,
        conversation_mode: str,
        probe_timeout_s: float,
    ) -> tuple[List[Dict[str, Any]], str]:
        mode = str(conversation_mode or "chat").lower()
        if mode not in {"chat", "discussion"}:
            return [], ""
        servers = self._collect_enabled_mcp_servers()
        if not servers:
            return [], "mcp_no_enabled_servers"
        tools_out: List[Dict[str, Any]] = []
        seen_names: set[str] = set()
        timeout_count = 0
        error_count = 0
        timeout_budget = max(0.2, float(probe_timeout_s))
        for server in servers:
            try:
                tools = asyncio.run(
                    asyncio.wait_for(self._probe_server_tools(server), timeout=timeout_budget)
                )
            except asyncio.TimeoutError:
                timeout_count += 1
                continue
            except Exception:
                error_count += 1
                continue
            for tool in tools:
                name = str(tool.get("name") or "").strip()
                if not name or name in seen_names:
                    continue
                seen_names.add(name)
                description = str(tool.get("description") or "")
                params_schema = tool.get("inputSchema") if isinstance(tool.get("inputSchema"), dict) else {}
                if not isinstance(params_schema, dict):
                    params_schema = {}
                tools_out.append(
                    {
                        "type": "function",
                        "function": {
                            "name": name,
                            "description": description,
                            "parameters": params_schema or {"type": "object", "properties": {}},
                        },
                    }
                )

        degraded_reason = ""
        if not tools_out and (timeout_count > 0 or error_count > 0):
            degraded_reason = "mcp_probe_timeout" if timeout_count > 0 else "mcp_probe_error"
        return tools_out, degraded_reason

    async def _probe_server_tools(self, server: MCPServerConfig) -> List[Dict[str, Any]]:
        client = MCPClient(server)
        try:
            await client.connect()
            return await client.list_tools()
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    def _find_tool_and_server(
        self,
        *,
        tool_name: str,
        servers: List[MCPServerConfig],
    ) -> Optional[Dict[str, Any]]:
        desired = str(tool_name or "").strip().lower()
        if not desired:
            return None
        package_filtered = [
            server
            for server in servers
            if desired in str((server.env or {}).get("OCTOPUSOS_MCP_PACKAGE_ID") or "").lower()
        ]
        candidates = package_filtered if package_filtered else servers
        for server in candidates:
            try:
                tools = asyncio.run(self._probe_server_tools(server))
            except Exception:
                continue
            for tool in tools:
                name = str(tool.get("name") or "")
                if name.lower() == desired:
                    return {"server": server, "tool_schema": tool}
        return None

    @staticmethod
    def _coerce_tool_params(tool_schema: Dict[str, Any], params: Dict[str, Any], user_input: str) -> Dict[str, Any]:
        output = dict(params or {})
        input_schema = tool_schema.get("inputSchema") if isinstance(tool_schema, dict) else {}
        if not isinstance(input_schema, dict):
            input_schema = {}
        required = input_schema.get("required") if isinstance(input_schema.get("required"), list) else []
        properties = input_schema.get("properties") if isinstance(input_schema.get("properties"), dict) else {}

        if "message" in required and "message" not in output:
            output["message"] = user_input
        elif len(required) == 1:
            key = str(required[0])
            if key not in output and properties.get(key, {}).get("type") == "string":
                output[key] = user_input
        return output

    def _invoke_mcp_tool(
        self,
        *,
        server: MCPServerConfig,
        tool_schema: Dict[str, Any],
        tool_name: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        _ = tool_schema
        async def _call() -> Dict[str, Any]:
            client = MCPClient(server)
            try:
                await client.connect()
                result = await client.call_tool(tool_name, params)
                return {"ok": True, "result": result}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}
            finally:
                try:
                    await client.disconnect()
                except Exception:
                    pass

        return asyncio.run(_call())

    def _execute_tool_intent_once(
        self,
        *,
        session_id: str,
        intent: Dict[str, Any],
        user_input: str,
    ) -> Dict[str, Any]:
        tool_name = str(intent.get("tool_name") or "").strip()
        servers = self._collect_enabled_mcp_servers()
        if not servers:
            return {
                "ok": False,
                "reason_code": "MCP_NO_ENABLED_SERVERS",
                "tool_name": tool_name,
                "error": "No MCP server is enabled",
                "why_tool_route": str(intent.get("reason") or ""),
            }

        match = self._find_tool_and_server(tool_name=tool_name, servers=servers)
        if match is None:
            return {
                "ok": False,
                "reason_code": "MCP_TOOL_NOT_FOUND",
                "tool_name": tool_name,
                "error": "Tool unavailable on enabled MCP servers",
                "why_tool_route": str(intent.get("reason") or ""),
            }

        server: MCPServerConfig = match["server"]
        tool_schema: Dict[str, Any] = match["tool_schema"]
        resolved_params = self._coerce_tool_params(tool_schema, intent.get("params") or {}, user_input)
        invoke_result = self._invoke_mcp_tool(
            server=server,
            tool_schema=tool_schema,
            tool_name=tool_name,
            params=resolved_params,
        )
        payload = {
            "ok": bool(invoke_result.get("ok")),
            "tool_name": tool_name,
            "server_id": server.id,
            "tool_params": resolved_params,
            "tool_result": invoke_result.get("result"),
            "error": invoke_result.get("error"),
            "why_tool_route": str(intent.get("reason") or ""),
        }
        if not payload["ok"]:
            payload["reason_code"] = "MCP_TOOL_EXEC_FAILED"

        try:
            log_audit_event(
                event_type="mcp_tool_call",
                task_id=None,
                level="info" if payload["ok"] else "warn",
                metadata={
                    "session_id": session_id,
                    "server_id": server.id,
                    "tool_name": tool_name,
                    "params": resolved_params,
                    "ok": payload["ok"],
                    "error": payload["error"],
                },
            )
        except Exception:
            pass
        return payload

    def _run_native_tool_loop(
        self,
        *,
        session_id: str,
        user_input: str,
        context_pack: Any,
        model_route: str,
        response_content: str,
        response_metadata: Dict[str, Any],
    ) -> Optional[tuple[str, Dict[str, Any]]]:
        tool_calls = response_metadata.get("tool_calls") if isinstance(response_metadata, dict) else None
        if not isinstance(tool_calls, list) or not tool_calls:
            return None

        executed_calls: List[Dict[str, Any]] = []
        tool_messages: List[Dict[str, Any]] = []
        assistant_tool_calls: List[Dict[str, Any]] = []

        for raw_call in tool_calls:
            if not isinstance(raw_call, dict):
                continue
            name = str(raw_call.get("name") or "").strip()
            if not name:
                continue
            args = raw_call.get("arguments")
            if not isinstance(args, dict):
                args = {}
            intent = {"tool_name": name, "params": args, "reason": "model_native_tool_call"}
            exec_payload = self._execute_tool_intent_once(
                session_id=session_id,
                intent=intent,
                user_input=user_input,
            )
            executed_calls.append(exec_payload)

            call_id = str(raw_call.get("id") or f"call_{name}")
            arguments_json = str(raw_call.get("arguments_json") or json.dumps(args, ensure_ascii=False))
            assistant_tool_calls.append(
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": arguments_json,
                    },
                }
            )
            tool_content = (
                json.dumps(exec_payload.get("tool_result") or {}, ensure_ascii=False)
                if exec_payload.get("ok")
                else json.dumps({"error": exec_payload.get("error")}, ensure_ascii=False)
            )
            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": name,
                    "content": tool_content,
                }
            )

        if not executed_calls:
            return None

        followup_messages: List[Dict[str, Any]] = list(context_pack.messages)
        followup_messages.append(
            {
                "role": "assistant",
                "content": response_content or "",
                "tool_calls": assistant_tool_calls,
            }
        )
        followup_messages.extend(tool_messages)

        followup_content, followup_metadata = self._invoke_model(
            context_pack=context_pack,
            model_route=model_route,
            session_id=session_id,
            messages_override=followup_messages,
            extra_generate_kwargs={"tool_choice": "none"},
        )
        merged_metadata = dict(followup_metadata or {})
        merged_metadata["decision_action"] = "tool_call"
        merged_metadata["tool_loop"] = {
            "native": True,
            "calls": executed_calls,
        }
        return followup_content, merged_metadata

    def _try_handle_tool_intent(
        self,
        *,
        session_id: str,
        user_input: str,
        stream: bool,
    ) -> Optional[Dict[str, Any]]:
        intent = self._detect_tool_intent(user_input)
        if intent is None:
            return None
        return self._dispatch_tool_intent(
            session_id=session_id,
            intent=intent,
            user_input=user_input,
            stream=stream,
        )

    def _dispatch_tool_intent(
        self,
        *,
        session_id: str,
        intent: Dict[str, Any],
        user_input: str,
        stream: bool,
    ) -> Dict[str, Any]:
        tool_name = str(intent.get("tool_name") or "").strip()
        exec_payload = self._execute_tool_intent_once(
            session_id=session_id,
            intent=intent,
            user_input=user_input,
        )
        if exec_payload.get("ok"):
            content = json.dumps(exec_payload.get("tool_result") or {}, ensure_ascii=False)
            metadata = {
                "dispatch": "tool_intent",
                "handled": True,
                "decision_action": "tool_call",
                "tool_name": tool_name,
                "server_id": exec_payload.get("server_id"),
                "tool_params": exec_payload.get("tool_params") or {},
                "why_tool_route": str(intent.get("reason") or ""),
            }
        else:
            reason_code = str(exec_payload.get("reason_code") or "")
            if reason_code == "MCP_NO_ENABLED_SERVERS":
                content = f"Detected explicit tool request for `{tool_name}`, but no MCP server is enabled."
            elif reason_code == "MCP_TOOL_NOT_FOUND":
                content = f"Detected explicit tool request for `{tool_name}`, but the tool is unavailable on enabled MCP servers."
            else:
                content = (
                    f"Detected explicit tool request for `{tool_name}`, but execution failed: "
                    f"{exec_payload.get('error')}"
                )
            metadata = {
                "dispatch": "tool_intent",
                "handled": False,
                "decision_action": "tool_call",
                "tool_name": tool_name,
                "server_id": exec_payload.get("server_id"),
                "tool_params": exec_payload.get("tool_params") or {},
                "reason_code": reason_code or "MCP_TOOL_EXEC_FAILED",
                "error": exec_payload.get("error"),
                "why_tool_route": str(intent.get("reason") or ""),
            }

        assistant_message = self.chat_service.add_message(
            session_id=session_id,
            role="assistant",
            content=content,
            metadata=metadata,
        )
        if stream:
            def tool_generator():
                yield content
            return tool_generator()
        return {
            "message_id": assistant_message.message_id,
            "content": content,
            "role": "assistant",
            "metadata": assistant_message.metadata,
            "context": {},
        }

    def _parse_tool_call_payload(self, content: str) -> Optional[Dict[str, Any]]:
        text = str(content or "").strip()
        if not text:
            return None
        try:
            payload = json.loads(text)
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None

        action = str(payload.get("action") or "").strip().lower()
        target = str(payload.get("target") or payload.get("tool") or "").strip()
        if action not in {"tool_call", ""}:
            return None
        if not target:
            return None
        raw_params = payload.get("params")
        params = raw_params if isinstance(raw_params, dict) else {}
        return {
            "tool_name": target,
            "params": params,
            "reason": "model_tool_call_payload",
        }

    def _intercept_tool_call_payload_for_chat(
        self,
        *,
        session_id: str,
        user_input: str,
        response_content: str,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        mode = str(context.get("conversation_mode") or "chat").lower()
        if mode not in {"chat", "discussion"}:
            return None
        intent = self._parse_tool_call_payload(response_content)
        if intent is None:
            return None
        return self._dispatch_tool_intent(
            session_id=session_id,
            intent=intent,
            user_input=user_input,
            stream=False,
        )

    @staticmethod
    def _parse_fx_pair_from_text(text: str) -> tuple[str, str]:
        raw = str(text or "").strip()
        match = re.search(r"(?<![A-Za-z])([A-Za-z]{3})\s*(?:/|to|->|兑|对|和|-)\s*([A-Za-z]{3})(?![A-Za-z])", raw, re.IGNORECASE)
        if match:
            return match.group(1).upper(), match.group(2).upper()
        codes = re.findall(r"(?<![A-Za-z])([A-Za-z]{3})(?![A-Za-z])", raw, re.IGNORECASE)
        if len(codes) >= 2:
            return codes[0].upper(), codes[1].upper()
        compact = re.search(r"\b([A-Za-z]{6})\b", raw, re.IGNORECASE)
        if compact:
            code = compact.group(1).upper()
            return code[:3], code[3:]
        return "AUD", "USD"

    def _llm_make_intent_plan(
        self,
        *,
        message: str,
        fact_request: Dict[str, Any],
    ) -> Optional[IntentPlan]:
        try:
            from octopusos.core.chat.adapters import get_adapter
            from octopusos.core.capabilities.external_facts.intent_plan import parse_intent_plan_payload

            adapter = get_adapter("ollama", self._resolve_router_model())
            prompt = (
                "You are an execution planner for external facts.\n"
                "Return STRICT JSON only with fields: "
                '{"intent":"analysis"|"query","capability_id":string,"item_id":string,'
                '"params":object,"constraints":object,"presentation":object}.\n'
                "Use capability_id='exchange_rate'.\n"
                "Use item_id='series' for analysis/trend requests and item_id='spot' for snapshot requests.\n"
                "For exchange rate params include base and quote as ISO-4217 uppercase.\n"
                f"Detected request: {json.dumps(fact_request, ensure_ascii=False)}\n"
                f"User message: {message}"
            )
            response, _ = adapter.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=220,
                stream=False,
            )
            content = str(response or "").strip()
            if not content:
                return None
            json_match = re.search(r"\{[\s\S]*\}", content)
            payload = json.loads(json_match.group(0) if json_match else content)
            if not isinstance(payload, dict):
                return None
            return parse_intent_plan_payload(payload)
        except Exception as exc:
            logger.debug("LLM intent plan generation failed", extra={"error": str(exc)})
            return None

    def _rule_make_intent_plan(
        self,
        *,
        message: str,
        fact_request: Dict[str, Any],
    ) -> IntentPlan:
        kind = str(fact_request.get("kind") or "").lower()
        intent = str(fact_request.get("intent") or "snapshot").lower()
        capability_id = "exchange_rate" if kind in {"fx", "exchange_rate"} else ""
        if capability_id == "exchange_rate":
            base, quote = self._parse_fx_pair_from_text(str(fact_request.get("query") or message))
            window = int(fact_request.get("window_minutes") or self._extract_analysis_window_minutes(message))
            return IntentPlan(
                intent="analysis" if intent == "analysis" else "query",
                capability_id=capability_id,
                item_id="series" if intent == "analysis" else "spot",
                params={
                    "base": base,
                    "quote": quote,
                    "query": str(fact_request.get("query") or message),
                    **({"window_minutes": max(1, min(240, window))} if intent == "analysis" else {}),
                },
                constraints={"past_only": True, "no_prediction": True} if intent == "analysis" else {},
                presentation={"chart": intent == "analysis", "metrics": ["min", "max", "delta", "pct_delta"]},
            )
        return IntentPlan(
            intent="analysis" if intent == "analysis" else "query",
            capability_id="exchange_rate",
            item_id="spot",
            params={"base": "AUD", "quote": "USD", "query": str(fact_request.get("query") or message)},
        )

    def _resolve_intent_plan(
        self,
        *,
        message: str,
        fact_request: Dict[str, Any],
    ) -> IntentPlan:
        from octopusos.core.capabilities.external_facts.intent_plan import validate_intent_plan

        llm_plan = self._llm_make_intent_plan(message=message, fact_request=fact_request)
        if llm_plan is not None:
            errors = validate_intent_plan(llm_plan)
            if not errors:
                return llm_plan
            logger.debug("LLM intent plan invalid; using fallback plan", extra={"errors": errors})
        return self._rule_make_intent_plan(message=message, fact_request=fact_request)

    def _execute_intent_plan(
        self,
        *,
        plan: IntentPlan,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        fact_result = self._run_async_in_sync(
            self.external_facts_plan_executor.execute_plan(
                plan,
                context={
                    "conversation_mode": context.get("conversation_mode"),
                    "execution_phase": context.get("execution_phase"),
                    "timezone": context.get("timezone"),
                    "locale": context.get("locale"),
                    "units": "C",
                    "now_iso": utc_now().isoformat(),
                },
                strict=True,
            )
        )
        fact = fact_result.to_dict()
        metadata = fact.get("metadata") if isinstance(fact.get("metadata"), dict) else {}
        entity_kind = str(metadata.get("entity_kind") or "query_fact")
        as_of = str(metadata.get("as_of") or context.get("now_iso") or utc_now().isoformat())
        source = str(metadata.get("source") or fact.get("provider_id") or "provider")
        params = metadata.get("plan", {}).get("params") if isinstance(metadata.get("plan"), dict) else {}
        query = str((params or {}).get("query") or (params or {}).get("query_raw") or "")
        pair = ""
        base = str((params or {}).get("base") or "").upper()
        quote = str((params or {}).get("quote") or "").upper()
        if base and quote:
            pair = f"{base}/{quote}"
        title = f"{str(fact.get('capability_id') or '').replace('_', ' ').title()} · {pair or str(fact.get('item_id') or '').title()}".strip()
        output_kind = str(fact.get("kind") or "")
        data = fact.get("data") if isinstance(fact.get("data"), dict) else {}
        trend: List[Dict[str, Any]] = []
        metrics: List[Dict[str, Any]] = []
        value: Optional[str] = None
        summary: str
        status = "unavailable" if fact.get("unavailable") else "ok"
        render_hint = "text" if fact.get("unavailable") else "card"
        if output_kind == "series":
            series_raw = data.get("series") if isinstance(data.get("series"), list) else []
            for point in series_raw:
                if not isinstance(point, dict):
                    continue
                t = str(point.get("t") or "").strip()
                v = point.get("v")
                try:
                    vf = float(v)
                except Exception:
                    continue
                if not t:
                    continue
                trend.append({"time": t, "value": vf})
            if trend:
                latest = trend[-1]["value"]
                min_v = min(p["value"] for p in trend)
                max_v = max(p["value"] for p in trend)
                first_v = trend[0]["value"]
                range_abs = max_v - min_v
                delta = latest - first_v
                delta_pct = (delta / first_v * 100.0) if first_v else 0.0
                value = f"{latest:.6f}"
                metrics = [
                    {"label": "Window", "value": f"{int((params or {}).get('window_minutes') or 0)}m"},
                    {"label": "Samples", "value": str(len(trend))},
                    {"label": "Min", "value": f"{min_v:.6f}"},
                    {"label": "Max", "value": f"{max_v:.6f}"},
                ]
                summary = self._format_professional_observation_summary(
                    subject=pair or query or "Series",
                    window_minutes=int((params or {}).get("window_minutes") or 0),
                    stats={
                        "min": min_v,
                        "max": max_v,
                        "range_abs": range_abs,
                        "delta": delta,
                        "delta_pct": delta_pct,
                        "last": latest,
                        "sample_count": len(trend),
                    },
                    locale=str(context.get("locale") or ""),
                )
            else:
                status = "partial"
                render_hint = "text"
                summary = "I found structured series materials, but no usable samples were returned."
        elif output_kind == "point":
            v = data.get("v")
            t = data.get("t")
            if v is not None:
                try:
                    value = f"{float(v):.10g}"
                except Exception:
                    value = str(v)
            metrics = [{"label": "As Of", "value": str(t or as_of)}]
            summary = f"{pair or query or 'Point'} snapshot ready."
        else:
            rows = data.get("rows") if isinstance(data.get("rows"), list) else []
            metrics = [{"label": "Rows", "value": str(len(rows))}]
            summary = f"{query or title} table result ready."
        if fact.get("unavailable"):
            summary = str(metadata.get("details") or "Structured provider item unavailable.")
        return {
            "kind": entity_kind,
            "status": status,
            "data": {
                "presentation": "query_fact",
                "query": query or pair,
                "title": title,
                "value": value,
                "unit": pair or None,
                "summary": summary,
                "metrics": metrics,
                "trend": trend,
                "capability_id": fact.get("capability_id"),
                "item_id": fact.get("item_id"),
                "platform_kind": output_kind,
                "platform_data": data,
                "fact": fact,
                "safe_summary": bool(fact.get("unavailable")),
            },
            "as_of": as_of,
            "confidence": "low" if fact.get("unavailable") else "high",
            "sources": [{"name": source, "type": "api", "url": ""}],
            "render_hint": render_hint,
            "fallback_text": summary,
            "evidence_ids": [],
            "confidence_reason": str(fact.get("unavailable_reason") or ""),
            "plan": metadata.get("plan") if isinstance(metadata.get("plan"), dict) else {},
        }

    def _summarize_generic_analysis_with_llm(
        self,
        *,
        kind: str,
        subject: str,
        window_minutes: int,
        points: List[Dict[str, Any]],
        stats: Dict[str, Any],
        seed_summary: str = "",
        locale: str = "",
    ) -> str:
        try:
            from octopusos.core.chat.adapters import get_adapter

            adapter = get_adapter("ollama", self._resolve_router_model())
            sample_points = points[-12:]
            prompt = (
                "You are a financial analyst.\n"
                "Write a professional factual summary in 1-2 sentences.\n"
                "Only describe observed data in this window.\n"
                "Do NOT include prediction, advice, probability, or external-cause speculation.\n"
                "Return STRICT JSON only: {\"summary\":\"...\"}.\n"
                f"Kind: {kind}\n"
                f"Subject: {subject}\n"
                f"Locale: {locale}\n"
                f"Window(minutes): {window_minutes}\n"
                f"Stats: {json.dumps(stats, ensure_ascii=False)}\n"
                f"Points: {json.dumps(sample_points, ensure_ascii=False)}\n"
                f"Seed summary: {seed_summary}"
            )
            response, _ = adapter.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=180,
                stream=False,
            )
            content = str(response or "").strip()
            json_match = re.search(r"\{[\s\S]*\}", content)
            payload = json.loads(json_match.group(0) if json_match else content)
            summary = str(payload.get("summary") or "").strip()
            if summary:
                return summary
        except Exception as exc:
            logger.debug("LLM generic analysis summary failed", extra={"error": str(exc), "kind": kind})
        return self._format_professional_observation_summary(
            subject=subject,
            window_minutes=window_minutes,
            stats=stats,
            locale=locale,
        )

    @staticmethod
    def _format_professional_observation_summary(
        *,
        subject: str,
        window_minutes: int,
        stats: Dict[str, Any],
        locale: str = "",
    ) -> str:
        min_v = float(stats.get("min", 0.0))
        max_v = float(stats.get("max", 0.0))
        range_abs = float(stats.get("range_abs", 0.0))
        delta = float(stats.get("delta", 0.0))
        delta_pct = float(stats.get("delta_pct", 0.0))
        last_v = float(stats.get("last", 0.0))
        samples = int(stats.get("sample_count", 0))
        delta_signed = f"{delta:+.6f}"
        delta_pct_signed = f"{delta_pct:+.5f}%"

        zh_locale = str(locale or "").lower().startswith("zh")
        has_cjk = bool(re.search(r"[\u4e00-\u9fff]", subject or ""))
        use_zh = zh_locale or has_cjk
        if use_zh:
            return (
                f"过去 {window_minutes} 分钟内，{subject} 在 {min_v:.6f}–{max_v:.6f} 区间内波动，"
                f"振幅 {range_abs:.6f}。窗口末值 {last_v:.6f}，较窗口起点变动 {delta_signed}（{delta_pct_signed}）；"
                f"样本数 {samples}。"
            )
        return (
            f"Over the last {window_minutes} minutes, {subject} traded within {min_v:.6f}–{max_v:.6f}, "
            f"with an absolute range of {range_abs:.6f}. The end-point was {last_v:.6f}, "
            f"for a start-to-end move of {delta_signed} ({delta_pct_signed}); samples={samples}."
        )

    def _build_generic_analysis_fact_result(
        self,
        *,
        request: Dict[str, Any],
        snapshot_fact: Dict[str, Any],
    ) -> Dict[str, Any]:
        kind = str(snapshot_fact.get("kind") or request.get("kind") or "query_fact")
        data = snapshot_fact.get("data") if isinstance(snapshot_fact.get("data"), dict) else {}
        window_minutes = int(request.get("window_minutes") or 5)
        trend_raw = data.get("trend") if isinstance(data.get("trend"), list) else []
        trend: List[Dict[str, Any]] = []
        for point in trend_raw:
            if not isinstance(point, dict):
                continue
            try:
                value = float(point.get("value"))
            except Exception:
                continue
            time_label = str(point.get("time") or "")
            if not time_label:
                continue
            trend.append({"time": time_label, "value": value})

        if len(trend) < 2:
            summary = str(
                data.get("summary")
                or snapshot_fact.get("fallback_text")
                or f"I can provide {kind} snapshot, but there are not enough points for {window_minutes}m analysis."
            )
            merged = dict(data)
            merged["presentation"] = "query_fact"
            merged["safe_summary"] = True
            merged["summary"] = summary
            merged["metrics"] = list(merged.get("metrics") or []) + [
                {"label": "Analysis Window", "value": f"{window_minutes}m"},
                {"label": "Samples", "value": str(len(trend))},
            ]
            merged["trend"] = trend
            return {
                **snapshot_fact,
                "status": "partial",
                "render_hint": "text",
                "data": merged,
                "fallback_text": summary,
                "confidence_reason": snapshot_fact.get("confidence_reason") or "insufficient_analysis_samples",
            }

        first = float(trend[0]["value"])
        last = float(trend[-1]["value"])
        min_value = min(float(p["value"]) for p in trend)
        max_value = max(float(p["value"]) for p in trend)
        delta = last - first
        delta_pct = (delta / first * 100.0) if first else 0.0
        stats = {
            "first": first,
            "last": last,
            "min": min_value,
            "max": max_value,
            "delta": delta,
            "delta_pct": delta_pct,
            "range_abs": max_value - min_value,
            "sample_count": len(trend),
        }
        subject = str(data.get("query") or request.get("query") or kind)
        summary = self._summarize_generic_analysis_with_llm(
            kind=kind,
            subject=subject,
            window_minutes=window_minutes,
            points=trend,
            stats=stats,
            seed_summary=str(data.get("summary") or ""),
            locale=str(request.get("locale") or ""),
        )
        merged = dict(data)
        merged["presentation"] = "query_fact"
        merged["summary"] = summary
        merged["value"] = merged.get("value") if merged.get("value") is not None else f"{last:.6f}"
        metrics = list(merged.get("metrics") or [])
        metrics.extend(
            [
                {"label": "Analysis Window", "value": f"{window_minutes}m"},
                {"label": "Samples", "value": str(len(trend))},
                {"label": "Min", "value": f"{min_value:.6f}"},
                {"label": "Max", "value": f"{max_value:.6f}"},
            ]
        )
        merged["metrics"] = metrics[:8]
        merged["trend"] = trend[-48:]
        return {
            **snapshot_fact,
            "status": "ok",
            "render_hint": "card",
            "data": merged,
            "fallback_text": summary,
        }

    @staticmethod
    def _is_raw_web_action_payload(content: str) -> bool:
        text = (content or "").strip()
        if not text:
            return False

        if '"external_info"' in text and '"declarations"' in text:
            return True
        if re.search(r'"action"\s*:\s*"(web_search|web_fetch|api_call)"', text, re.IGNORECASE):
            return True
        if (
            re.search(r'"action"\s*:', text, re.IGNORECASE)
            and re.search(r'"(reason|target|params)"\s*:', text, re.IGNORECASE)
        ):
            return True
        if re.search(r"`(web_search|web_fetch|api_call)`", text, re.IGNORECASE) and '"target"' in text:
            return True

        # Try parsing full JSON for action declaration contracts.
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                if isinstance(parsed.get("external_info"), dict):
                    return True
                action = str(parsed.get("action") or "").strip().lower()
                if action and action in {"web_search", "web_fetch", "api_call"}:
                    return True
                if action and any(k in parsed for k in ("reason", "target", "params")):
                    return True
        except Exception:
            pass
        return False

    def _sanitize_chat_tool_plan_output(
        self,
        *,
        response_content: str,
        context: Dict[str, Any],
    ) -> tuple[str, Dict[str, Any]]:
        mode = str(context.get("conversation_mode") or "chat").lower()
        if mode not in {"chat", "discussion"}:
            return response_content, {}
        if not self._is_raw_web_action_payload(response_content):
            return response_content, {}
        return (
            "I cannot show internal tool-plan payloads directly. "
            "I will fetch and verify external information, then return a structured result.",
            {
                "fallback_mode": "raw_action_sanitized",
                "tool_plan_sanitized": True,
            },
        )

    def _intercept_raw_action_payload_for_chat(
        self,
        *,
        session_id: str,
        user_input: str,
        response_content: str,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        mode = str(context.get("conversation_mode") or "chat").lower()
        if mode not in {"chat", "discussion"}:
            return None
        if not self._is_raw_web_action_payload(response_content):
            return None

        fact_request = self._resolve_external_fact_request(user_input, context)
        if fact_request:
            try:
                fact_result = self._run_async_in_sync(
                    self.external_facts.resolve(
                        kind=fact_request["kind"],
                        query=fact_request["query"],
                        context={
                            "conversation_mode": mode,
                            "execution_phase": context.get("execution_phase"),
                            "timezone": context.get("timezone"),
                            "locale": context.get("locale"),
                            "units": "C",
                            "now_iso": utc_now().isoformat(),
                        },
                        policy=self._resolve_external_facts_policy(mode=mode, kind=str(fact_request["kind"])),
                    )
                )
                classification = SimpleNamespace(
                    info_need_type=SimpleNamespace(value="external_fact_uncertain"),
                    confidence_level=SimpleNamespace(value="medium"),
                )
                return self._build_chat_response_from_fact_result(
                    session_id=session_id,
                    classification=classification,
                    context=context,
                    fact_result=fact_result.to_dict(),
                    stream=False,
                )
            except Exception as exc:
                logger.warning("Raw web action interception failed", extra={"session_id": session_id, "error": str(exc)})

        fallback = self.chat_service.add_message(
            session_id=session_id,
            role="assistant",
            content="I can’t verify a reliable structured external fact yet, so I’m providing a safe summary instead.",
            metadata={
                "conversation_mode": mode,
                "execution_phase": context.get("execution_phase"),
                "fallback_mode": "raw_action_intercepted",
            },
        )
        return {
            "message_id": fallback.message_id,
            "content": fallback.content,
            "role": "assistant",
            "metadata": fallback.metadata,
            "context": {},
        }

    def _build_chat_response_from_fact_result(
        self,
        session_id: str,
        classification: Any,
        context: Dict[str, Any],
        fact_result: Dict[str, Any],
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Build chat-safe assistant message from normalized FactResult."""
        kind = str(fact_result.get("kind") or "")
        status = str(fact_result.get("status") or "unavailable")
        data = fact_result.get("data") or {}
        presentation = str(data.get("presentation") or "")
        as_of = fact_result.get("as_of")
        confidence = fact_result.get("confidence")
        sources = fact_result.get("sources") or []
        provider = (sources[0] or {}).get("name") if sources else None

        metadata: Dict[str, Any] = {
            "classification": "require_comm",
            "info_need_type": classification.info_need_type.value,
            "confidence": classification.confidence_level.value,
            "conversation_mode": context.get("conversation_mode"),
            "execution_phase": context.get("execution_phase"),
            "fact_kind": kind,
            "fact_status": status,
            "fact_confidence": confidence,
            "fact_as_of": as_of,
            "fact_sources": sources,
            "fact_render_hint": fact_result.get("render_hint"),
            "fact_evidence_ids": fact_result.get("evidence_ids") or [],
            "fact_confidence_reason": fact_result.get("confidence_reason") or "",
            "fact_extraction_ids": fact_result.get("extraction_ids") or [],
            "fact_verification_ids": fact_result.get("verification_ids") or [],
            "fact_checks_summary": {
                "status": status,
                "confidence": confidence,
            },
        }

        if presentation == "query_fact":
            payload_data = data if isinstance(data, dict) else {}
            safe_summary = (
                status != "ok"
                or payload_data.get("safe_summary") is True
                or payload_data.get("value") is None
            )
            payload = {
                "kind": kind,
                "title": payload_data.get("title") or f"{kind.replace('_', ' ').title()} · {payload_data.get('query', '')}".strip(),
                "query": payload_data.get("query") if isinstance(payload_data, dict) else "",
                "value": payload_data.get("value") if isinstance(payload_data, dict) else None,
                "unit": payload_data.get("unit") if isinstance(payload_data, dict) else None,
                "summary": payload_data.get("summary") if isinstance(payload_data, dict) else None,
                "metrics": payload_data.get("metrics") if isinstance(payload_data, dict) else [],
                "trend": payload_data.get("trend") if isinstance(payload_data, dict) else [],
                "source": provider,
                "updated_at": as_of,
                "safe_summary": safe_summary,
                "sensitive": kind in {"calendar", "package"},
                "fact": payload_data.get("fact") if isinstance(payload_data.get("fact"), dict) else None,
                "export_data": {
                    "columns": ["time", "value"],
                    "rows": payload_data.get("trend") if isinstance(payload_data.get("trend"), list) else [],
                    "metrics": payload_data.get("metrics") if isinstance(payload_data.get("metrics"), list) else [],
                },
            }
            metadata.update(
                {
                    "result_type": "query_fact",
                    "payload": payload,
                    **({"fallback_mode": "query_fact_safe_summary"} if safe_summary else {}),
                }
            )
            response_content = str(
                payload.get("summary")
                or fact_result.get("fallback_text")
                or f"{kind} snapshot ready."
            )
        elif kind == "weather" and status == "ok" and fact_result.get("render_hint") == "card":
            location = str(data.get("location") or "Unknown location")
            temp_c = data.get("temp_c")
            condition = data.get("condition")
            wind_kmh = data.get("wind_kmh")
            response_content = (
                f"Current weather in {location}: "
                f"{temp_c if temp_c is not None else 'N/A'}°C, "
                f"{condition or 'condition unavailable'}."
            )
            metadata.update(
                {
                    "result_type": "weather",
                    "location": location,
                    "provider": provider,
                    "payload": {
                        "temp_c": temp_c,
                        "condition": condition,
                        "wind_kmh": wind_kmh,
                        "humidity_pct": data.get("humidity_pct"),
                        "high_c": data.get("high_c"),
                        "low_c": data.get("low_c"),
                        "summary": data.get("summary"),
                        "daily": data.get("daily") or [],
                        "hourly": data.get("hourly") or [],
                        "updated_at": as_of,
                    },
                }
            )
        elif status == "ok":
            payload_data = data if isinstance(data, dict) else {}
            if payload_data.get("value") is None and payload_data.get("rate") is not None:
                base = str(payload_data.get("base") or "").strip().upper()
                quote = str(payload_data.get("quote") or "").strip().upper()
                pair = f"{base}/{quote}" if (base and quote) else None
                payload_data = {
                    **payload_data,
                    "value": payload_data.get("rate"),
                    "unit": payload_data.get("unit") or pair,
                    "summary": payload_data.get("summary") or (
                        f"{pair}: {payload_data.get('rate')} (as of {as_of or 'unknown'})"
                        if pair
                        else payload_data.get("summary")
                    ),
                    "title": payload_data.get("title") or (
                        f"{kind.replace('_', ' ').title()} · {pair}" if pair else None
                    ),
                }
            payload = {
                "kind": kind,
                "title": payload_data.get("title") or f"{kind.replace('_', ' ').title()} · {payload_data.get('query', '')}".strip(),
                "query": payload_data.get("query") if isinstance(payload_data, dict) else "",
                "value": payload_data.get("value") if isinstance(payload_data, dict) else None,
                "unit": payload_data.get("unit") if isinstance(payload_data, dict) else None,
                "summary": payload_data.get("summary") if isinstance(payload_data, dict) else None,
                "metrics": payload_data.get("metrics") if isinstance(payload_data, dict) else [],
                "trend": payload_data.get("trend") if isinstance(payload_data, dict) else [],
                "source": provider,
                "updated_at": as_of,
            }
            metadata.update(
                {
                    "result_type": "query_fact",
                    "payload": payload,
                }
            )
            response_content = str(payload.get("summary") or fact_result.get("fallback_text") or f"{kind} snapshot ready.")
        else:
            if kind not in {"weather", "fx"}:
                payload = {
                    "kind": kind,
                    "title": f"{kind.replace('_', ' ').title()} · {data.get('query') if isinstance(data, dict) else ''}".strip(),
                    "query": data.get("query") if isinstance(data, dict) else "",
                    "summary": str(
                        fact_result.get("fallback_text")
                        or f"I found {kind} materials, but cannot verify a structured value yet."
                    ),
                    "value": None,
                    "metrics": [],
                    "trend": [],
                    "source": provider,
                    "updated_at": as_of,
                    "safe_summary": True,
                    "sensitive": kind in {"calendar", "package"},
                }
                metadata.update(
                    {
                        "result_type": "query_fact",
                        "payload": payload,
                        "fallback_mode": "query_fact_safe_summary",
                    }
                )
                response_content = str(payload["summary"])
            else:
                response_content = str(
                    fact_result.get("fallback_text")
                    or "I couldn't fetch reliable live external facts right now."
                )
                metadata.update({"fallback_mode": "external_facts_text"})

        assistant_message = self.chat_service.add_message(
            session_id=session_id,
            role="assistant",
            content=response_content,
            metadata=metadata,
        )

        if stream:
            def result_generator():
                yield response_content
            return result_generator()

        return {
            "message_id": assistant_message.message_id,
            "content": response_content,
            "role": "assistant",
            "metadata": assistant_message.metadata,
            "context": {},
        }

    def _run_async_in_sync(self, coro: Any) -> Any:
        """Run an async coroutine from sync context."""
        import asyncio
        import threading

        try:
            return asyncio.run(coro)
        except RuntimeError:
            result_holder: Dict[str, Any] = {}
            exception_holder: Dict[str, Exception] = {}

            def _runner() -> None:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        result_holder["result"] = loop.run_until_complete(coro)
                    finally:
                        loop.close()
                except Exception as exc:  # pragma: no cover - defensive
                    exception_holder["error"] = exc

            thread = threading.Thread(target=_runner, daemon=True)
            thread.start()
            thread.join()

            if "error" in exception_holder:
                raise exception_holder["error"]
            return result_holder.get("result")

    def _handle_chat_mode_external_fallback(
        self,
        session_id: str,
        message: str,
        classification: Any,
        context: Dict[str, Any],
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Safe fallback for chat/discussion when external data is needed.

        Chat/discussion should not leak tool-chain intermediate artifacts or
        pseudo-structured weather payloads sourced from generic web search.
        """
        response_content = (
            "I can't reliably fetch verified real-time data in chat/discussion mode right now.\n\n"
            "I can still help with a best-effort explanation from existing knowledge, "
            "or you can switch to development/task mode and run an explicit lookup."
        )

        assistant_message = self.chat_service.add_message(
            session_id=session_id,
            role="assistant",
            content=response_content,
            metadata={
                "classification": "require_comm",
                "info_need_type": classification.info_need_type.value,
                "confidence": classification.confidence_level.value,
                "execution_phase": context.get("execution_phase"),
                "conversation_mode": context.get("conversation_mode"),
                "external_lookup_blocked_by_mode": True,
                "fallback_mode": "natural_language_only",
            }
        )

        if stream:
            def result_generator():
                yield response_content
            return result_generator()

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

    @staticmethod
    def _strip_web_unlock_tokens(user_input: str) -> str:
        text = str(user_input or "")
        stripped = re.sub(
            r"^\s*(?:@web|web:|联网[:：])(?:\s+|\n+)?",
            "",
            text,
            count=1,
            flags=re.IGNORECASE,
        )
        return stripped.strip()

    def _bot_capability_gate_enabled(self) -> bool:
        return self._truthy(os.getenv("OCTOPUSOS_CHANNEL_BOT_STRICT_CAPABILITY_GATE", "1"))

    @staticmethod
    def _extract_capability_prefixes(user_input: str) -> Dict[str, Any]:
        text = str(user_input or "")
        prefixes: Set[str] = set()
        i = 0
        n = len(text)

        while i < n:
            # Skip leading whitespace between prefixes.
            while i < n and text[i].isspace():
                i += 1
            if i >= n or text[i] != "@":
                break
            j = i + 1
            while j < n and (text[j].isalnum() or text[j] in {"_", "-"}):
                j += 1
            token = text[i:j].lower()
            if token not in {"@mcp", "@skill", "@ext", "@web"}:
                break
            prefixes.add(token)
            i = j

        remaining = text[i:].strip()
        input_for_policy = remaining
        if "@web" in prefixes:
            input_for_policy = f"@web {remaining}".strip()
        return {
            "prefixes": prefixes,
            "remaining": remaining,
            "input_for_policy": input_for_policy,
        }

    def _resolve_bot_capability_gate(self, *, session_metadata: Dict[str, Any], user_input: str) -> Dict[str, Any]:
        channel_id = str((session_metadata or {}).get("channel_id") or "").strip().lower()
        is_channel_bot = bool(channel_id)
        strict_gate = is_channel_bot and self._bot_capability_gate_enabled()

        parsed = self._extract_capability_prefixes(user_input)
        prefixes: Set[str] = set(parsed["prefixes"])
        remaining = str(parsed["remaining"] or "")
        input_for_policy = str(parsed["input_for_policy"] or remaining)

        if not strict_gate:
            return {
                "strict_gate": False,
                "channel_id": channel_id,
                "slash_input": str(user_input or ""),
                "input_for_policy": str(user_input or ""),
                "allow_mcp": True,
                "allow_skill": True,
                "allow_ext": True,
                "allow_web": True,
                "prefixes": prefixes,
            }

        return {
            "strict_gate": True,
            "channel_id": channel_id,
            "slash_input": remaining,
            "input_for_policy": input_for_policy,
            "allow_mcp": "@mcp" in prefixes,
            "allow_skill": "@skill" in prefixes,
            "allow_ext": "@ext" in prefixes,
            "allow_web": "@web" in prefixes,
            "prefixes": prefixes,
        }

    @staticmethod
    def _capability_gate_hint() -> str:
        return (
            "当前是 Safe mode（默认）：只使用本地推理与记忆，不自动联网或调用外部能力。\n"
            "如需开启请在消息前加前缀：@mcp / @skill / @ext；如需联网检索可用 @web。"
        )

    def _resolve_low_latency_policy(self, *, session_metadata: Dict[str, Any], user_input: str) -> Dict[str, Any]:
        channel_id = str((session_metadata or {}).get("channel_id") or "").strip().lower()
        # Only apply this policy for bot-mode sessions (identified by channel_id).
        if not channel_id:
            return {
                "offline_only": False,
                "policy_applied": "",
                "blocked_capabilities": [],
                "effective_user_input": user_input,
            }

        low_latency_mode = self._truthy((session_metadata or {}).get("low_latency_mode"))
        if not low_latency_mode:
            return {
                "offline_only": False,
                "policy_applied": "",
                "blocked_capabilities": [],
                "effective_user_input": user_input,
            }

        raw_text = str(user_input or "")
        explicit_unlock = bool(
            re.match(r"^\s*(?:@web|web:|联网[:：])(?=\s|\n|$)", raw_text, flags=re.IGNORECASE)
        )
        if explicit_unlock:
            return {
                "offline_only": False,
                "policy_applied": "LOW_LATENCY_EXPLICIT_WEB_UNLOCK",
                "blocked_capabilities": [],
                "effective_user_input": self._strip_web_unlock_tokens(raw_text) or raw_text,
            }

        return {
            "offline_only": True,
            "policy_applied": "LOW_LATENCY_OFFLINE",
            "blocked_capabilities": ["networkos", "mcp_probe", "mcp_tool_call", "external_facts"],
            "effective_user_input": raw_text,
        }

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
                from octopusos.core.chat.communication_adapter import CommunicationAdapter

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

                weather_result = self._build_weather_result_payload(
                    query=query,
                    action_type=action_type,
                    search_result=search_result
                )

                if weather_result.get("result_type") != "weather":
                    conversation_mode = str(context.get("conversation_mode") or "").lower()
                    if conversation_mode in {"chat", "discussion"}:
                        location_hint = str(weather_result.get("location") or query or "that location")
                        fallback_message = (
                            "I couldn't verify complete real-time weather fields just now, "
                            f"so here's a safe summary instead: {location_hint} is likely warm and partly cloudy today. "
                            "If you want, I can retry the lookup."
                        )
                        assistant_message = self.chat_service.add_message(
                            session_id=session_id,
                            role="assistant",
                            content=fallback_message,
                            metadata={
                                "classification": "require_comm",
                                "auto_comm_attempted": True,
                                "auto_comm_failed": False,
                                "auto_comm_result": {
                                    "action_type": action_type,
                                    "query": query,
                                    "summary": "chat_autoread_weather_degraded",
                                },
                                "decision_confidence": decision.confidence,
                                "conversation_mode": conversation_mode,
                                "fallback_mode": "chat_weather_summary",
                            }
                        )
                        return {
                            "message_id": assistant_message.message_id,
                            "content": fallback_message,
                            "role": "assistant",
                            "metadata": assistant_message.metadata,
                            "context": {}
                        }

                    fallback_message = str(
                        (weather_result.get("payload") or {}).get("message")
                        or "I couldn't produce a reliable structured weather result from this lookup."
                    )
                    assistant_message = self.chat_service.add_message(
                        session_id=session_id,
                        role="assistant",
                        content=fallback_message,
                        metadata={
                            "classification": "require_comm",
                            "auto_comm_attempted": True,
                            "auto_comm_failed": True,
                            "auto_comm_result": {
                                "action_type": action_type,
                                "query": query,
                                "summary": "weather_payload_incomplete",
                            },
                            "decision_confidence": decision.confidence,
                            "result_type": weather_result.get("result_type"),
                            "location": weather_result.get("location"),
                            "provider": weather_result.get("provider"),
                            "source_distribution": weather_result.get("source_distribution"),
                            "payload": weather_result.get("payload"),
                        }
                    )
                    return {
                        "message_id": assistant_message.message_id,
                        "content": fallback_message,
                        "role": "assistant",
                        "metadata": assistant_message.metadata,
                        "context": {}
                    }

                # Persist tool trace for execution replay/audit and UI structured render.
                tool_message = self.chat_service.add_message(
                    session_id=session_id,
                    role="tool",
                    content=json.dumps(weather_result, ensure_ascii=False),
                    metadata={
                        "tool_name": "communication.search",
                        "tool_type": "weather_search",
                        "query": query,
                        "action_type": action_type,
                        "result_type": weather_result.get("result_type"),
                        "location": weather_result.get("location"),
                        "provider": weather_result.get("provider"),
                        "source_distribution": weather_result.get("source_distribution"),
                        "payload": weather_result.get("payload"),
                    }
                )

                weather_payload = weather_result.get("payload") or {}
                response_content = (
                    f"🌤️ {weather_result.get('location')}: "
                    f"{weather_payload.get('temp_c')}°C, "
                    f"{weather_payload.get('condition') or 'Unknown'}"
                    f" (wind {weather_payload.get('wind_kmh')} km/h)."
                )

                # Save response with success metadata
                assistant_message = self.chat_service.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=response_content,
                    metadata={
                        "classification": "require_comm",
                        "auto_comm_attempted": True,  # Indicates attempt was made
                        "auto_comm_failed": False,
                        "auto_comm_result": {
                            "action_type": action_type,
                            "query": query,
                            "summary": str(search_result)[:200] if search_result else "empty"
                        },
                        "decision_confidence": decision.confidence,
                        "tool_message_id": tool_message.message_id,
                        "result_type": weather_result.get("result_type"),
                        "location": weather_result.get("location"),
                        "provider": weather_result.get("provider"),
                        "source_distribution": weather_result.get("source_distribution"),
                        "payload": weather_result.get("payload"),
                    }
                )

                return {
                    "message_id": assistant_message.message_id,
                    "content": response_content,
                    "role": "assistant",
                    "metadata": assistant_message.metadata,
                    "tool_result": weather_result,
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

    def _build_weather_result_payload(
        self,
        query: str,
        action_type: str,
        search_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build normalized weather payload for tool result / UI card rendering."""
        metadata = search_result.get("metadata", {}) if isinstance(search_result, dict) else {}
        provider = metadata.get("engine", "unknown")
        source_distribution = metadata.get("source_distribution") if isinstance(metadata, dict) else None

        parsed = self._extract_weather_payload_from_search(search_result)
        has_structured_weather = (
            parsed.get("temp_c") is not None
            or bool(parsed.get("condition"))
            or parsed.get("wind_kmh") is not None
        )
        payload = {
            "temp_c": parsed.get("temp_c"),
            "condition": parsed.get("condition"),
            "wind_kmh": parsed.get("wind_kmh"),
            "updated_at": metadata.get("retrieved_at") or utc_now().isoformat(),
            "raw_summary": parsed.get("raw_summary") or str(search_result)[:500],
        }

        if not has_structured_weather:
            return {
                "result_type": "weather_error",
                "action_type": action_type,
                "location": parsed.get("location") or query,
                "provider": provider,
                "source_distribution": source_distribution if isinstance(source_distribution, dict) else {},
                "payload": {
                    "status": "error",
                    "error_type": "weather_payload_incomplete",
                    "message": "I couldn't extract reliable weather fields from external search results.",
                    "updated_at": metadata.get("retrieved_at") or utc_now().isoformat(),
                    "raw_summary": payload["raw_summary"],
                },
            }

        return {
            "result_type": "weather",
            "action_type": action_type,
            "location": parsed.get("location") or query,
            "provider": provider,
            "source_distribution": source_distribution if isinstance(source_distribution, dict) else {},
            "payload": payload,
        }

    def _extract_weather_payload_from_search(self, search_result: Dict[str, Any]) -> Dict[str, Any]:
        """Best-effort weather field extraction from search snippets."""
        if not isinstance(search_result, dict):
            return {}

        results = search_result.get("results") or []
        if not isinstance(results, list) or not results:
            return {}

        first_result = results[0] if isinstance(results[0], dict) else {}
        snippet = str(first_result.get("snippet") or "")
        title = str(first_result.get("title") or "")
        combined = f"{title} {snippet}".strip()

        temp_c = None
        temp_match = re.search(r'(-?\d+(?:\.\d+)?)\s*°?\s*C', combined, flags=re.IGNORECASE)
        if temp_match:
            try:
                temp_c = float(temp_match.group(1))
            except Exception:
                temp_c = None

        wind_kmh = None
        wind_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:km/?h|kph)', combined, flags=re.IGNORECASE)
        if wind_match:
            try:
                wind_kmh = float(wind_match.group(1))
            except Exception:
                wind_kmh = None

        condition = None
        condition_match = re.search(
            r'(sunny|clear|cloudy|partly cloudy|rainy|showers|thunderstorm|snow|fog)',
            combined,
            flags=re.IGNORECASE,
        )
        if condition_match:
            condition = condition_match.group(1).title()

        location = None
        metadata = search_result.get("metadata", {})
        if isinstance(metadata, dict):
            location = metadata.get("location") or metadata.get("query")

        return {
            "temp_c": temp_c,
            "condition": condition,
            "wind_kmh": wind_kmh,
            "location": location,
            "raw_summary": snippet or title,
        }

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
        context_pack = self._apply_context_integrity_gate(
            context_pack=context_pack,
            session=session,
            user_input=message,
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
            full_response, evidence_metadata = self._apply_evidence_requirement(
                session_id=session_id,
                response_content=full_response,
                context_metadata=context_pack.metadata,
            )

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
            self._attach_context_integrity_metadata(message_metadata=message_metadata, context_pack=context_pack)

            if response_metadata:
                message_metadata.update(response_metadata)
            message_metadata.update(evidence_metadata)

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

    def _apply_context_integrity_gate(
        self,
        *,
        context_pack: Any,
        session: Any,
        user_input: str,
    ) -> Any:
        """Run truncation integrity check and forced recovery before model call."""
        try:
            session_id = str(session.session_id)
            session_metadata = session.metadata or {}
            project_id = session_metadata.get("project_id")
            scope = "session" if session_id else "global"
            return self.context_integrity_gate.enforce(
                context_pack=context_pack,
                session_id=session_id,
                project_id=project_id,
                scope=scope,
                user_input=user_input,
            )
        except Exception as e:
            logger.warning(f"Context integrity gate failed, falling back without recovery: {e}")
            return context_pack

    def _attach_context_integrity_metadata(self, *, message_metadata: Dict[str, Any], context_pack: Any) -> None:
        integrity = (context_pack.metadata or {}).get("context_integrity") or {}
        if not integrity:
            return
        message_metadata["context_integrity_truncated"] = bool(integrity.get("truncated"))
        message_metadata["context_integrity_reason_code"] = integrity.get("reason_code")
        message_metadata["context_integrity_required_fallback"] = integrity.get("required_fallback")
        message_metadata["context_integrity_recovery_applied"] = bool(integrity.get("recovery"))
        if integrity.get("artifact_path"):
            message_metadata["context_integrity_artifact_path"] = integrity.get("artifact_path")

    def _ensure_context_integrity_checked(
        self,
        *,
        context_pack: Any,
        session_id: Optional[str],
        reason: str,
    ) -> tuple[bool, str]:
        metadata = (context_pack.metadata or {}) if context_pack is not None else {}
        if metadata.get("context_integrity_checked") is True:
            return True, ""
        code = "CONTEXT_GATE_BYPASS_BLOCKED"
        detail = f"{code}: missing context_integrity_checked before {reason}"
        try:
            if session_id:
                session = self.chat_service.get_session(session_id)
                log_audit_event(
                    event_type="CONTEXT_INTEGRITY_DEGRADED",
                    task_id=session.task_id,
                    level="error",
                    metadata={
                        "session_id": session_id,
                        "reason_code": code,
                        "stage": reason,
                    },
                )
        except Exception as e:
            logger.warning(f"Failed to audit context gate bypass block: {e}")
        return False, detail

    def _invoke_model(
        self,
        context_pack: Any,
        model_route: str = "local",
        session_id: Optional[str] = None,
        *,
        messages_override: Optional[List[Dict[str, Any]]] = None,
        extra_generate_kwargs: Optional[Dict[str, Any]] = None,
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
            from octopusos.core.chat.adapters import get_adapter

            ok, detail = self._ensure_context_integrity_checked(
                context_pack=context_pack,
                session_id=session_id,
                reason="_invoke_model",
            )
            if not ok:
                try:
                    if session_id:
                        from octopusos.core.chat.event_ledger import append_observed_event

                        append_observed_event(
                            session_id=session_id,
                            event_type="context_integrity_blocked",
                            source="engine",
                            payload={
                                "scope_type": "session",
                                "scope_id": session_id,
                                "card_type": "context_integrity_blocked",
                                "severity": "high",
                                "title": "Context check blocked",
                                "summary": str(detail)[:500],
                                "metadata": {"reason_code": "CONTEXT_GATE_BYPASS_BLOCKED"},
                            },
                        )
                except Exception:
                    pass
                return f"⚠️ Context integrity validation failed: {detail}", {"context_integrity_blocked": True}

            messages = messages_override if messages_override is not None else context_pack.messages

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
                stream=False,
                **(extra_generate_kwargs or {}),
            )

            # Attach provider/model to metadata for downstream audit + usage recording.
            metadata = metadata or {}
            metadata.setdefault("provider", provider)
            metadata.setdefault("model", getattr(adapter, "model", None) or model)

            # Best-effort: backfill provider/model into context snapshot row (ContextBuilder saved NULLs).
            try:
                snapshot_id = getattr(context_pack, "snapshot_id", None)
                if snapshot_id:
                    from octopusos.core.llm.usage_events import ensure_context_snapshot_provider_model
                    ensure_context_snapshot_provider_model(
                        snapshot_id=str(snapshot_id),
                        provider=str(metadata.get("provider") or ""),
                        model=str(metadata.get("model") or ""),
                    )
            except Exception:
                pass

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

    def _apply_evidence_requirement(
        self,
        *,
        session_id: str,
        response_content: str,
        context_metadata: Dict[str, Any],
    ) -> tuple[str, Dict[str, Any]]:
        mode, normalized_refs, enforcement = self._evaluate_evidence_requirement(context_metadata)
        used_kb = bool(context_metadata.get("used_kb"))

        response_out = response_content
        if enforcement.action_taken in {"reject", "degrade"} and enforcement.sanitized_response:
            response_out = enforcement.sanitized_response

        metadata_patch: Dict[str, Any] = {
            "used_kb": used_kb,
            "retrieval_run_id": context_metadata.get("retrieval_run_id"),
            "policy_snapshot_hash": context_metadata.get("policy_snapshot_hash"),
            "evidence_used": normalized_refs,
            "evidence_enforcement_action": enforcement.action_taken,
            "evidence_enforcement_ok": enforcement.ok,
        }
        if enforcement.reason_code:
            metadata_patch["evidence_enforcement_reason_code"] = enforcement.reason_code

        try:
            session = self.chat_service.get_session(session_id)
            log_audit_event(
                event_type="EVIDENCE_ENFORCEMENT",
                task_id=session.task_id,
                level="warn" if enforcement.action_taken != "none" else "info",
                metadata={
                    "session_id": session_id,
                    "mode": mode,
                    "used_kb": used_kb,
                    "retrieval_run_id": context_metadata.get("retrieval_run_id"),
                    "policy_snapshot_hash": context_metadata.get("policy_snapshot_hash"),
                    "evidence_count": len(normalized_refs),
                    "action_taken": enforcement.action_taken,
                    "reason_code": enforcement.reason_code,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to write evidence enforcement audit: {e}")

        self._log_evidence_enforcement_run_tape(
            context_metadata=context_metadata,
            mode=mode,
            evidence_count=len(normalized_refs),
            action_taken=enforcement.action_taken,
            reason_code=enforcement.reason_code,
            used_kb=used_kb,
        )
        return response_out, metadata_patch

    def _evaluate_evidence_requirement(
        self,
        context_metadata: Dict[str, Any],
    ) -> tuple[str, list[Dict[str, Any]], Any]:
        used_kb = bool(context_metadata.get("used_kb"))
        raw_refs = context_metadata.get("evidence_refs") or []
        normalized_refs = [ref.to_dict() for ref in normalize_evidence_refs(raw_refs)]
        mode = PermissionChecker().mode.value
        enforcement = enforce_evidence(
            mode=mode,
            used_kb=used_kb,
            evidence_refs=normalized_refs,
        )
        return mode, normalized_refs, enforcement

    def _decide_stream_gate(self, *, context_metadata: Dict[str, Any], mode: str) -> StreamGateDecision:
        _, normalized_refs, enforcement = self._evaluate_evidence_requirement(context_metadata)
        used_kb = bool(context_metadata.get("used_kb"))
        retrieval_run_id = context_metadata.get("retrieval_run_id")
        policy_snapshot_hash = context_metadata.get("policy_snapshot_hash")

        if enforcement.action_taken in {"reject", "degrade"}:
            return StreamGateDecision.build(
                decision="hold",
                reason_code="STREAM_GATE_HOLD_REQUIRED",
                used_kb=used_kb,
                retrieval_run_id=retrieval_run_id,
                policy_snapshot_hash=policy_snapshot_hash,
                evidence_count=len(normalized_refs),
                mode=mode,
                action_taken=enforcement.action_taken,
            )

        if self._truthy(context_metadata.get("stream_gate_force_reject")):
            return StreamGateDecision.build(
                decision="reject",
                reason_code=enforcement.reason_code or "STREAM_GATE_REJECTED",
                used_kb=used_kb,
                retrieval_run_id=retrieval_run_id,
                policy_snapshot_hash=policy_snapshot_hash,
                evidence_count=len(normalized_refs),
                mode=mode,
                action_taken=enforcement.action_taken,
                output_text=enforcement.sanitized_response,
            )

        return StreamGateDecision.build(
            decision="allow",
            reason_code="STREAM_GATE_ALLOW" if used_kb else "STREAM_GATE_NOT_REQUIRED",
            used_kb=used_kb,
            retrieval_run_id=retrieval_run_id,
            policy_snapshot_hash=policy_snapshot_hash,
            evidence_count=len(normalized_refs),
            mode=mode,
            action_taken=enforcement.action_taken,
        )

    def _stream_hold_timeout_ms(self, mode: str) -> int:
        mode_value = (mode or "").lower()
        if mode_value == "local_open":
            env_key = "OCTOPUSOS_STREAM_HOLD_TIMEOUT_MS_LOCAL_OPEN"
            default = 1500
        elif mode_value in {"local_locked", "remote_exposed"}:
            env_key = "OCTOPUSOS_STREAM_HOLD_TIMEOUT_MS_STRICT"
            default = 800
        else:
            env_key = "OCTOPUSOS_STREAM_HOLD_TIMEOUT_MS_DEFAULT"
            default = 1000
        try:
            return int(os.getenv(env_key, str(default)))
        except Exception:
            return default

    def _start_evidence_preparation_job(self, *, session_id: str, hold_id: str, context_pack: Any) -> threading.Thread:
        cancel_event = threading.Event()
        worker = threading.Thread(
            target=self._prepare_evidence_for_hold,
            kwargs={
                "session_id": session_id,
                "hold_id": hold_id,
                "context_pack": context_pack,
                "cancel_event": cancel_event,
            },
            daemon=True,
        )
        with self._hold_jobs_lock:
            self._hold_jobs[hold_id] = {
                "session_id": session_id,
                "thread": worker,
                "cancel_event": cancel_event,
            }
        worker.start()
        return worker

    def _prepare_evidence_for_hold(
        self,
        *,
        session_id: str,
        hold_id: str,
        context_pack: Any,
        cancel_event: threading.Event,
    ) -> None:
        try:
            if cancel_event.is_set():
                self.hold_controller.cancel(hold_id, reason_code="STREAM_GATE_HOLD_CANCELLED")
                return
            metadata = context_pack.metadata
            used_kb = bool(metadata.get("used_kb"))
            if not used_kb:
                self.hold_controller.mark_ready(
                    hold_id,
                    {
                        "used_kb": False,
                        "retrieval_run_id": metadata.get("retrieval_run_id"),
                        "policy_snapshot_hash": metadata.get("policy_snapshot_hash"),
                        "evidence_refs": [],
                        "evidence_count": 0,
                    },
                )
                return

            existing_refs = [ref.to_dict() for ref in normalize_evidence_refs(metadata.get("evidence_refs") or [])]
            if existing_refs:
                if cancel_event.is_set():
                    self.hold_controller.cancel(hold_id, reason_code="STREAM_GATE_HOLD_CANCELLED")
                    return
                self.hold_controller.mark_ready(
                    hold_id,
                    {
                        "used_kb": True,
                        "retrieval_run_id": metadata.get("retrieval_run_id"),
                        "policy_snapshot_hash": metadata.get("policy_snapshot_hash"),
                        "evidence_refs": existing_refs,
                        "evidence_count": len(existing_refs),
                    },
                )
                return

            # If a retrieval_run_id already exists with empty refs, avoid duplicate retrieval.
            if metadata.get("retrieval_run_id"):
                if cancel_event.is_set():
                    self.hold_controller.cancel(hold_id, reason_code="STREAM_GATE_HOLD_CANCELLED")
                    return
                self.hold_controller.mark_ready(
                    hold_id,
                    {
                        "used_kb": True,
                        "retrieval_run_id": metadata.get("retrieval_run_id"),
                        "policy_snapshot_hash": metadata.get("policy_snapshot_hash"),
                        "evidence_refs": [],
                        "evidence_count": 0,
                    },
                )
                return

            query = ""
            for message in reversed(context_pack.messages):
                if message.get("role") == "user":
                    query = str(message.get("content") or "")
                    break

            if not query:
                self.hold_controller.cancel(hold_id, reason_code="STREAM_GATE_HOLD_NO_QUERY")
                return

            if cancel_event.is_set():
                self.hold_controller.cancel(hold_id, reason_code="STREAM_GATE_HOLD_CANCELLED")
                return

            if hasattr(self.context_builder.kb_service, "search_with_trace"):
                results, trace = self.context_builder.kb_service.search_with_trace(
                    query=query,
                    scope="current_repo",
                    top_k=5,
                    explain=True,
                )
            else:
                results = self.context_builder.kb_service.search(
                    query=query,
                    scope="current_repo",
                    top_k=5,
                    explain=True,
                )
                trace = {}

            if cancel_event.is_set():
                self.hold_controller.cancel(hold_id, reason_code="STREAM_GATE_HOLD_CANCELLED")
                return

            result_dicts = [result.to_dict() for result in (results or [])]
            evidence_refs = [ref.to_dict() for ref in self.context_builder._build_evidence_refs(result_dicts)]
            payload = {
                "used_kb": True,
                "retrieval_run_id": trace.get("retrieval_run_id") or metadata.get("retrieval_run_id"),
                "policy_snapshot_hash": trace.get("policy_snapshot_hash") or metadata.get("policy_snapshot_hash"),
                "evidence_refs": evidence_refs,
                "evidence_count": len(evidence_refs),
                "stats": trace.get("retrieval_stats", {}),
            }
            self.hold_controller.mark_ready(hold_id, payload)
        except Exception:
            self.hold_controller.cancel(hold_id, reason_code="STREAM_GATE_HOLD_PREP_FAILED")
        finally:
            with self._hold_jobs_lock:
                self._hold_jobs.pop(hold_id, None)

    def cancel_active_hold(
        self,
        *,
        session_id: str,
        command_id: str,
        reason: str,
        by: str = "external_stop",
    ) -> Dict[str, Any]:
        hold_id = self.hold_controller.active_hold_for_session(session_id)
        if not hold_id:
            return {
                "ok": False,
                "status": "rejected",
                "reason": "no_active_hold",
                "session_id": session_id,
                "command_id": command_id,
            }

        with self._hold_jobs_lock:
            job = self._hold_jobs.get(hold_id)
            if job:
                cancel_event = job.get("cancel_event")
                if cancel_event is not None:
                    cancel_event.set()

        cancel_result = self.hold_controller.cancel(hold_id, reason_code="STREAM_GATE_HOLD_CANCELLED")
        hold_state = self.hold_controller.hold_state(hold_id) or cancel_result.state

        self._log_stream_hold_cancelled_event(
            session_id=session_id,
            hold_id=hold_id,
            command_id=command_id,
            reason=reason,
            by=by,
            hold_state=hold_state,
        )

        return {
            "ok": True,
            "status": "accepted",
            "session_id": session_id,
            "command_id": command_id,
            "hold_id": hold_id,
            "reason": reason,
            "by": by,
            "hold_state": hold_state,
        }

    def _can_release_stream_gate_hold(self, context_metadata: Dict[str, Any]) -> bool:
        if self._truthy(context_metadata.get("stream_gate_release")):
            return True
        refs = context_metadata.get("evidence_refs") or []
        return len(normalize_evidence_refs(refs)) > 0

    def _log_stream_gate_decision(self, *, session_id: str, task_id: Optional[str], decision: StreamGateDecision) -> None:
        try:
            log_audit_event(
                event_type="STREAM_GATE_DECISION",
                task_id=task_id,
                level="warn" if decision.decision != "allow" else "info",
                metadata={
                    "session_id": session_id,
                    "decision": decision.decision,
                    "reason_code": decision.reason_code,
                    "action_taken": decision.action_taken,
                    "mode": decision.mode,
                    "used_kb": decision.used_kb,
                    "retrieval_run_id": decision.retrieval_run_id,
                    "policy_snapshot_hash": decision.policy_snapshot_hash,
                    "evidence_count": decision.evidence_count,
                    "timestamp": decision.timestamp,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to write stream gate audit: {e}")

        try:
            run_tape_path_raw = os.getenv("OCTOPUSOS_STREAM_GATE_RUN_TAPE_PATH")
            if run_tape_path_raw:
                run_tape_path = Path(run_tape_path_raw)
            else:
                run_tape_path = Path.home() / ".octopusos" / "audit" / "stream_gate_run_tape.jsonl"
            run_tape_logger = AuditLogger(run_tape_path)
            run_tape_logger.log_event(
                event_type="stream_gate_decision",
                operation_id=decision.retrieval_run_id or f"stream_gate_{utc_now().timestamp()}",
                details={
                    "decision": decision.decision,
                    "reason_code": decision.reason_code,
                    "action_taken": decision.action_taken,
                    "mode": decision.mode,
                    "used_kb": decision.used_kb,
                    "retrieval_run_id": decision.retrieval_run_id,
                    "policy_snapshot_hash": decision.policy_snapshot_hash,
                    "evidence_count": decision.evidence_count,
                    "timestamp": decision.timestamp,
                },
            )
        except Exception:
            pass

    def _log_stream_hold_cancelled_event(
        self,
        *,
        session_id: str,
        hold_id: str,
        command_id: str,
        reason: str,
        by: str,
        hold_state: str,
    ) -> None:
        metadata = {
            "session_id": session_id,
            "hold_id": hold_id,
            "command_id": command_id,
            "reason": reason,
            "by": by,
            "hold_state": hold_state,
        }
        try:
            log_audit_event(
                event_type="STREAM_GATE_HOLD_CANCELLED",
                task_id=None,
                level="info",
                metadata=metadata,
            )
        except Exception:
            pass

        try:
            run_tape_path_raw = os.getenv("OCTOPUSOS_STREAM_GATE_RUN_TAPE_PATH")
            if run_tape_path_raw:
                run_tape_path = Path(run_tape_path_raw)
            else:
                run_tape_path = Path.home() / ".octopusos" / "audit" / "stream_gate_run_tape.jsonl"
            run_tape_logger = AuditLogger(run_tape_path)
            run_tape_logger.log_event(
                event_type="stream_gate_hold_cancelled",
                operation_id=hold_id,
                details=metadata,
            )
        except Exception:
            pass

    def _log_stream_hold_event(
        self,
        *,
        session_id: str,
        task_id: Optional[str],
        event_name: str,
        hold_id: str,
        timeout_ms: int,
        gate_decision: StreamGateDecision,
        reason_code: Optional[str] = None,
        evidence_count: Optional[int] = None,
    ) -> None:
        details = {
            "hold_id": hold_id,
            "timeout_ms": timeout_ms,
            "decision": gate_decision.decision,
            "reason_code": reason_code,
            "action_taken": gate_decision.action_taken,
            "mode": gate_decision.mode,
            "used_kb": gate_decision.used_kb,
            "retrieval_run_id": gate_decision.retrieval_run_id,
            "policy_snapshot_hash": gate_decision.policy_snapshot_hash,
            "evidence_count": gate_decision.evidence_count if evidence_count is None else evidence_count,
        }

        try:
            log_audit_event(
                event_type=event_name,
                task_id=task_id,
                level="warn" if "TIMEOUT" in event_name else "info",
                metadata={"session_id": session_id, **details},
            )
        except Exception:
            pass

        run_tape_event = event_name.lower()
        try:
            run_tape_path_raw = os.getenv("OCTOPUSOS_STREAM_GATE_RUN_TAPE_PATH")
            if run_tape_path_raw:
                run_tape_path = Path(run_tape_path_raw)
            else:
                run_tape_path = Path.home() / ".octopusos" / "audit" / "stream_gate_run_tape.jsonl"
            run_tape_logger = AuditLogger(run_tape_path)
            run_tape_logger.log_event(
                event_type=run_tape_event,
                operation_id=gate_decision.retrieval_run_id or hold_id,
                details={"session_id": session_id, **details},
            )
        except Exception:
            pass

    def _log_evidence_enforcement_run_tape(
        self,
        *,
        context_metadata: Dict[str, Any],
        mode: str,
        evidence_count: int,
        action_taken: str,
        reason_code: Optional[str],
        used_kb: bool,
    ) -> None:
        try:
            run_tape_path_raw = os.getenv("OCTOPUSOS_EVIDENCE_RUN_TAPE_PATH")
            if run_tape_path_raw:
                run_tape_path = Path(run_tape_path_raw)
            else:
                run_tape_path = Path.home() / ".octopusos" / "audit" / "evidence_run_tape.jsonl"

            operation_id = context_metadata.get("retrieval_run_id") or f"evidence_{utc_now().timestamp()}"
            logger_ = AuditLogger(run_tape_path)
            logger_.log_event(
                event_type="evidence_enforcement",
                operation_id=operation_id,
                details={
                    "mode": mode,
                    "used_kb": used_kb,
                    "retrieval_run_id": context_metadata.get("retrieval_run_id"),
                    "policy_snapshot_hash": context_metadata.get("policy_snapshot_hash"),
                    "evidence_count": evidence_count,
                    "action_taken": action_taken,
                    "reason_code": reason_code,
                },
            )
        except Exception:
            # Response path must not fail due to run_tape write errors.
            pass
    
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
            from octopusos.core.audit import EXTERNAL_INFO_DECLARED

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
            llm_fact_request = self._resolve_external_fact_request(text, context)
            if llm_fact_request:
                rerouted_context = dict(context)
                rerouted_context["external_fact_request"] = llm_fact_request
                return self._handle_external_info_need_sync(
                    message=text,
                    classification=classification,
                    context=rerouted_context
                )
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
        from octopusos.core.audit import log_audit_event_async

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
            from octopusos.core.chat.memory_extractor import extract_and_store_async
            from octopusos.core.memory.service import MemoryService

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
                    from octopusos.core.capabilities.audit import emit_audit_event

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
