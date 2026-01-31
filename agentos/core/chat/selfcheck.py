"""
Self-check module for AgentOS Chat Engine.

Verifies critical components can be loaded at startup to ensure fail-fast behavior.
This prevents silent failures where broken modules are only discovered at runtime.

Design Philosophy:
- Fail-fast: Detect module loading issues immediately at startup
- Explicit: Log each module check with clear success/failure indicators
- Comprehensive: Check all critical modules that could cause silent failures
- Extensible: Easy to add new checks as the system evolves

Usage:
    from agentos.core.chat.selfcheck import run_startup_checks

    # In ChatEngine.__init__:
    run_startup_checks()  # Raises RuntimeError if any critical module fails
"""

import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Critical modules that must be loadable at startup
# These are modules that, if broken, would cause silent failures
CRITICAL_MODULES = [
    "agentos.core.chat.communication_adapter",
    "agentos.core.chat.auto_comm_policy",
    "agentos.core.chat.info_need_classifier",
    "agentos.core.chat.multi_intent_splitter",
    "agentos.core.chat.context_builder",
    "agentos.core.chat.adapters",
]


def verify_critical_modules() -> None:
    """Verify all critical modules can be imported.

    This function attempts to import each critical module and collects
    any failures. If any module fails to load, a RuntimeError is raised
    with details about all failures.

    Raises:
        RuntimeError: If any critical module cannot be imported
    """
    failed: List[Tuple[str, str]] = []

    for module_name in CRITICAL_MODULES:
        try:
            __import__(module_name)
            logger.info(f"✅ {module_name} loaded successfully")
        except SyntaxError as e:
            error_msg = f"SyntaxError at line {e.lineno}: {e.msg}"
            logger.critical(f"❌ {module_name} has syntax error: {error_msg}")
            failed.append((module_name, error_msg))
        except ImportError as e:
            error_msg = f"ImportError: {str(e)}"
            logger.critical(f"❌ {module_name} import failed: {error_msg}")
            failed.append((module_name, error_msg))
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.critical(f"❌ {module_name} failed to load: {error_msg}")
            failed.append((module_name, error_msg))

    if failed:
        error_msg = "Critical modules failed to load:\n"
        for mod, err in failed:
            error_msg += f"  - {mod}: {err}\n"
        error_msg += "\nSystem cannot start. Please fix the module errors above."
        raise RuntimeError(error_msg)


def run_startup_checks() -> bool:
    """Run all startup self-checks.

    This is the main entry point for startup checks. It runs all configured
    checks and raises an exception if any check fails.

    Returns:
        True if all checks passed

    Raises:
        RuntimeError: If any startup check fails
    """
    logger.info("Running AgentOS Chat Engine startup self-checks...")

    try:
        verify_critical_modules()
        logger.info("✅ All startup checks passed")
        return True
    except RuntimeError as e:
        logger.critical(f"Startup checks failed: {e}")
        raise


# Optional: Add more specific checks as needed
def verify_adapters() -> None:
    """Verify model adapters can be instantiated.

    This is an example of a more specific check that could be added.
    Currently not enabled by default to avoid runtime dependencies.
    """
    try:
        from agentos.core.chat.adapters import get_adapter
        # Try to get a common adapter
        adapter = get_adapter("ollama")
        logger.info("✅ Model adapter system operational")
    except Exception as e:
        logger.warning(f"⚠️ Model adapter check failed: {e}")
        # Not critical - model might not be configured yet
