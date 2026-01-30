"""
Self-check Runner - Comprehensive system health checks

Provides a single entry point for diagnosing AgentOS health:
- Runtime environment
- Provider connectivity (local & cloud)
- Context availability (memory, RAG, sessions)
- Chat pipeline readiness

Sprint B Task #7 implementation
"""

import asyncio
import logging
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

from agentos.providers.registry import ProviderRegistry
from agentos.providers.base import ProviderState

logger = logging.getLogger(__name__)


@dataclass
class CheckAction:
    """Action that can be taken to fix an issue"""
    label: str
    method: Optional[str] = None  # "POST", "GET", etc.
    path: Optional[str] = None  # "/api/providers/ollama/start"
    ui: Optional[str] = None  # "drawer.cloud" for UI actions


@dataclass
class CheckItem:
    """Single self-check item"""
    id: str
    group: str
    name: str
    status: str  # "PASS", "WARN", "FAIL"
    detail: str
    hint: Optional[str] = None
    actions: List[CheckAction] = field(default_factory=list)


@dataclass
class SelfCheckResult:
    """Complete self-check result"""
    summary: str  # "OK", "WARN", "FAIL"
    ts: str
    items: List[CheckItem]


class SelfCheckRunner:
    """
    Self-check runner for AgentOS

    Runs comprehensive health checks and provides actionable diagnostics.
    """

    def __init__(self):
        self.registry = ProviderRegistry.get_instance()

    async def run(
        self,
        session_id: Optional[str] = None,
        include_network: bool = False,
        include_context: bool = True,
    ) -> SelfCheckResult:
        """
        Run comprehensive self-check

        Args:
            session_id: Session ID to check context binding for
            include_network: If True, actively test cloud providers (costs API calls)
            include_context: If True, check memory/RAG/session availability

        Returns:
            SelfCheckResult with summary and detailed items
        """
        # Gather all checks concurrently
        tasks = [
            self._check_runtime(),
            self._check_providers(include_network=include_network),
        ]

        if include_context:
            tasks.append(self._check_context(session_id=session_id))

        # Run all checks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results
        items = []
        for result in results:
            if isinstance(result, list):
                items.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Self-check task failed: {result}")

        # Calculate summary
        summary = self._calculate_summary(items)

        return SelfCheckResult(
            summary=summary,
            ts=datetime.now(timezone.utc).isoformat(),
            items=items,
        )

    def _calculate_summary(self, items: List[CheckItem]) -> str:
        """Calculate overall summary from items"""
        has_fail = any(item.status == "FAIL" for item in items)
        has_warn = any(item.status == "WARN" for item in items)

        if has_fail:
            return "FAIL"
        elif has_warn:
            return "WARN"
        else:
            return "OK"

    async def _check_runtime(self) -> List[CheckItem]:
        """Check runtime environment"""
        items = []

        # 1. Version check
        try:
            version = self._get_version()
            items.append(
                CheckItem(
                    id="runtime.version",
                    group="runtime",
                    name="AgentOS version",
                    status="PASS",
                    detail=version,
                    hint=None,
                    actions=[],
                )
            )
        except Exception as e:
            items.append(
                CheckItem(
                    id="runtime.version",
                    group="runtime",
                    name="AgentOS version",
                    status="WARN",
                    detail=f"Failed to read version: {str(e)}",
                    hint=None,
                    actions=[],
                )
            )

        # 2. Critical paths check
        paths_check = self._check_paths()
        items.append(paths_check)

        # 3. Permissions check
        permissions_check = self._check_permissions()
        items.append(permissions_check)

        return items

    def _get_version(self) -> str:
        """Get AgentOS version"""
        try:
            # Try to get git sha
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=2,
                cwd=Path(__file__).parent.parent.parent,
            )
            if result.returncode == 0:
                sha = result.stdout.strip()
                return f"agentos 0.3.2 (git {sha})"
        except Exception:
            pass

        return "agentos 0.3.2"

    def _check_paths(self) -> CheckItem:
        """Check critical paths are writable"""
        home = Path.home()
        paths = {
            "runtime": home / ".agentos" / "runtime",
            "secrets": home / ".agentos" / "secrets",
        }

        issues = []
        for name, path in paths.items():
            try:
                path.mkdir(parents=True, exist_ok=True)
                # Try to write a test file
                test_file = path / ".writetest"
                test_file.write_text("test")
                test_file.unlink()
            except Exception as e:
                issues.append(f"{name}: {str(e)[:30]}")

        if not issues:
            return CheckItem(
                id="runtime.paths",
                group="runtime",
                name="Critical paths writable",
                status="PASS",
                detail=f"~/.agentos/runtime, ~/.agentos/secrets",
                hint=None,
                actions=[],
            )
        else:
            return CheckItem(
                id="runtime.paths",
                group="runtime",
                name="Critical paths writable",
                status="FAIL",
                detail="; ".join(issues),
                hint="Check filesystem permissions for ~/.agentos",
                actions=[],
            )

    def _check_permissions(self) -> CheckItem:
        """Check secrets file permissions"""
        secrets_file = Path.home() / ".agentos" / "secrets" / "providers.json"

        if not secrets_file.exists():
            return CheckItem(
                id="runtime.permissions",
                group="runtime",
                name="Secrets file permissions",
                status="PASS",
                detail="No secrets file yet (will be 600 on creation)",
                hint=None,
                actions=[],
            )

        # Check permissions
        stat_info = secrets_file.stat()
        mode = stat_info.st_mode & 0o777

        if mode == 0o600:
            return CheckItem(
                id="runtime.permissions",
                group="runtime",
                name="Secrets file permissions",
                status="PASS",
                detail=f"Correct (600): {secrets_file}",
                hint=None,
                actions=[],
            )
        else:
            return CheckItem(
                id="runtime.permissions",
                group="runtime",
                name="Secrets file permissions",
                status="WARN",
                detail=f"Insecure ({oct(mode)[2:]}): {secrets_file}",
                hint="Run: chmod 600 ~/.agentos/secrets/providers.json",
                actions=[],
            )

    async def _check_providers(self, include_network: bool = False) -> List[CheckItem]:
        """
        Check provider status

        Args:
            include_network: If True, actively probe all providers (including cloud, may cost API calls).
                            If False, use cached status only (no network calls).
        """
        # Import ProviderState at function level (used throughout this method)
        from agentos.providers.base import ProviderStatus, ProviderState
        from agentos.common.reasons import ReasonCode, get_hint

        items = []

        # Get provider status based on include_network flag
        if include_network:
            # Force fresh probe for all providers (including cloud)
            status_list = await self.registry.get_all_status()
        else:
            # Use ONLY cached status (no probes)
            # This reads from registry cache without triggering network calls
            status_list = []
            for provider in self.registry.list_all():
                provider_id = provider.id
                if provider and hasattr(provider, '_status_cache') and provider._status_cache:
                    status_list.append(provider._status_cache)
                else:
                    # Provider has no cached status yet - mark as unknown

                    reason = ReasonCode.STALE_REFRESH
                    status = ProviderStatus(
                        id=provider_id,
                        type=provider.type,
                        state=ProviderState.DISCONNECTED,
                        endpoint=None,
                        latency_ms=None,
                        last_ok_at=None,
                        last_error="No cached status (run with include_network=true)",
                        reason_code=reason,
                        hint=get_hint(reason),
                    )
                    status_list.append(status)

        # Check each provider
        for status in status_list:
            if status is None:
                continue

            provider_id = status.id
            provider = self.registry.get(provider_id)
            if not provider:
                continue

            # Build check item
            if status.state == ProviderState.READY:
                latency_info = f" ({int(status.latency_ms)}ms)" if status.latency_ms else ""
                items.append(
                    CheckItem(
                        id=f"provider.{provider_id}",
                        group="providers",
                        name=f"{provider_id.title()} reachable",
                        status="PASS",
                        detail=f"READY{latency_info}",
                        hint=None,
                        actions=[],
                    )
                )
            elif status.state == ProviderState.DISCONNECTED:
                # Special handling for Ollama - offer start action
                actions = []
                hint = None

                if provider_id == "ollama":
                    # Check if CLI exists
                    try:
                        result = subprocess.run(
                            ["which", "ollama"],
                            capture_output=True,
                            timeout=2,
                        )
                        if result.returncode == 0:
                            # CLI exists, can start
                            actions.append(
                                CheckAction(
                                    label="Start Ollama",
                                    method="POST",
                                    path="/api/providers/ollama/start",
                                )
                            )
                            hint = "Click 'Start Ollama' or run: ollama serve"
                        else:
                            hint = "Install Ollama from: https://ollama.ai/download"
                    except Exception:
                        hint = "Install Ollama from: https://ollama.ai/download"

                elif provider.type.value == "cloud":
                    # Cloud provider not configured
                    actions.append(
                        CheckAction(
                            label="Configure",
                            ui="drawer.cloud",
                        )
                    )
                    hint = "Add API key in Settings → Cloud Config"

                items.append(
                    CheckItem(
                        id=f"provider.{provider_id}",
                        group="providers",
                        name=f"{provider_id.title()} configured",
                        status="WARN" if provider.type.value == "cloud" else "FAIL",
                        detail=f"DISCONNECTED ({status.last_error or 'not reachable'})",
                        hint=hint,
                        actions=actions,
                    )
                )
            elif status.state == ProviderState.ERROR:
                # Error state - authentication failure, network error, etc.
                error_msg = status.last_error or "unknown error"
                hint = None

                if "401" in error_msg or "Unauthorized" in error_msg:
                    hint = "Invalid API key - update in Settings → Cloud Config"

                items.append(
                    CheckItem(
                        id=f"provider.{provider_id}",
                        group="providers",
                        name=f"{provider_id.title()} status",
                        status="FAIL",
                        detail=f"ERROR ({error_msg})",
                        hint=hint,
                        actions=[],
                    )
                )
            elif status.state == ProviderState.DEGRADED:
                items.append(
                    CheckItem(
                        id=f"provider.{provider_id}",
                        group="providers",
                        name=f"{provider_id.title()} status",
                        status="WARN",
                        detail=f"DEGRADED ({status.last_error or 'partial service'})",
                        hint="Provider is reachable but may have limited functionality",
                        actions=[],
                    )
                )

        return items

    async def _check_context(self, session_id: Optional[str] = None) -> List[CheckItem]:
        """
        Check context availability

        This is a lightweight check for v0.3 - verifies basic infrastructure
        without Task #8's full context status implementation.
        """
        items = []

        # 1. Memory store check
        memory_check = await self._check_memory_store()
        items.append(memory_check)

        # 2. RAG check (placeholder for now)
        rag_check = self._check_rag()
        items.append(rag_check)

        # 3. Session binding check
        if session_id:
            session_check = await self._check_session_binding(session_id)
            items.append(session_check)

        return items

    async def _check_memory_store(self) -> CheckItem:
        """Check if memory store is read/write accessible"""
        try:
            # Try to import and test memory store
            # This is a basic check - actual implementation depends on your memory store
            home = Path.home()
            memory_path = home / ".agentos" / "memory"
            memory_path.mkdir(parents=True, exist_ok=True)

            # Write test
            test_file = memory_path / ".selfcheck_test"
            test_file.write_text("test")
            content = test_file.read_text()
            test_file.unlink()

            if content == "test":
                return CheckItem(
                    id="context.memory",
                    group="context",
                    name="Memory store read/write",
                    status="PASS",
                    detail="Read/write OK",
                    hint=None,
                    actions=[],
                )
            else:
                return CheckItem(
                    id="context.memory",
                    group="context",
                    name="Memory store read/write",
                    status="FAIL",
                    detail="Write/read mismatch",
                    hint="Check ~/.agentos/memory permissions",
                    actions=[],
                )

        except Exception as e:
            return CheckItem(
                id="context.memory",
                group="context",
                name="Memory store read/write",
                status="FAIL",
                detail=f"Failed: {str(e)[:50]}",
                hint="Check ~/.agentos/memory directory permissions",
                actions=[],
            )

    def _check_rag(self) -> CheckItem:
        """Check RAG availability (placeholder for v0.3)"""
        # For v0.3, we don't have RAG fully implemented yet
        # Return a WARN status indicating it's not configured
        return CheckItem(
            id="context.rag",
            group="context",
            name="RAG index availability",
            status="WARN",
            detail="Not configured (coming in v0.5+)",
            hint="RAG is not yet implemented in v0.3",
            actions=[],
        )

    async def _check_session_binding(self, session_id: str) -> CheckItem:
        """Check if session exists and is readable"""
        try:
            # Try to load session from store
            # This depends on your session store implementation
            from agentos.webui.api import sessions

            store = sessions.get_session_store()
            if not store:
                return CheckItem(
                    id="context.session_binding",
                    group="context",
                    name=f"Session '{session_id}' binding",
                    status="WARN",
                    detail="Session store not initialized",
                    hint=None,
                    actions=[],
                )

            # Check if session exists
            session = store.get_session(session_id)
            if session:
                msg_count = len(session.messages) if hasattr(session, "messages") else 0
                return CheckItem(
                    id="context.session_binding",
                    group="context",
                    name=f"Session '{session_id}' binding",
                    status="PASS",
                    detail=f"Session exists ({msg_count} messages)",
                    hint=None,
                    actions=[],
                )
            else:
                return CheckItem(
                    id="context.session_binding",
                    group="context",
                    name=f"Session '{session_id}' binding",
                    status="WARN",
                    detail="Session not found",
                    hint="Create a new session or switch to an existing one",
                    actions=[],
                )

        except Exception as e:
            return CheckItem(
                id="context.session_binding",
                group="context",
                name=f"Session '{session_id}' binding",
                status="FAIL",
                detail=f"Failed to check: {str(e)[:50]}",
                hint=None,
                actions=[],
            )
