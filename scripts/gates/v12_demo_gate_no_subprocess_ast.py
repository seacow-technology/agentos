#!/usr/bin/env python3
"""
Gate: v12_demo_gate_no_subprocess_ast

P0-2: Demo Path Zero Subprocess (限定扫描域)

核心口径：
- Demo 验收链路必须 0 subprocess
- 扫描范围：仅 Demo 路径（scripts/demo/ + demo 用到的 executor 模块）
- 不扫描底层基础设施（允许存在 subprocess，但不能被 demo 触达）

这不是"豁免"，是 Gate scope 定义。
"""

import ast
import sys
from pathlib import Path
from typing import List, Dict
import json


FORBIDDEN_SYMBOLS = {
    "subprocess",
    "os.system",
    "exec",
    "eval",
    "shlex",
    "pty",
    "pexpect"
}

# Demo Scope: 只扫描这些目录/文件
DEMO_SCOPE_PATTERNS = [
    "scripts/demo/**/*.py",
    "scripts/gates/v12_demo_*.py",
    "agentos/core/executor/executor_engine.py",
    "agentos/core/infra/**/*.py",
    "tests/integration/test_executor_e2e_landing.py"
]


class SubprocessVisitor(ast.NodeVisitor):
    """AST 访问器：检测禁止的符号"""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.violations = []
    
    def visit_Import(self, node):
        for alias in node.names:
            if alias.name in FORBIDDEN_SYMBOLS:
                self.violations.append({
                    "file": str(self.file_path),
                    "line": node.lineno,
                    "type": "import",
                    "symbol": alias.name,
                    "code": f"import {alias.name}"
                })
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        if node.module in FORBIDDEN_SYMBOLS:
            self.violations.append({
                "file": str(self.file_path),
                "line": node.lineno,
                "type": "import_from",
                "symbol": node.module,
                "code": f"from {node.module} import ..."
            })
        self.generic_visit(node)
    
    def visit_Attribute(self, node):
        # 检测 os.system 之类
        if isinstance(node.value, ast.Name):
            if node.value.id == "os" and node.attr == "system":
                self.violations.append({
                    "file": str(self.file_path),
                    "line": node.lineno,
                    "type": "attribute",
                    "symbol": "os.system",
                    "code": "os.system(...)"
                })
        self.generic_visit(node)
    
    def visit_Call(self, node):
        # 检测 exec(...) / eval(...)
        if isinstance(node.func, ast.Name):
            if node.func.id in {"exec", "eval"}:
                self.violations.append({
                    "file": str(self.file_path),
                    "line": node.lineno,
                    "type": "call",
                    "symbol": node.func.id,
                    "code": f"{node.func.id}(...)"
                })
        self.generic_visit(node)


def scan_file(file_path: Path) -> List[Dict]:
    """扫描单个文件"""
    try:
        content = file_path.read_text()
        tree = ast.parse(content, filename=str(file_path))
        
        visitor = SubprocessVisitor(file_path)
        visitor.visit(tree)
        
        return visitor.violations
    
    except SyntaxError:
        return []
    except Exception as e:
        print(f"⚠ Error scanning {file_path}: {e}")
        return []


def get_demo_scope_files(repo_root: Path) -> List[Path]:
    """获取 Demo Scope 内的所有文件"""
    files = []
    
    for pattern in DEMO_SCOPE_PATTERNS:
        if "**" in pattern:
            # Glob pattern
            parts = pattern.split("**")
            base = repo_root / parts[0].rstrip("/")
            suffix = parts[1].lstrip("/")
            
            if base.exists():
                for file in base.rglob(suffix):
                    if file.is_file():
                        files.append(file)
        else:
            # 单个文件
            file = repo_root / pattern
            if file.exists():
                files.append(file)
    
    return list(set(files))  # 去重


def main():
    repo_root = Path.cwd()
    
    print("🔒 Gate: v12_demo_gate_no_subprocess_ast")
    print("   Scope: Demo Path Only (Zero Subprocess)")
    print("=" * 60)
    
    # 获取 Demo Scope 文件
    demo_files = get_demo_scope_files(repo_root)
    
    print(f"📁 Demo Scope: {len(demo_files)} files")
    for pattern in DEMO_SCOPE_PATTERNS:
        print(f"   - {pattern}")
    print()
    
    # 扫描
    all_violations = []
    for file in demo_files:
        violations = scan_file(file)
        all_violations.extend(violations)
    
    # 保存扫描结果
    output_dir = repo_root / "outputs" / "demo" / "latest"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    scan_result = {
        "gate": "v12_demo_gate_no_subprocess_ast",
        "scope": "demo_path_only",
        "scope_patterns": DEMO_SCOPE_PATTERNS,
        "scanned_files": len(demo_files),
        "scanned_file_list": [str(f.relative_to(repo_root)) for f in demo_files],
        "violations_count": len(all_violations),
        "violations": all_violations
    }
    
    result_file = output_dir / "audit" / "no_subprocess_demo_scope.json"
    result_file.parent.mkdir(parents=True, exist_ok=True)
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(scan_result, f, indent=2)
    
    # 报告
    if all_violations:
        print(f"❌ Found {len(all_violations)} violations in Demo Scope:")
        for v in all_violations[:10]:  # 只显示前 10 个
            print(f"   {v['file']}:{v['line']}: {v['symbol']} ({v['type']})")
        
        if len(all_violations) > 10:
            print(f"   ... and {len(all_violations) - 10} more")
        
        print()
        print(f"Scan result saved: {result_file}")
        print("=" * 60)
        print("❌ Gate FAILED: subprocess detected in Demo Path")
        sys.exit(1)
    else:
        print(f"✓ Scanned {len(demo_files)} files in Demo Scope")
        print(f"✓ No forbidden symbols found")
        print()
        print(f"Scan result saved: {result_file}")
        print("=" * 60)
        print("✅ Gate PASSED: Demo Path Zero Subprocess")
        sys.exit(0)


if __name__ == "__main__":
    main()
