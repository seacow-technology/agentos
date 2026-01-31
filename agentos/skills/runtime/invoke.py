"""Skill Invoker - Runtime execution with phase gate and permission guards.

This module implements the core skill execution engine:
1. Phase Gate - Prevents execution during planning phase
2. Permission Guards - Enforces net/fs permissions from manifest
3. Skill Execution - Loads and runs skill code

Design Principles:
- Fail-closed: Default to deny unless explicitly allowed
- Defense in depth: Multiple layers of security checks
- Audit trail: All invocations logged for security review

Security Model:
- Phase Gate: Planning phase → 403 (highest priority check)
- Enable Check: Only enabled skills can be invoked
- Permission Guards: Net allowlist, fs read/write checks
- Execution: MVP uses dynamic import (production should use sandbox)

Integration with existing PhaseGate:
- Reuses agentos.core.chat.guards.phase_gate.PhaseGate
- Follows same phase naming (planning/execution)
- Compatible with session-based phase management

Usage:
    >>> from agentos.skills.runtime import SkillLoader, SkillInvoker
    >>> from agentos.skills.registry import SkillRegistry
    >>>
    >>> registry = SkillRegistry()
    >>> loader = SkillLoader(registry)
    >>> loader.load_enabled_skills()
    >>>
    >>> invoker = SkillInvoker(loader, execution_phase='execution')
    >>> result = invoker.invoke('test.skill', 'greet', {'name': 'Alice'})
"""

from typing import Any, Dict, Optional
import logging
import importlib.util
import sys
from pathlib import Path

from .loader import SkillLoader
from .sandbox import NetGuard, FsGuard, PermissionDeniedError

logger = logging.getLogger(__name__)


class PhaseViolationError(Exception):
    """Raised when skill invocation is attempted during planning phase.

    Planning phase should be pure computation without side effects.
    Skills are NOT allowed during planning to prevent:
    - Data leakage
    - Non-deterministic behavior
    - Side effects during plan generation
    """
    pass


class SkillNotEnabledError(Exception):
    """Raised when attempting to invoke a skill that is not enabled.

    Only skills with status='enabled' can be invoked. This ensures:
    - Explicit administrator approval before execution
    - Clear security boundary
    - Audit trail of enabled skills
    """
    pass


class SkillInvoker:
    """Invokes skills with phase gate and permission guards.

    The invoker is the main execution engine for skills. It enforces
    security policies through multiple layers:

    1. Phase Gate (highest priority)
       - Planning phase → PhaseViolationError
       - Execution phase → proceed to next check

    2. Enable Check
       - Skill not loaded → SkillNotEnabledError
       - Skill loaded → proceed to next check

    3. Permission Guards
       - Net access → check domain allowlist
       - Fs access → check read/write permissions

    4. Execution
       - Load skill module
       - Call handler function
       - Return result

    Attributes:
        loader: SkillLoader instance
        net_guard: Network permission guard
        fs_guard: Filesystem permission guard
        execution_phase: Current execution phase
    """

    def __init__(self, loader: SkillLoader, execution_phase: str = 'planning'):
        """Initialize invoker.

        Args:
            loader: SkillLoader instance with enabled skills
            execution_phase: Current phase ('planning' or 'execution')
                           Defaults to 'planning' (fail-safe)

        Security:
            Default phase is 'planning' which blocks all invocations.
            This fail-safe ensures explicit phase setting is required.
        """
        self.loader = loader
        self.net_guard = NetGuard()
        self.fs_guard = FsGuard()
        self.execution_phase = execution_phase

    def set_phase(self, phase: str):
        """Set execution phase.

        Args:
            phase: 'planning' or 'execution'

        Raises:
            ValueError: If phase is invalid
        """
        if phase not in ('planning', 'execution'):
            raise ValueError(f"Invalid phase: {phase}. Must be 'planning' or 'execution'")
        self.execution_phase = phase

    def invoke(self, skill_id: str, command: str, args: Dict[str, Any]) -> Any:
        """Invoke skill with security checks.

        This is the main entry point for skill execution. It performs
        the following checks in order:

        1. Phase Gate: Fail if planning phase
        2. Enable Check: Fail if skill not enabled
        3. Permission Check: Fail if permissions insufficient
        4. Execute: Load and run skill code

        Args:
            skill_id: Skill identifier (e.g., 'test.skill')
            command: Command to invoke (e.g., 'greet')
            args: Arguments to pass to command handler

        Returns:
            Result from skill handler

        Raises:
            PhaseViolationError: If invoked during planning phase
            SkillNotEnabledError: If skill is not enabled
            PermissionDeniedError: If permission check fails
            ValueError: If command not found in skill
            Exception: Any exception from skill execution

        Security:
            All exceptions are logged with security event metadata
            for audit trail and incident response.

        Example:
            >>> invoker.set_phase('execution')
            >>> result = invoker.invoke('test.skill', 'greet', {'name': 'Alice'})
            >>> print(result)  # "Hello, Alice!"
        """
        # Step 1: Phase Gate (highest priority)
        if self.execution_phase != 'execution':
            error_msg = (
                f"Skill invocation forbidden in {self.execution_phase} phase. "
                f"Skills can only be invoked during execution phase."
            )
            logger.warning(
                error_msg,
                extra={
                    "security_event": "phase_violation",
                    "skill_id": skill_id,
                    "command": command,
                    "phase": self.execution_phase,
                }
            )
            raise PhaseViolationError(error_msg)

        # Step 2: Enable Check
        skill = self.loader.get_skill(skill_id)
        if not skill:
            error_msg = f"Skill not enabled: {skill_id}"
            logger.warning(
                error_msg,
                extra={
                    "security_event": "skill_not_enabled",
                    "skill_id": skill_id,
                    "command": command,
                }
            )
            raise SkillNotEnabledError(error_msg)

        # Step 3: Permission Check
        manifest = skill['manifest_json']
        try:
            self._check_permissions(manifest, args)
        except PermissionDeniedError as e:
            logger.warning(
                f"Permission denied for skill {skill_id}: {e}",
                extra={
                    "security_event": "permission_denied",
                    "skill_id": skill_id,
                    "command": command,
                    "error": str(e),
                }
            )
            raise

        # Step 4: Execute
        logger.info(
            f"Invoking skill: {skill_id}.{command}",
            extra={
                "skill_id": skill_id,
                "command": command,
                "phase": self.execution_phase,
            }
        )

        try:
            result = self._execute_skill(skill, command, args)
            logger.info(
                f"Skill invocation successful: {skill_id}.{command}",
                extra={
                    "skill_id": skill_id,
                    "command": command,
                    "success": True,
                }
            )
            return result

        except Exception as e:
            logger.error(
                f"Skill invocation failed: {skill_id}.{command}: {e}",
                exc_info=True,
                extra={
                    "skill_id": skill_id,
                    "command": command,
                    "error": str(e),
                }
            )
            raise

    def _check_permissions(self, manifest: Dict[str, Any], args: Dict[str, Any]):
        """Check skill permissions against manifest.

        This method validates that the operation is allowed based on
        the permissions declared in the skill manifest.

        Args:
            manifest: Parsed skill manifest
            args: Arguments passed to skill (may contain permission-relevant data)

        Raises:
            PermissionDeniedError: If permission check fails

        MVP Implementation:
            - Net: Checks 'domain' field in args against allow_domains
            - Fs: Checks 'operation' field in args against read/write flags

        Production Enhancement:
            - Parse actual network calls (URL inspection)
            - Parse actual file operations (path inspection)
            - Integrate with OS-level sandboxing
            - Rate limiting per resource
        """
        permissions = manifest.get('requires', {}).get('permissions', {})

        # Net permission check
        # If 'domain' is in args, we need to check permissions
        if 'domain' in args:
            if 'net' in permissions:
                allow_domains = permissions['net'].get('allow_domains', [])
                self.net_guard.check_domain(args['domain'], allow_domains)
            else:
                # No net permission declared, but trying to access domain
                raise PermissionDeniedError(
                    f"Network access denied: skill does not declare net permissions. "
                    f"Attempted to access: {args['domain']}"
                )

        # Future: Intercept actual network calls via socket hooks

        # Fs permission check
        if 'fs' in permissions:
            fs_perms = permissions['fs']
            read_allowed = fs_perms.get('read', False)
            write_allowed = fs_perms.get('write', False)

            # MVP: Check if args contains operation field
            if 'operation' in args:
                operation = args['operation']

                if operation == 'read':
                    path = args.get('path', '<unknown>')
                    self.fs_guard.check_read(path, read_allowed)

                elif operation == 'write':
                    path = args.get('path', '<unknown>')
                    self.fs_guard.check_write(path, write_allowed)

            # Future: Intercept actual file operations via open() hooks

    def _execute_skill(self, skill: Dict[str, Any], command: str, args: Dict[str, Any]) -> Any:
        """Execute skill code.

        MVP Implementation:
            - Dynamic import of skill module
            - Direct function call

        Security Limitations (MVP):
            - No process isolation
            - No resource limits (CPU/memory)
            - No timeout enforcement
            - Skills run in same process as AgentOS

        Production Requirements:
            - Subprocess isolation (minimum)
            - Container isolation (recommended)
            - WASM sandbox (ideal)
            - Resource limits (CPU, memory, network)
            - Timeout enforcement

        Args:
            skill: Skill metadata from loader
            command: Command to invoke
            args: Arguments to pass

        Returns:
            Result from skill handler

        Raises:
            ValueError: If command not found
            Exception: Any exception from skill execution
        """
        # Get skill cache directory
        # Format: ~/.agentos/store/skills_cache/{skill_id}/{repo_hash}/
        cache_dir = Path.home() / ".agentos" / "store" / "skills_cache" / skill['skill_id']

        if skill.get('repo_hash'):
            cache_dir = cache_dir / skill['repo_hash']

        manifest = skill['manifest_json']

        # Get module path from manifest
        module_filename = manifest['entry']['module']
        module_path = cache_dir / module_filename

        if not module_path.exists():
            raise FileNotFoundError(
                f"Skill module not found: {module_path}. "
                f"Skill may not be properly imported."
            )

        # Find handler for command
        exports = manifest['entry']['exports']
        handler_name = None

        for export in exports:
            if export['command'] == command:
                handler_name = export['handler']
                break

        if not handler_name:
            raise ValueError(
                f"Command '{command}' not found in skill '{skill['skill_id']}'. "
                f"Available commands: {[e['command'] for e in exports]}"
            )

        # Dynamic module loading (MVP)
        # Security Note: This runs in the same process as AgentOS
        # Production should use subprocess/container isolation

        spec = importlib.util.spec_from_file_location(
            f"skill_{skill['skill_id']}",
            module_path
        )

        if not spec or not spec.loader:
            raise ImportError(f"Failed to load skill module: {module_path}")

        module = importlib.util.module_from_spec(spec)

        # Add to sys.modules to support relative imports within skill
        sys.modules[f"skill_{skill['skill_id']}"] = module

        # Execute module to define functions
        spec.loader.exec_module(module)

        # Get handler function
        if not hasattr(module, handler_name):
            raise AttributeError(
                f"Handler '{handler_name}' not found in skill module. "
                f"Check manifest exports configuration."
            )

        handler = getattr(module, handler_name)

        # Invoke handler
        return handler(**args)


__all__ = [
    "SkillInvoker",
    "PhaseViolationError",
    "SkillNotEnabledError",
    "PermissionDeniedError",
]
