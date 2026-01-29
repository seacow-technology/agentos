"""
Context Manager - Session-level context state management

Manages:
- Memory namespace binding
- RAG index binding
- Context refresh tracking
- Persistent storage (~/.agentos/runtime/session_context.json)

Sprint B Task #8 implementation
"""

import json
import logging
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class ContextState(Enum):
    """Context state for a session"""
    EMPTY = "EMPTY"
    ATTACHED = "ATTACHED"
    BUILDING = "BUILDING"
    STALE = "STALE"
    ERROR = "ERROR"


@dataclass
class MemoryConfig:
    """Memory configuration"""
    enabled: bool
    namespace: str


@dataclass
class RAGConfig:
    """RAG configuration"""
    enabled: bool
    index: Optional[str] = None


@dataclass
class SessionContext:
    """Session context binding"""
    session_id: str
    memory_namespace: Optional[str] = None
    rag_index: Optional[str] = None
    attached_at: Optional[str] = None
    last_refresh: Optional[str] = None
    refresh_in_progress: bool = False
    refresh_started_at: Optional[str] = None


@dataclass
class ContextStatus:
    """Complete context status for a session"""
    session_id: str
    state: ContextState
    updated_at: str
    tokens: Dict[str, Any]
    rag: Dict[str, Any]
    memory: Dict[str, Any]


class ContextManager:
    """
    Context manager for session-level context state

    Features:
    - Persistent storage in ~/.agentos/runtime/session_context.json
    - Atomic write operations (temp file + rename)
    - State calculation with health checks
    - Stale detection (10min threshold)
    """

    STALE_THRESHOLD_MINUTES = 10

    def __init__(self, context_file: Optional[Path] = None):
        if context_file is None:
            # Default to ~/.agentos/runtime/session_context.json
            home = Path.home()
            runtime_dir = home / ".agentos" / "runtime"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            context_file = runtime_dir / "session_context.json"

        self.context_file = context_file
        self._contexts: Dict[str, SessionContext] = {}
        self._load()

    def _load(self):
        """Load contexts from disk"""
        if not self.context_file.exists():
            self._contexts = {}
            return

        try:
            with open(self.context_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._contexts = {}
            for session_id, ctx_dict in data.items():
                self._contexts[session_id] = SessionContext(
                    session_id=session_id,
                    memory_namespace=ctx_dict.get("memory_namespace"),
                    rag_index=ctx_dict.get("rag_index"),
                    attached_at=ctx_dict.get("attached_at"),
                    last_refresh=ctx_dict.get("last_refresh"),
                    refresh_in_progress=ctx_dict.get("refresh_in_progress", False),
                    refresh_started_at=ctx_dict.get("refresh_started_at"),
                )

            logger.debug(f"Loaded session contexts: {len(self._contexts)} sessions")
        except Exception as e:
            logger.error(f"Failed to load session contexts: {e}")
            self._contexts = {}

    def _save(self):
        """
        Save contexts to disk (atomic write)

        Uses temp file + rename for atomicity
        """
        try:
            # Convert to dict
            data = {}
            for session_id, ctx in self._contexts.items():
                data[session_id] = {
                    "memory_namespace": ctx.memory_namespace,
                    "rag_index": ctx.rag_index,
                    "attached_at": ctx.attached_at,
                    "last_refresh": ctx.last_refresh,
                    "refresh_in_progress": ctx.refresh_in_progress,
                    "refresh_started_at": ctx.refresh_started_at,
                }

            # Write to temp file
            temp_file = self.context_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            # Atomic rename
            temp_file.replace(self.context_file)

            logger.debug(f"Saved session contexts: {len(self._contexts)} sessions")
        except Exception as e:
            logger.error(f"Failed to save session contexts: {e}")
            raise

    def get_context(self, session_id: str) -> Optional[SessionContext]:
        """Get context for a session"""
        return self._contexts.get(session_id)

    def attach(
        self,
        session_id: str,
        memory: Optional[MemoryConfig] = None,
        rag: Optional[RAGConfig] = None,
    ):
        """
        Attach context to a session

        Args:
            session_id: Session ID
            memory: Memory configuration
            rag: RAG configuration
        """
        ctx = self._contexts.get(session_id)
        if not ctx:
            ctx = SessionContext(session_id=session_id)
            self._contexts[session_id] = ctx

        # Update memory
        if memory:
            ctx.memory_namespace = memory.namespace if memory.enabled else None

        # Update RAG
        if rag:
            ctx.rag_index = rag.index if rag.enabled else None

        # Set attached_at if this is first attachment
        if not ctx.attached_at and (ctx.memory_namespace or ctx.rag_index):
            ctx.attached_at = datetime.now(timezone.utc).isoformat()

        self._save()
        logger.info(f"Attached context to session '{session_id}'")

    def detach(self, session_id: str):
        """
        Detach context from a session

        Removes all bindings but keeps the session entry
        """
        ctx = self._contexts.get(session_id)
        if ctx:
            ctx.memory_namespace = None
            ctx.rag_index = None
            ctx.attached_at = None
            ctx.last_refresh = None
            self._save()
            logger.info(f"Detached context from session '{session_id}'")

    def start_refresh(self, session_id: str):
        """Mark session as refresh in progress"""
        ctx = self._contexts.get(session_id)
        if not ctx:
            ctx = SessionContext(session_id=session_id)
            self._contexts[session_id] = ctx

        ctx.refresh_in_progress = True
        ctx.refresh_started_at = datetime.now(timezone.utc).isoformat()
        self._save()

    def complete_refresh(self, session_id: str):
        """Mark session refresh as complete"""
        ctx = self._contexts.get(session_id)
        if ctx:
            ctx.refresh_in_progress = False
            ctx.refresh_started_at = None
            ctx.last_refresh = datetime.now(timezone.utc).isoformat()
            self._save()

    def get_status(self, session_id: str) -> ContextStatus:
        """
        Get comprehensive status for a session

        Returns:
            ContextStatus with state, tokens, rag, memory info
        """
        ctx = self._contexts.get(session_id)

        # Calculate state
        state = self._calculate_state(ctx)

        # Build status
        status = ContextStatus(
            session_id=session_id,
            state=state,
            updated_at=datetime.now(timezone.utc).isoformat(),
            tokens=self._get_token_stats(session_id, ctx),
            rag=self._get_rag_status(ctx),
            memory=self._get_memory_status(ctx),
        )

        return status

    def _calculate_state(self, ctx: Optional[SessionContext]) -> ContextState:
        """
        Calculate context state based on bindings and health

        Rules:
        - EMPTY: No memory or RAG attached
        - BUILDING: Refresh in progress
        - STALE: Last refresh > 10 minutes ago
        - ERROR: Dependencies failed or store error
        - ATTACHED: Has bindings and healthy
        """
        if not ctx:
            return ContextState.EMPTY

        # Check if refresh in progress
        if ctx.refresh_in_progress:
            return ContextState.BUILDING

        # Check if anything is attached
        has_memory = ctx.memory_namespace is not None
        has_rag = ctx.rag_index is not None

        if not has_memory and not has_rag:
            return ContextState.EMPTY

        # Check for stale
        if ctx.last_refresh:
            try:
                last_refresh_dt = datetime.fromisoformat(ctx.last_refresh.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                age_minutes = (now - last_refresh_dt).total_seconds() / 60

                if age_minutes > self.STALE_THRESHOLD_MINUTES:
                    return ContextState.STALE
            except Exception:
                pass

        # Check for errors
        # For v0.3, we'll be lenient - only mark ERROR if critical failure
        # (e.g., store file corrupted, session doesn't exist)
        # Memory/RAG not available is just WARN in status, not ERROR state

        return ContextState.ATTACHED

    def _get_token_stats(self, session_id: str, ctx: Optional[SessionContext]) -> Dict[str, Any]:
        """
        Get token statistics for session

        v0.3: Placeholder - returns 0s, field structure ready for future
        """
        # TODO: Implement actual token counting in v0.4+
        return {
            "prompt": 0,
            "completion": 0,
            "context_window": 128000,
        }

    def _get_rag_status(self, ctx: Optional[SessionContext]) -> Dict[str, Any]:
        """
        Get RAG status

        v0.3: Simple check - if index specified, return basic info
        Real RAG health check will come in v0.5+
        """
        if not ctx or not ctx.rag_index:
            return {
                "enabled": False,
                "index": None,
                "last_refresh": None,
                "status": "NOT_CONFIGURED",
                "detail": None,
            }

        # For v0.3, if RAG index is set, we assume it's OK but with a warning
        # Real implementation will query actual RAG service
        return {
            "enabled": True,
            "index": ctx.rag_index,
            "last_refresh": ctx.last_refresh,
            "status": "WARN",
            "detail": "RAG service not fully implemented (v0.3)",
        }

    def _get_memory_status(self, ctx: Optional[SessionContext]) -> Dict[str, Any]:
        """
        Get memory status

        v0.3: Basic check - if namespace set, try to verify directory exists
        """
        if not ctx or not ctx.memory_namespace:
            return {
                "enabled": False,
                "namespace": None,
                "last_write": None,
                "status": "NOT_CONFIGURED",
            }

        # Check if memory directory exists and is accessible
        try:
            memory_dir = Path.home() / ".agentos" / "memory"
            memory_dir.mkdir(parents=True, exist_ok=True)

            # Try to get last write time (if any files exist)
            namespace_files = list(memory_dir.glob(f"{ctx.memory_namespace}*"))
            last_write = None

            if namespace_files:
                # Get most recent modification time
                most_recent = max(namespace_files, key=lambda p: p.stat().st_mtime)
                last_write = datetime.fromtimestamp(
                    most_recent.stat().st_mtime,
                    tz=timezone.utc
                ).isoformat()

            return {
                "enabled": True,
                "namespace": ctx.memory_namespace,
                "last_write": last_write,
                "status": "OK",
            }

        except Exception as e:
            return {
                "enabled": True,
                "namespace": ctx.memory_namespace,
                "last_write": None,
                "status": "ERROR",
                "detail": str(e)[:50],
            }
