"""Context builder for Chat Mode - assembles context from multiple sources"""

from typing import List, Dict, Any, Optional, Literal
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import logging
import hashlib
import json
import sqlite3

from agentos.core.chat.models import ChatMessage
from agentos.core.chat.service import ChatService
from agentos.core.memory.service import MemoryService
from agentos.core.project_kb.service import ProjectKBService
from agentos.util.ulid import ulid

logger = logging.getLogger(__name__)


class UsageWatermark(Enum):
    """Token usage watermarks for auto-summary trigger"""
    SAFE = "safe"          # < 60%
    WARNING = "warning"    # 60-80%
    CRITICAL = "critical"  # > 80%


@dataclass
class ContextBudget:
    """Context budget configuration"""
    max_tokens: int = 8000
    system_tokens: int = 1000
    window_tokens: int = 4000
    rag_tokens: int = 2000
    memory_tokens: int = 1000
    summary_tokens: int = 0  # Reserved for summary messages

    # NEW: Generation parameters
    generation_max_tokens: int = 2000  # Maximum tokens for model generation

    # NEW: Metadata fields
    auto_derived: bool = False  # Whether this budget was auto-derived from model window
    model_context_window: Optional[int] = None  # Original model context window (if auto-derived)

    # Watermark thresholds (as ratio of budget)
    safe_threshold: float = 0.6      # 60%
    critical_threshold: float = 0.8  # 80%


@dataclass
class ContextUsage:
    """Context usage statistics"""
    budget_tokens: int
    total_tokens_est: int
    tokens_system: int
    tokens_window: int
    tokens_rag: int
    tokens_memory: int
    tokens_summary: int
    tokens_policy: int = 0
    
    @property
    def usage_ratio(self) -> float:
        """Calculate usage ratio (0.0 to 1.0+)"""
        if self.budget_tokens == 0:
            return 0.0
        return self.total_tokens_est / self.budget_tokens
    
    @property
    def watermark(self) -> UsageWatermark:
        """Determine usage watermark level"""
        ratio = self.usage_ratio
        if ratio >= 0.8:
            return UsageWatermark.CRITICAL
        elif ratio >= 0.6:
            return UsageWatermark.WARNING
        else:
            return UsageWatermark.SAFE
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "budget_tokens": self.budget_tokens,
            "total_tokens_est": self.total_tokens_est,
            "tokens_system": self.tokens_system,
            "tokens_window": self.tokens_window,
            "tokens_rag": self.tokens_rag,
            "tokens_memory": self.tokens_memory,
            "tokens_summary": self.tokens_summary,
            "tokens_policy": self.tokens_policy,
            "usage_ratio": self.usage_ratio,
            "watermark": self.watermark.value,
            # NEW: Add breakdown for frontend
            "breakdown": {
                "system": self.tokens_system,
                "window": self.tokens_window,
                "rag": self.tokens_rag,
                "memory": self.tokens_memory
            }
        }


@dataclass
class ContextPack:
    """Assembled context ready for model"""
    messages: List[Dict[str, str]]  # OpenAI format
    metadata: Dict[str, Any]
    audit: Dict[str, Any]
    usage: ContextUsage  # NEW: Usage statistics
    snapshot_id: Optional[str] = None  # NEW: Snapshot ID if saved
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "messages": self.messages,
            "metadata": self.metadata,
            "audit": self.audit,
            "usage": self.usage.to_dict(),
            "snapshot_id": self.snapshot_id
        }


class ContextBuilder:
    """Builds context for Chat Mode with RAG, Memory, and budget management"""
    
    def __init__(
        self,
        chat_service: Optional[ChatService] = None,
        memory_service: Optional[MemoryService] = None,
        kb_service: Optional[ProjectKBService] = None,
        budget: Optional[ContextBudget] = None,
        budget_resolver: Optional['BudgetResolver'] = None,
        db_path: Optional[str] = None,
        enable_auto_summary: bool = True,
        enable_snapshots: bool = True
    ):
        """Initialize ContextBuilder

        Args:
            chat_service: ChatService instance
            memory_service: MemoryService instance
            kb_service: ProjectKBService instance
            budget: Context budget configuration (if None, uses budget_resolver)
            budget_resolver: BudgetResolver for auto-deriving budgets
            db_path: Database path (for snapshots)
            enable_auto_summary: Whether to auto-trigger summaries
            enable_snapshots: Whether to save context snapshots
        """
        self.chat_service = chat_service or ChatService()
        self.memory_service = memory_service or MemoryService()
        self.kb_service = kb_service or ProjectKBService()
        self.db_path = db_path or self.chat_service.db_path

        # Budget resolution: use provided budget or resolve via budget_resolver
        if budget is not None:
            self.budget = budget
        else:
            # Import here to avoid circular dependency
            from agentos.core.chat.budget_resolver import BudgetResolver
            resolver = budget_resolver or BudgetResolver(db_path=self.db_path)
            self.budget = resolver.get_default_budget()

        self.enable_auto_summary = enable_auto_summary
        self.enable_snapshots = enable_snapshots

        # Summary artifacts cache (artifact_id -> message range)
        self._summary_cache: Dict[str, tuple[int, int]] = {}
    
    def build(
        self,
        session_id: str,
        user_input: str,
        rag_enabled: bool = True,
        memory_enabled: bool = True,
        reason: Literal["send", "dry_run", "audit"] = "send"
    ) -> ContextPack:
        """Build context for a chat message

        Args:
            session_id: Chat session ID
            user_input: User's input message
            rag_enabled: Whether to include RAG context
            memory_enabled: Whether to include Memory facts
            reason: Reason for building context (send/dry_run/audit)

        Returns:
            ContextPack with assembled context
        """
        logger.info(f"Building context for session {session_id} (reason: {reason})")

        # NEW: Log budget source
        logger.info(
            f"Budget: {self.budget.max_tokens} tokens "
            f"(source: {'auto-derived' if self.budget.auto_derived else 'configured'}, "
            f"model_window: {self.budget.model_context_window})"
        )
        
        # 1. Load session window (recent messages)
        window_messages = self._load_session_window(session_id)
        
        # 2. Check if auto-summary should be triggered
        summary_artifacts = []
        if self.enable_auto_summary and reason == "send":
            summary_trigger = self._check_summary_trigger(session_id, window_messages)
            if summary_trigger:
                logger.info(f"Auto-summary triggered: {summary_trigger['reason']}")
                # Create summary (this will be handled after context build)
                # For now, load existing summaries
                summary_artifacts = self._load_summary_artifacts(session_id)
        else:
            summary_artifacts = self._load_summary_artifacts(session_id)
        
        # 3. Load pinned facts from Memory
        memory_facts = []
        if memory_enabled:
            memory_facts = self._load_memory_facts(session_id)
        
        # 4. Load RAG context
        rag_chunks = []
        if rag_enabled:
            rag_chunks = self._load_rag_context(user_input)
        
        # 5. Check budget and trim if needed
        context_parts = {
            "window": window_messages,
            "memory": memory_facts,
            "rag": rag_chunks,
            "summaries": summary_artifacts
        }
        
        trimmed_parts = self._apply_budget(context_parts)
        
        # 6. Load policy rules (system prompt)
        system_prompt = self._build_system_prompt(trimmed_parts, session_id)
        
        # 7. Assemble messages
        messages = self._assemble_messages(
            system_prompt=system_prompt,
            window_messages=trimmed_parts["window"],
            memory_facts=trimmed_parts["memory"],
            rag_chunks=trimmed_parts["rag"],
            summary_artifacts=trimmed_parts["summaries"],
            user_input=user_input
        )
        
        # 8. Calculate usage statistics
        usage = self._calculate_usage(
            system_prompt=system_prompt,
            window_messages=trimmed_parts["window"],
            memory_facts=trimmed_parts["memory"],
            rag_chunks=trimmed_parts["rag"],
            summary_artifacts=trimmed_parts["summaries"],
            user_input=user_input
        )
        
        # 9. Generate audit trail
        audit = self._generate_audit(
            session_id=session_id,
            messages=messages,
            rag_chunks=rag_chunks,
            memory_facts=memory_facts,
            summary_artifacts=summary_artifacts,
            usage=usage
        )
        
        # 10. Build metadata
        metadata = {
            "session_id": session_id,
            "total_tokens": usage.total_tokens_est,
            "rag_enabled": rag_enabled,
            "memory_enabled": memory_enabled,
            "window_count": len(trimmed_parts["window"]),
            "rag_count": len(rag_chunks),
            "memory_count": len(memory_facts),
            "summary_count": len(summary_artifacts),
            "usage_ratio": usage.usage_ratio,
            "watermark": usage.watermark.value
        }
        
        # 11. Save context snapshot (if enabled)
        snapshot_id = None
        if self.enable_snapshots:
            snapshot_id = self._save_snapshot(
                session_id=session_id,
                reason=reason,
                usage=usage,
                composition={
                    "window_msg_ids": [m.message_id for m in trimmed_parts["window"]],
                    "summary_artifact_ids": [s["artifact_id"] for s in summary_artifacts],
                    "rag_chunk_ids": [c.get("chunk_id") for c in rag_chunks],
                    "memory_ids": [f.get("id") for f in memory_facts]
                },
                assembled_hash=audit["context_hash"]
            )
        
        return ContextPack(
            messages=messages,
            metadata=metadata,
            audit=audit,
            usage=usage,
            snapshot_id=snapshot_id
        )
    
    def _load_session_window(self, session_id: str) -> List[ChatMessage]:
        """Load recent messages from session
        
        Args:
            session_id: Session ID
        
        Returns:
            List of recent messages
        """
        # Load last 10 messages (configurable)
        messages = self.chat_service.get_recent_messages(session_id, count=10)
        logger.debug(f"Loaded {len(messages)} messages from window")
        return messages
    
    def _load_memory_facts(self, session_id: str) -> List[Dict[str, Any]]:
        """Load pinned facts from Memory
        
        Args:
            session_id: Session ID
        
        Returns:
            List of memory items
        """
        try:
            # Get session to find project_id
            session = self.chat_service.get_session(session_id)
            project_id = session.metadata.get("project_id")
            
            if not project_id:
                logger.debug("No project_id in session metadata, skipping memory")
                return []
            
            # Build memory context
            memory_context = self.memory_service.build_context(
                project_id=project_id,
                agent_type="chat",
                confidence_threshold=0.3,
                budget={"max_memories": 10, "max_tokens": self.budget.memory_tokens}
            )
            
            memories = memory_context.get("memories", [])
            logger.debug(f"Loaded {len(memories)} memory facts")
            return memories
        
        except Exception as e:
            logger.warning(f"Failed to load memory facts: {e}")
            return []
    
    def _load_rag_context(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Load RAG context from ProjectKB
        
        Args:
            query: Search query
            top_k: Number of chunks to retrieve
        
        Returns:
            List of chunk results
        """
        try:
            results = self.kb_service.search(
                query=query,
                scope="current_repo",
                top_k=top_k,
                explain=True
            )
            
            logger.debug(f"Retrieved {len(results)} RAG chunks")
            return [r.to_dict() for r in results]
        
        except Exception as e:
            logger.warning(f"Failed to load RAG context: {e}")
            return []
    
    def _apply_budget(self, context_parts: Dict[str, Any]) -> Dict[str, Any]:
        """Apply token budget and trim context if needed

        Args:
            context_parts: Dictionary of context parts

        Returns:
            Trimmed context parts
        """
        # Estimate tokens for each part
        window_tokens = sum(msg.estimate_tokens() for msg in context_parts["window"])
        memory_tokens = sum(self._estimate_text_tokens(json.dumps(m)) for m in context_parts["memory"])
        rag_tokens = sum(self._estimate_text_tokens(c.get("content", "")) for c in context_parts["rag"])
        summary_tokens = sum(self._estimate_text_tokens(s.get("content", "")) for s in context_parts.get("summaries", []))

        total = window_tokens + memory_tokens + rag_tokens + summary_tokens

        logger.debug(f"Token usage: window={window_tokens}, memory={memory_tokens}, rag={rag_tokens}, summary={summary_tokens}, total={total}")

        # If under budget, return as-is
        if total <= (self.budget.max_tokens - self.budget.system_tokens):
            return context_parts

        # Otherwise, trim (priority: summaries > window > memory > rag)
        logger.warning(f"Context over budget ({total} tokens), trimming")

        # Store original counts for audit
        original_window = len(context_parts["window"])
        original_rag = len(context_parts["rag"])
        original_memory = len(context_parts["memory"])

        # Trim RAG first
        if rag_tokens > self.budget.rag_tokens:
            context_parts["rag"] = self._trim_rag(context_parts["rag"], self.budget.rag_tokens)

        # Trim memory if still over
        if memory_tokens > self.budget.memory_tokens:
            context_parts["memory"] = self._trim_memory(context_parts["memory"], self.budget.memory_tokens)

        # Trim window if still over (keep most recent)
        if window_tokens > self.budget.window_tokens:
            context_parts["window"] = self._trim_window(context_parts["window"], self.budget.window_tokens)

        # NEW: Log trimming operations
        trimmed_window = original_window - len(context_parts["window"])
        trimmed_rag = original_rag - len(context_parts["rag"])
        trimmed_memory = original_memory - len(context_parts["memory"])

        if trimmed_window > 0:
            logger.warning(f"Trimmed {trimmed_window} messages from window (budget: {self.budget.window_tokens})")
        if trimmed_rag > 0:
            logger.warning(f"Trimmed {trimmed_rag} RAG chunks (budget: {self.budget.rag_tokens})")
        if trimmed_memory > 0:
            logger.warning(f"Trimmed {trimmed_memory} memory facts (budget: {self.budget.memory_tokens})")

        return context_parts
    
    def _trim_rag(self, chunks: List[Dict[str, Any]], max_tokens: int) -> List[Dict[str, Any]]:
        """Trim RAG chunks to fit budget"""
        trimmed = []
        tokens = 0
        
        # Chunks are already sorted by score (highest first)
        for chunk in chunks:
            chunk_tokens = self._estimate_text_tokens(chunk.get("content", ""))
            if tokens + chunk_tokens <= max_tokens:
                trimmed.append(chunk)
                tokens += chunk_tokens
            else:
                break
        
        logger.debug(f"Trimmed RAG: {len(chunks)} -> {len(trimmed)} chunks")
        return trimmed
    
    def _trim_memory(self, facts: List[Dict[str, Any]], max_tokens: int) -> List[Dict[str, Any]]:
        """Trim memory facts to fit budget"""
        trimmed = []
        tokens = 0
        
        # Keep highest confidence facts
        sorted_facts = sorted(facts, key=lambda f: f.get("confidence", 0), reverse=True)
        
        for fact in sorted_facts:
            fact_tokens = self._estimate_text_tokens(json.dumps(fact))
            if tokens + fact_tokens <= max_tokens:
                trimmed.append(fact)
                tokens += fact_tokens
            else:
                break
        
        logger.debug(f"Trimmed memory: {len(facts)} -> {len(trimmed)} facts")
        return trimmed
    
    def _trim_window(self, messages: List[ChatMessage], max_tokens: int) -> List[ChatMessage]:
        """Trim message window to fit budget (keep most recent)"""
        trimmed = []
        tokens = 0
        
        # Iterate from most recent to oldest
        for msg in reversed(messages):
            msg_tokens = msg.estimate_tokens()
            if tokens + msg_tokens <= max_tokens:
                trimmed.insert(0, msg)  # Insert at beginning to maintain order
                tokens += msg_tokens
            else:
                break
        
        logger.debug(f"Trimmed window: {len(messages)} -> {len(trimmed)} messages")
        return trimmed
    
    def _build_system_prompt(self, context_parts: Dict[str, Any], session_id: str) -> str:
        """Build system prompt with context

        Args:
            context_parts: Trimmed context parts
            session_id: Session ID to get language preference

        Returns:
            System prompt string
        """
        prompt_parts = [
            "You are a helpful AI assistant in AgentOS Chat Mode.",
            "",
            "Your capabilities:",
            "- Answer questions about the codebase using RAG context",
            "- Access project memory for long-term facts",
            "- Execute slash commands (/summary, /extract, /task, etc.)",
            "- Maintain conversation context",
            "",
        ]

        # Add memory facts if available
        if context_parts["memory"]:
            prompt_parts.append("Project Memory:")
            for i, fact in enumerate(context_parts["memory"][:5], 1):
                summary = fact.get("content", {}).get("summary", "")
                prompt_parts.append(f"{i}. {summary}")
            prompt_parts.append("")

        # Add RAG context if available
        if context_parts["rag"]:
            prompt_parts.append("Relevant Documentation:")
            for i, chunk in enumerate(context_parts["rag"][:3], 1):
                path = chunk.get("path", "unknown")
                heading = chunk.get("heading", "")
                prompt_parts.append(f"{i}. {path} - {heading}")
            prompt_parts.append("")

        # Add language instruction based on session configuration
        language = self._get_language_preference(session_id)
        if language:
            language_instructions = {
                "en": "IMPORTANT: Always respond in English.",
                "zh": "重要提示：请始终使用中文回复。",
                "zh-CN": "重要提示：请始终使用简体中文回复。",
                "zh-TW": "重要提示：請始終使用繁體中文回覆。",
                "ja": "重要：常に日本語で応答してください。",
                "ko": "중요: 항상 한국어로 응답하세요.",
                "es": "IMPORTANTE: Responde siempre en español.",
                "fr": "IMPORTANT : Répondez toujours en français.",
                "de": "WICHTIG: Antworten Sie immer auf Deutsch.",
                "ru": "ВАЖНО: Всегда отвечайте на русском языке.",
            }
            instruction = language_instructions.get(language)
            if instruction:
                prompt_parts.append(instruction)
                prompt_parts.append("")

        prompt_parts.append("Respond concisely and helpfully.")

        return "\n".join(prompt_parts)

    def _get_language_preference(self, session_id: str) -> Optional[str]:
        """Get language preference from session metadata

        Args:
            session_id: Session ID

        Returns:
            Language code (e.g., "en", "zh") or None
        """
        try:
            session = self.chat_service.get_session(session_id)
            language = session.metadata.get("language")
            if language:
                logger.info(f"Session {session_id} language preference: {language}")
                return language
        except Exception as e:
            logger.warning(f"Failed to get language preference: {e}")
        return None

    def _assemble_messages(
        self,
        system_prompt: str,
        window_messages: List[ChatMessage],
        memory_facts: List[Dict[str, Any]],
        rag_chunks: List[Dict[str, Any]],
        summary_artifacts: List[Dict[str, Any]],
        user_input: str
    ) -> List[Dict[str, str]]:
        """Assemble final messages array
        
        Args:
            system_prompt: System prompt
            window_messages: Recent messages
            memory_facts: Memory facts
            rag_chunks: RAG chunks
            summary_artifacts: Summary artifacts
            user_input: Current user input
        
        Returns:
            List of messages in OpenAI format
        """
        messages = []
        
        # 1. System message
        messages.append({"role": "system", "content": system_prompt})
        
        # 2. Summary messages (if any) - inject as system messages
        for summary in summary_artifacts:
            summary_text = f"[Context Summary v{summary['version']}]\n{summary['content']}"
            messages.append({"role": "system", "content": summary_text})
        
        # 3. History messages (exclude system messages from history)
        for msg in window_messages:
            if msg.role != "system":
                messages.append(msg.to_openai_format())
        
        # 4. Current user input
        messages.append({"role": "user", "content": user_input})
        
        return messages
    
    def _generate_audit(
        self,
        session_id: str,
        messages: List[Dict[str, str]],
        rag_chunks: List[Dict[str, Any]],
        memory_facts: List[Dict[str, Any]],
        summary_artifacts: List[Dict[str, Any]],
        usage: ContextUsage
    ) -> Dict[str, Any]:
        """Generate audit trail

        Args:
            session_id: Session ID
            messages: Assembled messages
            rag_chunks: RAG chunks used
            memory_facts: Memory facts used
            summary_artifacts: Summary artifacts used
            usage: Usage statistics

        Returns:
            Audit dictionary
        """
        # Compute context hash
        context_str = json.dumps(messages, sort_keys=True)
        context_hash = hashlib.sha256(context_str.encode()).hexdigest()[:16]

        audit = {
            "session_id": session_id,
            "context_hash": context_hash,
            "rag_chunk_ids": [c.get("chunk_id") for c in rag_chunks],
            "memory_ids": [f.get("id") for f in memory_facts],
            "summary_artifact_ids": [s.get("artifact_id") for s in summary_artifacts],
            "final_tokens": usage.total_tokens_est,
            "message_count": len(messages),
            "usage": usage.to_dict(),
            "trimming_log": []  # NEW: Initialize trimming log
        }

        return audit
    
    def _estimate_text_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        return int(len(text) * 1.3)
    
    def _estimate_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Estimate total tokens in messages"""
        return sum(self._estimate_text_tokens(m.get("content", "")) for m in messages)
    
    # ============================================
    # NEW METHODS FOR PHASE B.1
    # ============================================
    
    def _check_summary_trigger(
        self,
        session_id: str,
        window_messages: List[ChatMessage]
    ) -> Optional[Dict[str, Any]]:
        """Check if auto-summary should be triggered
        
        Args:
            session_id: Session ID
            window_messages: Current window messages
        
        Returns:
            Trigger info dict if should trigger, None otherwise
        """
        # Check message count (trigger if > 20 messages in window)
        if len(window_messages) < 20:
            return None
        
        # Check if recent summary exists (don't trigger if last 5 messages)
        existing_summaries = self._load_summary_artifacts(session_id)
        if existing_summaries:
            # Check summary freshness
            last_summary = existing_summaries[-1]
            freshness_check = self._check_summary_freshness(
                last_summary,
                window_messages,
                session_id
            )

            if freshness_check["is_stale"]:
                # Summary is stale, trigger rebuild
                return {
                    "reason": "summary_stale",
                    "staleness_reason": freshness_check["reason"],
                    "last_summary_age": freshness_check["age_messages"],
                    "message_count": len(window_messages)
                }
            else:
                # Summary is fresh enough, don't trigger
                return None
        
        # Check token usage (this is checked after budget application)
        window_tokens = sum(msg.estimate_tokens() for msg in window_messages)
        window_budget = self.budget.window_tokens
        
        if window_tokens > window_budget * 0.8:  # 80% of window budget
            return {
                "reason": "window_budget_critical",
                "window_tokens": window_tokens,
                "window_budget": window_budget,
                "message_count": len(window_messages)
            }
        
        return None
    
    def _check_summary_freshness(
        self,
        last_summary: Dict[str, Any],
        window_messages: List[Any],
        session_id: str
    ) -> Dict[str, Any]:
        """
        Check if the last summary is still fresh enough.

        A summary is considered stale if:
        1. Too many messages since last summary (> 15 messages)
        2. Too many tokens since last summary (> 30% of window budget)
        3. Time-based staleness (> 1 hour for long conversations)

        Args:
            last_summary: Last summary artifact dict
            window_messages: Current window messages
            session_id: Session ID

        Returns:
            Dict with keys:
                - is_stale: bool
                - reason: str (if stale)
                - age_messages: int (messages since summary)
                - age_tokens: int (tokens since summary)
        """
        import json
        from datetime import datetime

        # Get summary metadata
        summary_metadata = last_summary.get("metadata")
        if isinstance(summary_metadata, str):
            summary_metadata = json.loads(summary_metadata)

        summary_created_at = summary_metadata.get("created_at")
        summary_last_message_id = summary_metadata.get("last_message_id")

        # Calculate message distance
        age_messages = 0
        if summary_last_message_id:
            # Find index of last summarized message
            try:
                last_idx = next(
                    i for i, msg in enumerate(window_messages)
                    if getattr(msg, 'message_id', None) == summary_last_message_id
                )
                age_messages = len(window_messages) - last_idx - 1
            except StopIteration:
                # Summary message not in window, assume stale
                age_messages = len(window_messages)
        else:
            # No last_message_id, assume all messages are new
            age_messages = len(window_messages)

        # Calculate token distance
        age_tokens = 0
        if summary_last_message_id:
            found_last = False
            for msg in window_messages:
                if found_last:
                    age_tokens += msg.estimate_tokens()
                if getattr(msg, 'message_id', None) == summary_last_message_id:
                    found_last = True
        else:
            age_tokens = sum(msg.estimate_tokens() for msg in window_messages)

        # Staleness thresholds
        MESSAGE_THRESHOLD = 15
        TOKEN_THRESHOLD = int(self.budget.window_tokens * 0.3)  # 30% of window
        TIME_THRESHOLD_SECONDS = 3600  # 1 hour

        # Check message staleness
        if age_messages > MESSAGE_THRESHOLD:
            return {
                "is_stale": True,
                "reason": f"Too many messages since last summary ({age_messages} > {MESSAGE_THRESHOLD})",
                "age_messages": age_messages,
                "age_tokens": age_tokens
            }

        # Check token staleness
        if age_tokens > TOKEN_THRESHOLD:
            return {
                "is_stale": True,
                "reason": f"Too many tokens since last summary ({age_tokens} > {TOKEN_THRESHOLD})",
                "age_messages": age_messages,
                "age_tokens": age_tokens
            }

        # Check time staleness (for long conversations)
        if summary_created_at:
            try:
                summary_time = datetime.fromisoformat(summary_created_at)
                age_seconds = (datetime.now() - summary_time).total_seconds()

                if age_seconds > TIME_THRESHOLD_SECONDS and age_messages > 5:
                    return {
                        "is_stale": True,
                        "reason": f"Summary too old ({age_seconds / 3600:.1f} hours)",
                        "age_messages": age_messages,
                        "age_tokens": age_tokens
                    }
            except (ValueError, TypeError):
                # Invalid timestamp, ignore time check
                pass

        # Summary is fresh
        return {
            "is_stale": False,
            "age_messages": age_messages,
            "age_tokens": age_tokens
        }

    def _load_summary_artifacts(self, session_id: str) -> List[Dict[str, Any]]:
        """Load existing summary artifacts for session
        
        Args:
            session_id: Session ID
        
        Returns:
            List of summary artifact dicts
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT artifact_id, content, version, metadata
                FROM artifacts
                WHERE session_id = ? AND artifact_type = 'summary'
                ORDER BY created_at ASC
            """, (session_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            summaries = []
            for row in rows:
                metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                summaries.append({
                    "artifact_id": row["artifact_id"],
                    "content": row["content"],
                    "version": row["version"],
                    "metadata": metadata
                })
            
            return summaries
        
        except Exception as e:
            logger.warning(f"Failed to load summary artifacts: {e}")
            return []
    
    def _calculate_usage(
        self,
        system_prompt: str,
        window_messages: List[ChatMessage],
        memory_facts: List[Dict[str, Any]],
        rag_chunks: List[Dict[str, Any]],
        summary_artifacts: List[Dict[str, Any]],
        user_input: str
    ) -> ContextUsage:
        """Calculate token usage statistics
        
        Args:
            system_prompt: System prompt
            window_messages: Window messages
            memory_facts: Memory facts
            rag_chunks: RAG chunks
            summary_artifacts: Summary artifacts
            user_input: User input
        
        Returns:
            ContextUsage object
        """
        tokens_system = self._estimate_text_tokens(system_prompt)
        tokens_window = sum(msg.estimate_tokens() for msg in window_messages)
        tokens_memory = sum(self._estimate_text_tokens(json.dumps(m)) for m in memory_facts)
        tokens_rag = sum(self._estimate_text_tokens(c.get("content", "")) for c in rag_chunks)
        tokens_summary = sum(self._estimate_text_tokens(s.get("content", "")) for s in summary_artifacts)
        tokens_user = self._estimate_text_tokens(user_input)
        
        total = tokens_system + tokens_window + tokens_memory + tokens_rag + tokens_summary + tokens_user
        
        return ContextUsage(
            budget_tokens=self.budget.max_tokens,
            total_tokens_est=total,
            tokens_system=tokens_system,
            tokens_window=tokens_window,
            tokens_rag=tokens_rag,
            tokens_memory=tokens_memory,
            tokens_summary=tokens_summary,
            tokens_policy=0  # Not implemented yet
        )
    
    def _save_snapshot(
        self,
        session_id: str,
        reason: str,
        usage: ContextUsage,
        composition: Dict[str, List[str]],
        assembled_hash: str
    ) -> str:
        """Save context snapshot to database
        
        Args:
            session_id: Session ID
            reason: Reason for snapshot
            usage: Usage statistics
            composition: Composition details
            assembled_hash: Hash of assembled messages
        
        Returns:
            Snapshot ID
        """
        snapshot_id = ulid()
        created_at = int(datetime.now(timezone.utc).timestamp() * 1000)
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Insert snapshot
            cursor.execute("""
                INSERT INTO context_snapshots (
                    snapshot_id, session_id, created_at, reason,
                    provider, model,
                    budget_tokens, total_tokens_est,
                    tokens_system, tokens_window, tokens_rag,
                    tokens_memory, tokens_summary, tokens_policy,
                    composition_json, assembled_hash, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot_id, session_id, created_at, reason,
                None, None,  # provider, model (filled in by engine)
                usage.budget_tokens, usage.total_tokens_est,
                usage.tokens_system, usage.tokens_window, usage.tokens_rag,
                usage.tokens_memory, usage.tokens_summary, usage.tokens_policy,
                json.dumps(composition),
                assembled_hash,
                json.dumps({"watermark": usage.watermark.value, "usage_ratio": usage.usage_ratio})
            ))
            
            # Insert snapshot items
            for item_type, item_ids in composition.items():
                # Convert item_type from plural to singular
                type_map = {
                    "window_msg_ids": "window_msg",
                    "summary_artifact_ids": "summary",
                    "rag_chunk_ids": "rag_chunk",
                    "memory_ids": "memory"
                }
                item_type_single = type_map.get(item_type, item_type)
                
                for rank, item_id in enumerate(item_ids):
                    cursor.execute("""
                        INSERT INTO context_snapshot_items (
                            snapshot_id, item_type, item_id, tokens_est, rank, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        snapshot_id, item_type_single, item_id, 0, rank, None
                    ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Saved context snapshot {snapshot_id}")
            return snapshot_id
        
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
            return snapshot_id  # Return ID even if save failed
    
