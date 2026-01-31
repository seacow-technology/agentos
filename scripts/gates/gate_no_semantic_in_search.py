#!/usr/bin/env python3
"""Gate - Prevent Semantic Analysis in Search Phase

This gate ensures that the search phase does NOT output semantic analysis fields.
Search results should be factual metadata only - NO summaries, NO interpretations,
NO "why_it_matters" explanations.

CRITICAL PRINCIPLE:
- Search phase: Returns candidate sources (metadata only)
- Fetch phase: Retrieves content (still no interpretation)
- Brief phase: Synthesizes and analyzes (semantic analysis allowed)

Forbidden Fields in Search Phase:
1. summary - Descriptive summaries of what content means
2. why_it_matters - Importance/impact explanations
3. analysis - Content analysis or interpretation
4. impact - Impact assessments
5. implication - Implications or consequences
6. importance - Importance ratings or explanations
7. assessment - Quality or relevance assessments

Allowed Fields:
- title - From source metadata
- url - From source metadata
- snippet - Raw text from search engine (no modification)
- priority_score - Metadata-based scoring (no semantic analysis)
- priority_reasons - ONLY enumerated reasons from whitelist

Special Case - priority_reason:
- ✅ ALLOWED: Enum values from PriorityReason (GOV_DOMAIN, EDU_DOMAIN, etc.)
- ❌ FORBIDDEN: Dynamic text generation ("This is important because...")

Exit codes:
- 0: Success (no semantic fields in search phase)
- 1: Violations found

Usage:
    python scripts/gates/gate_no_semantic_in_search.py
"""

import ast
import os
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Set

# Root directory for scanning
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Files to check
FILES_TO_CHECK = [
    "agentos/core/communication/connectors/web_search.py",
    "agentos/core/communication/priority/priority_scoring.py",
    "agentos/core/chat/comm_commands.py",
]

# Forbidden field names
FORBIDDEN_FIELDS = {
    "summary",
    "why_it_matters",
    "analysis",
    "impact",
    "implication",
    "importance",
    "assessment",
}

# Allowed fields (for documentation purposes)
ALLOWED_FIELDS = {
    "title",
    "url",
    "snippet",
    "priority_score",
    "priority_reasons",
    "domain_score",
    "source_type_score",
    "document_type_score",
    "recency_score",
    "reasons",  # Must be enum values
    "metadata",
    "rank",
    "domain",
    "path",
}

# Whitelist: Specific patterns that are allowed despite containing forbidden field names
# Format: (file_path_suffix, line_pattern, reason)
WHITELIST_PATTERNS = [
    # comm_commands.py: Brief generation is ALLOWED to have semantic fields
    ("comm_commands.py", "_format_brief", "Brief phase allows semantic analysis"),
    ("comm_commands.py", "_generate_importance", "Brief phase allows semantic analysis"),
    ("comm_commands.py", "summary", "Brief phase uses summary for display"),

    # Test files are allowed to check for forbidden fields
    ("test_", "", "Test files can reference forbidden fields"),
]


class SemanticFieldVisitor(ast.NodeVisitor):
    """AST visitor to detect semantic analysis fields in search phase."""

    def __init__(self, filename: str):
        self.filename = filename
        self.violations: List[Tuple[int, str, str]] = []
        self.brief_function_depth = 0  # Track nesting level in brief functions
        self.function_stack: List[str] = []

    def _handle_function_def(self, node) -> None:
        """Common handler for FunctionDef and AsyncFunctionDef."""
        self.function_stack.append(node.name)

        # Check if we're in brief generation functions (allowed to have semantic fields)
        brief_function_patterns = [
            "_format_brief",
            "_generate_importance",
            "handle_brief",
            "_execute_brief_pipeline",
            "_fetch_and_verify",  # Part of brief pipeline
            "_multi_query_search",  # Part of brief pipeline
            "_filter_candidates",  # Part of brief pipeline
        ]

        # If we're entering a brief function, increment depth
        # This allows nested functions (like fetch_one inside _fetch_and_verify) to also be exempt
        if any(pattern in node.name for pattern in brief_function_patterns):
            self.brief_function_depth += 1

        self.generic_visit(node)

        # If we were in a brief function, decrement depth when leaving
        if any(pattern in node.name for pattern in brief_function_patterns):
            self.brief_function_depth -= 1

        self.function_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track function context for brief phase detection."""
        self._handle_function_def(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Track async function context for brief phase detection."""
        self._handle_function_def(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        """Visit dictionary literals to check for forbidden keys."""
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                field_name = key.value
                if self._is_forbidden_field(field_name):
                    line_no = key.lineno
                    context = self._get_context()
                    self.violations.append((
                        line_no,
                        f"Dictionary key '{field_name}' in {context}",
                        f"Forbidden semantic field '{field_name}' found in search phase"
                    ))

        self.generic_visit(node)

    def visit_keyword(self, node: ast.keyword) -> None:
        """Visit keyword arguments to check for forbidden parameter names."""
        if node.arg and self._is_forbidden_field(node.arg):
            line_no = node.value.lineno if hasattr(node.value, 'lineno') else 0
            context = self._get_context()
            self.violations.append((
                line_no,
                f"Keyword argument '{node.arg}' in {context}",
                f"Forbidden semantic field '{node.arg}' found in search phase"
            ))

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Visit assignments to check for forbidden field names."""
        for target in node.targets:
            # Check dictionary subscription: result["summary"] = ...
            if isinstance(target, ast.Subscript):
                if isinstance(target.slice, ast.Constant):
                    field_name = target.slice.value
                    if isinstance(field_name, str) and self._is_forbidden_field(field_name):
                        line_no = node.lineno
                        context = self._get_context()
                        self.violations.append((
                            line_no,
                            f"Assignment to '{field_name}' in {context}",
                            f"Forbidden semantic field '{field_name}' found in search phase"
                        ))

        self.generic_visit(node)

    def _is_forbidden_field(self, field_name: str) -> bool:
        """Check if field name is forbidden.

        Returns False if:
        - We're in a brief generation function (brief phase allows semantic analysis)
        - Field is in allowed list
        - File path matches whitelist pattern
        """
        # Brief phase is allowed to have semantic fields
        # Check if we're inside any level of brief function nesting
        if self.brief_function_depth > 0:
            return False

        # Check whitelist patterns
        for pattern_file, pattern_line, _ in WHITELIST_PATTERNS:
            if pattern_file in self.filename:
                if not pattern_line or any(pattern_line in func for func in self.function_stack):
                    return False

        # Check if field is in forbidden list
        return field_name.lower() in FORBIDDEN_FIELDS

    def _get_context(self) -> str:
        """Get current context (function name)."""
        if self.function_stack:
            return f"function {self.function_stack[-1]}"
        return "module level"

    def _get_relative_path(self) -> str:
        """Get relative path from project root."""
        try:
            rel_path = Path(self.filename).relative_to(PROJECT_ROOT)
            return str(rel_path).replace(os.sep, "/")
        except ValueError:
            return self.filename


def scan_file(file_path: Path) -> List[Tuple[int, str, str]]:
    """Scan a single file for semantic field violations.

    Returns:
        List of (line_number, context, reason) tuples
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Parse AST
        tree = ast.parse(source, filename=str(file_path))

        # Visit nodes
        visitor = SemanticFieldVisitor(str(file_path))
        visitor.visit(tree)

        return visitor.violations

    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Error scanning {file_path}: {e}", file=sys.stderr)
        return []


def check_priority_reason_compliance(file_path: Path) -> List[Tuple[int, str, str]]:
    """Check if priority_reason fields use only enum values.

    This function checks for dynamic string generation in priority_reason fields,
    which is forbidden. Only PriorityReason enum values are allowed.

    Returns:
        List of (line_number, context, reason) tuples
    """
    violations = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename=str(file_path))

        # Look for assignments to priority_reason that are not enum values
        for node in ast.walk(tree):
            # Check for dictionary assignments: {"priority_reason": "dynamic text..."}
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value in ["priority_reason", "priority_reasons"]:
                        # Check if value is a dynamic string (not an enum)
                        if isinstance(value, ast.Constant) and isinstance(value.value, str):
                            # Check if it looks like a dynamic description (contains spaces)
                            if " " in value.value and not value.value.isupper():
                                violations.append((
                                    key.lineno,
                                    f"priority_reason assignment",
                                    f"priority_reason uses dynamic text instead of PriorityReason enum"
                                ))

    except Exception as e:
        print(f"Error checking priority_reason compliance in {file_path}: {e}", file=sys.stderr)

    return violations


def scan_all_files() -> Dict[Path, List[Tuple[int, str, str]]]:
    """Scan all target files for violations."""
    all_violations = {}

    for file_rel in FILES_TO_CHECK:
        file_path = PROJECT_ROOT / file_rel

        if not file_path.exists():
            print(f"Warning: File not found: {file_rel}", file=sys.stderr)
            continue

        # Check for semantic fields
        violations = scan_file(file_path)

        # Check for priority_reason compliance (only for priority_scoring.py)
        if "priority_scoring.py" in str(file_path):
            priority_violations = check_priority_reason_compliance(file_path)
            violations.extend(priority_violations)

        if violations:
            all_violations[file_path] = violations

    return all_violations


def print_report(violations: Dict[Path, List[Tuple[int, str, str]]]) -> None:
    """Print violation report."""
    print("=" * 80)
    print("Gate: No Semantic Analysis in Search Phase")
    print("=" * 80)
    print()

    if not violations:
        print("✓ PASS: No semantic fields detected in search phase")
        print()
        print("Search phase outputs metadata only:")
        print("  ✓ title - From source metadata")
        print("  ✓ url - From source metadata")
        print("  ✓ snippet - Raw search engine text")
        print("  ✓ priority_score - Metadata-based scoring")
        print("  ✓ priority_reasons - Enum values only")
        print()
        print("Forbidden fields (not found):")
        for field in sorted(FORBIDDEN_FIELDS):
            print(f"  ✗ {field} - Would indicate semantic analysis")
        print()
        print("Files checked:")
        for file_rel in FILES_TO_CHECK:
            print(f"  ✓ {file_rel}")
        return

    print(f"✗ FAIL: Found {len(violations)} file(s) with semantic field violations")
    print()

    # Summary by violation type
    violation_types: Dict[str, int] = {}
    for file_violations in violations.values():
        for _, context, reason in file_violations:
            violation_types[reason] = violation_types.get(reason, 0) + 1

    print("Violation Summary:")
    for reason, count in sorted(violation_types.items(), key=lambda x: -x[1]):
        print(f"  - {reason}: {count} occurrence(s)")
    print()

    # Detailed violations
    print("Detailed Violations:")
    print()

    for file_path, file_violations in sorted(violations.items()):
        try:
            rel_path = file_path.relative_to(PROJECT_ROOT)
        except ValueError:
            rel_path = file_path

        print(f"File: {rel_path}")

        for line_no, context, reason in file_violations:
            print(f"  Line {line_no}: {context}")
            print(f"    Reason: {reason}")
        print()

    print("=" * 80)
    print("Phase Separation Rules:")
    print("=" * 80)
    print()
    print("1. SEARCH Phase (metadata only):")
    print("   ✓ Allowed: title, url, snippet (raw), priority_score")
    print("   ✗ Forbidden: summary, why_it_matters, analysis, impact")
    print()
    print("2. FETCH Phase (content only):")
    print("   ✓ Allowed: raw text, links, images, metadata")
    print("   ✗ Forbidden: summary, why_it_matters, analysis, impact")
    print()
    print("3. BRIEF Phase (synthesis allowed):")
    print("   ✓ Allowed: summary, why_it_matters, analysis, assessment")
    print("   ✓ Purpose: Human-readable synthesis of verified sources")
    print()
    print("=" * 80)
    print("Required Actions:")
    print("=" * 80)
    print()
    print("1. Remove semantic fields from search/fetch outputs:")
    print("   - Replace 'summary' with 'snippet' (raw text)")
    print("   - Remove 'why_it_matters' fields")
    print("   - Remove 'analysis', 'impact', 'assessment' fields")
    print()
    print("2. For priority_reason fields:")
    print("   - Use ONLY PriorityReason enum values")
    print("   - Do NOT generate dynamic descriptions")
    print()
    print("3. Move semantic analysis to brief phase:")
    print("   - Only _format_brief() can add interpretations")
    print("   - Brief phase runs AFTER fetch verification")
    print()
    print("Example (CORRECT - Search Phase):")
    print("------------------------")
    print("""
{
    "title": "Climate Policy 2025",
    "url": "https://example.gov/policy.pdf",
    "snippet": "Updated 2025. New climate framework...",
    "priority_score": {
        "total_score": 95,
        "reasons": [
            PriorityReason.GOV_DOMAIN,
            PriorityReason.PDF_DOCUMENT,
            PriorityReason.CURRENT_YEAR
        ]
    }
}
    """)
    print()
    print("Example (WRONG - Search Phase):")
    print("------------------------")
    print("""
{
    "title": "Climate Policy 2025",
    "url": "https://example.gov/policy.pdf",
    "summary": "This policy introduces important changes...",  # ❌ FORBIDDEN
    "why_it_matters": "Critical for climate action",           # ❌ FORBIDDEN
    "priority_reason": "High authority government source"      # ❌ FORBIDDEN (dynamic text)
}
    """)
    print()


def main() -> int:
    """Main entry point."""
    print(f"Scanning search phase files in: {PROJECT_ROOT}")
    print(f"Checking for semantic analysis violations")
    print()

    # Scan for violations
    violations = scan_all_files()

    # Print report
    print_report(violations)

    # Return exit code
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
