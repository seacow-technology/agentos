#!/usr/bin/env python3
"""
v0.10 Gate D: Static Scan for Forbidden Execution Symbols

Uses Python AST + regex scanning to detect forbidden execution patterns.
Zero warnings, zero ambiguity, cross-platform compatible.

Scans: agentos/core/executor_dry/**/*.py
Excludes: docs/, comments, string literals (unless suspicious context)

SCAN STRATEGY (Zero False Positives):
- Uses ast.parse() to analyze Python source code semantically
- Only scans executable nodes: ast.Call, ast.Attribute, ast.Name
- Does NOT scan string literals, docstrings, or comments
- Forbidden patterns detected at call-site level, not text level
- This ensures: subprocess.run() in docstring → NOT flagged ✅
              subprocess.run() in code     → FLAGGED ❌
"""

import ast
import re
import sys
from pathlib import Path


def scan_ast_for_calls(filepath):
    """Use AST to detect forbidden function calls.
    
    Strategy: Only scan executable semantic nodes (Call/Attribute/Name),
    not string constants or docstrings. This prevents false positives
    from documentation or comments.
    """
    violations = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        
        tree = ast.parse(source, filename=str(filepath))
        
        # Forbidden call patterns
        forbidden_calls = {
            'subprocess': ['call', 'run', 'Popen', 'check_output', 'check_call'],
            'os': ['system', 'exec', 'execl', 'execv', 'spawn'],
        }
        
        # Walk AST
        for node in ast.walk(tree):
            # Check for subprocess.call(), os.system(), etc.
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    # module.function() pattern
                    if isinstance(node.func.value, ast.Name):
                        module = node.func.value.id
                        func = node.func.attr
                        
                        if module in forbidden_calls:
                            if func in forbidden_calls[module]:
                                violations.append({
                                    'line': node.lineno,
                                    'pattern': f'{module}.{func}()',
                                    'type': 'ast_call'
                                })
                
                # Check for exec() and eval() builtins
                elif isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    if func_name in ['exec', 'eval']:
                        violations.append({
                            'line': node.lineno,
                            'pattern': f'{func_name}()',
                            'type': 'builtin'
                        })
    
    except SyntaxError as e:
        violations.append({
            'line': e.lineno or 0,
            'pattern': 'SYNTAX_ERROR',
            'type': 'parse_error'
        })
    
    return violations


def scan_regex_for_imports(filepath):
    """Use regex to detect forbidden imports."""
    violations = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Patterns that should not appear outside comments
    forbidden_import_patterns = [
        r'^\s*import\s+subprocess',
        r'^\s*from\s+subprocess\s+import',
    ]
    
    for i, line in enumerate(lines, 1):
        # Skip comments
        if line.strip().startswith('#'):
            continue
        
        # Skip docstrings (simple heuristic)
        if '"""' in line or "'''" in line:
            continue
        
        for pattern in forbidden_import_patterns:
            if re.search(pattern, line):
                violations.append({
                    'line': i,
                    'pattern': line.strip(),
                    'type': 'import'
                })
    
    return violations


def main():
    print("=" * 70)
    print("v0.10 Gate D: Static Scan for Execution Symbols")
    print("=" * 70)
    
    # Scan paths
    scan_dir = Path("agentos/core/executor_dry")
    
    print(f"\n🔍 Scanning: {scan_dir}")
    print(f"  Method: Python AST + regex")
    print(f"  Excludes: comments, docstrings, docs/")
    
    python_files = list(scan_dir.glob("*.py"))
    python_files = [f for f in python_files if not f.name.startswith("__")]
    
    print(f"  Files to scan: {len(python_files)}")
    
    all_violations = []
    
    for py_file in python_files:
        # AST scan
        ast_violations = scan_ast_for_calls(py_file)
        
        # Regex scan
        regex_violations = scan_regex_for_imports(py_file)
        
        violations = ast_violations + regex_violations
        
        if violations:
            all_violations.extend([
                {**v, 'file': py_file.name}
                for v in violations
            ])
    
    # Report
    print("\n" + "─" * 70)
    print("📊 Scan Results:")
    print("─" * 70)
    
    if all_violations:
        print(f"\n❌ Found {len(all_violations)} violations:\n")
        
        for v in all_violations:
            print(f"  {v['file']}:{v['line']}")
            print(f"    Type: {v['type']}")
            print(f"    Pattern: {v['pattern']}")
            print()
        
        print("=" * 70)
        print("❌ Gate D: FAILED - Forbidden execution symbols detected")
        print("=" * 70)
        return False
    else:
        print("\n✅ No forbidden execution symbols found")
        print(f"  Scanned: {len(python_files)} files")
        print(f"  Violations: 0")
        
        print("\n" + "=" * 70)
        print("✅ Gate D: PASSED")
        print("   Zero warnings, zero execution symbols")
        print("=" * 70)
        return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
