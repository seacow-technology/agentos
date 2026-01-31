#!/usr/bin/env python3
"""Gate - Prevent Implicit External I/O in Chat Core

This gate ensures that all external I/O (web search, web fetch, etc.) in Chat
goes through the explicit command interface (/comm commands), preventing
implicit external I/O calls embedded in LLM response handling.

Forbidden Patterns:
1. Direct calls to comm_adapter.search() or comm_adapter.fetch() in engine.py or service.py
2. Direct calls to WebSearchConnector or WebFetchConnector in LLM processing
3. Direct calls to CommunicationService.execute() outside comm_commands.py

Allowed Patterns:
- Using comm_adapter through /comm slash commands (comm_commands.py)
- Using command_router to invoke /comm commands
- Registering comm_adapter in initialization code

Exit codes:
- 0: Success (no implicit external I/O)
- 1: Violations found

Usage:
    python scripts/gates/gate_no_implicit_external_io.py
"""

import ast
import os
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Set

# Root directory for scanning
ROOT_DIR = Path(__file__).parent.parent.parent / "agentos"

# Critical files where direct external I/O is FORBIDDEN
CRITICAL_FILES = {
    "agentos/core/chat/engine.py": "Chat Engine (orchestration only)",
    "agentos/core/chat/service.py": "Chat Service (persistence only)",
    "agentos/core/chat/context_builder.py": "Context Builder (local context only)",
    "agentos/core/chat/models.py": "Chat Models (data structures only)",
}

# Forbidden method calls in critical files
FORBIDDEN_METHODS = {
    # CommunicationAdapter methods
    "search": "comm_adapter.search() - Use /comm search instead",
    "fetch": "comm_adapter.fetch() - Use /comm fetch instead",

    # Direct connector calls
    "WebSearchConnector": "Direct WebSearchConnector - Use /comm commands",
    "WebFetchConnector": "Direct WebFetchConnector - Use /comm commands",

    # Direct service calls (only allowed in comm_commands.py)
    "execute": "CommunicationService.execute() - Use /comm commands",
}

# Whitelist: Files allowed to make external I/O calls
WHITELIST = {
    # Command handlers (the ONLY sanctioned channel)
    "agentos/core/chat/comm_commands.py",

    # Communication adapter (initialization only)
    "agentos/core/chat/communication_adapter.py",

    # Slash command router (routing only)
    "agentos/core/chat/slash_command_router.py",

    # Handler registration
    "agentos/core/chat/handlers/__init__.py",

    # Test files (allowed for testing)
    "tests/",
    "test_",
}

# Directories to exclude
EXCLUDE_DIRS = {
    "__pycache__",
    ".git",
    ".pytest_cache",
    "venv",
    "env",
    ".venv",
    "node_modules",
}


class ExternalIOVisitor(ast.NodeVisitor):
    """AST visitor to detect external I/O calls."""

    def __init__(self, filename: str):
        self.filename = filename
        self.violations: List[Tuple[int, str, str]] = []

    def visit_Call(self, node: ast.Call) -> None:
        """Visit function/method calls."""
        # Check for method calls (e.g., obj.method())
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr

            # Check if this is a forbidden method
            if method_name in FORBIDDEN_METHODS:
                # Try to get the object name
                obj_name = self._get_obj_name(node.func.value)

                # Check for specific patterns
                if self._is_forbidden_call(obj_name, method_name):
                    line_no = node.lineno
                    call_expr = f"{obj_name}.{method_name}()"
                    reason = FORBIDDEN_METHODS[method_name]
                    self.violations.append((line_no, call_expr, reason))

        # Continue visiting child nodes
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Visit import statements."""
        for alias in node.names:
            if self._is_forbidden_import(alias.name):
                line_no = node.lineno
                import_expr = f"import {alias.name}"
                reason = "Direct import of web connector - Use /comm commands"
                self.violations.append((line_no, import_expr, reason))

        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit from...import statements."""
        if node.module:
            for alias in node.names:
                full_name = f"{node.module}.{alias.name}"
                if self._is_forbidden_import(full_name):
                    line_no = node.lineno
                    import_expr = f"from {node.module} import {alias.name}"
                    reason = "Direct import of web connector - Use /comm commands"
                    self.violations.append((line_no, import_expr, reason))

        self.generic_visit(node)

    def _get_obj_name(self, node: ast.AST) -> str:
        """Extract object name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            # Handle chained attributes (e.g., self.comm_adapter)
            base = self._get_obj_name(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        else:
            return ""

    def _is_forbidden_call(self, obj_name: str, method_name: str) -> bool:
        """Check if this is a forbidden method call."""
        # Check for comm_adapter.search() or comm_adapter.fetch()
        if "comm_adapter" in obj_name and method_name in ["search", "fetch"]:
            return True

        # Check for service.execute() (CommunicationService)
        # Match patterns like: service, self.service, comm_service, self.comm_service
        service_patterns = ["service", "comm_service", "communication_service"]
        if method_name == "execute":
            for pattern in service_patterns:
                if pattern in obj_name:
                    return True

        # Check for direct connector instantiation
        if method_name in ["WebSearchConnector", "WebFetchConnector"]:
            return True

        return False

    def _is_forbidden_import(self, import_name: str) -> bool:
        """Check if this is a forbidden import in critical files."""
        # Check for direct connector imports (forbidden in ALL critical files)
        forbidden_imports = [
            "web_search",  # Module name
            "web_fetch",   # Module name
            "WebSearchConnector",  # Class name
            "WebFetchConnector",   # Class name
        ]

        return any(forbidden in import_name for forbidden in forbidden_imports)

    def _get_relative_path(self) -> str:
        """Get relative path from project root."""
        try:
            rel_path = Path(self.filename).relative_to(Path(__file__).parent.parent.parent)
            return str(rel_path).replace(os.sep, "/")
        except ValueError:
            return self.filename


def is_whitelisted(file_path: Path) -> bool:
    """Check if file is whitelisted."""
    try:
        rel_path = file_path.relative_to(Path(__file__).parent.parent.parent)
        rel_str = str(rel_path).replace(os.sep, "/")

        # Check if path starts with any whitelist entry
        for allowed in WHITELIST:
            if rel_str.startswith(allowed) or allowed in rel_str:
                return True

        return False
    except ValueError:
        return False


def is_critical_file(file_path: Path) -> bool:
    """Check if file is a critical file where external I/O is forbidden."""
    try:
        rel_path = file_path.relative_to(Path(__file__).parent.parent.parent)
        rel_str = str(rel_path).replace(os.sep, "/")

        return rel_str in CRITICAL_FILES
    except ValueError:
        return False


def scan_file(file_path: Path) -> List[Tuple[int, str, str]]:
    """Scan a single file for implicit external I/O calls.

    Returns:
        List of (line_number, call_expression, reason) tuples
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Parse AST
        tree = ast.parse(source, filename=str(file_path))

        # Visit nodes
        visitor = ExternalIOVisitor(str(file_path))
        visitor.visit(tree)

        return visitor.violations

    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Error scanning {file_path}: {e}", file=sys.stderr)
        return []


def scan_directory(root: Path) -> Dict[Path, List[Tuple[int, str, str]]]:
    """Scan directory for implicit external I/O violations."""
    all_violations = {}

    # Scan critical files first
    for critical_file_rel in CRITICAL_FILES.keys():
        critical_file = Path(__file__).parent.parent.parent / critical_file_rel

        if not critical_file.exists():
            print(f"Warning: Critical file not found: {critical_file_rel}", file=sys.stderr)
            continue

        # Skip whitelisted files
        if is_whitelisted(critical_file):
            continue

        # Scan file
        violations = scan_file(critical_file)
        if violations:
            all_violations[critical_file] = violations

    # Scan all Python files in chat directory
    chat_dir = root / "core" / "chat"
    if chat_dir.exists():
        for path in chat_dir.rglob("*.py"):
            # Skip excluded directories
            if any(excluded in path.parts for excluded in EXCLUDE_DIRS):
                continue

            # Skip whitelisted files
            if is_whitelisted(path):
                continue

            # Skip non-critical files (we only enforce on critical files)
            if not is_critical_file(path):
                continue

            # Scan file
            violations = scan_file(path)
            if violations:
                all_violations[path] = violations

    return all_violations


def print_report(violations: Dict[Path, List[Tuple[int, str, str]]]) -> None:
    """Print violation report."""
    print("=" * 80)
    print("Gate: No Implicit External I/O in Chat Core")
    print("=" * 80)
    print()

    if not violations:
        print("✓ PASS: No implicit external I/O detected")
        print()
        print("All external I/O goes through explicit /comm commands:")
        print("  - /comm search <query>")
        print("  - /comm fetch <url>")
        print()
        print("Critical files checked:")
        for critical_file, description in CRITICAL_FILES.items():
            print(f"  ✓ {critical_file} - {description}")
        return

    print(f"✗ FAIL: Found {len(violations)} file(s) with implicit external I/O")
    print()

    # Summary by violation type
    violation_types: Dict[str, int] = {}
    for file_violations in violations.values():
        for _, _, reason in file_violations:
            violation_types[reason] = violation_types.get(reason, 0) + 1

    print("Violation Summary:")
    for reason, count in sorted(violation_types.items(), key=lambda x: -x[1]):
        print(f"  - {reason}: {count} occurrence(s)")
    print()

    # Detailed violations
    print("Detailed Violations:")
    print()

    for file_path, file_violations in sorted(violations.items()):
        rel_path = file_path.relative_to(Path(__file__).parent.parent.parent)
        critical_desc = CRITICAL_FILES.get(str(rel_path).replace(os.sep, "/"), "")

        print(f"File: {rel_path}")
        if critical_desc:
            print(f"  Role: {critical_desc}")

        for line_no, call_expr, reason in file_violations:
            print(f"  Line {line_no}: {call_expr}")
            print(f"    Reason: {reason}")
        print()

    print("=" * 80)
    print("Required Actions:")
    print("=" * 80)
    print()
    print("1. Remove direct external I/O calls from critical files:")
    print("   - Do NOT call comm_adapter.search() or comm_adapter.fetch() in engine.py")
    print("   - Do NOT call comm_adapter.search() or comm_adapter.fetch() in service.py")
    print("   - Do NOT import WebSearchConnector or WebFetchConnector in core files")
    print()
    print("2. Use explicit /comm commands instead:")
    print("   - User types: /comm search <query>")
    print("   - User types: /comm fetch <url>")
    print("   - Slash command router handles the request")
    print("   - comm_commands.py executes the call")
    print()
    print("3. If you need external info:")
    print("   - Prompt the user to use /comm commands")
    print("   - Use ExternalInfoDeclaration to document the need")
    print("   - Let the user approve and execute the command")
    print()
    print("Example (CORRECT):")
    print("------------------------")
    print("""
# In engine.py or service.py
def handle_message(user_input: str):
    # Detect need for external info
    if needs_web_search(user_input):
        return suggest_comm_command("search", user_input)

    # Process message normally
    return process_message(user_input)

def suggest_comm_command(command_type: str, query: str) -> str:
    '''Suggest using /comm command.'''
    return f"To search the web, use: /comm search {query}"
    """)
    print()
    print("Example (WRONG):")
    print("------------------------")
    print("""
# In engine.py (FORBIDDEN!)
def handle_message(user_input: str):
    # This is IMPLICIT external I/O - FORBIDDEN!
    if needs_web_search(user_input):
        results = comm_adapter.search(user_input)  # ❌ FORBIDDEN
        return format_results(results)
    """)
    print()


def main() -> int:
    """Main entry point."""
    print(f"Scanning: {ROOT_DIR / 'core' / 'chat'}")
    print(f"Checking for implicit external I/O in critical files")
    print()

    # Scan for violations
    violations = scan_directory(ROOT_DIR)

    # Print report
    print_report(violations)

    # Return exit code
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
